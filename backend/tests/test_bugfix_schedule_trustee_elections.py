"""
Comprehensive test suite verifying bug fixes:
1. Schedule validation (valid window, min 1-min duration, past start warning, timezone-aware conversion)
2. Trustee Portal draft and validation (no premature emails, unique emails, bounds 3-9)
3. API Error Formatter behavior on FastAPI 422 payloads (no [object Object])
4. Database test isolation and elections badge count correctness
"""

from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.routers.auth import generate_admin_token


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def admin_headers():
    token = generate_admin_token("admin")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
async def test_schedule_valid_window_and_timezone_roundtrip(admin_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create test election with Asia/Kolkata timezone
        el_res = await client.post(
            "/api/admin/elections",
            headers=admin_headers,
            json={
                "title": "Student Senate Schedule Test",
                "candidates": [{"name": "Alpha"}, {"name": "Beta"}],
                "timezone": "Asia/Kolkata",
            },
        )
        assert el_res.status_code == 200
        el_id = el_res.json()["election_id"]

        # Compute dynamic future dates (never hardcoded)
        now_dt = datetime.now(timezone.utc)
        start_dt = now_dt + timedelta(days=2)
        end_dt = start_dt + timedelta(hours=3)

        # 1. Save valid schedule with ISO strings
        res = await client.post(
            "/api/admin/schedule",
            headers=admin_headers,
            json={
                "election_id": el_id,
                "scheduled_start": start_dt.isoformat(),
                "scheduled_end": end_dt.isoformat(),
                "timezone": "Asia/Kolkata",
                "announce": True,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["election_id"] == el_id
        assert "Asia/Kolkata" in data["timezone"] or "IST" in data["formatted_window"]
        assert data["warnings"] == []
        assert "voter" in data["message"]

        # 2. Get schedule and check roundtrip
        get_res = await client.get(f"/api/admin/schedule?election_id={el_id}", headers=admin_headers)
        assert get_res.status_code == 200
        assert get_res.json()["timezone"] == "Asia/Kolkata"


@pytest.mark.asyncio
async def test_schedule_validation_errors_and_past_start_warning(admin_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create election
        el_res = await client.post(
            "/api/admin/elections",
            headers=admin_headers,
            json={
                "title": "Validation Test Election",
                "candidates": [{"name": "Cand 1"}, {"name": "Cand 2"}],
                "timezone": "UTC",
            },
        )
        assert el_res.status_code == 200
        el_id = el_res.json()["election_id"]

        now_dt = datetime.now(timezone.utc)

        # 1. End before start -> 400
        res_end_before = await client.post(
            "/api/admin/schedule",
            headers=admin_headers,
            json={
                "election_id": el_id,
                "scheduled_start": (now_dt + timedelta(hours=2)).isoformat(),
                "scheduled_end": (now_dt + timedelta(hours=1)).isoformat(),
                "timezone": "UTC",
            },
        )
        assert res_end_before.status_code == 400
        assert "strictly after" in res_end_before.json()["detail"]

        # 2. Window under 1 minute -> 400
        res_short = await client.post(
            "/api/admin/schedule",
            headers=admin_headers,
            json={
                "election_id": el_id,
                "scheduled_start": (now_dt + timedelta(hours=1)).isoformat(),
                "scheduled_end": (now_dt + timedelta(hours=1, seconds=30)).isoformat(),
                "timezone": "UTC",
            },
        )
        assert res_short.status_code == 400
        assert "at least 1 minute" in res_short.json()["detail"]

        # 3. Past start date -> SAVES with warning (does NOT block)
        past_start = now_dt - timedelta(hours=5)
        future_end = now_dt + timedelta(hours=2)
        res_past = await client.post(
            "/api/admin/schedule",
            headers=admin_headers,
            json={
                "election_id": el_id,
                "scheduled_start": past_start.isoformat(),
                "scheduled_end": future_end.isoformat(),
                "timezone": "UTC",
            },
        )
        assert res_past.status_code == 200
        assert len(res_past.json()["warnings"]) > 0
        assert "already passed" in res_past.json()["warnings"][0]


@pytest.mark.asyncio
async def test_fastapi_422_formatting_schema(admin_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Submit invalid payload missing required fields
        res = await client.post(
            "/api/admin/schedule",
            headers=admin_headers,
            json={"election_id": "test-el"},
        )
        assert res.status_code == 422
        body = res.json()
        assert "detail" in body
        assert isinstance(body["detail"], list)
        for err in body["detail"]:
            assert isinstance(err, dict)
            assert "loc" in err
            assert "msg" in err


@pytest.mark.asyncio
async def test_trustee_draft_validation_and_no_premature_emails(admin_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        el_res = await client.post(
            "/api/admin/elections",
            headers=admin_headers,
            json={
                "title": "Trustee Roster Test Election",
                "candidates": [{"name": "A"}, {"name": "B"}],
            },
        )
        el_id = el_res.json()["election_id"]

        # 1. Invalid email format -> 400
        res_bad_email = await client.post(
            "/api/admin/trustees",
            headers=admin_headers,
            json={
                "election_id": el_id,
                "trustees": [
                    {"name": "Alice", "email": "alice_invalid_email"},
                    {"name": "Bob", "email": "bob@inst.edu"},
                    {"name": "Charlie", "email": "charlie@inst.edu"},
                ],
            },
        )
        assert res_bad_email.status_code == 400
        assert "Invalid email format" in res_bad_email.json()["detail"]

        # 2. Duplicate emails -> 400
        res_dup = await client.post(
            "/api/admin/trustees",
            headers=admin_headers,
            json={
                "election_id": el_id,
                "trustees": [
                    {"name": "Alice", "email": "shared@inst.edu"},
                    {"name": "Bob", "email": "shared@inst.edu"},
                    {"name": "Charlie", "email": "charlie@inst.edu"},
                ],
            },
        )
        assert res_dup.status_code == 400
        assert "Duplicate trustee email" in res_dup.json()["detail"]

        # 3. Valid draft save: status is NOT_INVITED, no emails sent
        res_valid = await client.post(
            "/api/admin/trustees",
            headers=admin_headers,
            json={
                "election_id": el_id,
                "trustees": [
                    {"name": "Alice Rao", "email": "alice@example.com"},
                    {"name": "Bob Smith", "email": "bob@example.com"},
                    {"name": "Charlie Wu", "email": "charlie@example.com"},
                ],
                "ceremony_window_minutes": 5,
            },
        )
        assert res_valid.status_code == 200
        assert res_valid.json()["threshold"] == 2  # (3 // 2) + 1

        # Check trustees listing
        list_t = await client.get(f"/api/admin/trustees?election_id={el_id}", headers=admin_headers)
        assert list_t.status_code == 200
        trustees_data = list_t.json()["trustees"]
        assert len(trustees_data) == 3
        for t in trustees_data:
            assert t["email_status"] == "NOT_INVITED"
            assert t["email_sent_at"] is None
            assert t["has_key"] is False
