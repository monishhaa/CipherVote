"""
Anonymous Ballot Casting & ZKP Ingestion Router.
"""

from datetime import datetime, timezone
import hashlib
import json
import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.bulletin_board.hash_chain import (
    compute_ballot_payload_hash,
    compute_genesis_hash,
)
from app.core.crypto.blind_signature import (
    RSABlindPublicKey,
    verify_blind_signature,
)
from app.core.crypto.elgamal import Ciphertext, PublicKey
from app.core.crypto.zkp import (
    DisjunctiveZKP,
    EqualityZKP,
    verify_ballot_sum_to_one,
    verify_disjunctive_chaum_pedersen,
)
from app.models import Ballot, Election, get_db
from app.schemas import BallotCastRequest, BallotCastResponse

router = APIRouter(prefix="/ballots", tags=["Ballots"])


@router.post("/cast", response_model=BallotCastResponse)
async def cast_ballot(
    req: BallotCastRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Cast an anonymous encrypted ballot.
    Verifies blind signature, disjunctive ZKPs for all candidates, and sum-to-one ZKP,
    then appends to the append-only bulletin board hash chain.
    Enforces that the election is in OPEN status and within the scheduled window.
    """
    # 1. Fetch Election
    el_res = await db.execute(select(Election).where(Election.election_id == req.election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    if election.status != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Election is not open for voting (Current status: {election.status})",
        )

    # Check if scheduled_end has elapsed
    if election.scheduled_end:
        now_utc = datetime.utcnow()
        if now_utc > election.scheduled_end:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Voting closed: The scheduled voting end time has elapsed.",
            )

    # 2. Verify Blind Token Signature
    blind_pk = RSABlindPublicKey(
        n=int(election.blind_rsa_n, 16),
        e=election.blind_rsa_e,
    )
    try:
        sig_int = int(req.token_signature, 16)
        if not verify_blind_signature(req.token_nonce, sig_int, blind_pk):
            raise HTTPException(status_code=401, detail="Invalid voting token signature.")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"Token verification error: {str(e)}")

    # 3. Double-Voting Prevention (Token Replay Check)
    existing_ballot = await db.execute(select(Ballot).where(Ballot.token_signature == req.token_signature))
    if existing_ballot.scalars().first():
        raise HTTPException(status_code=403, detail="Double-voting blocked: Token has already been spent.")

    # 4. Parse & Verify Cryptographic Ciphertexts & ZKPs
    election_pk = PublicKey(h=int(election.public_key_h, 16))
    candidates = json.loads(election.candidates_json)
    if len(req.ciphertexts) != len(candidates):
        raise HTTPException(
            status_code=400,
            detail=f"Ciphertext count ({len(req.ciphertexts)}) does not match candidate count ({len(candidates)})",
        )

    parsed_cts = [Ciphertext(c1=int(c.c1, 16), c2=int(c.c2, 16)) for c in req.ciphertexts]

    # Verify 1-of-2 ZKP for each candidate
    if len(req.zkp_proofs.disjunctive_proofs) != len(candidates):
        raise HTTPException(status_code=400, detail="Missing disjunctive ZKP for some candidates")

    for idx, (ct, zkp_item) in enumerate(zip(parsed_cts, req.zkp_proofs.disjunctive_proofs)):
        zkp = DisjunctiveZKP(
            a0=int(zkp_item.a0, 16), b0=int(zkp_item.b0, 16),
            a1=int(zkp_item.a1, 16), b1=int(zkp_item.b1, 16),
            c0=int(zkp_item.c0, 16), c1=int(zkp_item.c1, 16),
            z0=int(zkp_item.z0, 16), z1=int(zkp_item.z1, 16),
        )
        if not verify_disjunctive_chaum_pedersen(election_pk, ct, zkp):
            raise HTTPException(
                status_code=400,
                detail=f"ZKP verification failed: Candidate #{idx} vote is not in {{0, 1}}",
            )

    # Verify Sum-to-One ZKP
    sum_zkp_item = req.zkp_proofs.sum_proof
    sum_zkp = EqualityZKP(
        a=int(sum_zkp_item.a, 16), b=int(sum_zkp_item.b, 16),
        c=int(sum_zkp_item.c, 16), z=int(sum_zkp_item.z, 16),
    )
    if not verify_ballot_sum_to_one(election_pk, parsed_cts, sum_zkp):
        raise HTTPException(
            status_code=400,
            detail="ZKP verification failed: Ballot votes do not sum to exactly 1.",
        )

    # 5. Append to Bulletin Board Hash Chain
    last_ballot_res = await db.execute(
        select(Ballot).where(Ballot.election_id == req.election_id).order_by(Ballot.sequence_number.desc())
    )
    last_ballot = last_ballot_res.scalars().first()

    next_seq = (last_ballot.sequence_number + 1) if last_ballot else 1
    prev_hash = last_ballot.block_hash if last_ballot else compute_genesis_hash(req.election_id)
    now_ts = int(time.time())

    cts_data = [c.model_dump() for c in req.ciphertexts]
    cts_json = json.dumps(cts_data, sort_keys=True)
    zkp_json = json.dumps(req.zkp_proofs.model_dump(), sort_keys=True)

    block_hash = compute_ballot_payload_hash(
        sequence_number=next_seq,
        timestamp=now_ts,
        ciphertexts_json=cts_json,
        token_signature=req.token_signature,
        previous_hash=prev_hash,
    )

    # Deterministic receipt code
    receipt_raw = hashlib.sha256(f"{block_hash}:{req.token_nonce}".encode("utf-8")).hexdigest()[:12].upper()
    receipt_code = f"{receipt_raw[0:4]}-{receipt_raw[4:8]}-{receipt_raw[8:12]}"

    ballot = Ballot(
        election_id=req.election_id,
        sequence_number=next_seq,
        timestamp=now_ts,
        ciphertexts_json=cts_json,
        zkp_proofs_json=zkp_json,
        token_signature=req.token_signature,
        receipt_code=receipt_code,
        previous_hash=prev_hash,
        block_hash=block_hash,
    )
    db.add(ballot)
    await db.commit()

    return BallotCastResponse(
        receipt_code=receipt_code,
        sequence_number=next_seq,
        block_hash=block_hash,
        timestamp=now_ts,
        message="Ballot successfully cast, verified, and appended to the public bulletin board.",
    )
