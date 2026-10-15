"""
SecureVote CLI & Database Reset Tool
Usage:
    python -m app.cli reset-all
    python -m app.cli reset-demo
"""

import asyncio
import sys
from sqlalchemy import delete
from app.models.database import AsyncSessionLocal, init_db
from app.models.entities import Election, Trustee, Voter, Ballot, Notification, EmailOutbox, TallyResult


async def reset_database(clear_elections: bool = False):
    await init_db()
    async with AsyncSessionLocal() as session:
        print("[SecureVote] Resetting database tables...")
        await session.execute(delete(Voter))
        await session.execute(delete(Ballot))
        await session.execute(delete(Notification))
        await session.execute(delete(EmailOutbox))
        await session.execute(delete(TallyResult))
        await session.execute(delete(Trustee))
        if clear_elections:
            await session.execute(delete(Election))
            print("[SecureVote] All elections, trustees, voters, and ballots purged.")
        else:
            print("[SecureVote] All voters, ballots, outbox rows, and trustees purged. Elections preserved in clean REGISTRATION state.")
        await session.commit()
    print("[SecureVote] Clean state achieved.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset-all":
        asyncio.run(reset_database(clear_elections=True))
    else:
        asyncio.run(reset_database(clear_elections=False))
