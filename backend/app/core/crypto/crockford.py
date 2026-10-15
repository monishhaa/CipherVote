"""
Crockford Base32 Encoding, Checksum, and Normalization for CipherVote Trustee Codes.

Conforms to Douglas Crockford's Base32 specification:
- Alphabet: 0123456789ABCDEFGHJKMNPQRSTVWXYZ (32 symbols, excludes I, L, O, U)
- Normalization:
  - 'i', 'I', 'l', 'L' -> '1'
  - 'o', 'O' -> '0'
  - dashes, spaces, and punctuation are stripped
  - case-insensitive
- 80-bit random entropy -> 16 Crockford Base32 characters + 1 check character in 4 groups of 4:
  e.g. "T1-7K9A-B2M4-W8F6-3D1X-7" (or position-tagged "T1:7K9A-B2M4-W8F6-3D1X")
"""

import re
import secrets
from typing import Tuple

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CROCKFORD_CHECK_SYMBOLS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ*~$=U"
CROCKFORD_DECODE_MAP = {c: i for i, c in enumerate(CROCKFORD_ALPHABET)}


def normalize_crockford(input_str: str) -> str:
    """
    Normalizes a Crockford Base32 input string:
    - Uppercases
    - Replaces 'I', 'L' with '1'
    - Replaces 'O' with '0'
    - Strips leading position tags (e.g. "T1", "T2", "T3"...) if followed by full code
    - Strips all non-alphanumeric characters (spaces, dashes, colons, etc.)
    """
    if not input_str:
        return ""
    
    cleaned = input_str.strip().upper()
    
    # Strip leading position tag like "T1-", "T1:", "T1 " or "T1"
    match = re.match(r"^T\d+[\s:\-_]*(.*)$", cleaned)
    if match and len(match.group(1).replace("-", "").replace(" ", "")) >= 16:
        cleaned = match.group(1)
    
    # Replace lookalikes
    cleaned = cleaned.replace("I", "1").replace("L", "1").replace("O", "0")
    # Remove dashes, spaces, and formatting
    cleaned = re.sub(r"[^0-9A-Z*~$=U]", "", cleaned)
    return cleaned


def compute_crockford_checksum(payload_chars: str) -> str:
    """
    Computes Crockford Modulo-37 Check Symbol over normalized characters.
    """
    total = 0
    for char in payload_chars:
        val = CROCKFORD_DECODE_MAP.get(char, 0)
        total = (total * 32 + val) % 37
    return CROCKFORD_CHECK_SYMBOLS[total]


def verify_crockford_checksum(payload_chars: str, check_char: str) -> bool:
    """Verifies that the provided check character matches the payload."""
    expected = compute_crockford_checksum(payload_chars)
    return check_char.upper() == expected


def encode_crockford_80bit(raw_bytes: bytes) -> str:
    """
    Encodes 10 bytes (80 bits) into 16 Crockford Base32 characters.
    """
    if len(raw_bytes) != 10:
        raise ValueError("raw_bytes must be exactly 10 bytes (80 bits)")
    
    num = int.from_bytes(raw_bytes, "big")
    chars = []
    for _ in range(16):
        val = num & 0x1F
        chars.append(CROCKFORD_ALPHABET[val])
        num >>= 5
    
    # Characters were extracted least-significant bit first, so reverse
    chars.reverse()
    return "".join(chars)


def generate_trustee_code(position: int) -> Tuple[str, str, str]:
    """
    Generates a secure 80-bit trustee code.
    Returns:
    - display_code: formatted string e.g. "T1-7K9A-B2M4-W8F6-3D1X-7"
    - raw_code: normalized canonical payload e.g. "7K9AB2M4W8F63D1X7"
    - position_tag: e.g. "T1"
    """
    raw_bytes = secrets.token_bytes(10)
    base_chars = encode_crockford_80bit(raw_bytes)
    check_char = compute_crockford_checksum(base_chars)
    
    pos_tag = f"T{position}"
    formatted = f"{pos_tag}-{base_chars[0:4]}-{base_chars[4:8]}-{base_chars[8:12]}-{base_chars[12:16]}-{check_char}"
    canonical_raw = f"{base_chars}{check_char}"
    
    return formatted, canonical_raw, pos_tag


def parse_and_validate_trustee_code(input_code: str, expected_position: int) -> Tuple[bool, str, str]:
    """
    Validates and normalizes a trustee code.
    Returns (is_valid, normalized_payload, error_msg).
    """
    norm = normalize_crockford(input_code)
    
    if len(norm) == 17:
        payload = norm[:16]
        check = norm[16]
        if not verify_crockford_checksum(payload, check):
            return False, "", "Invalid code checksum. Please check for mistyped characters."
        return True, norm, ""
    elif len(norm) == 16:
        # User entered 16 characters without check symbol
        check = compute_crockford_checksum(norm)
        return True, f"{norm}{check}", ""
    else:
        return False, "", f"Code must be 16 characters (or 17 with check digit), got {len(norm)}."
