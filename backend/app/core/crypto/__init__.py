"""
SecureVote Cryptographic Core Package.
"""

from .constants import G, P, Q, get_random_scalar, hash_to_scalar, mod_inverse
from .elgamal import (
    Ciphertext,
    PrivateKey,
    PublicKey,
    decrypt,
    encrypt,
    generate_keypair,
    homomorphic_add,
    homomorphic_sum,
    solve_discrete_log,
)
from .shamir import (
    TrusteeShare,
    VoterCredential,
    compute_lagrange_coefficient,
    compute_partial_decryption,
    create_voter_credential,
    split_trustee_key,
    threshold_decrypt,
    verify_voter_credential,
)
from .blind_signature import (
    RSABlindPrivateKey,
    RSABlindPublicKey,
    blind_message,
    blind_sign,
    generate_blind_rsa_keypair,
    unblind_signature,
    verify_blind_signature,
)
from .zkp import (
    DisjunctiveZKP,
    EqualityZKP,
    SchnorrProof,
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
from .timelock import (
    ElectionClock,
    compute_sloth_vdf,
    decrypt_share_b,
    derive_timelock_key,
    encrypt_share_b,
    verify_sloth_vdf,
)

__all__ = [
    "G", "P", "Q", "get_random_scalar", "hash_to_scalar", "mod_inverse",
    "Ciphertext", "PrivateKey", "PublicKey", "generate_keypair", "encrypt", "decrypt",
    "homomorphic_add", "homomorphic_sum", "solve_discrete_log",
    "TrusteeShare", "VoterCredential", "create_voter_credential", "verify_voter_credential",
    "split_trustee_key", "compute_lagrange_coefficient", "compute_partial_decryption", "threshold_decrypt",
    "RSABlindPrivateKey", "RSABlindPublicKey", "generate_blind_rsa_keypair", "blind_message", "blind_sign", "unblind_signature", "verify_blind_signature",
    "DisjunctiveZKP", "EqualityZKP", "TrusteeDLEQProof", "SchnorrProof",
    "prove_disjunctive_chaum_pedersen", "verify_disjunctive_chaum_pedersen",
    "prove_ballot_sum_to_one", "verify_ballot_sum_to_one",
    "prove_trustee_partial_decryption", "verify_trustee_partial_decryption",
    "prove_schnorr_knowledge", "verify_schnorr_knowledge",
    "ElectionClock", "derive_timelock_key", "encrypt_share_b", "decrypt_share_b",
    "compute_sloth_vdf", "verify_sloth_vdf",
]
