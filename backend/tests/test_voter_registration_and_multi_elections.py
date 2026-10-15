"""
Comprehensive tests for Public Elections Endpoint, Multi-Election Voter Scoping,
and Registration Flow validations.
"""

import time
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.database import init_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    await init_db()


ADMIN_HEADERS = {"Authorization": "Bearer admin_session_valid_2026"}


async def create_test_election(client: AsyncClient, election_id: str, title: str = "Test Election"):
    now_ts = int(time.time())
    payload = {
        "election_id": election_id,
        "title": title,
        "candidates": [
            {"id": 0, "name": "Alice Candidate"},
            {"id": 1, "name": "Bob Candidate"},
        ],
        "open_time": now_ts + 3600,
        "close_time": now_ts + 7200,
    }
    res = await client.post("/api/election/setup", json=payload, headers=ADMIN_HEADERS)
    assert res.status_code == 200, f"Setup failed: {res.text}"
    return res.json()


@pytest.mark.asyncio
async def test_public_elections_endpoint_unauthenticated_and_no_secrets():
    """Verify GET /api/public/elections requires no auth and exposes zero cryptographic secrets."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ts = int(time.time() * 1000)
        el_id = f"pub-test-{ts}"
        await create_test_election(ac, el_id, title="Public Audit Check Election")

        # Call endpoint without any Authorization headers
        res = await ac.get("/api/public/elections")
        assert res.status_code == 200
        data = res.json()
        assert "elections" in data
        assert isinstance(data["elections"], list)

        match = next((e for e in data["elections"] if e["election_id"] == el_id), None)
        assert match is not None
        assert match["title"] == "Public Audit Check Election"
        assert match["status"] == "REGISTRATION"
        assert match["registration_open"] is True
        assert match["closed_reason"] is None
        assert "scheduled_window" in match

        # Strict security audit: ensure no private secrets are exposed
        for el in data["elections"]:
            assert "blind_rsa_d" not in el
            assert "private_key" not in el
            assert "trustee_shares" not in el
            assert "passphrase" not in el
            assert "salt" not in el
            assert "code_hash" not in el
            assert "link_token_hash" not in el


@pytest.mark.asyncio
async def test_multi_election_voter_registration_scoping():
    """Verify same Voter ID and email can register in two different elections, but fails within one."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ts = int(time.time() * 1000)
        el1 = f"election-dept-cs-{ts}"
        el2 = f"election-dept-math-{ts}"

        await create_test_election(ac, el1, title="CS Dept Election")
        await create_test_election(ac, el2, title="Math Dept Election")

        voter_id = f"voter-common-{ts}"
        email = f"common-{ts}@university.edu"

        reg_body = {
            "election_id": el1,
            "voter_id": voter_id,
            "full_name": "Elena Common",
            "email": email,
            "password": "Password123!",
            "face_embedding": [0.03] * 128,
        }

        # 1. Register in Election 1 -> Succeeds
        res1 = await ac.post(f"/api/voter/register?election_id={el1}", json=reg_body)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["voter_id"] == voter_id
        assert data1["email"] == email

        # 2. Register same Voter ID and Email in Election 2 -> Succeeds! (Scoped per election)
        reg_body_2 = dict(reg_body)
        reg_body_2["election_id"] = el2
        res2 = await ac.post(f"/api/voter/register?election_id={el2}", json=reg_body_2)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["voter_id"] == voter_id
        assert data2["email"] == email

        # 3. Attempt duplicate registration in Election 1 with same voter_id -> 409 Conflict
        dup_id_body = dict(reg_body)
        dup_id_body["email"] = f"other-{ts}@university.edu"
        res_dup_id = await ac.post(f"/api/voter/register?election_id={el1}", json=dup_id_body)
        assert res_dup_id.status_code == 409
        err1 = res_dup_id.json()["detail"]
        assert err1["code"] == "DUPLICATE_VOTER_ID"
        assert "already registered in this election" in err1["message"]

        # 4. Attempt duplicate registration in Election 1 with same email -> 409 Conflict
        dup_email_body = dict(reg_body)
        dup_email_body["voter_id"] = f"voter-another-{ts}"
        res_dup_email = await ac.post(f"/api/voter/register?election_id={el1}", json=dup_email_body)
        assert res_dup_email.status_code == 409
        err2 = res_dup_email.json()["detail"]
        assert err2["code"] == "DUPLICATE_EMAIL"
        assert "already registered in this election" in err2["message"]


@pytest.mark.asyncio
async def test_register_rejection_for_missing_unknown_and_closed_election():
    """Verify readable error responses for missing, non-existent, or non-registrable elections."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ts = int(time.time() * 1000)
        el_id = f"el-closed-check-{ts}"
        await create_test_election(ac, el_id, title="Closed Check Election")

        reg_body = {
            "voter_id": f"voter-val-{ts}",
            "full_name": "Val User",
            "email": f"val-{ts}@university.edu",
            "password": "Password123!",
            "face_embedding": [0.04] * 128,
        }

        # A) Missing election_id (empty string and no query param)
        res_missing = await ac.post("/api/voter/register", json={**reg_body, "election_id": ""})
        assert res_missing.status_code == 400
        assert "Election ID is required" in res_missing.text

        # B) Non-existent election_id
        res_unknown = await ac.post("/api/voter/register", json={**reg_body, "election_id": "non-existent-election-9999"})
        assert res_unknown.status_code == 404
        assert "not found" in res_unknown.text

        # C) Open election (admin opens voting) -> registration must be rejected with "Voting has started"
        open_res = await ac.post(f"/api/election/clock/warp?election_id={el_id}", json={"target_status": "OPEN"}, headers=ADMIN_HEADERS)
        assert open_res.status_code == 200

        res_open = await ac.post("/api/voter/register", json={**reg_body, "election_id": el_id})
        assert res_open.status_code == 400
        err_open = res_open.json()["detail"]
        assert err_open["error"] == "REGISTRATION_CLOSED"
        assert "Voting has started" in err_open["message"]

        # Check public endpoint reflects closed reason
        pub_res = await ac.get("/api/public/elections")
        assert pub_res.status_code == 200
        el_pub = next(e for e in pub_res.json()["elections"] if e["election_id"] == el_id)
        assert el_pub["registration_open"] is False
        assert el_pub["closed_reason"] == "Voting has started"

        # D) Closed election
        close_res = await ac.post(f"/api/election/clock/warp?election_id={el_id}", json={"target_status": "CLOSED"}, headers=ADMIN_HEADERS)
        assert close_res.status_code == 200

        res_closed = await ac.post("/api/voter/register", json={**reg_body, "election_id": el_id})
        assert res_closed.status_code == 400
        err_closed = res_closed.json()["detail"]
        assert err_closed["error"] == "REGISTRATION_CLOSED"
        assert "Voting has closed" in err_closed["message"]


@pytest.mark.asyncio
async def test_voter_login_and_me_with_election_scoping():
    """Verify voter login and /me endpoint respect election_id scoping."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ts = int(time.time() * 1000)
        el_id = f"el-login-scope-{ts}"
        await create_test_election(ac, el_id, title="Login Scope Election")

        voter_id = f"voter-login-{ts}"
        email = f"voter-login-{ts}@university.edu"
        password = "SecurePassword2026!"

        # Register voter
        reg_res = await ac.post(
            f"/api/voter/register?election_id={el_id}",
            json={
                "election_id": el_id,
                "voter_id": voter_id,
                "full_name": "Login Test Voter",
                "email": email,
                "password": password,
                "face_embedding": [0.05] * 128,
            },
        )
        assert reg_res.status_code == 200

        # Login with voter_id, password, and election_id
        login_res = await ac.post(
            "/api/voter/login",
            json={
                "voter_id": voter_id,
                "password": password,
                "election_id": el_id,
            },
        )
        assert login_res.status_code == 200
        login_data = login_res.json()
        assert login_data["success"] is True
        assert login_data["election_id"] == el_id
        token = login_data["token"]

        # Call /me with voter token
        me_res = await ac.get(
            f"/api/voter/me?election_id={el_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["voter_id"] == voter_id
        assert me_data["election_id"] == el_id
        assert me_data["status_label"] == "Registered"


@pytest.mark.asyncio
async def test_my_elections_endpoint_and_unregistered_forbidden():
    """Verify GET /api/voter/my-elections returns only voter's registered elections and 403 on unregistered."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ts = int(time.time() * 1000)
        el_1 = f"my-el-1-{ts}"
        el_2 = f"my-el-2-{ts}"
        el_unreg = f"my-el-unreg-{ts}"

        await create_test_election(ac, el_1, title="Registered Election 1")
        await create_test_election(ac, el_2, title="Registered Election 2")
        await create_test_election(ac, el_unreg, title="Unregistered Election")

        voter_id = f"voter-my-el-{ts}"
        email = f"voter-my-el-{ts}@university.edu"
        pwd = "SecretPass123!"

        # Register voter for el_1 and el_2
        for el in [el_1, el_2]:
            r = await ac.post(
                f"/api/voter/register?election_id={el}",
                json={
                    "election_id": el,
                    "voter_id": voter_id,
                    "full_name": "Multi Scope Voter",
                    "email": email,
                    "password": pwd,
                    "face_embedding": [0.03] * 128,
                },
            )
            assert r.status_code == 200

        # Login
        login_res = await ac.post(
            "/api/voter/login",
            json={"voter_id": voter_id, "password": pwd},
        )
        assert login_res.status_code == 200
        l_data = login_res.json()
        token = l_data["token"]
        assert "my_elections" in l_data
        returned_ids = l_data["my_elections"]
        assert el_1 in returned_ids
        assert el_2 in returned_ids
        assert el_unreg not in returned_ids

        # Test GET /api/voter/my-elections
        my_res = await ac.get(
            "/api/voter/my-elections",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert my_res.status_code == 200
        my_data = my_res.json()
        assert len(my_data["elections"]) == 2
        my_ids = [e["election_id"] for e in my_data["elections"]]
        assert el_1 in my_ids
        assert el_2 in my_ids
        assert el_unreg not in my_ids

        # Access /api/voter/me for unregistered election -> MUST return 403 Forbidden
        forbidden_res = await ac.get(
            f"/api/voter/me?election_id={el_unreg}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert forbidden_res.status_code == 403


@pytest.mark.asyncio
async def test_no_hardcoded_council_2026_autoseed():
    """Verify that requesting an uninitialized election returns 404 and does not auto-seed council-2026."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/election/status?election_id=nonexistent-election-999")
        assert res.status_code == 404
