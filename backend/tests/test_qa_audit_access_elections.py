"""Regression tests for access guards and per-election isolation."""

import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.config import settings
from app.core.bulletin_board.hash_chain import compute_genesis_hash
from app.core.security import generate_voter_session_token
from app.main import app
from app.models import AsyncSessionLocal, Election, Voter
from app.routers.auth import generate_admin_token


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _admin_headers():
    token = generate_admin_token(settings.ADMIN_USERNAME.strip() or "admin")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _payload(title: str):
    return {
        "title": title,
        "description": f"Notes for {title}",
        "candidates": [{"name": f"{title} option A"}, {"name": f"{title} option B"}],
        "timezone": "UTC",
    }


def test_suite_refuses_dev_database():
    url = settings.DATABASE_URL
    assert "test_securevote.db" in url or "memory" in url
    assert not url.endswith("/securevote.db")
    assert not url.endswith("\\securevote.db")


@pytest.mark.asyncio
async def test_role_guards_and_hashed_admin_login():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        voter_token = generate_voter_session_token(f"v{int(time.time())}", "qa@example.com")
        voter_on_admin = await client.get(
            "/api/admin/elections",
            headers={"Authorization": f"Bearer {voter_token}"},
        )
        assert voter_on_admin.status_code == 403

        admin_token = generate_admin_token("admin")
        admin_on_voter = await client.get(
            "/api/voter/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert admin_on_voter.status_code in (401, 403)

        missing = await client.get("/api/admin/elections")
        assert missing.status_code == 401

        bad = await client.post(
            "/api/admin/login",
            json={"username": settings.ADMIN_USERNAME, "password": f"wrong-{time.time()}"},
        )
        assert bad.status_code == 401

        good = await client.post(
            "/api/admin/login",
            json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        )
        assert good.status_code == 200
        body = good.json()
        assert body["token"]
        assert settings.ADMIN_PASSWORD not in body["token"]


@pytest.mark.asyncio
async def test_election_edit_archive_delete_and_isolation():
    stamp = int(time.time() * 1000)
    title_a = f"QA election {stamp}"
    title_b = f"QA election {stamp + 1}"
    headers = _admin_headers()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created_a = await client.post("/api/admin/elections", headers=headers, json=_payload(title_a))
        created_b = await client.post("/api/admin/elections", headers=headers, json=_payload(title_b))
        assert created_a.status_code == 200, created_a.text
        assert created_b.status_code == 200, created_b.text
        id_a = created_a.json()["election_id"]
        id_b = created_b.json()["election_id"]
        assert id_a != id_b

        edited = await client.put(
            f"/api/admin/elections/{id_a}",
            headers=headers,
            json={
                "title": f"{title_a} revised",
                "description": "revised notes",
                "candidates": [{"name": f"{title_a} left"}, {"name": f"{title_a} right"}],
                "timezone": "Asia/Kolkata",
            },
        )
        assert edited.status_code == 200, edited.text

        listed = await client.get("/api/admin/elections", headers=headers)
        assert listed.status_code == 200
        row_a = next(item for item in listed.json()["elections"] if item["election_id"] == id_a)
        row_b = next(item for item in listed.json()["elections"] if item["election_id"] == id_b)
        assert row_a["registered_voters"] == 0
        assert row_b["registered_voters"] == 0
        assert row_a["description"] == "revised notes"

        async with AsyncSessionLocal() as db:
            election_a = (await db.execute(select(Election).where(Election.election_id == id_a))).scalars().first()
            election_b = (await db.execute(select(Election).where(Election.election_id == id_b))).scalars().first()
            assert election_a.blind_rsa_n != election_b.blind_rsa_n
            assert election_a.blind_rsa_d != election_b.blind_rsa_d
            assert compute_genesis_hash(id_a) != compute_genesis_hash(id_b)

            shared_voter_id = f"voter-{stamp}"
            db.add(
                Voter(
                    election_id=id_b,
                    voter_id=shared_voter_id,
                    full_name=f"Roll {stamp}",
                    email=f"roll-{stamp}@example.com",
                    encrypted_face_template="enc",
                    credential_commitment="commit",
                    encrypted_share_b="share",
                )
            )
            await db.commit()

        roll_a = await client.get(f"/api/admin/voters?election_id={id_a}", headers=headers)
        roll_b = await client.get(f"/api/admin/voters?election_id={id_b}", headers=headers)
        assert roll_a.status_code == 200
        assert roll_b.status_code == 200
        assert roll_a.json()["voters"] == [] or len(roll_a.json().get("voters", [])) == 0
        assert len(roll_b.json()["voters"]) == 1

        listed_after = await client.get("/api/admin/elections", headers=headers)
        counts = {item["election_id"]: item["registered_voters"] for item in listed_after.json()["elections"]}
        assert counts[id_a] == 0
        assert counts[id_b] == 1

        removed = await client.delete(f"/api/admin/elections/{id_a}", headers=headers)
        assert removed.status_code == 200, removed.text

        async with AsyncSessionLocal() as db:
            election_b = (await db.execute(select(Election).where(Election.election_id == id_b))).scalars().first()
            election_b.status = "OPEN"
            election_b.actual_open_at = election_b.created_at
            await db.commit()

        locked = await client.put(
            f"/api/admin/elections/{id_b}",
            headers=headers,
            json=_payload(f"{title_b} too late"),
        )
        assert locked.status_code == 400

        archived = await client.post(f"/api/admin/elections/{id_b}/archive", headers=headers)
        assert archived.status_code == 200, archived.text
        public = await client.get("/api/public/elections")
        public_ids = [item["election_id"] for item in public.json()["elections"]]
        assert id_b not in public_ids

        removed_with_voters = await client.delete(f"/api/admin/elections/{id_b}", headers=headers)
        assert removed_with_voters.status_code == 200, removed_with_voters.text
        listed_final = await client.get("/api/admin/elections", headers=headers)
        remaining_ids = [item["election_id"] for item in listed_final.json()["elections"]]
        assert id_b not in remaining_ids
        async with AsyncSessionLocal() as db:
            leftover = (await db.execute(select(Voter).where(Voter.election_id == id_b))).scalars().first()
            assert leftover is None
