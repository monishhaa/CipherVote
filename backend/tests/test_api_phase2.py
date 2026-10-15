"""
End-to-End Integration Tests for SecureVote Phase 2 Backend API.
Tests:
1. Election Setup & Key Generation
2. Voter Registration & Face Template Vault
3. Time-Lock Enforcement & Share B Release
4. 2-of-2 Credential Authentication & Chaum Blind Token Issuance
5. Multi-Candidate Ballot Encryption, ZKP Generation & Casting
6. Bulletin Board Hash Chain & Merkle Receipt Audit
7. Homomorphic Tallying & 3-of-5 Trustee Threshold Decryption
"""

import hashlib
import time
import pytest
from httpx import ASGITransport, AsyncClient
from app.core.crypto.blind_signature import (
    RSABlindPublicKey,
    blind_message,
    unblind_signature,
)
from app.core.crypto.elgamal import PublicKey, encrypt
from app.core.crypto.zkp import (
    prove_ballot_sum_to_one,
    prove_disjunctive_chaum_pedersen,
)
import pytest_asyncio
from app.main import app
from app.models.database import init_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_full_phase2_api_workflow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Setup Election
        election_id = f"test-election-{int(time.time() * 1000)}"
        setup_payload = {
            "election_id": election_id,
            "title": "Student Council 2026",
            "candidates": [
                {"id": 0, "name": "Alice Candidate"},
                {"id": 1, "name": "Bob Candidate"},
                {"id": 2, "name": "Charlie Candidate"},
            ],
            "open_time": int(time.time()) + 100,  # Starts in future
            "close_time": int(time.time()) + 1000,
        }
        admin_headers = {"Authorization": "Bearer admin_session_valid_2026"}
        res = await client.post("/api/election/setup", json=setup_payload, headers=admin_headers)
        assert res.status_code == 200, res.text
        el_data = res.json()
        assert el_data["status"] == "REGISTRATION"
        assert el_data["is_open"] is False
        pk_h = int(el_data["public_key_h"], 16)
        blind_n = int(el_data["blind_rsa_n"], 16)
        blind_e = el_data["blind_rsa_e"]
        election_pk = PublicKey(h=pk_h)
        blind_rsa_pk = RSABlindPublicKey(n=blind_n, e=blind_e)

        # 2. Register Voter (Priya)
        fake_face_vec = [0.05 * i for i in range(128)]
        reg_payload = {
            "voter_id": f"voter-priya-{int(time.time() * 1000)}",
            "full_name": "Priya Sharma",
            "email": f"priya-{int(time.time() * 1000)}@college.edu",
            "face_embedding": fake_face_vec,
        }
        reg_res = await client.post(f"/api/voters/register?election_id={election_id}", json=reg_payload)
        assert reg_res.status_code == 200, reg_res.text
        voter_data = reg_res.json()
        share_a = voter_data["share_a"]
        commitment = voter_data["commitment"]

        # 3. Time-Lock Test: Attempt to retrieve Share B before election open -> 403 Forbidden
        locked_res = await client.get(f"/api/voters/share_b/{reg_payload['voter_id']}?election_id={election_id}")
        assert locked_res.status_code == 403

        # 4. Warp Clock to OPEN
        warp_res = await client.post(
            f"/api/election/clock/warp?election_id={election_id}",
            json={"target_status": "OPEN"},
            headers=admin_headers,
        )

        assert warp_res.status_code == 200

        # 5. Retrieve Unlocked Share B
        unlocked_res = await client.get(f"/api/voters/share_b/{reg_payload['voter_id']}?election_id={election_id}")
        assert unlocked_res.status_code == 200
        share_b = unlocked_res.json()["share_b"]
        assert share_b is not None

        # 6. Request Blind-Signed Voting Token
        ballot_nonce = f"ballot_uuid_nonce_{int(time.time() * 1000)}"
        m_prime, r_blind, _ = blind_message(ballot_nonce, blind_rsa_pk)

        token_req = {
            "voter_id": reg_payload["voter_id"],
            "share_a": share_a,
            "share_b": share_b,
            "blinded_token": hex(m_prime),
            "liveness_telemetry": {
                "challenge_id": "challenge-123",
                "ear_scores": [0.35, 0.15, 0.38],
                "yaw_angles": [-15.0, 0.0, 20.0],
                "probe_embedding": fake_face_vec,
            },
        }
        token_res = await client.post(f"/api/auth/blind-token?election_id={election_id}", json=token_req)
        assert token_res.status_code == 200, token_res.text
        s_prime = int(token_res.json()["blind_signature"], 16)

        # Unblind signature on voter client side
        unblinded_sig = unblind_signature(s_prime, r_blind, blind_rsa_pk)

        # Double issuance prevention test
        double_token_res = await client.post(f"/api/auth/blind-token?election_id={election_id}", json=token_req)
        assert double_token_res.status_code == 403

        # 7. Voter encrypts vote for Candidate #1 (Bob) -> [0, 1, 0]
        votes = [0, 1, 0]
        cts = []
        randomizers = []
        disjunctive_proofs = []

        for v in votes:
            ct, r = encrypt(election_pk, v)
            cts.append(ct)
            randomizers.append(r)
            zkp = prove_disjunctive_chaum_pedersen(election_pk, ct, v, r)
            disjunctive_proofs.append(zkp.to_dict())

        sum_proof = prove_ballot_sum_to_one(election_pk, cts, randomizers)

        ballot_payload = {
            "election_id": election_id,
            "ciphertexts": [ct.to_dict() for ct in cts],
            "zkp_proofs": {
                "disjunctive_proofs": disjunctive_proofs,
                "sum_proof": sum_proof.to_dict(),
            },
            "token_nonce": ballot_nonce,
            "token_signature": hex(unblinded_sig),
        }

        # 8. Cast Ballot
        cast_res = await client.post("/api/ballots/cast", json=ballot_payload)
        assert cast_res.status_code == 200, cast_res.text
        cast_data = cast_res.json()
        assert cast_data["sequence_number"] == 1
        receipt_code = cast_data["receipt_code"]

        # Double-voting prevention (Token replay check)
        double_cast_res = await client.post("/api/ballots/cast", json=ballot_payload)
        assert double_cast_res.status_code == 403

        # 9. Verify Public Bulletin Board & Merkle Proof
        bb_res = await client.get(f"/api/bulletin-board?election_id={election_id}")
        assert bb_res.status_code == 200
        assert bb_res.json()["total_ballots"] == 1

        verify_bb_res = await client.get(f"/api/bulletin-board/verify?election_id={election_id}")
        assert verify_bb_res.status_code == 200
        assert verify_bb_res.json()["is_valid"] is True

        receipt_res = await client.get(f"/api/bulletin-board/receipt/{receipt_code}?election_id={election_id}")
        assert receipt_res.status_code == 200
        assert receipt_res.json()["receipt_code"] == receipt_code

        # 10. Compute Homomorphic Tally with 3 Trustees (1, 2, 3)
        tally_res = await client.post(f"/api/tally/compute?election_id={election_id}&trustee_ids=1,2,3")
        assert tally_res.status_code == 200, tally_res.text
        tally_data = tally_res.json()
        results = tally_data["candidate_results"]
        assert results["Alice Candidate"] == 0
        assert results["Bob Candidate"] == 1
        assert results["Charlie Candidate"] == 0
