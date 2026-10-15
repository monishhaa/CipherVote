"""
Bulletin Board package for SecureVote.
"""

from .hash_chain import (
    BulletinBoardEntry,
    compute_ballot_payload_hash,
    compute_genesis_hash,
    verify_hash_chain,
)
from .merkle_tree import MerkleInclusionProof, MerkleTree, verify_merkle_proof

__all__ = [
    "BulletinBoardEntry",
    "compute_ballot_payload_hash",
    "compute_genesis_hash",
    "verify_hash_chain",
    "MerkleTree",
    "MerkleInclusionProof",
    "verify_merkle_proof",
]
