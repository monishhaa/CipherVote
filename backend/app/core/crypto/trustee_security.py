"""
Cryptographic Security Primitives for Trustee Codes, Link Tokens, and Encrypted Share Protection at Rest.

Requirements:
- Code storage: Per-slot scrypt/PBKDF2 hash with unique salt. Never store plaintext codes.
- Full passphrase commitment: Salted hash commitment of the ordered position-tagged concatenation:
  e.g. "T1:7K9AB2M4W8F63D1X7|T2:8M3ND4L1V7P92K0Y5|..."
- Encrypted shares at rest: Each trustee's ElGamal decryption key share s_i is encrypted under
  a key derived from that trustee's Crockford code. Without the trustee's code, the share cannot be decrypted.
- Constant-time verification on all sensitive comparisons.
"""

import hashlib
import hmac
import os
import secrets
from typing import List, Optional, Tuple
from .crockford import normalize_crockford


def derive_key_from_code(normalized_code: str, salt: bytes, length: int = 32) -> bytes:
    """Derives a symmetric key from a normalized Crockford code using scrypt (or PBKDF2 fallback)."""
    code_bytes = normalized_code.encode("utf-8")
    try:
        return hashlib.scrypt(code_bytes, salt=salt, n=16384, r=8, p=1, maxmem=32 * 1024 * 1024, dklen=length)
    except Exception:
        return hashlib.pbkdf2_hmac("sha256", code_bytes, salt, 100_000, dklen=length)


def hash_trustee_code(raw_code: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    """
    Computes secure salted hash of a trustee code for storage.
    Returns (hash_hex, salt_hex).
    """
    norm = normalize_crockford(raw_code)
    if not salt:
        salt = secrets.token_bytes(16)
    derived = derive_key_from_code(norm, salt, length=32)
    return derived.hex(), salt.hex()


def verify_trustee_code(input_code: str, stored_hash_hex: str, stored_salt_hex: str) -> bool:
    """
    Verifies an input code against stored hash in constant time.
    """
    if not stored_hash_hex or not stored_salt_hex:
        return False
    try:
        salt = bytes.fromhex(stored_salt_hex)
        expected_bytes = bytes.fromhex(stored_hash_hex)
        norm = normalize_crockford(input_code)
        derived = derive_key_from_code(norm, salt, length=32)
        return hmac.compare_digest(derived, expected_bytes)
    except Exception:
        return False


def hash_link_token(token: str) -> str:
    """Computes SHA-256 hash of a link token for lookup in DB."""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def encrypt_share_at_rest(share_value: int, raw_code: str) -> Tuple[str, str]:
    """
    Encrypts a trustee's secret share integer s_i under their code.
    Returns (encrypted_blob, salt_hex).
    """
    norm = normalize_crockford(raw_code)
    salt = secrets.token_bytes(16)
    iv = secrets.token_bytes(16)
    key = derive_key_from_code(norm, salt, length=32)

    plaintext = hex(share_value).encode("utf-8")
    
    # Authenticated keystream cipher (CTR-like stream + HMAC-SHA256 tag)
    keystream = b""
    counter = 0
    while len(keystream) < len(plaintext):
        block = hmac.new(key, iv + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        keystream += block
        counter += 1
    keystream = keystream[:len(plaintext)]
    
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, keystream))
    tag = hmac.new(key, iv + ciphertext, hashlib.sha256).digest()
    
    blob = f"v1:{salt.hex()}:{iv.hex()}:{ciphertext.hex()}:{tag.hex()}"
    return blob, salt.hex()


def decrypt_share_at_rest(encrypted_blob: str, raw_code: str) -> Optional[int]:
    """
    Decrypts a trustee's secret share integer s_i using their code.
    Returns None if code is invalid or tag verification fails.
    """
    if not encrypted_blob or not raw_code:
        return None
    try:
        parts = encrypted_blob.split(":")
        if len(parts) != 5 or parts[0] != "v1":
            return None
        
        salt = bytes.fromhex(parts[1])
        iv = bytes.fromhex(parts[2])
        ciphertext = bytes.fromhex(parts[3])
        tag = bytes.fromhex(parts[4])
        
        norm = normalize_crockford(raw_code)
        key = derive_key_from_code(norm, salt, length=32)
        
        # Verify HMAC tag in constant time
        expected_tag = hmac.new(key, iv + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_tag, tag):
            return None
        
        # Decrypt
        keystream = b""
        counter = 0
        while len(keystream) < len(ciphertext):
            block = hmac.new(key, iv + counter.to_bytes(4, "big"), hashlib.sha256).digest()
            keystream += block
            counter += 1
        keystream = keystream[:len(ciphertext)]
        
        plaintext = bytes(a ^ b for a, b in zip(ciphertext, keystream))
        val_str = plaintext.decode("utf-8")
        return int(val_str, 16)
    except Exception:
        return None


def compute_full_passphrase_commitment(
    ordered_position_codes: List[Tuple[int, str]], salt: Optional[bytes] = None
) -> Tuple[str, str]:
    """
    Computes a salted cryptographic commitment over the ordered position-tagged concatenation:
    "T1:<norm1>|T2:<norm2>|...|TN:<normN>"
    Returns (commitment_hex, salt_hex).
    """
    if not salt:
        salt = secrets.token_bytes(16)
    
    # Sort strictly by position 1..N
    sorted_parts = sorted(ordered_position_codes, key=lambda x: x[0])
    tagged_parts = [f"T{pos}:{normalize_crockford(code)}" for pos, code in sorted_parts]
    full_string = "|".join(tagged_parts)
    
    commitment = hmac.new(salt, full_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return commitment, salt.hex()


def verify_full_passphrase_commitment(
    ordered_position_codes: List[Tuple[int, str]], stored_commitment: str, stored_salt_hex: str
) -> bool:
    """
    Verifies that the provided collection of codes matches the stored commitment.
    """
    if not stored_commitment or not stored_salt_hex:
        return False
    try:
        salt = bytes.fromhex(stored_salt_hex)
        expected_commitment, _ = compute_full_passphrase_commitment(ordered_position_codes, salt=salt)
        return hmac.compare_digest(expected_commitment, stored_commitment)
    except Exception:
        return False
