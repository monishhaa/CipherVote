"""
Non-Interactive Zero-Knowledge Proofs (NIZK) with Fiat-Shamir Heuristic (SHA-256).
1. Disjunctive Chaum-Pedersen (1-of-2 ZKP): Proves ciphertext encrypts 0 or 1.
2. Homomorphic Sum-to-One Proof: Proves vector of ciphertexts sums to 1.
3. Trustee Partial Decryption DLEQ Proof: Proves correct discrete log equality for partial decryptions.
4. Schnorr NIZK Proof: Proves knowledge of secret key.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
from .constants import G, P, Q, get_random_scalar, hash_to_scalar
from .elgamal import Ciphertext, PublicKey, homomorphic_sum


@dataclass(frozen=True)
class DisjunctiveZKP:
    """Disjunctive Chaum-Pedersen (1-of-2) Proof."""
    a0: int
    b0: int
    a1: int
    b1: int
    c0: int
    c1: int
    z0: int
    z1: int

    def to_dict(self) -> Dict[str, str]:
        return {
            "a0": hex(self.a0),
            "b0": hex(self.b0),
            "a1": hex(self.a1),
            "b1": hex(self.b1),
            "c0": hex(self.c0),
            "c1": hex(self.c1),
            "z0": hex(self.z0),
            "z1": hex(self.z1),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, str]) -> "DisjunctiveZKP":
        return cls(
            a0=int(d["a0"], 16),
            b0=int(d["b0"], 16),
            a1=int(d["a1"], 16),
            b1=int(d["b1"], 16),
            c0=int(d["c0"], 16),
            c1=int(d["c1"], 16),
            z0=int(d["z0"], 16),
            z1=int(d["z1"], 16),
        )


def prove_disjunctive_chaum_pedersen(
    pk: PublicKey, ct: Ciphertext, v: int, r: int
) -> DisjunctiveZKP:
    """
    Generate 1-out-of-2 ZKP proving ct encrypts v in {0, 1} with randomness r.
    """
    if v not in (0, 1):
        raise ValueError(f"Vote must be 0 or 1 for disjunctive proof, got {v}")

    g_inv = pow(G, -1, P)
    c2_div_g = (ct.c2 * g_inv) % P

    if v == 0:
        # Real branch is 0, simulate branch 1
        w = get_random_scalar(Q)
        c1_sim = get_random_scalar(Q)
        z1_sim = get_random_scalar(Q)

        # Simulate branch 1 commitments
        # a1 = g^z1 * c1^(-c1_sim) mod p
        # b1 = h^z1 * (c2/g)^(-c1_sim) mod p
        c1_inv = pow(ct.c1, -1, P)
        c2_div_g_inv = pow(c2_div_g, -1, P)

        a1 = (pow(G, z1_sim, P) * pow(c1_inv, c1_sim, P)) % P
        b1 = (pow(pk.h, z1_sim, P) * pow(c2_div_g_inv, c1_sim, P)) % P

        # Real branch 0 commitments
        a0 = pow(G, w, P)
        b0 = pow(pk.h, w, P)

        # Master challenge
        c = hash_to_scalar(G, pk.h, ct.c1, ct.c2, a0, b0, a1, b1, order=Q)

        c0 = (c - c1_sim) % Q
        z0 = (w + c0 * r) % Q

        return DisjunctiveZKP(
            a0=a0, b0=b0, a1=a1, b1=b1,
            c0=c0, c1=c1_sim, z0=z0, z1=z1_sim,
        )
    else:
        # Real branch is 1, simulate branch 0
        w = get_random_scalar(Q)
        c0_sim = get_random_scalar(Q)
        z0_sim = get_random_scalar(Q)

        # Simulate branch 0 commitments
        # a0 = g^z0 * c1^(-c0_sim) mod p
        # b0 = h^z0 * c2^(-c0_sim) mod p
        c1_inv = pow(ct.c1, -1, P)
        c2_inv = pow(ct.c2, -1, P)

        a0 = (pow(G, z0_sim, P) * pow(c1_inv, c0_sim, P)) % P
        b0 = (pow(pk.h, z0_sim, P) * pow(c2_inv, c0_sim, P)) % P

        # Real branch 1 commitments
        a1 = pow(G, w, P)
        b1 = pow(pk.h, w, P)

        # Master challenge
        c = hash_to_scalar(G, pk.h, ct.c1, ct.c2, a0, b0, a1, b1, order=Q)

        c1 = (c - c0_sim) % Q
        z1 = (w + c1 * r) % Q

        return DisjunctiveZKP(
            a0=a0, b0=b0, a1=a1, b1=b1,
            c0=c0_sim, c1=c1, z0=z0_sim, z1=z1,
        )


def verify_disjunctive_chaum_pedersen(
    pk: PublicKey, ct: Ciphertext, proof: DisjunctiveZKP
) -> bool:
    """
    Verify 1-out-of-2 ZKP. Returns True if valid, False otherwise.
    """
    try:
        # 1. Verify challenge sum
        c = hash_to_scalar(G, pk.h, ct.c1, ct.c2, proof.a0, proof.b0, proof.a1, proof.b1, order=Q)
        if (proof.c0 + proof.c1) % Q != c:
            return False

        # 2. Check branch 0 equations:
        # g^z0 == a0 * c1^c0 mod p
        # h^z0 == b0 * c2^c0 mod p
        lhs_a0 = pow(G, proof.z0, P)
        rhs_a0 = (proof.a0 * pow(ct.c1, proof.c0, P)) % P
        if lhs_a0 != rhs_a0:
            return False

        lhs_b0 = pow(pk.h, proof.z0, P)
        rhs_b0 = (proof.b0 * pow(ct.c2, proof.c0, P)) % P
        if lhs_b0 != rhs_b0:
            return False

        # 3. Check branch 1 equations:
        # g^z1 == a1 * c1^c1 mod p
        # h^z1 == b1 * (c2 / g)^c1 mod p
        g_inv = pow(G, -1, P)
        c2_div_g = (ct.c2 * g_inv) % P

        lhs_a1 = pow(G, proof.z1, P)
        rhs_a1 = (proof.a1 * pow(ct.c1, proof.c1, P)) % P
        if lhs_a1 != rhs_a1:
            return False

        lhs_b1 = pow(pk.h, proof.z1, P)
        rhs_b1 = (proof.b1 * pow(c2_div_g, proof.c1, P)) % P
        if lhs_b1 != rhs_b1:
            return False

        return True
    except Exception:
        return False


# ==========================================
# Sum-to-One Equality Proof
# ==========================================

@dataclass(frozen=True)
class EqualityZKP:
    """DLEQ Proof: a = g^w, b = h^w, z = w + c*r."""
    a: int
    b: int
    c: int
    z: int

    def to_dict(self) -> Dict[str, str]:
        return {"a": hex(self.a), "b": hex(self.b), "c": hex(self.c), "z": hex(self.z)}

    @classmethod
    def from_dict(cls, d: Dict[str, str]) -> "EqualityZKP":
        return cls(
            a=int(d["a"], 16), b=int(d["b"], 16),
            c=int(d["c"], 16), z=int(d["z"], 16),
        )


def prove_ballot_sum_to_one(
    pk: PublicKey, ciphertexts: List[Ciphertext], randomizers: List[int]
) -> EqualityZKP:
    """
    Prove that sum of encrypted candidate votes = 1.
    Aggregates (C1, C2) = (g^R, h^R * g^1) where R = sum(randomizers) mod Q.
    Proves log_g(C1) == log_h(C2 / g) == R.
    """
    agg_ct = homomorphic_sum(ciphertexts)
    r_sum = sum(randomizers) % Q

    w = get_random_scalar(Q)
    a = pow(G, w, P)
    b = pow(pk.h, w, P)

    c = hash_to_scalar(G, pk.h, agg_ct.c1, agg_ct.c2, a, b, order=Q)
    z = (w + c * r_sum) % Q

    return EqualityZKP(a=a, b=b, c=c, z=z)


def verify_ballot_sum_to_one(
    pk: PublicKey, ciphertexts: List[Ciphertext], proof: EqualityZKP
) -> bool:
    """
    Verify sum-to-one equality proof for candidate ciphertexts.
    """
    try:
        agg_ct = homomorphic_sum(ciphertexts)
        g_inv = pow(G, -1, P)
        c2_div_g = (agg_ct.c2 * g_inv) % P

        c = hash_to_scalar(G, pk.h, agg_ct.c1, agg_ct.c2, proof.a, proof.b, order=Q)
        if c != proof.c:
            return False

        # Check g^z == a * C1^c mod p
        lhs_a = pow(G, proof.z, P)
        rhs_a = (proof.a * pow(agg_ct.c1, proof.c, P)) % P
        if lhs_a != rhs_a:
            return False

        # Check h^z == b * (C2/g)^c mod p
        lhs_b = pow(pk.h, proof.z, P)
        rhs_b = (proof.b * pow(c2_div_g, proof.c, P)) % P
        if lhs_b != rhs_b:
            return False

        return True
    except Exception:
        return False


# ==========================================
# Trustee Partial Decryption DLEQ Proof
# ==========================================

@dataclass(frozen=True)
class TrusteeDLEQProof:
    """Proves log_g(h_i) == log_{c1}(D_i) == s_i."""
    a: int
    b: int
    c: int
    z: int

    def to_dict(self) -> Dict[str, str]:
        return {"a": hex(self.a), "b": hex(self.b), "c": hex(self.c), "z": hex(self.z)}

    @classmethod
    def from_dict(cls, d: Dict[str, str]) -> "TrusteeDLEQProof":
        return cls(
            a=int(d["a"], 16), b=int(d["b"], 16),
            c=int(d["c"], 16), z=int(d["z"], 16),
        )


def prove_trustee_partial_decryption(
    share_value_s_i: int, verification_key_h_i: int, c1: int, d_i: int
) -> TrusteeDLEQProof:
    """
    Trustee proves log_g(h_i) == log_{c1}(D_i) = s_i.
    """
    w = get_random_scalar(Q)
    a = pow(G, w, P)
    b = pow(c1, w, P)

    c = hash_to_scalar(G, verification_key_h_i, c1, d_i, a, b, order=Q)
    z = (w + c * share_value_s_i) % Q

    return TrusteeDLEQProof(a=a, b=b, c=c, z=z)


def verify_trustee_partial_decryption(
    verification_key_h_i: int, c1: int, d_i: int, proof: TrusteeDLEQProof
) -> bool:
    """
    Verify trustee partial decryption DLEQ proof.
    """
    try:
        c = hash_to_scalar(G, verification_key_h_i, c1, d_i, proof.a, proof.b, order=Q)
        if c != proof.c:
            return False

        # Check g^z == a * h_i^c mod p
        lhs_a = pow(G, proof.z, P)
        rhs_a = (proof.a * pow(verification_key_h_i, proof.c, P)) % P
        if lhs_a != rhs_a:
            return False

        # Check c1^z == b * D_i^c mod p
        lhs_b = pow(c1, proof.z, P)
        rhs_b = (proof.b * pow(d_i, proof.c, P)) % P
        if lhs_b != rhs_b:
            return False

        return True
    except Exception:
        return False


# ==========================================
# Schnorr NIZK (Knowledge of Secret Key)
# ==========================================

@dataclass(frozen=True)
class SchnorrProof:
    a: int
    c: int
    z: int

    def to_dict(self) -> Dict[str, str]:
        return {"a": hex(self.a), "c": hex(self.c), "z": hex(self.z)}

    @classmethod
    def from_dict(cls, d: Dict[str, str]) -> "SchnorrProof":
        return cls(a=int(d["a"], 16), c=int(d["c"], 16), z=int(d["z"], 16))


def prove_schnorr_knowledge(secret_key: int, public_key_h: int) -> SchnorrProof:
    """Generate Schnorr NIZK proof of knowledge of secret key x for h = g^x mod p."""
    w = get_random_scalar(Q)
    a = pow(G, w, P)
    c = hash_to_scalar(G, public_key_h, a, order=Q)
    z = (w + c * secret_key) % Q
    return SchnorrProof(a=a, c=c, z=z)


def verify_schnorr_knowledge(public_key_h: int, proof: SchnorrProof) -> bool:
    """Verify Schnorr NIZK proof."""
    try:
        c = hash_to_scalar(G, public_key_h, proof.a, order=Q)
        if c != proof.c:
            return False
        lhs = pow(G, proof.z, P)
        rhs = (proof.a * pow(public_key_h, proof.c, P)) % P
        return lhs == rhs
    except Exception:
        return False
