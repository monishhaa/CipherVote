"""
Polynomial Shamir Secret Sharing over prime field Fq.
Supports:
1. 2-of-2 voter credential split with SHA-256 commitment.
2. 3-of-5 threshold trustee election key distribution & threshold partial decryption.
"""

from dataclasses import dataclass
import hashlib
from typing import Dict, List, Tuple
from .constants import G, P, Q, get_random_scalar, mod_inverse
from .elgamal import Ciphertext, PublicKey, solve_discrete_log


@dataclass(frozen=True)
class VoterCredential:
    share_a: str  # Hex string of Share A given to voter
    share_b: str  # Hex string of Share B (time-locked on server)
    commitment: str  # SHA-256 hash of secret S


def create_voter_credential() -> VoterCredential:
    """
    Generate secret voting credential S, split into 2-of-2 additive shares:
    S = (s_a + s_b) mod Q
    Commitment = SHA256(S)
    """
    secret = get_random_scalar(Q)
    share_a = get_random_scalar(Q)
    share_b = (secret - share_a) % Q

    secret_bytes = secret.to_bytes(256, "big")
    commitment = hashlib.sha256(secret_bytes).hexdigest()

    return VoterCredential(
        share_a=hex(share_a),
        share_b=hex(share_b),
        commitment=commitment,
    )


def verify_voter_credential(share_a_hex: str, share_b_hex: str, stored_commitment: str) -> Tuple[bool, int]:
    """
    Combine Share A and Share B, verify against stored commitment.
    Returns (is_valid, reconstructed_secret).
    """
    try:
        s_a = int(share_a_hex, 16) % Q
        s_b = int(share_b_hex, 16) % Q
        secret = (s_a + s_b) % Q
        secret_bytes = secret.to_bytes(256, "big")
        computed_hash = hashlib.sha256(secret_bytes).hexdigest()
        is_valid = (computed_hash == stored_commitment)
        return is_valid, secret
    except Exception:
        return False, 0


# ==========================================
# (t, n) Threshold Trustee Secret Sharing
# ==========================================

@dataclass(frozen=True)
class TrusteeShare:
    trustee_id: int  # x-coordinate in [1..n]
    share_value: int  # y-coordinate s_i = f(i) mod Q
    public_verification_key: int  # h_i = g^(s_i) mod P

    def to_dict(self) -> Dict[str, str]:
        return {
            "trustee_id": str(self.trustee_id),
            "share_value": hex(self.share_value),
            "public_verification_key": hex(self.public_verification_key),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "TrusteeShare":
        return cls(
            trustee_id=int(data["trustee_id"]),
            share_value=int(data["share_value"], 16),
            public_verification_key=int(data["public_verification_key"], 16),
        )


def split_trustee_key(
    threshold: int = 3, num_trustees: int = 5
) -> Tuple[PublicKey, List[TrusteeShare], int]:
    """
    Generate election private key x and split into n shares with threshold t.
    Polynomial f(z) = x + a_1*z + ... + a_{t-1}*z^{t-1} mod Q.
    Returns (ElectionPublicKey, List of TrusteeShare, PrivateKey_x).
    """
    secret_x = get_random_scalar(Q)
    election_pk = PublicKey(h=pow(G, secret_x, P))

    # Generate polynomial coefficients a_1 ... a_{t-1}
    coefficients = [secret_x] + [get_random_scalar(Q) for _ in range(threshold - 1)]

    shares: List[TrusteeShare] = []
    for i in range(1, num_trustees + 1):
        # Evaluate polynomial at z = i
        val = 0
        for power, coeff in enumerate(coefficients):
            val = (val + coeff * pow(i, power, Q)) % Q
        h_i = pow(G, val, P)
        shares.append(TrusteeShare(trustee_id=i, share_value=val, public_verification_key=h_i))

    return election_pk, shares, secret_x


def compute_lagrange_coefficient(trustee_id: int, present_ids: List[int]) -> int:
    """
    Compute Lagrange basis polynomial lambda_j(0) = prod_{m != j} (-m) / (j - m) mod Q.
    """
    num = 1
    den = 1
    for m in present_ids:
        if m == trustee_id:
            continue
        num = (num * (-m)) % Q
        den = (den * (trustee_id - m)) % Q
    return (num * mod_inverse(den, Q)) % Q


def compute_partial_decryption(share: TrusteeShare, ct: Ciphertext) -> int:
    """
    Trustee computes partial decryption factor D_i = c1^(s_i) mod P.
    """
    return pow(ct.c1, share.share_value, P)


def threshold_decrypt(
    partial_decryptions: List[Tuple[int, int]], ct: Ciphertext, max_votes: int = 10000
) -> int:
    """
    Combine threshold partial decryptions (trustee_id, D_i) to decrypt ct:
    1. Compute aggregate D = prod_{i in I} (D_i ^ lambda_i(0)) mod P = c1^x mod P.
    2. Compute g^V = c2 * D^(-1) mod P.
    3. Solve discrete log for V.
    """
    present_ids = [t_id for t_id, _ in partial_decryptions]
    aggregate_d = 1
    for t_id, d_i in partial_decryptions:
        lambda_i = compute_lagrange_coefficient(t_id, present_ids)
        factor = pow(d_i, lambda_i, P)
        aggregate_d = (aggregate_d * factor) % P

    d_inv = pow(aggregate_d, -1, P)
    g_v = (ct.c2 * d_inv) % P
    return solve_discrete_log(g_v, max_votes=max_votes)
