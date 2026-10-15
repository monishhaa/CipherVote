"""
Append-Only Cryptographic Hash Chain for SecureVote Bulletin Board.
Enforces verifiable sequential ordering and tamper-evident history:
H_0 = SHA-256("GENESIS:" + ElectionID)
H_i = SHA-256(H_{i-1} || Sequence_i || Timestamp_i || CiphertextHash_i || TokenSigHash_i)
"""

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple


def compute_genesis_hash(election_id: str) -> str:
    """Compute deterministic genesis hash for an election."""
    return hashlib.sha256(f"SECUREVOTE:GENESIS:{election_id}".encode("utf-8")).hexdigest()


def compute_ballot_payload_hash(
    sequence_number: int,
    timestamp: int,
    ciphertexts_json: str,
    token_signature: str,
    previous_hash: str,
) -> str:
    """
    Compute block hash for an incoming ballot entry:
    H_i = SHA256(H_{i-1} || Seq || Ts || Hash(Ciphertexts) || Hash(Sig))
    """
    hasher = hashlib.sha256()
    hasher.update(previous_hash.encode("utf-8"))
    hasher.update(b"|")
    hasher.update(str(sequence_number).encode("utf-8"))
    hasher.update(b"|")
    hasher.update(str(timestamp).encode("utf-8"))
    hasher.update(b"|")
    hasher.update(hashlib.sha256(ciphertexts_json.encode("utf-8")).hexdigest().encode("utf-8"))
    hasher.update(b"|")
    hasher.update(hashlib.sha256(token_signature.encode("utf-8")).hexdigest().encode("utf-8"))
    return hasher.hexdigest()


@dataclass
class BulletinBoardEntry:
    sequence_number: int
    timestamp: int
    ciphertexts: List[Dict[str, str]]
    zkp_proofs: Dict[str, Any]
    token_signature: str
    receipt_code: str
    previous_hash: str
    block_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence_number": self.sequence_number,
            "timestamp": self.timestamp,
            "ciphertexts": self.ciphertexts,
            "zkp_proofs": self.zkp_proofs,
            "token_signature": self.token_signature,
            "receipt_code": self.receipt_code,
            "previous_hash": self.previous_hash,
            "block_hash": self.block_hash,
        }


def verify_hash_chain(
    election_id: str, entries: List[BulletinBoardEntry]
) -> Tuple[bool, Optional[str]]:
    """
    Verify complete cryptographic integrity of the bulletin board hash chain.
    Returns (is_valid, error_message_if_any).
    """
    if not entries:
        return True, None

    expected_prev = compute_genesis_hash(election_id)

    for idx, entry in enumerate(entries, start=1):
        if entry.sequence_number != idx:
            return False, f"Sequence number mismatch at index {idx}: got {entry.sequence_number}"

        if entry.previous_hash != expected_prev:
            return (
                False,
                f"Previous hash broken at sequence {entry.sequence_number}. "
                f"Expected {expected_prev}, got {entry.previous_hash}",
            )

        cts_json = json.dumps(entry.ciphertexts, sort_keys=True)
        computed_hash = compute_ballot_payload_hash(
            sequence_number=entry.sequence_number,
            timestamp=entry.timestamp,
            ciphertexts_json=cts_json,
            token_signature=entry.token_signature,
            previous_hash=entry.previous_hash,
        )

        if computed_hash != entry.block_hash:
            return (
                False,
                f"Block hash integrity failure at sequence {entry.sequence_number}. "
                f"Computed {computed_hash}, stored {entry.block_hash}",
            )

        expected_prev = entry.block_hash

    return True, None
