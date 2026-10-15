"""
Homomorphic Tally Computation & 3-of-5 Trustee Joint Decryption Router.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.bulletin_board.merkle_tree import MerkleTree
from app.core.crypto.elgamal import Ciphertext, homomorphic_sum
from app.core.crypto.shamir import (
    TrusteeShare,
    compute_partial_decryption,
    threshold_decrypt,
)
from app.core.crypto.zkp import (
    prove_trustee_partial_decryption,
    verify_trustee_partial_decryption,
)
from app.models import Ballot, Election, TallyResult, Trustee, get_db
from app.schemas import TallyResultResponse

router = APIRouter(prefix="/tally", tags=["Tally & Threshold Decryption"])


@router.post("/compute", response_model=TallyResultResponse)
async def compute_election_tally(
    election_id: str = "council-2026",
    trustee_ids: str = "1,2,3",  # Comma separated list of at least 3 trustees
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger homomorphic tallying:
    1. Homomorphically aggregate candidate ciphertexts across all ballots in bulletin board.
    2. Collect partial decryptions & DLEQ proofs from specified trustees (minimum 3).
    3. Jointly decrypt final candidate totals via Lagrange interpolation without decrypting individual ballots.
    4. Publish verified tally results.
    """
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    # Fetch all ballots
    ballots_res = await db.execute(
        select(Ballot).where(Ballot.election_id == election_id).order_by(Ballot.sequence_number.asc())
    )
    ballots = ballots_res.scalars().all()
    if not ballots:
        raise HTTPException(status_code=400, detail="No ballots cast in this election.")

    # Parse requested trustees (at least 3)
    requested_ids = [int(x.strip()) for x in trustee_ids.split(",") if x.strip()]
    if len(requested_ids) < 3:
        raise HTTPException(status_code=400, detail="At least 3 trustees required for threshold decryption.")

    t_res = await db.execute(
        select(Trustee).where(Trustee.election_id == election_id, Trustee.trustee_id.in_(requested_ids))
    )
    trustees = t_res.scalars().all()
    if len(trustees) < 3:
        raise HTTPException(status_code=400, detail=f"Found only {len(trustees)} matching trustees; need at least 3.")

    candidates = json.loads(election.candidates_json)
    num_candidates = len(candidates)

    # 1. Homomorphically aggregate each candidate column
    aggregated_ciphertexts = []
    for cand_idx in range(num_candidates):
        cand_cts = []
        for b in ballots:
            cts_data = json.loads(b.ciphertexts_json)
            cand_cts.append(Ciphertext(c1=int(cts_data[cand_idx]["c1"], 16), c2=int(cts_data[cand_idx]["c2"], 16)))
        agg = homomorphic_sum(cand_cts)
        aggregated_ciphertexts.append(agg)

    # 2. Collect partial decryptions & DLEQ proofs
    candidate_results = {}
    trustee_contributions = []

    for cand_idx, cand in enumerate(candidates):
        agg_ct = aggregated_ciphertexts[cand_idx]
        partial_decs = []

        for t in trustees:
            share = TrusteeShare(
                trustee_id=t.trustee_id,
                share_value=int(t.encrypted_share_value, 16),
                public_verification_key=int(t.verification_key_h, 16),
            )
            d_i = compute_partial_decryption(share, agg_ct)
            proof = prove_trustee_partial_decryption(
                share_value_s_i=share.share_value,
                verification_key_h_i=share.public_verification_key,
                c1=agg_ct.c1,
                d_i=d_i,
            )
            # Verify proof immediately
            if not verify_trustee_partial_decryption(share.public_verification_key, agg_ct.c1, d_i, proof):
                raise HTTPException(status_code=500, detail=f"Trustee {t.trustee_id} DLEQ proof generation failed.")

            partial_decs.append((share.trustee_id, d_i))
            trustee_contributions.append({
                "candidate_id": cand_idx,
                "trustee_id": t.trustee_id,
                "d_i": hex(d_i),
                "proof": proof.to_dict(),
            })

        # 3. Combine with Lagrange interpolation and solve discrete log
        votes_count = threshold_decrypt(partial_decs, agg_ct, max_votes=len(ballots))
        candidate_results[cand["name"]] = votes_count

    # 4. Save Tally Result
    leaf_hashes = [b.block_hash for b in ballots]
    merkle_tree = MerkleTree(leaf_hashes)

    existing_tally_res = await db.execute(select(TallyResult).where(TallyResult.election_id == election_id))
    existing_tally = existing_tally_res.scalars().first()
    if existing_tally:
        await db.delete(existing_tally)

    tally_record = TallyResult(
        election_id=election_id,
        total_ballots=len(ballots),
        candidate_totals_json=json.dumps(candidate_results),
        aggregated_ciphertexts_json=json.dumps([ct.to_dict() for ct in aggregated_ciphertexts]),
        trustee_contributions_json=json.dumps(trustee_contributions),
        bulletin_board_root_hash=merkle_tree.root,
    )
    db.add(tally_record)
    election.status = "CLOSED"
    await db.commit()

    return TallyResultResponse(
        election_id=election_id,
        total_ballots=len(ballots),
        candidate_results=candidate_results,
        bulletin_board_root_hash=merkle_tree.root,
        trustee_shares_used=[t.trustee_id for t in trustees],
        status="TALLY_PUBLISHED",
    )


@router.get("/result", response_model=TallyResultResponse)
async def get_tally_result(
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
):
    """Retrieve published election results."""
    t_res = await db.execute(select(TallyResult).where(TallyResult.election_id == election_id))
    tally = t_res.scalars().first()
    if not tally:
        raise HTTPException(status_code=404, detail="Tally has not been computed yet for this election.")

    contributions = json.loads(tally.trustee_contributions_json)
    trustees_used = sorted(list(set(c["trustee_id"] for c in contributions)))

    return TallyResultResponse(
        election_id=election_id,
        total_ballots=tally.total_ballots,
        candidate_results=json.loads(tally.candidate_totals_json),
        bulletin_board_root_hash=tally.bulletin_board_root_hash,
        trustee_shares_used=trustees_used,
        status="TALLY_PUBLISHED",
    )
