"""
Chaum RSA Blind Signature Scheme (RSA-2048).
Provides cryptographic unlinkability between authenticated voter identities
and anonymous voting tokens.
"""

from dataclasses import dataclass
import hashlib
import math
import secrets
from typing import Dict, Tuple


SMALL_PRIMES = [
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71,
    73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151,
    157, 163, 167, 173, 179, 181, 191, 193, 197, 199, 211, 223, 227, 229, 233,
    239, 241, 251, 257, 263, 269, 271, 277, 281, 283, 293, 307, 311, 313, 317,
    331, 337, 347, 349, 353, 359, 367, 373, 379, 383, 389, 397, 401, 409, 419,
    421, 431, 433, 439, 443, 449, 457, 461, 463, 467, 479, 487, 491, 499, 503,
]


def _is_probable_prime(n: int, k: int = 20) -> bool:
    """Miller-Rabin primality test with small primes pre-sieve."""
    if n < 2:
        return False
    for p in SMALL_PRIMES:
        if n == p:
            return True
        if n % p == 0:
            return False

    r, d = 0, n - 1
    while d % 2 == 0:
        r += 1
        d //= 2

    for _ in range(k):
        a = secrets.randbelow(n - 4) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _generate_prime(bits: int) -> int:
    """Generate a random prime of the specified bit length."""
    while True:
        p = secrets.randbits(bits)
        # Ensure bit length and oddness
        p |= (1 << (bits - 1)) | 1
        if _is_probable_prime(p):
            return p


@dataclass(frozen=True)
class RSABlindPublicKey:
    n: int
    e: int = 65537

    def to_dict(self) -> Dict[str, str]:
        return {"n": hex(self.n), "e": hex(self.e)}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "RSABlindPublicKey":
        return cls(n=int(data["n"], 16), e=int(data.get("e", "0x10001"), 16))


@dataclass(frozen=True)
class RSABlindPrivateKey:
    n: int
    d: int
    public_key: RSABlindPublicKey

    def to_dict(self) -> Dict[str, str]:
        return {"n": hex(self.n), "d": hex(self.d), "e": hex(self.public_key.e)}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "RSABlindPrivateKey":
        n = int(data["n"], 16)
        d = int(data["d"], 16)
        e = int(data.get("e", "0x10001"), 16)
        return cls(n=n, d=d, public_key=RSABlindPublicKey(n=n, e=e))


def generate_blind_rsa_keypair(bits: int = 2048) -> RSABlindPrivateKey:
    """Generate RSA keypair for Chaum blind signatures."""
    e = 65537
    half_bits = bits // 2
    while True:
        p = _generate_prime(half_bits)
        q = _generate_prime(half_bits)
        if p == q:
            continue
        phi = (p - 1) * (q - 1)
        if math.gcd(e, phi) == 1:
            d = pow(e, -1, phi)
            n = p * q
            return RSABlindPrivateKey(n=n, d=d, public_key=RSABlindPublicKey(n=n, e=e))


def hash_message_to_int(message: str, n: int) -> int:
    """Full Domain Hash mapping string message into Zn*."""
    # Deterministic expansion using SHA-256 rounds
    counter = 0
    while True:
        h = hashlib.sha256(f"{message}:{counter}".encode("utf-8")).digest()
        val = int.from_bytes(h, "big")
        if 1 < val < n and math.gcd(val, n) == 1:
            return val
        counter += 1


def blind_message(message: str, pk: RSABlindPublicKey) -> Tuple[int, int, int]:
    """
    Client blinds message m:
    1. m_int = H(message) mod N
    2. Pick random r in Zn*
    3. Blinded message m' = (m_int * r^e) mod N
    Returns (m_prime, r, m_int).
    """
    m_int = hash_message_to_int(message, pk.n)
    while True:
        r = secrets.randbelow(pk.n - 2) + 2
        if math.gcd(r, pk.n) == 1:
            break
    r_e = pow(r, pk.e, pk.n)
    m_prime = (m_int * r_e) % pk.n
    return m_prime, r, m_int


def blind_sign(sk: RSABlindPrivateKey, m_prime: int) -> int:
    """
    Server blind-signs blinded message m':
    s' = (m')^d mod N
    """
    return pow(m_prime, sk.d, sk.n)


def unblind_signature(s_prime: int, r: int, pk: RSABlindPublicKey) -> int:
    """
    Client unblinds signature s':
    s = (s' * r^(-1)) mod N
    """
    r_inv = pow(r, -1, pk.n)
    s = (s_prime * r_inv) % pk.n
    return s


def verify_blind_signature(message: str, signature: int, pk: RSABlindPublicKey) -> bool:
    """
    Public verification: check (s^e) mod N == H(message) mod N.
    """
    try:
        m_int = hash_message_to_int(message, pk.n)
        recovered_m = pow(signature, pk.e, pk.n)
        return recovered_m == m_int
    except Exception:
        return False
