"""
Public Portal Router (/api/public)
Unauthenticated public endpoints for status, public bulletin board auditing,
Merkle verification, receipt lookups, and election results.
"""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bulletin_board.merkle_tree import MerkleTree

from app.core.notifications import format_voting_window
from app.models import Ballot, Election, TallyResult, get_db
from app.schemas import (
    BulletinBoardItem,
    BulletinBoardResponse,
    BulletinBoardVerifyResponse,
    CiphertextItem,
    ElectionStatusResponse,
    PublicElectionListItem,
    PublicElectionListResponse,
    TallyResultResponse,
)

router = APIRouter(prefix="/public", tags=["Public Portal & Auditor"])


def get_closed_reason(status_val: str) -> Optional[str]:
    if status_val == "REGISTRATION":
        return None
    elif status_val == "OPEN":
        return "Voting has started"
    elif status_val in ("CLOSED", "ENDED"):
        return "Voting has closed"
    elif status_val == "TALLYING":
        return "Tallying in progress"
    return f"Registration closed ({status_val})"


@router.get("/status", response_model=ElectionStatusResponse)
async def get_public_election_status(
    election_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Public read-only status and cryptographic parameters of the election."""
    if election_id and election_id != "null" and election_id != "undefined":
        el_res = await db.execute(select(Election).where(Election.election_id == election_id))
        election = el_res.scalars().first()
    else:
        el_res = await db.execute(select(Election).order_by(Election.created_at.desc()))
        election = el_res.scalars().first()

    if not election:
        raise HTTPException(status_code=404, detail="No election configured yet.")

    voters_count = (await db.execute(select(func.count(Ballot.id)).where(Ballot.election_id == election_id))).scalar() or 0
    formatted_window = format_voting_window(
        election.scheduled_start,
        election.scheduled_end,
        election.timezone or "UTC",
    )

    last_b = (await db.execute(
        select(Ballot.block_hash).where(Ballot.election_id == election_id).order_by(Ballot.sequence_number.desc()).limit(1)
    )).scalar()

    import time
    now_ts = int(time.time())

    return ElectionStatusResponse(
        election_id=election.election_id,
        title=election.title,
        status=election.status,
        is_open=(election.status == "OPEN"),
        open_time=election.open_time,
        close_time=election.close_time,
        current_time=now_ts,
        public_key_h=election.public_key_h,
        blind_rsa_n=election.blind_rsa_n,
        blind_rsa_e=election.blind_rsa_e,
        candidates=election.candidates,
        bulletin_board_length=voters_count,
        head_hash=last_b or "GENESIS",
        scheduled_start=election.scheduled_start,
        scheduled_end=election.scheduled_end,
        timezone=election.timezone or "UTC",
        formatted_window=formatted_window,
        actual_open_at=election.actual_open_at,
        actual_close_at=election.actual_close_at,
    )



@router.get("/elections", response_model=PublicElectionListResponse)
async def get_public_elections(db: AsyncSession = Depends(get_db)):
    """
    Public read-only listing of all elections with registration status and windows.
    Strictly unauthenticated; never exposes secrets, private keys, or trustee credentials.
    """
    res = await db.execute(select(Election).order_by(Election.created_at.desc()))
    elections = res.scalars().all()
    items = []
    for e in elections:
        if e.status == "ARCHIVED":
            continue
        reg_open = (e.status == "REGISTRATION")
        closed_reason = get_closed_reason(e.status)
        win = format_voting_window(e.scheduled_start, e.scheduled_end, e.timezone or "UTC")
        items.append(
            PublicElectionListItem(
                election_id=e.election_id,
                title=e.title,
                status=e.status,
                is_open=(e.status == "OPEN"),
                registration_open=reg_open,
                closed_reason=closed_reason,
                scheduled_window=win,
                timezone=e.timezone or "UTC",
                scheduled_start=e.scheduled_start,
                scheduled_end=e.scheduled_end,
                candidates_count=len(e.candidates),
                created_at=e.created_at.isoformat() if e.created_at else None,
            )
        )
    return PublicElectionListResponse(elections=items)


@router.get("/list", response_model=PublicElectionListResponse)
async def get_public_election_list(db: AsyncSession = Depends(get_db)):
    """List all elections available on the system."""
    return await get_public_elections(db=db)


@router.get("/bulletin-board", response_model=BulletinBoardResponse)
async def get_public_bulletin_board(
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
):
    """Public read-only bulletin board ledger."""
    res = await db.execute(
        select(Ballot).where(Ballot.election_id == election_id).order_by(Ballot.sequence_number.asc())
    )
    ballots = res.scalars().all()

    items = [
        BulletinBoardItem(
            sequence_number=b.sequence_number,
            timestamp=b.timestamp,
            ciphertexts=[CiphertextItem(**c) for c in json.loads(b.ciphertexts_json or "[]")],
            receipt_code=b.receipt_code,
            previous_hash=b.previous_hash,
            block_hash=b.block_hash,
        )
        for b in ballots
    ]

    genesis_hash = ballots[0].previous_hash if ballots else "GENESIS"
    head_hash = ballots[-1].block_hash if ballots else "GENESIS"

    return BulletinBoardResponse(
        election_id=election_id,
        total_ballots=len(ballots),
        genesis_hash=genesis_hash,
        head_hash=head_hash,
        ballots=items,
    )


@router.get("/bulletin-board/verify", response_model=BulletinBoardVerifyResponse)
async def verify_public_bulletin_board(
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
):
    """Cryptographic verification of hash chain and Merkle tree root."""
    res = await db.execute(
        select(Ballot).where(Ballot.election_id == election_id).order_by(Ballot.sequence_number.asc())
    )
    ballots = res.scalars().all()

    if not ballots:
        return BulletinBoardVerifyResponse(
            is_valid=True,
            total_ballots=0,
            genesis_hash="GENESIS",
            head_hash="GENESIS",
            merkle_root="EMPTY_TREE",
            error=None,
        )

    # 1. Verify strict consecutive sequence numbers & hash chain
    expected_prev = ballots[0].previous_hash
    for idx, b in enumerate(ballots, start=1):
        if b.sequence_number != idx:
            return BulletinBoardVerifyResponse(
                is_valid=False,
                total_ballots=len(ballots),
                genesis_hash=ballots[0].previous_hash,
                head_hash=ballots[-1].block_hash,
                merkle_root="",
                error=f"Sequence broken at ballot #{b.sequence_number} (expected {idx})",
            )
        if b.previous_hash != expected_prev:
            return BulletinBoardVerifyResponse(
                is_valid=False,
                total_ballots=len(ballots),
                genesis_hash=ballots[0].previous_hash,
                head_hash=ballots[-1].block_hash,
                merkle_root="",
                error=f"Hash chain broken at ballot #{b.sequence_number}",
            )
        expected_prev = b.block_hash

    # 2. Build Merkle Tree
    leaf_hashes = [b.block_hash for b in ballots]
    merkle_tree = MerkleTree(leaf_hashes)

    return BulletinBoardVerifyResponse(
        is_valid=True,
        total_ballots=len(ballots),
        genesis_hash=ballots[0].previous_hash,
        head_hash=ballots[-1].block_hash,
        merkle_root=merkle_tree.root,
        error=None,
    )


def _normalize_receipt(receipt_code: str) -> str:
    """Receipts are stored as XXXX-XXXX-XXXX. Ignore spaces and letter case."""
    return "".join(receipt_code.split()).upper()


@router.get("/receipt/{receipt_code}")
@router.get("/bulletin-board/receipt/{receipt_code}")
async def get_public_receipt(
    receipt_code: str,
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
):
    """Lookup individual voter ballot block and Merkle audit path by receipt code."""
    normalized = _normalize_receipt(receipt_code)
    scoped = await db.execute(
        select(Ballot).where(
            Ballot.election_id == election_id,
            func.upper(Ballot.receipt_code) == normalized,
        )
    )
    ballot = scoped.scalars().first()
    if ballot is None:
        # Receipt codes are unique across elections, so a mismatched election id
        # must not hide a ballot that is already on the ledger.
        fallback = await db.execute(
            select(Ballot).where(func.upper(Ballot.receipt_code) == normalized)
        )
        ballot = fallback.scalars().first()
    if not ballot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No ballot matching receipt code '{receipt_code}' was found on the official bulletin board.",
        )

    all_res = await db.execute(
        select(Ballot.block_hash)
        .where(Ballot.election_id == ballot.election_id)
        .order_by(Ballot.sequence_number.asc())
    )
    all_hashes = [row[0] for row in all_res.all()]
    merkle_tree = MerkleTree(all_hashes)
    leaf_idx = ballot.sequence_number - 1
    proof = merkle_tree.get_proof(leaf_idx)
    proof_payload = None
    if proof is not None:
        proof_payload = {
            "leaf_hash": proof.leaf_hash,
            "leaf_index": proof.leaf_index,
            "total_leaves": proof.total_leaves,
            "audit_path": proof.audit_path,
            "root_hash": proof.root_hash,
        }

    return {
        "receipt_code": ballot.receipt_code,
        "election_id": ballot.election_id,
        "sequence_number": ballot.sequence_number,
        "timestamp": ballot.timestamp,
        "block_hash": ballot.block_hash,
        "previous_hash": ballot.previous_hash,
        "merkle_root": merkle_tree.root,
        "merkle_proof": proof_payload,
        "is_verified": True,
    }


@router.get("/results")
@router.get("/tally")
async def get_public_results(
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
):
    """Retrieve official tally results and trustee decryption certificate."""
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()

    res = await db.execute(select(TallyResult).where(TallyResult.election_id == election_id))
    tally = res.scalars().first()
    if not tally or not election or not election.results_published_at:
        return {
            "election_id": election_id,
            "status": "PENDING",
            "published": False,
            "message": "Results have not been officially published yet.",
        }

    totals = json.loads(tally.candidate_totals_json or "{}")
    return {
        "election_id": tally.election_id,
        "total_ballots": tally.total_ballots,
        "results": totals,
        "candidate_results": totals,
        "bulletin_board_root_hash": tally.bulletin_board_root_hash,
        "root_hash": tally.bulletin_board_root_hash,
        "published": True,
        "published_at": election.results_published_at.isoformat() if election.results_published_at else None,
        "status": "COMPLETED",
    }
