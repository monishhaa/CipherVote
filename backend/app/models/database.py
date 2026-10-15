"""
SQLAlchemy Async Database Setup & Migration.
"""

from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30} if "sqlite" in settings.DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all database tables and safely migrate columns if missing."""
    async with engine.begin() as conn:
        if "sqlite" in settings.DATABASE_URL:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
        await conn.run_sync(Base.metadata.create_all)

        # Lightweight schema migration for SQLite
        if "sqlite" in settings.DATABASE_URL:
            try:
                res = await conn.execute(text("PRAGMA table_info(elections)"))
                existing_cols = {row[1] for row in res.fetchall()}
                new_cols = [
                    ("scheduled_start", "DATETIME"),
                    ("scheduled_end", "DATETIME"),
                    ("timezone", "VARCHAR(64) DEFAULT 'UTC'"),
                    ("schedule_published_at", "DATETIME"),
                    ("actual_open_at", "DATETIME"),
                    ("actual_close_at", "DATETIME"),
                    ("trustee_threshold", "INTEGER DEFAULT 3"),
                    ("ceremony_window_minutes", "INTEGER DEFAULT 5"),
                    ("invitations_sent_at", "DATETIME"),
                    ("ceremony_unlocked_at", "DATETIME"),
                    ("results_published_at", "DATETIME"),
                    ("full_passphrase_commitment", "VARCHAR(128)"),
                    ("full_passphrase_salt", "VARCHAR(64)"),
                    ("private_key_x", "TEXT"),
                    ("description", "TEXT"),
                ]
                for col_name, col_type in new_cols:
                    if col_name not in existing_cols:
                        await conn.execute(text(f"ALTER TABLE elections ADD COLUMN {col_name} {col_type}"))

                # Migrate trustees
                res_t = await conn.execute(text("PRAGMA table_info(trustees)"))
                existing_t_cols = {row[1] for row in res_t.fetchall()}
                new_t_cols = [
                    ("email", "VARCHAR(256)"),
                    ("position", "INTEGER DEFAULT 1"),
                    ("link_token_hash", "VARCHAR(128)"),
                    ("code_hash", "VARCHAR(256)"),
                    ("code_salt", "VARCHAR(64)"),
                    ("email_status", "VARCHAR(32) DEFAULT 'PENDING'"),
                    ("email_sent_at", "DATETIME"),
                    ("link_opened_at", "DATETIME"),
                    ("failed_attempts", "INTEGER DEFAULT 0"),
                    ("locked_until", "DATETIME"),
                    ("has_approved", "BOOLEAN DEFAULT 0"),
                    ("approved_at", "DATETIME"),
                    ("partial_decryption_json", "TEXT"),
                ]
                for col_name, col_type in new_t_cols:
                    if col_name not in existing_t_cols:
                        await conn.execute(text(f"ALTER TABLE trustees ADD COLUMN {col_name} {col_type}"))

                # Migrate voters
                res_v = await conn.execute(text("PRAGMA table_info(voters)"))
                existing_v_cols = {row[1] for row in res_v.fetchall()}
                if "password_hash" not in existing_v_cols:
                    await conn.execute(text("ALTER TABLE voters ADD COLUMN password_hash VARCHAR(256)"))
                if "election_id" not in existing_v_cols:
                    await conn.execute(text("ALTER TABLE voters ADD COLUMN election_id VARCHAR(64)"))
                    await conn.execute(text("UPDATE voters SET election_id = 'council-2026' WHERE election_id IS NULL OR election_id = ''"))

                # Migrate voter indexes to per-election scoping
                try:
                    await conn.execute(text("DROP INDEX IF EXISTS ix_voters_voter_id"))
                    await conn.execute(text("DROP INDEX IF EXISTS ix_voters_email"))
                    await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_election_voter ON voters (election_id, voter_id)"))
                    await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_election_email ON voters (election_id, email)"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_voters_voter_id ON voters (voter_id)"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_voters_email ON voters (email)"))
                except Exception as idx_err:
                    print(f"[DB MIGRATION NOTICE] Index migration: {idx_err}")
            except Exception as e:
                print(f"[DB MIGRATION WARNING] SQLite column check: {e}")

