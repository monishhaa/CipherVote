"""
Cryptographic Time-Lock & Election Clock Manager.
Provides verifiable time-gated key derivation and Sloth VDF simulation
so Share B cannot be decrypted by anyone before election opening time.
"""

from dataclasses import dataclass
import hashlib
import hmac
import time
from typing import Dict, Optional, Tuple
from .constants import P, Q


def derive_timelock_key(master_secret: bytes, election_id: str, open_timestamp: int) -> bytes:
    """
    Derive symmetric key bound to election and open timestamp using HKDF-like HMAC construction.
    """
    salt = f"SECUREVOTE:TIMELOCK:{election_id}".encode("utf-8")
    info = f"EPOCH:{open_timestamp}".encode("utf-8")
    prk = hmac.new(salt, master_secret, hashlib.sha256).digest()
    return hmac.new(prk, info, hashlib.sha256).digest()


def encrypt_share_b(share_b_hex: str, timelock_key: bytes) -> str:
    """
    Encrypt Share B with timelock key using XOR mask with SHA-256 stream and HMAC integrity.
    """
    hex_clean = share_b_hex[2:] if share_b_hex.startswith("0x") else share_b_hex
    if len(hex_clean) % 2 != 0:
        hex_clean = "0" + hex_clean
    raw_data = bytes.fromhex(hex_clean)
    # Stream key
    keystream = hashlib.sha256(timelock_key + b"ENCRYPT").digest()
    # Repeat keystream if needed
    while len(keystream) < len(raw_data):
        keystream += hashlib.sha256(keystream).digest()
    keystream = keystream[:len(raw_data)]

    ciphertext = bytes(a ^ b for a, b in zip(raw_data, keystream))
    tag = hmac.new(timelock_key, ciphertext, hashlib.sha256).hexdigest()
    return f"{ciphertext.hex()}:{tag}"


def decrypt_share_b(encrypted_blob: str, timelock_key: bytes) -> Optional[str]:
    """
    Decrypt Share B if given valid timelock key.
    """
    try:
        parts = encrypted_blob.split(":")
        if len(parts) != 2:
            return None
        ct_hex, tag = parts
        ciphertext = bytes.fromhex(ct_hex)

        # Verify HMAC tag
        expected_tag = hmac.new(timelock_key, ciphertext, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_tag, tag):
            return None

        keystream = hashlib.sha256(timelock_key + b"ENCRYPT").digest()
        while len(keystream) < len(ciphertext):
            keystream += hashlib.sha256(keystream).digest()
        keystream = keystream[:len(ciphertext)]

        plaintext = bytes(a ^ b for a, b in zip(ciphertext, keystream))
        return hex(int.from_bytes(plaintext, "big"))
    except Exception:
        return None


# ==========================================
# Sloth VDF (Verifiable Delay Function)
# ==========================================

def _sloth_step(x: int, p: int) -> int:
    """One sequential step in Sloth permutation."""
    half = (p - 1) // 2
    is_qr = (pow(x, half, p) == 1)
    base = x if is_qr else (-x % p)
    sqrt_val = pow(base, (p + 1) // 4, p)
    # Choose canonical square root in [1, (p-1)/2]
    if sqrt_val > half:
        sqrt_val = p - sqrt_val
    return sqrt_val if is_qr else (p - sqrt_val)


def _sloth_step_verify(y: int, p: int) -> int:
    """One verification step in Sloth permutation (squaring)."""
    half = (p - 1) // 2
    if y <= half:
        return pow(y, 2, p)
    else:
        return (-pow(y, 2, p)) % p


def compute_sloth_vdf(seed: int, iterations: int, prime: int = P) -> int:
    """
    Sloth VDF evaluation: sequential modular square root iterations.
    Cannot be parallelized; enforces physical sequential delay.
    """
    val = (seed % prime)
    if val <= 1:
        val = 2
    for _ in range(iterations):
        val = _sloth_step(val, prime)
    return val


def verify_sloth_vdf(seed: int, solution: int, iterations: int, prime: int = P) -> bool:
    """
    Sloth VDF verification: successive squaring back to seed.
    """
    try:
        val = solution % prime
        for _ in range(iterations):
            val = _sloth_step_verify(val, prime)
        expected = seed % prime
        if expected <= 1:
            expected = 2
        return (val % prime) == expected
    except Exception:
        return False


@dataclass
class ElectionClock:
    """
    Election clock manager supporting real-time and fast-forward simulation.
    """
    open_time: int
    close_time: int
    simulated_offset: int = 0  # In seconds

    @property
    def current_time(self) -> int:
        return int(time.time()) + self.simulated_offset

    @property
    def is_open(self) -> bool:
        return self.open_time <= self.current_time < self.close_time

    @property
    def is_closed(self) -> bool:
        return self.current_time >= self.close_time

    @property
    def is_pre_election(self) -> bool:
        return self.current_time < self.open_time

    def warp_to(self, target_timestamp: int):
        """Simulate fast-forwarding the clock to a specific timestamp."""
        self.simulated_offset = target_timestamp - int(time.time())

    def warp_to_open(self):
        """Fast-forward to election open time."""
        self.warp_to(self.open_time + 1)

    def warp_to_closed(self):
        """Fast-forward to election close time."""
        self.warp_to(self.close_time + 1)
