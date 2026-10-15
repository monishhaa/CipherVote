"""
Pytest Suite for Create Election Page, Elections Switcher, and Trustee Portal Cleanup.
"""

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
async def test_create_election_validation_and_lifecycle(admin_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Missing title -> 400
        res = await client.post(
            "/api/admin/elections",
            headers=admin_headers,
            json={"title": "", "candidates": [{"name": "Alice"}, {"name": "Bob"}]},
        )
        assert res.status_code == 422 or res.status_code == 400

        # 2. Duplicate candidates -> 400
        res = await client.post(
            "/api/admin/elections",
            headers=admin_headers,
            json={
                "title": "2026 Student Union",
                "candidates": [{"name": "Alice"}, {"name": "alice"}],
            },
        )
        assert res.status_code == 400
        assert "Duplicate candidate name" in res.json()["detail"]

        # 3. Less than 2 candidates -> 422 or 400
        res = await client.post(
            "/api/admin/elections",
            headers=admin_headers,
            json={
                "title": "2026 Student Union",
                "candidates": [{"name": "Alice"}],
            },
        )
        assert res.status_code in (400, 422)

        # 4. Valid creation
        res = await client.post(
            "/api/admin/elections",
            headers=admin_headers,
            json={
                "title": "Faculty Senate 2026",
                "candidates": [{"name": "Prof. Smith"}, {"name": "Prof. Davis"}],
                "timezone": "Asia/Kolkata",
            },
        )
        assert res.status_code == 200
        el_id = res.json()["election_id"]
        assert "faculty-senate-2026" in el_id

        # 5. List elections
        res_list = await client.get("/api/admin/elections", headers=admin_headers)
        assert res_list.status_code == 200
        assert any(e["election_id"] == el_id for e in res_list.json()["elections"])

        # 6. Trustee roster starts EMPTY for new election
        res_t = await client.get(f"/api/admin/trustees?election_id={el_id}", headers=admin_headers)
        assert res_t.status_code == 200
        assert len(res_t.json()["trustees"]) == 0
        assert res_t.json()["is_roster_locked"] is False

        # 7. Draft save does NOT mark as invited or lock roster
        res_save = await client.post(
            "/api/admin/trustees",
            headers=admin_headers,
            json={
                "election_id": el_id,
                "trustees": [
                    {"name": "Trustee 1", "email": "t1@inst.edu"},
                    {"name": "Trustee 2", "email": "t2@inst.edu"},
                    {"name": "Trustee 3", "email": "t3@inst.edu"},
                ],
            },
        )
        assert res_save.status_code == 200
        res_t2 = await client.get(f"/api/admin/trustees?election_id={el_id}", headers=admin_headers)
        assert res_t2.json()["trustees"][0]["email_status"] == "NOT_INVITED"
        assert res_t2.json()["is_roster_locked"] is False
