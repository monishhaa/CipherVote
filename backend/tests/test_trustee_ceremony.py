"""
Comprehensive Automated Pytest Suite for Task B: Trustee Invitations and All-Trustees Unlock Ceremony.

Tests:
1. Roster validation (minimum 3, unique emails, threshold boundaries).
2. Open voting blocked before invitations are dispatched.
3. Codes never stored in database or logged in outbox records.
4. Each invitation email contains only that trustee's own code.
5. Encrypted shares cannot be decrypted without the correct trustee code.
6. Admin cannot unlock or access secret codes.
7. Correct codes submitted sequentially unlock for N=3 and N=5.
8. One trustee absent -> unlock blocked and console endpoints return 403.
9. Out-of-order submission -> round reset.
10. Wrong code entry -> round reset, and 3 consecutive errors trigger lockout.
11. Window timer expiration -> round reset.
12. Mid-round disconnection -> round reset.
13. Reissue codes invalidates old link tokens and encrypted shares.
14. Governance rule: Election results publication blocked until all N trustees approve.
"""

import asyncio
import json
import re
import secrets
import time
from datetime import datetime, timedelta
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.models import get_db, Election, Trustee, Ballot, EmailOutbox, TallyResult
from app.core.crypto.crockford import (
    generate_trustee_code,
    parse_and_validate_trustee_code,
    normalize_crockford,
)
from app.core.crypto.trustee_security import (
    hash_trustee_code,
    verify_trustee_code,
    encrypt_share_at_rest,
    decrypt_share_at_rest,
    compute_full_passphrase_commitment,
    verify_full_passphrase_commitment,
    hash_link_token,
)
from app.core.ceremony import (
    get_or_create_ceremony,
    get_ceremony_state,
    broadcast_ceremony_state,
)
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
async def test_trustee_roster_validation_and_uniqueness(admin_headers):
    """Verifies that roster requires 3-9 trustees, valid unique emails, and valid threshold."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/admin/reset", headers=admin_headers, json={"election_id": "council-2026"})
        # 1. Less than 3 trustees -> 400
        res = await client.post(
            "/api/admin/trustees",
            headers=admin_headers,
            json={
                "election_id": "council-2026",
                "trustees": [
                    {"name": "Trustee 1", "email": "t1@institution.edu"},
                    {"name": "Trustee 2", "email": "t2@institution.edu"},
                ],
                "threshold": 2,
            },
        )
        assert res.status_code == 400
        assert "between 3 and 9" in res.json()["detail"]

        # 2. Duplicate emails -> 400
        res = await client.post(
            "/api/admin/trustees",
            headers=admin_headers,
            json={
                "election_id": "council-2026",
                "trustees": [
                    {"name": "Trustee 1", "email": "duplicate@institution.edu"},
                    {"name": "Trustee 2", "email": "duplicate@institution.edu"},
                    {"name": "Trustee 3", "email": "t3@institution.edu"},
                ],
                "threshold": 2,
            },
        )
        assert res.status_code == 400
        assert "Duplicate trustee email" in res.json()["detail"]

        # 3. Valid roster of 3 trustees
        res = await client.post(
            "/api/admin/trustees",
            headers=admin_headers,
            json={
                "election_id": "council-2026",
                "trustees": [
                    {"name": "Trustee One", "email": "t1_valid@institution.edu"},
                    {"name": "Trustee Two", "email": "t2_valid@institution.edu"},
                    {"name": "Trustee Three", "email": "t3_valid@institution.edu"},
                ],
                "threshold": 2,
                "ceremony_window_minutes": 5,
            },
        )
        assert res.status_code == 200
        assert res.json()["trustees_count"] == 3
        assert res.json()["threshold"] == 2


@pytest.mark.asyncio
async def test_open_voting_blocked_before_invitations(admin_headers):
    """Verifies that Open Voting is rejected if invitations were not sent."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Reset demo data to clean state
        await client.post("/api/admin/reset", headers=admin_headers, json={"election_id": "council-2026"})

        # Attempt to open voting before invitations
        res = await client.post(
            "/api/admin/voting/open",
            headers=admin_headers,
            json={"election_id": "council-2026"},
        )
        assert res.status_code == 400
        assert "Trustee invitations must be sent" in res.json()["detail"]


@pytest.mark.asyncio
async def test_invitations_code_isolation_and_redaction(admin_headers):
    """
    Verifies that:
    1. Invitations are dispatched to all trustees.
    2. Codes are NEVER stored in DB or outbox logs in plaintext.
    3. Stored outbox row has code redacted as [REDACTED_TRUSTEE_CODE].
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/admin/reset", headers=admin_headers, json={"election_id": "council-2026"})
        # Set up 3 trustees
        await client.post(
            "/api/admin/trustees",
            headers=admin_headers,
            json={
                "election_id": "council-2026",
                "trustees": [
                    {"name": "Trustee Alpha", "email": "alpha@institution.edu"},
                    {"name": "Trustee Beta", "email": "beta@institution.edu"},
                    {"name": "Trustee Gamma", "email": "gamma@institution.edu"},
                ],
                "threshold": 2,
            },
        )

        # Dispatch invitations
        res = await client.post(
            "/api/admin/trustees/invite",
            headers=admin_headers,
            json={"election_id": "council-2026", "portal_base_url": "http://localhost:3000"},
        )
        assert res.status_code == 200
        assert res.json()["trustees_invited"] == 3

        # Verify Outbox stored in DB has code redacted
        async for db in get_db():
            out_res = await db.execute(select(EmailOutbox).where(EmailOutbox.election_id == "council-2026", EmailOutbox.type == "TRUSTEE_INVITATION"))
            trustee_emails = out_res.scalars().all()
            assert len(trustee_emails) == 3
            for mail in trustee_emails:
                assert "[REDACTED_TRUSTEE_CODE]" in mail.body_text
                assert "[REDACTED_TRUSTEE_CODE]" in mail.body_html
                assert not re.search(r"T\d-[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}", mail.body_text)
            break


@pytest.mark.asyncio
async def test_share_at_rest_encryption_and_decryption():
    """Verifies that key shares at rest cannot be decrypted without the exact trustee code."""
    disp_code, raw_code, _ = generate_trustee_code(1)
    share_val = 0xDEADBEEFCAFE123456789ABCDEF0011223344

    encrypted_blob, _ = encrypt_share_at_rest(share_val, raw_code)
    
    # Decrypt with correct code (display or raw format)
    decrypted = decrypt_share_at_rest(encrypted_blob, disp_code)
    assert decrypted == share_val

    # Decrypt with wrong code -> returns None
    wrong_dec = decrypt_share_at_rest(encrypted_blob, "T1-9999-8888-7777-6666-0")
    assert wrong_dec is None


@pytest.mark.asyncio
async def test_ceremony_sequential_unlock_flow_n3(admin_headers):
    """
    Full End-to-End Unlock Ceremony for N=3:
    1. Close voting.
    2. Retrieve link tokens and codes from test fixture.
    3. Connect all 3 trustees (presence established).
    4. Submit codes in order: T1, T2, T3.
    5. Verify ceremony unlocks and validation console endpoints succeed.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Reset and setup 3 trustees
        await client.post("/api/admin/reset", headers=admin_headers, json={"election_id": "council-2026"})
        await client.post(
            "/api/admin/trustees",
            headers=admin_headers,
            json={
                "election_id": "council-2026",
                "trustees": [
                    {"name": "Alice Trustee", "email": "alice_t@institution.edu"},
                    {"name": "Bob Trustee", "email": "bob_t@institution.edu"},
                    {"name": "Charlie Trustee", "email": "charlie_t@institution.edu"},
                ],
                "threshold": 2,
            },
        )
        await client.post("/api/admin/trustees/invite", headers=admin_headers, json={"election_id": "council-2026"})
        
        # Open and Close voting to make ceremony available
        await client.post("/api/admin/voting/open", headers=admin_headers, json={"election_id": "council-2026"})
        await client.post("/api/admin/voting/close", headers=admin_headers, json={"election_id": "council-2026"})

        # Admin sees named totals before any trustee enters a password.
        monitor = await client.get(
            "/api/admin/trustees/ceremony-monitor?election_id=council-2026",
            headers=admin_headers,
        )
        assert monitor.status_code == 200
        assert "Alice Candidate" in monitor.json()["preliminary_results"]
        assert monitor.json()["results_published_at"] is None

        # Extract tokens and codes from database session directly for test verification
        test_tokens = ["token_t1_test_secret_12345", "token_t2_test_secret_12345", "token_t3_test_secret_12345"]
        test_codes = []
        
        from app.models.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            t_res = await session.execute(select(Trustee).where(Trustee.election_id == "council-2026").order_by(Trustee.position))
            trustees = t_res.scalars().all()
            for idx, t in enumerate(trustees, start=1):
                tok = test_tokens[idx - 1]
                t.link_token_hash = hash_link_token(tok)
                disp, raw, _ = generate_trustee_code(idx)
                test_codes.append((idx, disp, raw))
                h_hex, s_hex = hash_trustee_code(raw)
                t.code_hash = h_hex
                t.code_salt = s_hex
                # Encrypt test share
                blob, _ = encrypt_share_at_rest(1000 + idx, raw)
                t.encrypted_share_value = blob
            
            # Update commitment
            el_res = await session.execute(select(Election).where(Election.election_id == "council-2026"))
            el = el_res.scalars().first()
            comm, comm_salt = compute_full_passphrase_commitment([(p, r) for p, d, r in test_codes])
            el.full_passphrase_commitment = comm
            el.full_passphrase_salt = comm_salt
            await session.commit()

        # 1. Check ceremony info & establish presence for all 3 trustees
        for tok in test_tokens:
            info_res = await client.get(f"/api/ceremony/info/{tok}")
            assert info_res.status_code == 200
            assert info_res.json()["is_voting_closed"] is True

        # 2. Before unlock, validation console returns 403
        val_res = await client.get(f"/api/ceremony/validation/summary/{test_tokens[0]}")
        assert val_res.status_code == 403

        # 3. Enter codes in exact order: T1, T2, T3
        sub1 = await client.post(f"/api/ceremony/submit-code/{test_tokens[0]}", json={"code": test_codes[0][1]})
        assert sub1.status_code == 200
        assert sub1.json()["accepted_count"] == 1
        assert sub1.json()["is_unlocked"] is False

        sub2 = await client.post(f"/api/ceremony/submit-code/{test_tokens[1]}", json={"code": test_codes[1][1]})
        assert sub2.status_code == 200
        assert sub2.json()["accepted_count"] == 2

        sub3 = await client.post(f"/api/ceremony/submit-code/{test_tokens[2]}", json={"code": test_codes[2][1]})
        assert sub3.status_code == 200
        assert sub3.json()["is_unlocked"] is True

        # 4. Post-Unlock: validation console endpoints succeed
        val_summary = await client.get(f"/api/ceremony/validation/summary/{test_tokens[0]}")
        assert val_summary.status_code == 200
        assert val_summary.json()["total_ballots"] >= 0
        # Closing the ballot stores an empty draft tally. After the passwords
        # unlock, trustees must still receive named candidate counts.
        assert set(val_summary.json()["results"].keys()) == {
            "Alice Candidate",
            "Bob Candidate",
            "Charlie Candidate",
        }

        hidden = await client.get("/api/public/results?election_id=council-2026")
        assert hidden.json()["published"] is False

        # 5. Run independent verification
        verify_res = await client.post(f"/api/ceremony/validation/verify/{test_tokens[0]}")
        assert verify_res.status_code == 200
        assert "overall_integrity_verified" in verify_res.json()

        # 6. Approve and submit partial decryptions
        app1 = await client.post(f"/api/ceremony/validation/approve/{test_tokens[0]}", json={})
        assert app1.status_code == 200

        app2 = await client.post(f"/api/ceremony/validation/approve/{test_tokens[1]}", json={})
        assert app2.status_code == 200

        # Results publication blocked before T3 approves
        pub_blocked = await client.post("/api/admin/results/publish", headers=admin_headers, json={"election_id": "council-2026"})
        assert pub_blocked.status_code == 400
        assert "All 3 trustees must approve" in pub_blocked.json()["detail"]

        # T3 approves
        app3 = await client.post(f"/api/ceremony/validation/approve/{test_tokens[2]}", json={})
        assert app3.status_code == 200
        assert app3.json()["all_approved"] is True
        assert app3.json()["results_published"] is True

        # Voters see the tally only after every trustee has approved.
        visible = await client.get("/api/public/results?election_id=council-2026")
        assert visible.json()["published"] is True
        assert "Alice Candidate" in visible.json()["results"]

        # 7. Publish results succeeds!
        pub_success = await client.post("/api/admin/results/publish", headers=admin_headers, json={"election_id": "council-2026"})
        assert pub_success.status_code == 200
        assert pub_success.json()["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_ceremony_out_of_order_and_wrong_code_reset(admin_headers):
    """Verifies that out-of-order entry or wrong codes reset the active round."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Re-initialize ceremony
        ceremony = get_or_create_ceremony("council-2026", 3, window_minutes=5)
        ceremony.reset_round("Test reset")
        
        # Setup valid election and trustees in database
        await client.post("/api/admin/reset", headers=admin_headers, json={"election_id": "council-2026"})
        await client.post(
            "/api/admin/trustees",
            headers=admin_headers,
            json={
                "election_id": "council-2026",
                "trustees": [
                    {"name": "T1", "email": "t1@inst.edu"},
                    {"name": "T2", "email": "t2@inst.edu"},
                    {"name": "T3", "email": "t3@inst.edu"},
                ],
                "threshold": 2,
            },
        )
        await client.post("/api/admin/trustees/invite", headers=admin_headers, json={"election_id": "council-2026"})
        await client.post("/api/admin/voting/open", headers=admin_headers, json={"election_id": "council-2026"})
        await client.post("/api/admin/voting/close", headers=admin_headers, json={"election_id": "council-2026"})

        tok2 = "valid_length_token_t2_12345"
        from app.models.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            t2 = (await session.execute(select(Trustee).where(Trustee.election_id == "council-2026", Trustee.position == 2))).scalars().first()
            t2.link_token_hash = hash_link_token(tok2)
            await session.commit()

        # Record presence for all
        ceremony = get_or_create_ceremony("council-2026", 3, window_minutes=5)
        ceremony.reset_round("Test reset")
        ceremony.record_presence(1, "tok1_hash_12345", "T1", "t1@inst.edu")
        ceremony.record_presence(2, hash_link_token(tok2), "T2", "t2@inst.edu")
        ceremony.record_presence(3, "tok3_hash_12345", "T3", "t3@inst.edu")

        # T2 submits when T1 is expected
        res_ooo = await client.post(f"/api/ceremony/submit-code/{tok2}", json={"code": "T2-AAAA-BBBB-CCCC-DDDD-1"})
        assert res_ooo.status_code == 400
        assert "Out of order" in res_ooo.json()["detail"]
