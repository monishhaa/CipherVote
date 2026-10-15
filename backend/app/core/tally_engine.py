"""
Core Tally & Decryption Engine.
Computes homomorphic candidate tallies using either:
1. Existing TallyResult record.
2. Master private key x (for admin preview / trustee preliminary verification before approval).
3. Trustee partial decryptions (Lagrange threshold decryption).
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ballot, Election, TallyResult, Trustee
from app.core.bulletin_board.hash_chain import compute_genesis_hash
from app.core.crypto.elgamal import Ciphertext, homomorphic_sum, solve_discrete_log, P, G
from app.core.crypto.shamir import threshold_decrypt


async def get_or_compute_election_tally(
    election: Election,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Computes or retrieves candidate tallies for an election.
    Safe for Admin Preview and Trustee Console Verification before final publication.
    """
    candidates = election.candidates
    default_totals = {c.get("name", f"Candidate {c.get('id')}"): 0 for c in candidates}

    # Official rows are written only after every trustee approves.
    # Closing the ballot box stores candidate_totals_json="{}" as a draft seal.
    # That empty map must not be treated as a finished tally, or trustees and
    # the admin would see no candidate counts after the passwords are verified.
    t_res = await db.execute(select(TallyResult).where(TallyResult.election_id == election.election_id))
    tally = t_res.scalars().first()
    if tally and election.results_published_at and tally.candidate_totals_json:
        try:
            totals = json.loads(tally.candidate_totals_json)
        except json.JSONDecodeError:
            totals = None
        if isinstance(totals, dict) and totals:
            return {
                "total_ballots": tally.total_ballots,
                "results": totals,
                "candidate_results": totals,
                "root_hash": tally.bulletin_board_root_hash,
                "is_official": True,
            }

    # 2. Fetch all cast ballots
    b_res = await db.execute(
        select(Ballot).where(Ballot.election_id == election.election_id).order_by(Ballot.sequence_number)
    )
    ballots = b_res.scalars().all()
    num_ballots = len(ballots)

    if not ballots:
        return {
            "total_ballots": 0,
            "results": default_totals,
            "candidate_results": default_totals,
            "root_hash": compute_genesis_hash(election.election_id),
            "is_official": False,
        }

    head_hash = ballots[-1].block_hash
    num_candidates = len(candidates)
    candidate_ciphertexts = [[] for _ in range(num_candidates)]

    for b in ballots:
        votes_raw = json.loads(b.ciphertexts_json)
        for idx, c_obj in enumerate(votes_raw):
            if idx < num_candidates:
                c1_int = int(c_obj["c1"], 16) if isinstance(c_obj["c1"], str) else int(c_obj["c1"])
                c2_int = int(c_obj["c2"], 16) if isinstance(c_obj["c2"], str) else int(c_obj["c2"])
                candidate_ciphertexts[idx].append(Ciphertext(c1_int, c2_int))

    agg_ciphertexts = []
    for idx in range(num_candidates):
        c_list = candidate_ciphertexts[idx]
        agg_ciphertexts.append(homomorphic_sum(c_list) if c_list else Ciphertext(1, 1))

    # Path A: master key is kept so the admin and unlocked trustees can preview
    # the tally before anyone approves. A failed discrete log falls through to
    # trustee partials instead of hiding the candidate list.
    if election.private_key_x:
        try:
            x_val = int(election.private_key_x, 16)
            computed_totals = {}
            for idx, c in enumerate(candidates):
                c_name = c.get("name", f"Candidate {c.get('id')}")
                agg = agg_ciphertexts[idx]
                c1_x = pow(agg.c1, x_val, P)
                c1_x_inv = pow(c1_x, P - 2, P)
                message = (agg.c2 * c1_x_inv) % P
                votes = solve_discrete_log(message, max_votes=max(num_ballots, 1))
                computed_totals[c_name] = votes

            return {
                "total_ballots": num_ballots,
                "results": computed_totals,
                "candidate_results": computed_totals,
                "root_hash": head_hash,
                "is_official": False,
            }
        except (TypeError, ValueError):
            pass

    # Path B: If trustees have submitted partial decryptions
    t_stmt = select(Trustee).where(Trustee.election_id == election.election_id).order_by(Trustee.position)
    t_res = await db.execute(t_stmt)
    all_trustees = t_res.scalars().all()
    approved_trustees = [t for t in all_trustees if t.partial_decryption_json]
    t_val = election.trustee_threshold or ((len(all_trustees) // 2) + 1)

    if len(approved_trustees) >= t_val:
        participating = approved_trustees[:t_val]
        computed_totals = {}
        for c_idx, c in enumerate(candidates):
            c_name = c.get("name", f"Candidate {c.get('id')}")
            partials_for_c = []
            for t in participating:
                p_data = json.loads(t.partial_decryption_json or "[]")
                d_i_val = None
                if isinstance(p_data, list):
                    for item in p_data:
                        if item.get("candidate_id") == c_idx:
                            f_str = item.get("partial_decryption_factor") or item.get("d_i")
                            if f_str:
                                d_i_val = int(f_str, 16) if isinstance(f_str, str) else int(f_str)
                            break
                elif isinstance(p_data, dict):
                    f_str = p_data.get("partial_decryption_factor") or p_data.get("d_i")
                    if f_str:
                        d_i_val = int(f_str, 16) if isinstance(f_str, str) else int(f_str)
                if d_i_val is not None:
                    partials_for_c.append((t.trustee_id, d_i_val))

            vote_count = threshold_decrypt(partials_for_c, agg_ciphertexts[c_idx], max_votes=num_ballots)
            computed_totals[c_name] = vote_count

        return {
            "total_ballots": num_ballots,
            "results": computed_totals,
            "candidate_results": computed_totals,
            "root_hash": head_hash,
            "is_official": False,
        }

    return {
        "total_ballots": num_ballots,
        "results": default_totals,
        "candidate_results": default_totals,
        "root_hash": head_hash,
        "is_official": False,
    }


async def publish_official_results(election: Election, db: AsyncSession) -> Dict[str, Any]:
    """
    Persist the decrypted tally and mark it public.

    Callers must already have confirmed every trustee approved. Voters read
    this row only after results_published_at is set. Admin and trustee previews
    use get_or_compute_election_tally and do not wait for this step.
    """
    tally_data = await get_or_compute_election_tally(election, db)
    totals = tally_data.get("results") or {}
    total_ballots = int(tally_data.get("total_ballots") or 0)
    root_hash = tally_data.get("root_hash") or "COMPUTED_ROOT"

    await db.execute(delete(TallyResult).where(TallyResult.election_id == election.election_id))
    db.add(
        TallyResult(
            election_id=election.election_id,
            total_ballots=total_ballots,
            candidate_totals_json=json.dumps(totals),
            aggregated_ciphertexts_json="[]",
            trustee_contributions_json="[]",
            bulletin_board_root_hash=root_hash,
            tallied_at=datetime.utcnow(),
        )
    )
    election.status = "COMPLETED"
    published_at = election.results_published_at or datetime.utcnow()
    election.results_published_at = published_at
    election_id = election.election_id
    await db.commit()

    return {
        "status": "SUCCESS",
        "election_id": election_id,
        "total_ballots": total_ballots,
        "results": totals,
        "published_at": published_at.isoformat(),
        "message": "Election results verified by every trustee and published to voters.",
    }
