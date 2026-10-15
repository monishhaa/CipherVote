"""
Cryptographic constants and group parameters for SecureVote.
Uses RFC 3526 2048-bit MODP Group 14 (Safe Prime p = 2q + 1, Generator g = 2).
"""

import hashlib
import secrets
from typing import Union

# RFC 3526 2048-bit MODP Group 14 Prime p
# p = 2^2048 - 2^1984 - 1 + 2^64 * { [2^1918 pi] + 124476 }
RFC3526_P_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF"
)

P = int(RFC3526_P_HEX, 16)
# Group order q for safe prime p = 2q + 1
Q = (P - 1) // 2
# Generator g
G = 2


def get_random_scalar(order: int = Q) -> int:
    """Generate a cryptographically secure random scalar in [1, order - 1]."""
    return secrets.randbelow(order - 1) + 1


def mod_inverse(a: int, m: int = Q) -> int:
    """Compute modular inverse a^(-1) mod m."""
    return pow(a, -1, m)


def hash_to_scalar(*args: Union[int, str, bytes], order: int = Q) -> int:
    """
    Fiat-Shamir hash function using SHA-256 mapped to integer scalar in [1, order - 1].
    Accepts integers, strings, or bytes.
    """
    hasher = hashlib.sha256()
    for arg in args:
        if isinstance(arg, int):
            # Encode integer as big-endian hex/bytes
            hex_str = hex(arg)[2:]
            if len(hex_str) % 2 != 0:
                hex_str = "0" + hex_str
            hasher.update(bytes.fromhex(hex_str))
        elif isinstance(arg, str):
            hasher.update(arg.encode("utf-8"))
        elif isinstance(arg, bytes):
            hasher.update(arg)
        hasher.update(b"|")  # domain separation delimiter
    digest = hasher.digest()
    return int.from_bytes(digest, "big") % order
