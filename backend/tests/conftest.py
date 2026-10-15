"""
Pytest configuration for backend test suite.
Guarantees strict test database isolation so automated tests NEVER contaminate
the primary development database (securevote.db).
"""

import os
import pytest

# Enforce isolated test database BEFORE app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_securevote.db"
os.environ["SMTP_HOST"] = ""

from app.config import settings
settings.SMTP_HOST = ""
from app.models.database import engine, Base, init_db

# Hard safety guard: abort immediately if DATABASE_URL points to dev database
assert "test_securevote.db" in settings.DATABASE_URL or "memory" in settings.DATABASE_URL, (
    f"FATAL: Test suite attempted to run against dev database: {settings.DATABASE_URL}"
)


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    """Ensure data directories exist and environment is configured for testing."""
    os.makedirs(os.path.join(settings.DATA_DIR, "outbox"), exist_ok=True)
    os.makedirs(os.path.join(settings.DATA_DIR, "emails"), exist_ok=True)
    
    # Initialize the database schema for the test database synchronously or via loop
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())

    # Seed default test election "council-2026"
    from app.models.database import AsyncSessionLocal
    from app.models.entities import Election
    from sqlalchemy import select

    async def seed_test_election():
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Election).where(Election.election_id == "council-2026"))
            if not res.scalars().first():
                el = Election(
                    election_id="council-2026",
                    title="University Student Council Election 2026",
                    status="REGISTRATION",
                    open_time=1791923212,
                    close_time=1791926812,
                    timezone="UTC",
                    public_key_h="0x0",
                    blind_rsa_n="0x615d085d7849c1bbaeda7d438bd9ea08044f2ebc40c7da72778b476d9063bc812848b5617cfce4da467da06efbdda1ae5a1f1c96b7edf607855532e465df3bea2691974e36e2bd20eedd7784171b8273098672b1582b6041123cd9fc1932c7f0be8e2ecd3243f08be10dd5c1d544bab3c628428bd3884eef0c5a7d5175f080ed",
                    blind_rsa_e=65537,
                    blind_rsa_d="0x9f362297b63be631a29c667a2e170a3c51cfa9fced71e2258c969516f52622fa9185541536edd4cd9ab793c1e8db63a85876c7a92edc5195bad2b786059025c793e50726c06d0f745542df50717aede01dee01b90874f4312101ef4e22cd57228c19f112dd7a8d93a186976a623bc23231c660e2696caaa001970ae846ee499",
                    candidates_json='[{"id": 0, "name": "Alice Candidate"}, {"id": 1, "name": "Bob Candidate"}, {"id": 2, "name": "Charlie Candidate"}]',
                    trustee_threshold=2,
                    ceremony_window_minutes=5,
                )
                session.add(el)
                await session.commit()

    loop.run_until_complete(seed_test_election())
    
    yield
    # Cleanup test db file after session if desired
    test_db_path = "test_securevote.db"
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass

