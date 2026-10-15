"""
Comprehensive Test Suite for Admin-Controlled Voting Schedule, In-Site Notifications, Email Outbox, and Role Access Security.
"""

from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models.database import AsyncSessionLocal, init_db
from app.models.entities import Election, EmailOutbox, Notification, Voter
from app.routers.auth import generate_admin_token


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_environment():
    await init_db()


ADMIN_AUTH = {"Authorization": f"Bearer {generate_admin_token('admin')}"}


@pytest.mark.asyncio
async def test_admin_authentication_and_unauthorized_access():
    """Verify that admin mutation endpoints return 401 Unauthorized when unauthenticated."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated schedule mutation
        r1 = await client.post("/api/election/schedule", json={})
        assert r1.status_code == 401

        # 2. Unauthenticated open-voting / close-voting
        r2 = await client.post("/api/election/open-voting?election_id=council-2026")
        assert r2.status_code == 401

        r3 = await client.post("/api/election/close-voting?election_id=council-2026")
        assert r3.status_code == 401

        # 3. Unauthenticated admin notifications audit
        r4 = await client.get("/api/election/admin/notifications")
        assert r4.status_code == 401

        # 4. Admin login with valid credentials
        login_res = await client.post(
            "/api/auth/admin-login",
            json={"username": "admin", "password": "admin2026"},
        )
        assert login_res.status_code == 200
        data = login_res.json()
        assert data["success"] is True
        assert data["token"].startswith(("securevote_admin_", "ciphervote_admin_"))


        # 5. Admin login with invalid credentials
        bad_login = await client.post(
            "/api/auth/admin-login",
            json={"username": "admin", "password": "wrongpassword"},
        )
        assert bad_login.status_code == 401

        # 6. Role separation: Voter session on /api/admin/* is rejected with 401/403
        from app.core.security import generate_voter_session_token
        voter_auth = {"Authorization": f"Bearer {generate_voter_session_token('voter-test', 'voter@test.com')}"}
        r_voter_on_admin = await client.get("/api/admin/overview", headers=voter_auth)
        assert r_voter_on_admin.status_code in (401, 403)

        # 7. Role separation: Admin session on /api/voter/me is rejected with 401/403
        r_admin_on_voter = await client.get("/api/voter/me", headers=ADMIN_AUTH)
        assert r_admin_on_voter.status_code in (401, 403)

        # 8. Public portal endpoints require no authentication
        r_pub_status = await client.get("/api/public/status?election_id=council-2026")
        assert r_pub_status.status_code == 200

        r_pub_bb = await client.get("/api/public/bulletin-board?election_id=council-2026")
        assert r_pub_bb.status_code == 200

        r_pub_verify = await client.get("/api/public/bulletin-board/verify?election_id=council-2026")
        assert r_pub_verify.status_code == 200



@pytest.mark.asyncio
async def test_schedule_setting_validation_and_locking():
    """Verify dynamic schedule setting, validation (end > start), and edit lock once OPEN."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        election_id = f"sched-el-{ts}"

        # 1. Create Election via setup
        setup_payload = {
            "election_id": election_id,
            "title": "Faculty Senate Election",
            "candidates": [
                {"id": 0, "name": "Candidate One"},
                {"id": 1, "name": "Candidate Two"},
            ],
            "open_time": int(datetime.now(timezone.utc).timestamp()) + 3600,
            "close_time": int(datetime.now(timezone.utc).timestamp()) + 7200,
        }
        res_setup = await client.post("/api/election/setup", json=setup_payload, headers=ADMIN_AUTH)
        assert res_setup.status_code == 200

        # 2. Invalid schedule: end before start -> 400
        now = datetime.now(timezone.utc)
        bad_sched = {
            "election_id": election_id,
            "scheduled_start": (now + timedelta(days=2)).isoformat(),
            "scheduled_end": (now + timedelta(days=1)).isoformat(),
            "timezone": "Asia/Kolkata",
            "announce": True,
        }
        res_bad = await client.post("/api/election/schedule", json=bad_sched, headers=ADMIN_AUTH)
        assert res_bad.status_code == 400

        # 3. Valid schedule: start in future, end after start
        valid_start = now + timedelta(days=3)
        valid_end = now + timedelta(days=5)
        good_sched = {
            "election_id": election_id,
            "scheduled_start": valid_start.isoformat(),
            "scheduled_end": valid_end.isoformat(),
            "timezone": "Asia/Kolkata",
            "announce": True,
        }
        res_good = await client.post("/api/election/schedule", json=good_sched, headers=ADMIN_AUTH)
        assert res_good.status_code == 200
        data = res_good.json()
        assert data["timezone"] == "Asia/Kolkata"
        assert "IST" in data["formatted_window"]

        # 4. Open election and verify schedule becomes locked
        open_res = await client.post(f"/api/election/open-voting?election_id={election_id}", headers=ADMIN_AUTH)
        assert open_res.status_code == 200

        # Attempt to edit schedule while election is OPEN -> 400
        edit_locked = await client.post("/api/election/schedule", json=good_sched, headers=ADMIN_AUTH)
        assert edit_locked.status_code == 400
        assert "Cannot edit schedule" in edit_locked.json()["detail"]


@pytest.mark.asyncio
async def test_registration_notifications_and_zero_secrets():
    """Verify that voter registration triggers in-site notifications and email, with zero cryptographic secrets in communications."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        election_id = f"notif-el-{ts}"

        # 1. Setup election with active schedule
        now = datetime.now(timezone.utc)
        setup_payload = {
            "election_id": election_id,
            "title": "Department Council Election",
            "candidates": [{"id": 0, "name": "Candidate Alpha"}],
            "open_time": int(now.timestamp()) + 3600,
            "close_time": int(now.timestamp()) + 7200,
        }
        await client.post("/api/election/setup", json=setup_payload, headers=ADMIN_AUTH)

        sched_payload = {
            "election_id": election_id,
            "scheduled_start": (now + timedelta(days=1)).isoformat(),
            "scheduled_end": (now + timedelta(days=2)).isoformat(),
            "timezone": "UTC",
            "announce": True,
        }
        await client.post("/api/election/schedule", json=sched_payload, headers=ADMIN_AUTH)

        # 2. Register voter
        voter_id = f"voter-sec-{ts}"
        voter_email = f"voter-{ts}@institute.edu"
        reg_payload = {
            "voter_id": voter_id,
            "full_name": "Marcus Security Test",
            "email": voter_email,
            "face_embedding": [0.02 * i for i in range(128)],
        }
        res_reg = await client.post(f"/api/voters/register?election_id={election_id}", json=reg_payload)
        assert res_reg.status_code == 200
        reg_json = res_reg.json()
        share_a_val = reg_json["share_a"]

        # 3. Check in-site notifications for voter
        notif_res = await client.get(f"/api/voters/notifications?voter_id={voter_id}&election_id={election_id}")
        assert notif_res.status_code == 200
        notifs = notif_res.json()["notifications"]
        assert len(notifs) >= 1
        reg_notif = notifs[0]
        assert "Registration Confirmed" in reg_notif["title"]
        assert reg_notif["read_at"] is None

        # Mark read
        mark_res = await client.post(
            "/api/voters/notifications/mark-read",
            json={"voter_id": voter_id, "notification_ids": [reg_notif["id"]]},
        )
        assert mark_res.status_code == 200

        # Verify read status updated
        notif_res2 = await client.get(f"/api/voters/notifications?voter_id={voter_id}&election_id={election_id}")
        assert notif_res2.json()["unread_count"] == 0

        # 4. Check outbox records in DB and verify ZERO SECRETS
        async with AsyncSessionLocal() as session:
            out_res = await session.execute(
                select(EmailOutbox).where(EmailOutbox.to_email == voter_email)
            )
            outbox_entries = out_res.scalars().all()
            assert len(outbox_entries) >= 1

            for entry in outbox_entries:
                body = entry.body_text + " " + entry.body_html
                # CRITICAL SECURITY CHECK: No Share A or Share B in emails
                assert share_a_val not in body, "SECURITY VIOLATION: Share A leaked in email body!"
                assert "share_b" not in body.lower()
                assert "private_key" not in body.lower()
                # Verify branding
                assert "SecureVote" in body



@pytest.mark.asyncio
async def test_admin_open_close_flow_and_ballot_enforcement():
    """Verify admin Open Voting action unlocks Share B and Close Voting blocks subsequent ballots."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        election_id = f"flow-el-{ts}"

        # 1. Setup election
        setup_payload = {
            "election_id": election_id,
            "title": "Board of Governors Election",
            "candidates": [
                {"id": 0, "name": "Candidate A"},
                {"id": 1, "name": "Candidate B"},
            ],
            "open_time": int(datetime.now(timezone.utc).timestamp()) + 3600,
            "close_time": int(datetime.now(timezone.utc).timestamp()) + 7200,
        }
        await client.post("/api/election/setup", json=setup_payload, headers=ADMIN_AUTH)

        # 2. Register voter
        voter_id = f"voter-flow-{ts}"
        reg_payload = {
            "voter_id": voter_id,
            "full_name": "Elena Flow Test",
            "email": f"elena-{ts}@institute.edu",
            "face_embedding": [0.04 * i for i in range(128)],
        }
        await client.post(f"/api/voters/register?election_id={election_id}", json=reg_payload)

        # 3. Time-lock check: Share B is 403 Forbidden while election status is REGISTRATION
        sb_res1 = await client.get(f"/api/voters/share_b/{voter_id}?election_id={election_id}")
        assert sb_res1.status_code == 403

        # 4. Admin clicks "Open voting"
        open_res = await client.post(f"/api/election/open-voting?election_id={election_id}", headers=ADMIN_AUTH)
        assert open_res.status_code == 200
        assert open_res.json()["status"] == "OPEN"

        # 5. Share B is now unlocked
        sb_res2 = await client.get(f"/api/voters/share_b/{voter_id}?election_id={election_id}")
        assert sb_res2.status_code == 200
        assert "share_b" in sb_res2.json()

        # 6. Admin clicks "Close voting and begin tally"
        close_res = await client.post(f"/api/election/close-voting?election_id={election_id}", headers=ADMIN_AUTH)
        assert close_res.status_code == 200
        assert close_res.json()["status"] in ("CLOSED", "TALLYING")

        # 7. Attempt to cast ballot when TALLYING -> 403 Forbidden
        fake_ballot = {
            "election_id": election_id,
            "ciphertexts": [{"c1": "0x123", "c2": "0x456"}],
            "zkp_proofs": {
                "disjunctive_proofs": [
                    {"a0": "0x1", "b0": "0x2", "a1": "0x3", "b1": "0x4", "c0": "0x5", "c1": "0x6", "z0": "0x7", "z1": "0x8"}
                ],
                "sum_proof": {"a": "0x1", "b": "0x2", "c": "0x3", "z": "0x4"},
            },
            "token_nonce": "nonce_test",
            "token_signature": "0x1234",
        }
        cast_res = await client.post("/api/ballots/cast", json=fake_ballot)
        assert cast_res.status_code == 403
        assert "Election is not open for voting" in cast_res.json()["detail"]



@pytest.mark.asyncio
async def test_admin_notifications_outbox_audit_and_retry():
    """Verify admin notifications outbox table and retry failed endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/election/admin/notifications", headers=ADMIN_AUTH)
        assert res.status_code == 200
        data = res.json()
        assert "outbox" in data
        assert "total_sent" in data
        assert "total_notifications" in data

        # Retry endpoint
        retry_res = await client.post("/api/election/admin/notifications/retry", headers=ADMIN_AUTH)
        assert retry_res.status_code == 200
        assert "retried_count" in retry_res.json()
