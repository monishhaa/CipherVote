"""
CLI Script to Reset SecureVote Demo Data.
Clears voters, shares, tokens, ballots, and logs, returning the election to REGISTRATION.
"""

import asyncio
import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from sqlalchemy import delete, select
from app.models import Ballot, Election, LoginAuditLog, TallyResult, Voter
from app.models.database import AsyncSessionLocal, init_db


async def reset_demo_data(election_id: str = "council-2026"):
    await init_db()
    async with AsyncSessionLocal() as db:
        print(f"[*] Resetting demo database for election '{election_id}'...")
        await db.execute(delete(Ballot).where(Ballot.election_id == election_id))
        await db.execute(delete(TallyResult).where(TallyResult.election_id == election_id))
        await db.execute(delete(Voter))
        await db.execute(delete(LoginAuditLog))

        el_res = await db.execute(select(Election).where(Election.election_id == election_id))
        election = el_res.scalars().first()
        if election:
            election.status = "REGISTRATION"
            election.simulated_clock_offset = 0

        await db.commit()
        print("[+] SUCCESS: Cleared all voters, shares, ballots, and logs. Election status reset to 'REGISTRATION'.")


if __name__ == "__main__":
    asyncio.run(reset_demo_data())
