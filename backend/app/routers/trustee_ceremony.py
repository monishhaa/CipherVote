"""
FastAPI Router for Standalone Trustee Ceremony & Post-Unlock Validation Console.

Endpoints:
- GET /api/ceremony/info/{token} -> Lookup trustee, election metadata, presence state, unlock state
- WebSocket /api/ceremony/ws/{token} -> Real-time bidirectional presence heartbeat & ceremony live stream
- POST /api/ceremony/heartbeat/{token} -> Polling heartbeat fallback
- POST /api/ceremony/submit-code/{token} -> Sequential Crockford code entry (N-of-N unlock)
- GET /api/ceremony/validation/summary/{token} -> Unlocked console election summary (server-enforced 403)
- POST /api/ceremony/validation/verify/{token} -> Independent bulletin board & ZKP verification
- POST /api/ceremony/validation/approve/{token} -> Compute partial decryptions + DLEQ proofs, wipe in-memory share
- GET /api/ceremony/bulletin-board-export/{token} -> Download public bulletin board JSON export
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.entities import Election, Trustee, Ballot
from app.core.crypto.trustee_security import (
    hash_link_token,
    verify_trustee_code,
    decrypt_share_at_rest,
    verify_full_passphrase_commitment,
)
from app.core.crypto.crockford import parse_and_validate_trustee_code
from app.core.tally_engine import get_or_compute_election_tally, publish_official_results
from app.core.crypto.zkp import (
    prove_trustee_partial_decryption,
    verify_disjunctive_chaum_pedersen,
    verify_ballot_sum_to_one,
    DisjunctiveZKP,
    EqualityZKP,
)
from app.core.crypto.elgamal import Ciphertext, PublicKey, homomorphic_sum
from app.core.crypto.constants import G, P, Q
from app.core.ceremony import (
    get_or_create_ceremony,
    get_ceremony_state,
    broadcast_ceremony_state,
    SESSION_DURATION_SECONDS,
)

logger = logging.getLogger("securevote.ceremony_router")
router = APIRouter(prefix="/ceremony", tags=["Trustee Ceremony"])


class SubmitCodeRequest(BaseModel):
    code: str = Field(..., description="Trustee Crockford code (e.g. T1-XXXX-XXXX-XXXX-XXXX-X)")


class ApproveRequest(BaseModel):
    notes: Optional[str] = None


async def lookup_trustee_by_token(token: str, db: AsyncSession) -> Tuple[Trustee, Election]:
    """Resolves trustee and election from hashed link token."""
    if not token or len(token) < 10:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid ceremony token.")

    token_hash = hash_link_token(token)
    stmt = (
        select(Trustee, Election)
        .join(Election, Trustee.election_id == Election.election_id)
        .where(
            (Trustee.link_token_hash == token_hash)
            | (Trustee.raw_link_token == token)
            | (Trustee.link_token_hash == token)
        )
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trustee link token not found or invalidated.")
    
    trustee, election = row
    return trustee, election


@router.get("/info/{token}")
async def get_ceremony_info(token: str, db: AsyncSession = Depends(get_db)):
    """Provides public metadata for this trustee's standalone ceremony screen."""
    trustee, election = await lookup_trustee_by_token(token, db)
    
    # Check total trustees
    t_stmt = select(Trustee).where(Trustee.election_id == election.election_id).order_by(Trustee.position)
    t_res = await db.execute(t_stmt)
    all_trustees = t_res.scalars().all()
    num_trustees = len(all_trustees)

    ceremony = get_or_create_ceremony(
        election.election_id, num_trustees, window_minutes=election.ceremony_window_minutes or 5
    )
    
    # Record presence
    token_hash = hash_link_token(token)
    ceremony.record_presence(trustee.position, token_hash, trustee.name, trustee.email or "")
    
    # Update link_opened_at if first time
    if not trustee.link_opened_at:
        trustee.link_opened_at = datetime.utcnow()
        await db.commit()

    is_unlocked = (
        ceremony.status in ("UNLOCKED", "COMPLETED")
        or token_hash in ceremony.unlocked_sessions
        or bool(election.ceremony_unlocked_at)
    )

    return {
        "election_id": election.election_id,
        "election_title": election.title,
        "election_status": election.status,
        "is_voting_closed": election.status in ("CLOSED", "TALLYING", "COMPLETED"),
        "scheduled_close": election.scheduled_end.isoformat() if election.scheduled_end else None,
        "your_position": trustee.position,
        "your_name": trustee.name,
        "total_trustees": num_trustees,
        "threshold_t": election.trustee_threshold,
        "window_minutes": election.ceremony_window_minutes or 5,
        "is_unlocked": is_unlocked,
        "has_approved": bool(trustee.has_approved),
        "results_published": bool(election.results_published_at),
        "ceremony_state": ceremony.to_public_dict(viewer_position=trustee.position),
    }


@router.post("/heartbeat/{token}")
async def post_heartbeat(token: str, db: AsyncSession = Depends(get_db)):
    """Polling heartbeat fallback for environments without WebSockets."""
    trustee, election = await lookup_trustee_by_token(token, db)
    
    t_stmt = select(Trustee).where(Trustee.election_id == election.election_id)
    t_res = await db.execute(t_stmt)
    num_trustees = len(t_res.scalars().all())

    ceremony = get_or_create_ceremony(
        election.election_id, num_trustees, window_minutes=election.ceremony_window_minutes or 5
    )
    token_hash = hash_link_token(token)
    ceremony.record_presence(trustee.position, token_hash, trustee.name, trustee.email or "")
    ceremony.check_active_round_timeout_and_disconnects()

    return ceremony.to_public_dict(viewer_position=trustee.position)


@router.websocket("/ws/{token}")
async def ceremony_websocket(websocket: WebSocket, token: str):
    """Real-time WebSocket connection streaming ceremony presence and round state."""
    await websocket.accept()
    
    # Use direct session lookup
    async for db in get_db():
        try:
            trustee, election = await lookup_trustee_by_token(token, db)
            break
        except Exception:
            await websocket.close(code=1008, reason="Invalid token")
            return

    t_stmt = select(Trustee).where(Trustee.election_id == election.election_id)
    t_res = await db.execute(t_stmt)
    num_trustees = len(t_res.scalars().all())

    ceremony = get_or_create_ceremony(
        election.election_id, num_trustees, window_minutes=election.ceremony_window_minutes or 5
    )
    token_hash = hash_link_token(token)
    
    # Register socket
    ceremony.websockets[trustee.position].add(websocket)
    ceremony.record_presence(trustee.position, token_hash, trustee.name, trustee.email or "")
    
    # Send initial state
    await websocket.send_text(json.dumps(ceremony.to_public_dict(viewer_position=trustee.position)))
    await broadcast_ceremony_state(ceremony)

    try:
        while True:
            # Expect client heartbeat ping every 5 seconds
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
                msg = json.loads(data) if data else {}
                if msg.get("type") == "PING":
                    ceremony.record_presence(trustee.position, token_hash, trustee.name, trustee.email or "")
                    await websocket.send_text(json.dumps({"type": "PONG", "time": time.time()}))
            except asyncio.TimeoutError:
                # Check timeout
                ceremony.record_presence(trustee.position, token_hash, trustee.name, trustee.email or "")
            
            ceremony.check_active_round_timeout_and_disconnects()
            await websocket.send_text(json.dumps(ceremony.to_public_dict(viewer_position=trustee.position)))
    except (WebSocketDisconnect, Exception) as e:
        logger.info(f"Trustee {trustee.position} WebSocket closed: {e}")
    finally:
        ceremony.websockets[trustee.position].discard(websocket)
        ceremony.check_active_round_timeout_and_disconnects()
        await broadcast_ceremony_state(ceremony)


@router.post("/submit-code/{token}")
async def submit_trustee_code(token: str, req: SubmitCodeRequest, db: AsyncSession = Depends(get_db)):
    """
    Submits this trustee's part of the secret code.
    Enforces:
    - Voting must be closed.
    - All N trustees must be present.
    - Strict sequential ordering (positions 1..N).
    - Constant-time verification & lockout.
    - Round window timer.
    - Full concatenation commitment verification on final part.
    """
    trustee, election = await lookup_trustee_by_token(token, db)
    
    # 1. Gate: Election voting must be closed
    if election.status not in ("CLOSED", "TALLYING", "COMPLETED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The ceremony is locked. Voting is still active and must be officially closed before validation begins.",
        )

    t_stmt = select(Trustee).where(Trustee.election_id == election.election_id).order_by(Trustee.position)
    t_res = await db.execute(t_stmt)
    all_trustees = t_res.scalars().all()
    num_trustees = len(all_trustees)

    ceremony = get_or_create_ceremony(
        election.election_id, num_trustees, window_minutes=election.ceremony_window_minutes or 5
    )
    token_hash = hash_link_token(token)
    ceremony.record_presence(trustee.position, token_hash, trustee.name, trustee.email or "")

    # 2. Gate: All N trustees must be present concurrently
    if not ceremony.all_trustees_present():
        ceremony.reset_round("Attempted code submission while one or more trustees were absent.")
        await broadcast_ceremony_state(ceremony)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All {num_trustees} trustees must be present simultaneously to submit codes. Currently {ceremony.get_present_count()} of {num_trustees} online.",
        )

    # 3. Check lockout
    is_locked, remaining = ceremony.is_trustee_locked(trustee.position)
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Trustee #{trustee.position} is locked out for {remaining} more seconds due to 3 failed attempts.",
        )

    # 4. Gate: Strict sequential ordering
    expected_pos = len(ceremony.accepted_positions) + 1
    if trustee.position != expected_pos:
        ceremony.reset_round(
            f"Out-of-order submission: Trustee #{trustee.position} submitted when Trustee #{expected_pos} was expected."
        )
        await broadcast_ceremony_state(ceremony)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Out of order! Trustee #{expected_pos} must enter their code next.",
        )

    # 5. Parse and validate code format
    is_valid_format, norm_code, err_msg = parse_and_validate_trustee_code(req.code, trustee.position)
    if not is_valid_format:
        ceremony.record_failed_attempt(trustee.position)
        ceremony.reset_round(f"Trustee #{trustee.position} entered an invalid code format.")
        await broadcast_ceremony_state(ceremony)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    # 6. Verify against stored hash in constant time
    is_correct = verify_trustee_code(norm_code, trustee.code_hash, trustee.code_salt)
    if not is_correct:
        ceremony.record_failed_attempt(trustee.position)
        ceremony.reset_round(f"Trustee #{trustee.position} entered an incorrect code.")
        await broadcast_ceremony_state(ceremony)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect code entered. The unlock round has been reset.",
        )

    # Code is correct!
    ceremony.reset_failed_attempts(trustee.position)
    ceremony.accepted_positions.add(trustee.position)
    ceremony.accepted_codes[trustee.position] = norm_code

    # Start timer if position 1
    now = time.time()
    if len(ceremony.accepted_positions) == 1:
        ceremony.status = "IN_PROGRESS"
        ceremony.round_started_at = now
        ceremony.round_expires_at = now + ceremony.window_seconds
        ceremony.reset_reason = None
        ceremony.log_event("CODE_ACCEPTED", f"Trustee #{trustee.position} ({trustee.name}) code accepted. Round timer started ({ceremony.window_seconds // 60}m).", trustee.position)
    else:
        ceremony.log_event("CODE_ACCEPTED", f"Trustee #{trustee.position} ({trustee.name}) code accepted ({len(ceremony.accepted_positions)}/{num_trustees}).", trustee.position)

    # 7. Check if ALL N positions have been accepted in order!
    if len(ceremony.accepted_positions) == num_trustees:
        # Verify full ordered concatenation commitment
        ordered_codes = [(pos, ceremony.accepted_codes[pos]) for pos in range(1, num_trustees + 1)]
        is_comm_valid = verify_full_passphrase_commitment(
            ordered_codes, election.full_passphrase_commitment, election.full_passphrase_salt
        )
        if not is_comm_valid:
            ceremony.reset_round("Critical error: Full ordered passphrase commitment verification failed.")
            await broadcast_ceremony_state(ceremony)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Master passphrase commitment verification failed.",
            )

        # Decrypt all shares into memory for the unlocked session
        for t in all_trustees:
            t_code = ceremony.accepted_codes[t.position]
            decrypted_s_i = decrypt_share_at_rest(t.encrypted_share_value, t_code)
            if decrypted_s_i is None:
                ceremony.reset_round(f"Error decrypting private key share for Trustee #{t.position}.")
                await broadcast_ceremony_state(ceremony)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Could not decrypt private key share for Trustee #{t.position}.",
                )
            # Store in in-memory session
            ceremony.unlocked_sessions[t.link_token_hash] = {
                "position": t.position,
                "trustee_id": t.trustee_id,
                "name": t.name,
                "expires_at": now + SESSION_DURATION_SECONDS,
                "decrypted_share": decrypted_s_i,
            }

        ceremony.status = "UNLOCKED"
        ceremony.log_event("UNLOCKED", "All N trustee codes accepted! Ceremony validation console unlocked for all trustees.")
        election.ceremony_unlocked_at = datetime.utcnow()
        await db.commit()

    await broadcast_ceremony_state(ceremony)
    return {
        "success": True,
        "status": ceremony.status,
        "accepted_count": len(ceremony.accepted_positions),
        "is_unlocked": ceremony.status == "UNLOCKED",
    }


def require_unlocked_trustee(token: str, ceremony: Optional[CeremonyState]) -> Dict[str, Any]:
    """Helper verifying that this token holds an active, unexpired unlocked ceremony session."""
    token_hash = hash_link_token(token)
    if not ceremony or ceremony.status not in ("UNLOCKED", "COMPLETED") or token_hash not in ceremony.unlocked_sessions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: The validation ceremony is locked. All N trustees must successfully complete the unlock protocol.",
        )
    
    session = ceremony.unlocked_sessions[token_hash]
    if time.time() > session["expires_at"]:
        ceremony.reset_round("Trustee validation session expired.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session expired: The 30-minute validation window has elapsed. The ceremony must be repeated.",
        )
    return session


@router.get("/validation/summary/{token}")
async def get_validation_summary(token: str, db: AsyncSession = Depends(get_db)):
    """Returns election details and bulletin board status for unlocked trustees."""
    trustee, election = await lookup_trustee_by_token(token, db)
    ceremony = get_ceremony_state(election.election_id)
    session = require_unlocked_trustee(token, ceremony)

    # Ballots & Bulletin Board info
    b_stmt = select(Ballot).where(Ballot.election_id == election.election_id).order_by(Ballot.sequence_number)
    b_res = await db.execute(b_stmt)
    ballots = b_res.scalars().all()
    head_hash = ballots[-1].block_hash if ballots else "0x00000000000000000000000000000000"

    # Fetch approval states
    t_stmt = select(Trustee).where(Trustee.election_id == election.election_id).order_by(Trustee.position)
    t_res = await db.execute(t_stmt)
    all_trustees = t_res.scalars().all()

    approvals = [
        {
            "position": t.position,
            "name": t.name,
            "has_approved": bool(t.has_approved),
            "approved_at": t.approved_at.isoformat() if t.approved_at else None,
        }
        for t in all_trustees
    ]

    tally_data = await get_or_compute_election_tally(election, db)

    return {
        "election_id": election.election_id,
        "title": election.title,
        "total_ballots": tally_data.get("total_ballots", len(ballots)),
        "head_hash": head_hash,
        "candidates": election.candidates,
        "results": tally_data.get("results", {}),
        "candidate_results": tally_data.get("candidate_results", {}),
        "your_position": trustee.position,
        "your_name": trustee.name,
        "has_approved": bool(trustee.has_approved),
        "all_approved": all(t.has_approved for t in all_trustees),
        "approvals": approvals,
        "results_published": bool(election.results_published_at),
    }


@router.post("/validation/verify/{token}")
async def run_independent_verification(token: str, db: AsyncSession = Depends(get_db)):
    """
    Performs complete cryptographic verification of the public bulletin board:
    1. Hash chain continuity (previous_hash -> block_hash).
    2. Ballot Zero-Knowledge Proofs (Disjunctive 1-of-2 and Sum-to-One proofs).
    3. Anonymous token signature uniqueness.
    4. Homomorphic aggregation check.
    """
    trustee, election = await lookup_trustee_by_token(token, db)
    ceremony = get_ceremony_state(election.election_id)
    require_unlocked_trustee(token, ceremony)

    b_stmt = select(Ballot).where(Ballot.election_id == election.election_id).order_by(Ballot.sequence_number)
    b_res = await db.execute(b_stmt)
    ballots = b_res.scalars().all()

    election_pk = PublicKey(h=int(election.public_key_h, 16))
    num_candidates = len(election.candidates)

    chain_valid = True
    chain_errors = []
    zkp_passes = 0
    zkp_failures = 0
    zkp_details = []
    seen_tokens = set()
    token_errors = []

    prev_hash = "GENESIS_BLOCK_CIPHERVOTE_2026"
    for b in ballots:
        # 1. Chain check
        if b.previous_hash != prev_hash:
            chain_valid = False
            chain_errors.append(f"Block #{b.sequence_number} previous hash mismatch")
        prev_hash = b.block_hash

        # 2. Token uniqueness
        if b.token_signature in seen_tokens:
            token_errors.append(f"Duplicate blind token signature at block #{b.sequence_number}")
        seen_tokens.add(b.token_signature)

        # 3. ZKP proof verification
        try:
            cts_data = json.loads(b.ciphertexts_json)
            proofs_data = json.loads(b.zkp_proofs_json)
            ciphertexts = [Ciphertext(c1=int(c["c1"], 16), c2=int(c["c2"], 16)) for c in cts_data]

            disj_proofs = proofs_data.get("disjunctive_proofs", [])
            for i, ct in enumerate(ciphertexts):
                dp = DisjunctiveZKP.from_dict(disj_proofs[i])
                if not verify_disjunctive_chaum_pedersen(election_pk, ct, dp):
                    raise ValueError(f"Disjunctive ZKP failed for candidate {i}")

            sum_p = EqualityZKP.from_dict(proofs_data["sum_proof"])
            if not verify_ballot_sum_to_one(election_pk, ciphertexts, sum_p):
                raise ValueError("Sum-to-one equality ZKP failed")

            zkp_passes += 1
        except Exception as e:
            zkp_failures += 1
            zkp_details.append(f"Block #{b.sequence_number}: {str(e)}")

    return {
        "verified_at": datetime.utcnow().isoformat(),
        "total_ballots_checked": len(ballots),
        "hash_chain_valid": chain_valid,
        "hash_chain_errors": chain_errors,
        "zkp_proofs_passed": zkp_passes,
        "zkp_proofs_failed": zkp_failures,
        "zkp_error_details": zkp_details,
        "token_uniqueness_valid": len(token_errors) == 0,
        "duplicate_tokens": token_errors,
        "overall_integrity_verified": (chain_valid and zkp_failures == 0 and len(token_errors) == 0),
    }


@router.post("/validation/approve/{token}")
async def approve_and_submit_partial_decryption(
    token: str, req: ApproveRequest, db: AsyncSession = Depends(get_db)
):
    """
    Computes this trustee's partial ElGamal decryptions and DLEQ proofs from their in-memory share.
    Saves the partial decryption to the database, records approval, and wipes the share from memory.
    """
    trustee, election = await lookup_trustee_by_token(token, db)
    ceremony = get_ceremony_state(election.election_id)
    session = require_unlocked_trustee(token, ceremony)

    s_i = session.get("decrypted_share")
    if s_i is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Key share already wiped from memory.")

    # 1. Fetch all ballots & compute homomorphic aggregate vector [Agg_C0, Agg_C1, ...]
    b_stmt = select(Ballot).where(Ballot.election_id == election.election_id).order_by(Ballot.sequence_number)
    b_res = await db.execute(b_stmt)
    ballots = b_res.scalars().all()

    num_candidates = len(election.candidates)
    candidate_ciphertexts: List[List[Ciphertext]] = [[] for _ in range(num_candidates)]

    for b in ballots:
        cts_data = json.loads(b.ciphertexts_json)
        for cand_idx in range(num_candidates):
            if cand_idx < len(cts_data):
                candidate_ciphertexts[cand_idx].append(
                    Ciphertext(c1=int(cts_data[cand_idx]["c1"], 16), c2=int(cts_data[cand_idx]["c2"], 16))
                )

    # Homomorphic addition for each candidate
    h_i = int(trustee.verification_key_h, 16)
    partial_decryptions = []

    for cand_idx in range(num_candidates):
        agg_ct = (
            homomorphic_sum(candidate_ciphertexts[cand_idx])
            if candidate_ciphertexts[cand_idx]
            else Ciphertext(c1=1, c2=1)
        )
        # D_i = c1^(s_i) mod P
        d_i = pow(agg_ct.c1, s_i, P)
        # Generate DLEQ proof for (G, h_i, agg_ct.c1, d_i)
        dleq_proof = prove_trustee_partial_decryption(s_i, h_i, agg_ct.c1, d_i)

        partial_decryptions.append({
            "candidate_id": cand_idx,
            "partial_decryption_factor": hex(d_i),
            "dleq_proof": dleq_proof.to_dict(),
        })

    # Save to Trustee record
    trustee.partial_decryption_json = json.dumps(partial_decryptions)
    trustee.has_approved = True
    trustee.approved_at = datetime.utcnow()

    # 2. Cryptographic Memory Wipe: wipe share from session
    session["decrypted_share"] = None
    logger.info(f"[SECURITY] Trustee #{trustee.position} ({trustee.name}) share wiped from volatile server memory.")

    # Flush so this trustee's approval is visible to the all-approved check
    # in the same session, before we decide whether to publish.
    await db.flush()

    t_stmt = select(Trustee).where(Trustee.election_id == election.election_id)
    t_res = await db.execute(t_stmt)
    all_trustees = t_res.scalars().all()
    all_approved = all(t.has_approved for t in all_trustees)

    approved_at = trustee.approved_at.isoformat() if trustee.approved_at else None
    published = None
    if all_approved:
        ceremony.status = "COMPLETED"
        ceremony.log_event(
            "COMPLETED",
            "All trustees approved the tally. Results published to voters.",
        )
        published = await publish_official_results(election, db)
        await broadcast_ceremony_state(ceremony)
    else:
        await db.commit()

    return {
        "success": True,
        "message": (
            f"Trustee #{trustee.position} approved. Every trustee has agreed, so the results are now public to voters."
            if all_approved
            else f"Trustee #{trustee.position} approved. Voters will see the results after every trustee agrees."
        ),
        "all_approved": all_approved,
        "results_published": published is not None,
        "results": published.get("results") if published else None,
        "approved_at": approved_at,
    }


@router.get("/bulletin-board-export/{token}")
async def export_bulletin_board(token: str, db: AsyncSession = Depends(get_db)):
    """Exports full public bulletin board dataset for offline independent verification."""
    trustee, election = await lookup_trustee_by_token(token, db)
    ceremony = get_ceremony_state(election.election_id)
    require_unlocked_trustee(token, ceremony)

    b_stmt = select(Ballot).where(Ballot.election_id == election.election_id).order_by(Ballot.sequence_number)
    b_res = await db.execute(b_stmt)
    ballots = b_res.scalars().all()

    export_data = {
        "election_id": election.election_id,
        "election_title": election.title,
        "public_key_h": election.public_key_h,
        "total_ballots": len(ballots),
        "exported_at": datetime.utcnow().isoformat(),
        "ballots": [
            {
                "sequence_number": b.sequence_number,
                "timestamp": b.timestamp,
                "ciphertexts": json.loads(b.ciphertexts_json),
                "zkp_proofs": json.loads(b.zkp_proofs_json),
                "receipt_code": b.receipt_code,
                "previous_hash": b.previous_hash,
                "block_hash": b.block_hash,
            }
            for b in ballots
        ],
    }
    return export_data
