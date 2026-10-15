"""
Comprehensive Unit & Tamper Test Suite for SecureVote Cryptographic Core.
Tests:
- Additive ElGamal & Homomorphic Tallying
- Shamir Secret Sharing (2-of-2 Voter Credentials & 3-of-5 Trustee Thresholds)
- Chaum RSA Blind Signatures
- Disjunctive Chaum-Pedersen (1-of-2 ZKP) with 5 Tamper Scenarios
- Homomorphic Sum-to-One Equality Proof with Tamper Scenarios
- Trustee Partial Decryption DLEQ Proofs with Tamper Scenarios
- Schnorr NIZK Knowledge Proofs
- Time-Lock Mechanism & Sloth VDF
"""

import hashlib
import pytest
from app.core.crypto.constants import G, P, Q, get_random_scalar
from app.core.crypto.elgamal import (
    Ciphertext,
    decrypt,
    encrypt,
    generate_keypair,
    homomorphic_add,
    homomorphic_sum,
    solve_discrete_log,
)
from app.core.crypto.shamir import (
    compute_partial_decryption,
    create_voter_credential,
    split_trustee_key,
    threshold_decrypt,
    verify_voter_credential,
)
from app.core.crypto.blind_signature import (
    blind_message,
    blind_sign,
    generate_blind_rsa_keypair,
    unblind_signature,
    verify_blind_signature,
)
from app.core.crypto.zkp import (
    DisjunctiveZKP,
    EqualityZKP,
    TrusteeDLEQProof,
    prove_ballot_sum_to_one,
    prove_disjunctive_chaum_pedersen,
    prove_schnorr_knowledge,
    prove_trustee_partial_decryption,
    verify_ballot_sum_to_one,
    verify_disjunctive_chaum_pedersen,
    verify_schnorr_knowledge,
    verify_trustee_partial_decryption,
)
from app.core.crypto.timelock import (
    ElectionClock,
    compute_sloth_vdf,
    decrypt_share_b,
    derive_timelock_key,
    encrypt_share_b,
    verify_sloth_vdf,
)


# ==========================================
# 1. ElGamal Tests
# ==========================================

def test_elgamal_encryption_and_decryption():
    """Test basic encryption and decryption of integer votes."""
    keypair = generate_keypair()
    for vote in [0, 1, 5, 42]:
        ct, r = encrypt(keypair.public_key, vote)
        recovered_vote = decrypt(keypair, ct)
        assert recovered_vote == vote, f"Expected {vote}, got {recovered_vote}"


def test_elgamal_homomorphic_addition():
    """Test that multiplying ciphertexts adds the underlying plaintext votes."""
    keypair = generate_keypair()
    votes = [1, 0, 1, 1, 0, 1, 0, 1, 1, 1]  # Sum = 7
    cts = [encrypt(keypair.public_key, v)[0] for v in votes]

    # Homomorphically add
    agg_ct = homomorphic_sum(cts)
    total_votes = decrypt(keypair, agg_ct)
    assert total_votes == sum(votes) == 7


def test_discrete_log_solver_speed():
    """Test solving discrete logs up to large tally numbers."""
    keypair = generate_keypair()
    tally = 2500
    g_tally = pow(G, tally, P)
    recovered = solve_discrete_log(g_tally, max_votes=5000)
    assert recovered == tally


# ==========================================
# 2. Shamir Secret Sharing Tests
# ==========================================

def test_voter_credential_2_of_2():
    """Test 2-of-2 voter credential splitting, verification, and tamper rejection."""
    cred = create_voter_credential()

    # Valid combination
    valid, secret = verify_voter_credential(cred.share_a, cred.share_b, cred.commitment)
    assert valid is True
    assert secret > 0

    # Tampered Share A
    tampered_a = hex(int(cred.share_a, 16) ^ 0xFF)
    invalid1, _ = verify_voter_credential(tampered_a, cred.share_b, cred.commitment)
    assert invalid1 is False

    # Tampered Share B
    tampered_b = hex(int(cred.share_b, 16) ^ 0x01)
    invalid2, _ = verify_voter_credential(cred.share_a, tampered_b, cred.commitment)
    assert invalid2 is False

    # Tampered Commitment
    fake_commitment = hashlib.sha256(b"fake_secret").hexdigest()
    invalid3, _ = verify_voter_credential(cred.share_a, cred.share_b, fake_commitment)
    assert invalid3 is False


def test_trustee_threshold_3_of_5_decryption():
    """Test that any 3 of 5 trustees can jointly decrypt homomorphic tallies."""
    election_pk, shares, secret_x = split_trustee_key(threshold=3, num_trustees=5)

    # Simulate 5 votes for a candidate (sum = 3)
    votes = [1, 0, 1, 1, 0]
    cts = [encrypt(election_pk, v)[0] for v in votes]
    agg_ct = homomorphic_sum(cts)

    # Test all 10 possible 3-trustee combinations
    from itertools import combinations
    for combo in combinations(shares, 3):
        partial_decs = [(s.trustee_id, compute_partial_decryption(s, agg_ct)) for s in combo]
        result = threshold_decrypt(partial_decs, agg_ct)
        assert result == sum(votes) == 3


# ==========================================
# 3. Chaum RSA Blind Signature Tests
# ==========================================

def test_chaum_rsa_blind_signature():
    """Test complete flow of RSA blind signing, unblinding, and verification."""
    sk = generate_blind_rsa_keypair(bits=1024)  # 1024-bit for fast unit test
    pk = sk.public_key
    ballot_nonce = "voter_token_uuid_8fa91230-cb41"

    # 1. Voter blinds message
    m_prime, r, m_int = blind_message(ballot_nonce, pk)

    # 2. Server blind-signs
    s_prime = blind_sign(sk, m_prime)

    # 3. Voter unblinds
    s = unblind_signature(s_prime, r, pk)

    # 4. Public verification
    assert verify_blind_signature(ballot_nonce, s, pk) is True

    # Tamper test: Altered ballot nonce fails verification
    assert verify_blind_signature("tampered_nonce", s, pk) is False

    # Tamper test: Corrupted signature fails verification
    assert verify_blind_signature(ballot_nonce, s ^ 0x01, pk) is False


# ==========================================
# 4. Disjunctive Chaum-Pedersen ZKP Tests
# ==========================================

def test_disjunctive_zkp_valid_0_and_1():
    """Test generating and verifying 1-of-2 ZKP for both 0 and 1 votes."""
    keypair = generate_keypair()

    # Vote 0
    ct0, r0 = encrypt(keypair.public_key, 0)
    proof0 = prove_disjunctive_chaum_pedersen(keypair.public_key, ct0, 0, r0)
    assert verify_disjunctive_chaum_pedersen(keypair.public_key, ct0, proof0) is True

    # Vote 1
    ct1, r1 = encrypt(keypair.public_key, 1)
    proof1 = prove_disjunctive_chaum_pedersen(keypair.public_key, ct1, 1, r1)
    assert verify_disjunctive_chaum_pedersen(keypair.public_key, ct1, proof1) is True


def test_disjunctive_zkp_tamper_detection():
    """Test that all tampering attempts in 1-of-2 ZKP are 100% detected and rejected."""
    keypair = generate_keypair()
    ct, r = encrypt(keypair.public_key, 1)
    proof = prove_disjunctive_chaum_pedersen(keypair.public_key, ct, 1, r)

    # Tamper 1: Modifying ciphertext c1
    bad_ct1 = Ciphertext(c1=(ct.c1 * 2) % P, c2=ct.c2)
    assert verify_disjunctive_chaum_pedersen(keypair.public_key, bad_ct1, proof) is False

    # Tamper 2: Modifying ciphertext c2
    bad_ct2 = Ciphertext(c1=ct.c1, c2=(ct.c2 * 3) % P)
    assert verify_disjunctive_chaum_pedersen(keypair.public_key, bad_ct2, proof) is False

    # Tamper 3: Modifying challenge c0
    bad_proof_c0 = DisjunctiveZKP(
        a0=proof.a0, b0=proof.b0, a1=proof.a1, b1=proof.b1,
        c0=(proof.c0 + 1) % Q, c1=proof.c1, z0=proof.z0, z1=proof.z1,
    )
    assert verify_disjunctive_chaum_pedersen(keypair.public_key, ct, bad_proof_c0) is False

    # Tamper 4: Modifying response scalar z1
    bad_proof_z1 = DisjunctiveZKP(
        a0=proof.a0, b0=proof.b0, a1=proof.a1, b1=proof.b1,
        c0=proof.c0, c1=proof.c1, z0=proof.z0, z1=(proof.z1 + 1) % Q,
    )
    assert verify_disjunctive_chaum_pedersen(keypair.public_key, ct, bad_proof_z1) is False

    # Tamper 5: Illegal vote value (v = 2) cannot be proved
    with pytest.raises(ValueError):
        ct2, r2 = encrypt(keypair.public_key, 2)
        prove_disjunctive_chaum_pedersen(keypair.public_key, ct2, 2, r2)


# ==========================================
# 5. Sum-to-One Equality Proof Tests
# ==========================================

def test_sum_to_one_proof_and_tamper():
    """Test multi-candidate ballot sum proof and fraud detection."""
    keypair = generate_keypair()

    # Valid ballot: 3 candidates, vote for Candidate B -> [0, 1, 0]
    votes = [0, 1, 0]
    cts = []
    rs = []
    for v in votes:
        ct, r = encrypt(keypair.public_key, v)
        cts.append(ct)
        rs.append(r)

    # Generate valid sum proof
    sum_proof = prove_ballot_sum_to_one(keypair.public_key, cts, rs)
    assert verify_ballot_sum_to_one(keypair.public_key, cts, sum_proof) is True

    # Tamper 1: Corrupted scalar in proof
    bad_proof = EqualityZKP(a=sum_proof.a, b=sum_proof.b, c=sum_proof.c, z=(sum_proof.z + 1) % Q)
    assert verify_ballot_sum_to_one(keypair.public_key, cts, bad_proof) is False

    # Tamper 2: Fraudulent ballot with sum = 2 (voting twice: [1, 1, 0])
    fraud_votes = [1, 1, 0]
    fraud_cts = []
    fraud_rs = []
    for v in fraud_votes:
        ct, r = encrypt(keypair.public_key, v)
        fraud_cts.append(ct)
        fraud_rs.append(r)

    # Attempting to verify standard proof against fraudulent ballot
    fraud_proof = prove_ballot_sum_to_one(keypair.public_key, fraud_cts, fraud_rs)
    assert verify_ballot_sum_to_one(keypair.public_key, fraud_cts, fraud_proof) is False


# ==========================================
# 6. Trustee DLEQ & Schnorr Proof Tests
# ==========================================

def test_trustee_dleq_proof():
    """Test trustee partial decryption DLEQ proof and tamper rejection."""
    election_pk, shares, _ = split_trustee_key(threshold=3, num_trustees=5)
    ct, _ = encrypt(election_pk, 1)

    trustee1 = shares[0]
    d1 = compute_partial_decryption(trustee1, ct)

    # Generate valid DLEQ proof
    proof = prove_trustee_partial_decryption(
        share_value_s_i=trustee1.share_value,
        verification_key_h_i=trustee1.public_verification_key,
        c1=ct.c1,
        d_i=d1,
    )
    assert verify_trustee_partial_decryption(
        trustee1.public_verification_key, ct.c1, d1, proof
    ) is True

    # Tamper: Fake partial decryption factor D1'
    bad_d1 = (d1 * 2) % P
    assert verify_trustee_partial_decryption(
        trustee1.public_verification_key, ct.c1, bad_d1, proof
    ) is False


def test_schnorr_knowledge_proof():
    """Test Schnorr NIZK proof of secret key."""
    sk = get_random_scalar(Q)
    pk_h = pow(G, sk, P)

    proof = prove_schnorr_knowledge(sk, pk_h)
    assert verify_schnorr_knowledge(pk_h, proof) is True

    # Tampered verification key fails
    bad_h = pow(G, sk + 1, P)
    assert verify_schnorr_knowledge(bad_h, proof) is False


# ==========================================
# 7. Time-Lock & Sloth VDF Tests
# ==========================================

def test_timelock_encryption_flow():
    """Test time-lock key derivation, encryption, and timed decryption."""
    master_key = b"super_secret_election_master_key_32"
    election_id = "council-election-2026"
    open_time = 1775000000

    timelock_key = derive_timelock_key(master_key, election_id, open_time)
    share_b_hex = "0x123456789abcdef0"

    encrypted_blob = encrypt_share_b(share_b_hex, timelock_key)
    decrypted_hex = decrypt_share_b(encrypted_blob, timelock_key)
    assert decrypted_hex == share_b_hex

    # Decryption with invalid key fails
    wrong_key = derive_timelock_key(master_key, election_id, open_time + 3600)
    assert decrypt_share_b(encrypted_blob, wrong_key) is None


def test_sloth_vdf():
    """Test Sloth VDF sequential computation and fast verification."""
    seed = 123456789
    iterations = 20
    solution = compute_sloth_vdf(seed, iterations, prime=P)
    assert verify_sloth_vdf(seed, solution, iterations, prime=P) is True
    assert verify_sloth_vdf(seed, solution + 1, iterations, prime=P) is False
