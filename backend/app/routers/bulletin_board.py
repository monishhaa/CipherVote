"""
Public Bulletin Board & Merkle Audit Router.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.bulletin_board.hash_chain import (
    BulletinBoardEntry,
    compute_genesis_hash,
    verify_hash_chain,
)
from app.core.bulletin_board.merkle_tree import MerkleTree
from app.models import Ballot, Election, get_db
from app.schemas import (
    BulletinBoardItem,
    BulletinBoardResponse,
    BulletinBoardVerifyResponse,
    CiphertextItem,
)

router = APIRouter(prefix="/bulletin-board", tags=["Public Bulletin Board"])


@router.get("", response_model=BulletinBoardResponse)
async def get_bulletin_board(
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full append-only bulletin board ledger for public auditing."""
    ballots_res = await db.execute(
        select(Ballot).where(Ballot.election_id == election_id).order_by(Ballot.sequence_number.asc())
    )
    ballots = ballots_res.scalars().all()

    items = []
    for b in ballots:
        cts_data = json.loads(b.ciphertexts_json)
        items.append(
            BulletinBoardItem(
                sequence_number=b.sequence_number,
                timestamp=b.timestamp,
                ciphertexts=[CiphertextItem(**c) for c in cts_data],
                receipt_code=b.receipt_code,
                previous_hash=b.previous_hash,
                block_hash=b.block_hash,
            )
        )

    genesis_hash = compute_genesis_hash(election_id)
    head_hash = ballots[-1].block_hash if ballots else genesis_hash

    return BulletinBoardResponse(
        election_id=election_id,
        total_ballots=len(ballots),
        genesis_hash=genesis_hash,
        head_hash=head_hash,
        ballots=items,
    )


@router.get("/verify", response_model=BulletinBoardVerifyResponse)
async def verify_bulletin_board_integrity(
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
):
    """Cryptographically verify the entire bulletin board hash chain and return Merkle root."""
    ballots_res = await db.execute(
        select(Ballot).where(Ballot.election_id == election_id).order_by(Ballot.sequence_number.asc())
    )
    ballots = ballots_res.scalars().all()

    entries = [
        BulletinBoardEntry(
            sequence_number=b.sequence_number,
            timestamp=b.timestamp,
            ciphertexts=json.loads(b.ciphertexts_json),
            zkp_proofs=json.loads(b.zkp_proofs_json),
            token_signature=b.token_signature,
            receipt_code=b.receipt_code,
            previous_hash=b.previous_hash,
            block_hash=b.block_hash,
        )
        for b in ballots
    ]

    is_valid, error = verify_hash_chain(election_id, entries)
    leaf_hashes = [b.block_hash for b in ballots]
    merkle_tree = MerkleTree(leaf_hashes)

    genesis_hash = compute_genesis_hash(election_id)
    head_hash = ballots[-1].block_hash if ballots else genesis_hash

    return BulletinBoardVerifyResponse(
        is_valid=is_valid,
        total_ballots=len(ballots),
        genesis_hash=genesis_hash,
        head_hash=head_hash,
        merkle_root=merkle_tree.root,
        error=error,
    )


@router.get("/receipt/{receipt_code}")
async def lookup_ballot_receipt(
    receipt_code: str,
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
):
    """Lookup a ballot by receipt code and return Merkle inclusion proof."""
    ballots_res = await db.execute(
        select(Ballot).where(Ballot.election_id == election_id).order_by(Ballot.sequence_number.asc())
    )
    all_ballots = ballots_res.scalars().all()

    normalized = "".join(receipt_code.split()).upper()
    target_idx = None
    target_ballot = None
    for idx, b in enumerate(all_ballots):
        stored = "".join((b.receipt_code or "").split()).upper()
        if stored == normalized:
            target_idx = idx
            target_ballot = b
            break
    if target_ballot is None:
        any_res = await db.execute(select(Ballot).order_by(Ballot.sequence_number.asc()))
        any_ballots = any_res.scalars().all()
        for idx, b in enumerate(any_ballots):
            stored = "".join((b.receipt_code or "").split()).upper()
            if stored == normalized:
                all_ballots = [row for row in any_ballots if row.election_id == b.election_id]
                target_ballot = b
                target_idx = next(i for i, row in enumerate(all_ballots) if row.id == b.id)
                break

    if target_ballot is None or target_idx is None:
        raise HTTPException(status_code=404, detail="Receipt code not found in bulletin board")

    leaf_hashes = [b.block_hash for b in all_ballots]
    merkle_tree = MerkleTree(leaf_hashes)
    proof = merkle_tree.get_proof(target_idx)

    return {
        "receipt_code": target_ballot.receipt_code,
        "sequence_number": target_ballot.sequence_number,
        "timestamp": target_ballot.timestamp,
        "block_hash": target_ballot.block_hash,
        "previous_hash": target_ballot.previous_hash,
        "merkle_proof": proof,
    }
