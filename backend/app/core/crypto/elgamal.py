"""
Additive / Exponential ElGamal cryptosystem over RFC 3526 2048-bit MODP Group.
Provides homomorphic addition of encrypted votes:
E(v1) * E(v2) = E(v1 + v2 mod q)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math
from .constants import G, P, Q, get_random_scalar


@dataclass(frozen=True)
class PublicKey:
    h: int  # h = g^x mod p

    def to_dict(self) -> Dict[str, str]:
        return {"h": hex(self.h)}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "PublicKey":
        return cls(h=int(data["h"], 16))


@dataclass(frozen=True)
class PrivateKey:
    x: int  # secret key x in [1, q-1]
    public_key: PublicKey

    def to_dict(self) -> Dict[str, str]:
        return {"x": hex(self.x), "h": hex(self.public_key.h)}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "PrivateKey":
        x = int(data["x"], 16)
        h = int(data["h"], 16)
        return cls(x=x, public_key=PublicKey(h=h))


@dataclass(frozen=True)
class Ciphertext:
    c1: int  # c1 = g^r mod p
    c2: int  # c2 = h^r * g^m mod p

    def to_dict(self) -> Dict[str, str]:
        return {"c1": hex(self.c1), "c2": hex(self.c2)}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "Ciphertext":
        return cls(c1=int(data["c1"], 16), c2=int(data["c2"], 16))


def generate_keypair() -> PrivateKey:
    """Generate a fresh ElGamal keypair."""
    x = get_random_scalar(Q)
    h = pow(G, x, P)
    return PrivateKey(x=x, public_key=PublicKey(h=h))


def encrypt(pk: PublicKey, m: int, r: Optional[int] = None) -> Tuple[Ciphertext, int]:
    """
    Encrypt message m (an integer vote, typically 0 or 1).
    Returns (Ciphertext, randomness_r).
    c1 = g^r mod p
    c2 = (h^r * g^m) mod p
    """
    if r is None:
        r = get_random_scalar(Q)
    c1 = pow(G, r, P)
    hr = pow(pk.h, r, P)
    gm = pow(G, m, P)
    c2 = (hr * gm) % P
    return Ciphertext(c1=c1, c2=c2), r


def homomorphic_add(ct1: Ciphertext, ct2: Ciphertext) -> Ciphertext:
    """Homomorphically add two encrypted ciphertexts: E(m1 + m2)."""
    c1 = (ct1.c1 * ct2.c1) % P
    c2 = (ct1.c2 * ct2.c2) % P
    return Ciphertext(c1=c1, c2=c2)


def homomorphic_sum(ciphertexts: List[Ciphertext]) -> Ciphertext:
    """Homomorphically sum a list of encrypted ciphertexts."""
    if not ciphertexts:
        return Ciphertext(c1=1, c2=1)
    c1_total = 1
    c2_total = 1
    for ct in ciphertexts:
        c1_total = (c1_total * ct.c1) % P
        c2_total = (c2_total * ct.c2) % P
    return Ciphertext(c1=c1_total, c2=c2_total)


# Global precomputed lookup table for small vote tallies [0..10,000]
_DLOG_TABLE: Dict[int, int] = {}


def _init_dlog_table(limit: int = 10000):
    global _DLOG_TABLE
    if len(_DLOG_TABLE) >= limit:
        return
    cur = 1
    for v in range(limit + 1):
        _DLOG_TABLE[cur] = v
        cur = (cur * G) % P


def solve_discrete_log(g_m: int, max_votes: int = 10000) -> int:
    """
    Solve g^m = g_m mod p for m in [0, max_votes].
    Uses precomputed hash table or Baby-Step Giant-Step.
    """
    if not _DLOG_TABLE or max_votes > len(_DLOG_TABLE):
        _init_dlog_table(max(max_votes, 10000))

    if g_m in _DLOG_TABLE:
        return _DLOG_TABLE[g_m]

    # Baby-Step Giant-Step fallback for larger vote counts
    m_step = int(math.isqrt(max_votes)) + 1
    table = {}
    cur = 1
    for j in range(m_step):
        table[cur] = j
        cur = (cur * G) % P

    g_inv_m = pow(pow(G, m_step, P), -1, P)
    gamma = g_m
    for i in range(m_step):
        if gamma in table:
            return i * m_step + table[gamma]
        gamma = (gamma * g_inv_m) % P

    raise ValueError(f"Discrete logarithm not found within bound {max_votes}")


def decrypt(sk: PrivateKey, ct: Ciphertext, max_votes: int = 10000) -> int:
    """
    Decrypt ciphertext using private key x.
    1. Compute M = c2 * (c1^x)^(-1) mod p = g^m mod p
    2. Solve discrete logarithm m = log_g(M).
    """
    c1_x = pow(ct.c1, sk.x, P)
    c1_x_inv = pow(c1_x, -1, P)
    g_m = (ct.c2 * c1_x_inv) % P
    return solve_discrete_log(g_m, max_votes=max_votes)
