import pytest
import time
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.database import init_db
from app.core.crypto.elgamal import PublicKey, encrypt
from app.core.crypto.blind_signature import RSABlindPublicKey, blind_message, unblind_signature
from app.core.crypto.zkp import prove_disjunctive_chaum_pedersen, prove_ballot_sum_to_one

@pytest.mark.asyncio
async def test_org_election_creation_registration_and_voting_flow():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Setup new Organization Election
        org_election_id = f"acme-org-{int(time.time())}"
        setup_payload = {
            "election_id": org_election_id,
            "title": "Acme Corp Annual Board Election 2026",
            "candidates": [
                {"id": 0, "name": "Elena Rostova", "party": "Engineering"},
                {"id": 1, "name": "Marcus Vance", "party": "Operations"},
                {"id": 2, "name": "Sarah Chen", "party": "Finance"},
            ],
            "open_time": int(time.time()) + 1000,
            "close_time": int(time.time()) + 10000,
        }
        admin_headers = {"Authorization": "Bearer admin_session_valid_2026"}
        res_setup = await client.post("/api/election/setup", json=setup_payload, headers=admin_headers)
        assert res_setup.status_code == 200, res_setup.text
        el_info = res_setup.json()
        assert el_info["election_id"] == org_election_id
        assert len(el_info["candidates"]) == 3

        # 2. List elections
        res_list = await client.get("/api/election/list")
        assert res_list.status_code == 200
        elections = res_list.json()["elections"]
        assert any(e["election_id"] == org_election_id for e in elections)

        # 3. Register Voter for Acme Org (Sends Share A to email)
        unique_voter_id = f"voter-emp-{int(time.time() * 1000)}"
        reg_payload = {
            "voter_id": unique_voter_id,
            "full_name": "Dr. Sarah Connor",
            "email": f"{unique_voter_id}@acme.corp",
            "face_embedding": [0.03 * i for i in range(128)],
        }
        res_reg = await client.post(f"/api/voters/register?election_id={org_election_id}", json=reg_payload)
        assert res_reg.status_code == 200, res_reg.text
        reg_data = res_reg.json()
        assert "Registration successful" in reg_data["message"]
        share_a = reg_data["share_a"]

        # 4. Warp Election to OPEN
        res_warp = await client.post(
            f"/api/election/clock/warp?election_id={org_election_id}",
            json={"target_status": "OPEN"},
            headers=admin_headers,
        )
        assert res_warp.status_code == 200

        # 5. Fetch time-locked Share B
        res_sb = await client.get(f"/api/voters/share_b/{unique_voter_id}?election_id={org_election_id}")
        assert res_sb.status_code == 200
        share_b = res_sb.json()["share_b"]

        # 6. Request Blind Voting Token
        el_status = (await client.get(f"/api/election/status?election_id={org_election_id}")).json()
        election_pk = PublicKey(h=int(el_status["public_key_h"], 16))
        blind_rsa_pk = RSABlindPublicKey(n=int(el_status["blind_rsa_n"], 16), e=el_status["blind_rsa_e"])

        ballot_nonce = f"ballot_nonce_{unique_voter_id}"
        m_prime, r_blind, _ = blind_message(ballot_nonce, blind_rsa_pk)

        token_req = {
            "voter_id": unique_voter_id,
            "share_a": share_a,
            "share_b": share_b,
            "blinded_token": hex(m_prime),
            "liveness_telemetry": {
                "challenge_id": "chal-01",
                "ear_scores": [0.35, 0.16, 0.36],
                "yaw_angles": [0.0, -11.5, 0.0],
                "probe_embedding": [0.03 * i for i in range(128)],
            },
        }
        res_tok = await client.post(f"/api/auth/blind-token?election_id={org_election_id}", json=token_req)
        assert res_tok.status_code == 200, res_tok.text
        s_prime = int(res_tok.json()["blind_signature"], 16)
        unblinded_sig = unblind_signature(s_prime, r_blind, blind_rsa_pk)

        # 7. In-Browser Vote Encryption for Candidate 1 (Marcus Vance: [0, 1, 0])
        ct0, r0 = encrypt(election_pk, 0)
        ct1, r1 = encrypt(election_pk, 1)
        ct2, r2 = encrypt(election_pk, 0)

        p0 = prove_disjunctive_chaum_pedersen(election_pk, ct0, 0, r0)
        p1 = prove_disjunctive_chaum_pedersen(election_pk, ct1, 1, r1)
        p2 = prove_disjunctive_chaum_pedersen(election_pk, ct2, 0, r2)
        sum_p = prove_ballot_sum_to_one(election_pk, [ct0, ct1, ct2], [r0, r1, r2])

        cast_payload = {
            "election_id": org_election_id,
            "ciphertexts": [ct0.to_dict(), ct1.to_dict(), ct2.to_dict()],
            "zkp_proofs": {
                "disjunctive_proofs": [p0.to_dict(), p1.to_dict(), p2.to_dict()],
                "sum_proof": sum_p.to_dict(),
            },
            "token_nonce": ballot_nonce,
            "token_signature": hex(unblinded_sig),
        }
        res_cast = await client.post("/api/ballots/cast", json=cast_payload)
        assert res_cast.status_code == 200, res_cast.text
        receipt_info = res_cast.json()
        assert "receipt_code" in receipt_info
        assert receipt_info["sequence_number"] == 1

        # 8. Verify on Bulletin Board
        res_bb = await client.get(f"/api/bulletin-board?election_id={org_election_id}")
        assert res_bb.status_code == 200
        assert res_bb.json()["total_ballots"] == 1

        # 9. Verify Chain Integrity
        res_audit = await client.get(f"/api/bulletin-board/verify?election_id={org_election_id}")
        assert res_audit.status_code == 200
        assert res_audit.json()["is_valid"] is True
