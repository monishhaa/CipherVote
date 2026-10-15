import time
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete
from app.main import app
from app.models.database import AsyncSessionLocal, init_db
from app.models.entities import Ballot, TallyResult, Voter, LoginAuditLog

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    await init_db()


ADMIN_HEADERS = {"Authorization": "Bearer admin_session_valid_2026"}

async def create_test_election(client: AsyncClient, election_id: str):
    payload = {
        "election_id": election_id,
        "title": "Student Council 2026",
        "candidates": [
            {"id": 0, "name": "Alice Candidate"},
            {"id": 1, "name": "Bob Candidate"},
            {"id": 2, "name": "Charlie Candidate"},
        ],
        "open_time": int(time.time()) + 3600,
        "close_time": int(time.time()) + 7200,
    }
    await client.post("/api/election/setup", json=payload, headers=ADMIN_HEADERS)

@pytest.mark.asyncio
async def test_register_voter_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        election_id = f"test-el-{int(time.time() * 1000)}"
        await create_test_election(ac, election_id)

        # Register fresh voter
        reg_payload = {
            "voter_id": "test-voter-001",
            "full_name": "Test User",
            "email": "test001@university.edu",
            "face_embedding": [0.05] * 128
        }
        res = await ac.post(f"/api/voters/register?election_id={election_id}", json=reg_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["voter_id"] == "test-voter-001"
        assert "share_a" in data
        assert "commitment" in data
        assert "Registration successful" in data["message"]


@pytest.mark.asyncio
async def test_duplicate_voter_id_case_and_whitespace():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        election_id = f"test-el-{int(time.time() * 1000)}"
        await create_test_election(ac, election_id)

        # Register initial voter
        reg_payload = {
            "voter_id": "alice-smith",
            "full_name": "Alice Smith",
            "email": "alice@university.edu",
            "face_embedding": [0.01] * 128
        }
        res1 = await ac.post(f"/api/voters/register?election_id={election_id}", json=reg_payload)
        assert res1.status_code == 200

        # Attempt duplicate with uppercase & whitespace in voter_id
        dup_payload = {
            "voter_id": "   ALICE-SMITH   ",
            "full_name": "Alice Another",
            "email": "different_alice@university.edu",
            "face_embedding": [0.02] * 128
        }
        res2 = await ac.post(f"/api/voters/register?election_id={election_id}", json=dup_payload)
        assert res2.status_code == 409
        err_data = res2.json()["detail"]
        assert err_data["field"] == "voter_id"
        assert err_data["code"] == "DUPLICATE_VOTER_ID"
        assert "already registered" in err_data["message"]

@pytest.mark.asyncio
async def test_duplicate_email_case_and_whitespace():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        election_id = f"test-el-{int(time.time() * 1000)}"
        await create_test_election(ac, election_id)

        # Register initial voter
        reg_payload = {
            "voter_id": "bob-jones",
            "full_name": "Bob Jones",
            "email": "bob.jones@university.edu",
            "face_embedding": [0.01] * 128
        }
        res1 = await ac.post(f"/api/voters/register?election_id={election_id}", json=reg_payload)
        assert res1.status_code == 200

        # Attempt duplicate with uppercase & whitespace in email
        dup_payload = {
            "voter_id": "bob-jones-2",
            "full_name": "Bob Jones 2",
            "email": "  BOB.JONES@UNIVERSITY.EDU  ",
            "face_embedding": [0.02] * 128
        }
        res2 = await ac.post(f"/api/voters/register?election_id={election_id}", json=dup_payload)
        assert res2.status_code == 409
        err_data = res2.json()["detail"]
        assert err_data["field"] == "email"
        assert err_data["code"] == "DUPLICATE_EMAIL"
        assert "already registered" in err_data["message"]

@pytest.mark.asyncio
async def test_registration_blocked_when_election_not_in_registration_phase():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        election_id = f"test-el-{int(time.time() * 1000)}"
        await create_test_election(ac, election_id)

        # Warp election to OPEN
        warp_res = await ac.post(
            f"/api/election/clock/warp?election_id={election_id}",
            json={"target_status": "OPEN"},
            headers=ADMIN_HEADERS,
        )
        assert warp_res.status_code == 200

        # Try to register
        reg_payload = {
            "voter_id": "late-voter",
            "full_name": "Late Voter",
            "email": "late@university.edu",
            "face_embedding": [0.01] * 128
        }
        res = await ac.post(f"/api/voters/register?election_id={election_id}", json=reg_payload)
        assert res.status_code == 400
        detail = res.json()["detail"]
        assert "Registration is closed" in detail["message"]

@pytest.mark.asyncio
async def test_reset_demo_data_allows_reregistration():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        election_id = f"test-el-{int(time.time() * 1000)}"
        await create_test_election(ac, election_id)

        # 0. Initial Reset
        reset_res0 = await ac.post(f"/api/election/reset?election_id={election_id}", headers=ADMIN_HEADERS)
        assert reset_res0.status_code == 200

        # 1. Register voter-priya
        reg_payload = {
            "voter_id": "voter-priya",
            "full_name": "Priya Sharma",
            "email": "priya.sharma@university.edu",
            "face_embedding": [0.03] * 128
        }
        res1 = await ac.post(f"/api/voters/register?election_id={election_id}", json=reg_payload)
        assert res1.status_code == 200

        # 2. Reset election
        reset_res = await ac.post(f"/api/election/reset?election_id={election_id}", headers=ADMIN_HEADERS)
        assert reset_res.status_code == 200

        # 3. Re-register voter-priya successfully
        res2 = await ac.post(f"/api/voters/register?election_id={election_id}", json=reg_payload)
        assert res2.status_code == 200
        assert res2.json()["voter_id"] == "voter-priya"

@pytest.mark.asyncio
async def test_lfw_sample_voters_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/voters/lfw-samples?count=3")
        assert res.status_code == 200
        samples = res.json()["samples"]
        assert len(samples) > 0
        first = samples[0]
        assert "sample_id" in first
        assert "full_name" in first
        assert "email" in first
        assert "embedding" in first
        assert len(first["embedding"]) == 128

@pytest.mark.asyncio
async def test_process_face_valid_and_invalid():
    import base64
    import os

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Test with valid LFW face image
        sample_path = "data/lfw/lfw-deepfunneled/lfw-deepfunneled/Aaron_Peirsol/Aaron_Peirsol_0001.jpg"
        if os.path.exists(sample_path):
            with open(sample_path, "rb") as f:
                b64_str = base64.b64encode(f.read()).decode("utf-8")

            res = await ac.post("/api/voters/process-face", json={"image_base64": f"data:image/jpeg;base64,{b64_str}"})
            assert res.status_code == 200
            data = res.json()
            assert data["face_count"] == 1
            assert len(data["embedding"]) == 128

        # 2. Test with empty / blank black image (no face)
        blank_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 200 # invalid / blank
        res_blank = await ac.post("/api/voters/process-face", json={"image_base64": base64.b64encode(blank_bytes).decode("utf-8")})
        assert res_blank.status_code == 400
        detail = res_blank.json()["detail"]
        assert detail["code"] in ["NO_FACE_DETECTED", "INVALID_IMAGE_PAYLOAD"]
