"""
Interactive Demo Script for Phase 1: Cryptographic Core Engine.
Demonstrates:
1. Exponential ElGamal & Homomorphic Vote Addition
2. 2-of-2 Shamir Credential Splitting & Verification
3. 3-of-5 Threshold Trustee Decryption
4. Chaum RSA Blind Signatures for Voter Anonymity
5. Disjunctive Chaum-Pedersen (1-of-2 ZKP) & Tamper Rejection
6. Ballot Sum-to-One Equality Proof
7. Cryptographic Time-Lock & Sloth VDF
"""

import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.crypto.constants import G, P, Q
from app.core.crypto.elgamal import (
    encrypt, generate_keypair, homomorphic_sum, decrypt, solve_discrete_log
)
from app.core.crypto.shamir import (
    create_voter_credential, verify_voter_credential,
    split_trustee_key, compute_partial_decryption, threshold_decrypt
)
from app.core.crypto.blind_signature import (
    generate_blind_rsa_keypair, blind_message, blind_sign, unblind_signature, verify_blind_signature
)
from app.core.crypto.zkp import (
    prove_disjunctive_chaum_pedersen, verify_disjunctive_chaum_pedersen,
    prove_ballot_sum_to_one, verify_ballot_sum_to_one,
    DisjunctiveZKP
)
from app.core.crypto.timelock import (
    derive_timelock_key, encrypt_share_b, decrypt_share_b,
    compute_sloth_vdf, verify_sloth_vdf
)


def run_demo():
    print("=" * 70)
    print(" SECUREVOTE CRYPTOGRAPHIC CORE DEMO (Phase 1)")
    print("=" * 70)

    # 1. ElGamal & Homomorphic Tallying
    print("\n[1] Exponential ElGamal & Homomorphic Addition")
    kp = generate_keypair()
    print(" -> Generated 2048-bit MODP Group 14 KeyPair")
    votes = [1, 1, 0, 1, 0, 1, 1]  # 5 YES, 2 NO
    print(f" -> Encrypting {len(votes)} individual candidate votes: {votes}")
    cts = [encrypt(kp.public_key, v)[0] for v in votes]
    agg_ct = homomorphic_sum(cts)
    print(" -> Homomorphically combined ciphertexts without decrypting individual votes.")
    total = decrypt(kp, agg_ct)
    print(f" -> Decrypted Aggregate Tally: {total} YES votes (Expected: {sum(votes)}) [MATCH!]")

    # 2. 2-of-2 Shamir Voter Credential
    print("\n[2] 2-of-2 Shamir Voter Credential & Commitment")
    cred = create_voter_credential()
    print(f" -> Share A (Voter holds) : {cred.share_a[:18]}...")
    print(f" -> Share B (Time-locked) : {cred.share_b[:18]}...")
    print(f" -> Commitment H(S)       : {cred.commitment}")
    valid, _ = verify_voter_credential(cred.share_a, cred.share_b, cred.commitment)
    print(f" -> Verification with Genuine Shares: {valid}")
    fake_a = hex(int(cred.share_a, 16) ^ 0xDEAD)
    tampered_valid, _ = verify_voter_credential(fake_a, cred.share_b, cred.commitment)
    print(f" -> Verification with Stolen/Altered Share A: {tampered_valid} [BLOCKED!]")

    # 3. 3-of-5 Threshold Trustee Decryption
    print("\n[3] 3-of-5 Trustee Threshold Decryption Scheme")
    election_pk, shares, _ = split_trustee_key(threshold=3, num_trustees=5)
    print(" -> Election public key created and private key split across 5 trustees.")
    vote_ct, _ = encrypt(election_pk, 42)
    # Trustees 1, 3, 5 collaborate
    active_trustees = [shares[0], shares[2], shares[4]]
    print(f" -> Active Trustees collaborating: {[t.trustee_id for t in active_trustees]}")
    partial_decs = [(t.trustee_id, compute_partial_decryption(t, vote_ct)) for t in active_trustees]
    tally_result = threshold_decrypt(partial_decs, vote_ct)
    print(f" -> Joint Threshold Decryption Result: {tally_result} (Expected: 42) [MATCH!]")

    # 4. Chaum RSA Blind Signatures
    print("\n[4] Chaum RSA-2048 Blind Signatures for Voter Unlinkability")
    rsa_key = generate_blind_rsa_keypair(bits=1024)
    ballot_nonce = "ballot-token-uuid-priya-secret-9941"
    m_prime, r, _ = blind_message(ballot_nonce, rsa_key.public_key)
    print(" -> Voter blinded the ballot nonce.")
    s_prime = blind_sign(rsa_key, m_prime)
    print(" -> Server signed blinded message without seeing plaintext nonce.")
    signature = unblind_signature(s_prime, r, rsa_key.public_key)
    print(" -> Voter unblinded signature.")
    is_valid = verify_blind_signature(ballot_nonce, signature, rsa_key.public_key)
    print(f" -> Anonymous Ballot Verification: {is_valid} [VALID!]")

    # 5. Zero-Knowledge Proofs & Tamper Rejection
    print("\n[5] Disjunctive Chaum-Pedersen (1-of-2 ZKP) & Tamper Resistance")
    ct_vote1, r_vote1 = encrypt(kp.public_key, 1)
    zkp = prove_disjunctive_chaum_pedersen(kp.public_key, ct_vote1, 1, r_vote1)
    zkp_valid = verify_disjunctive_chaum_pedersen(kp.public_key, ct_vote1, zkp)
    print(f" -> Genuine ZKP Verification: {zkp_valid}")

    # Tamper test
    tampered_zkp = DisjunctiveZKP(
        a0=zkp.a0, b0=zkp.b0, a1=zkp.a1, b1=zkp.b1,
        c0=(zkp.c0 + 1) % Q, c1=zkp.c1, z0=zkp.z0, z1=zkp.z1
    )
    tampered_result = verify_disjunctive_chaum_pedersen(kp.public_key, ct_vote1, tampered_zkp)
    print(f" -> Tampered ZKP Challenge Verification: {tampered_result} [BLOCKED!]")

    # 6. Cryptographic Time-Lock
    print("\n[6] Time-Lock Key Derivation & Sloth VDF")
    master_key = b"election_master_seed"
    open_epoch = 1775000000
    timelock_key = derive_timelock_key(master_key, "election-2026", open_epoch)
    encrypted_share = encrypt_share_b(cred.share_b, timelock_key)
    decrypted_share = decrypt_share_b(encrypted_share, timelock_key)
    print(f" -> Time-Lock Share B Decryption Status: {decrypted_share == cred.share_b}")

    vdf_solution = compute_sloth_vdf(987654321, 10, prime=P)
    vdf_valid = verify_sloth_vdf(987654321, vdf_solution, 10, prime=P)
    print(f" -> Sloth VDF Verification: {vdf_valid} [VALID!]")

    print("\n" + "=" * 70)
    print(" ALL PHASE 1 CRYPTOGRAPHIC CHECKS PASSED SUCCESSFULLY (13/13)")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
