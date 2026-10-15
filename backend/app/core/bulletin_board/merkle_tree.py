"""
Merkle Tree & Inclusion Proof Generator for SecureVote Bulletin Board.
Enables instant receipt verification with O(log N) proof size.
"""

from dataclasses import dataclass
import hashlib
from typing import Dict, List, Optional, Tuple


def _hash_pair(left: str, right: str) -> str:
    """Combine two hex child hashes."""
    hasher = hashlib.sha256()
    hasher.update(bytes.fromhex(left))
    hasher.update(bytes.fromhex(right))
    return hasher.hexdigest()


@dataclass
class MerkleInclusionProof:
    leaf_hash: str
    leaf_index: int
    total_leaves: int
    audit_path: List[Dict[str, str]]  # List of {"position": "left"|"right", "hash": "..."}
    root_hash: str


class MerkleTree:
    def __init__(self, leaf_hashes: List[str]):
        if not leaf_hashes:
            self.leaves = [hashlib.sha256(b"EMPTY_MERKLE_TREE").hexdigest()]
        else:
            self.leaves = list(leaf_hashes)
        self.levels: List[List[str]] = [self.leaves]
        self._build_tree()

    def _build_tree(self):
        current_level = self.leaves
        while len(current_level) > 1:
            next_level: List[str] = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else current_level[i]
                next_level.append(_hash_pair(left, right))
            self.levels.append(next_level)
            current_level = next_level

    @property
    def root(self) -> str:
        return self.levels[-1][0]

    def get_proof(self, index: int) -> Optional[MerkleInclusionProof]:
        """Generate Merkle audit path proof for leaf at given index."""
        if index < 0 or index >= len(self.leaves):
            return None

        audit_path: List[Dict[str, str]] = []
        cur_idx = index
        for level in self.levels[:-1]:
            is_right_sibling = (cur_idx % 2 == 0)
            sibling_idx = cur_idx + 1 if is_right_sibling else cur_idx - 1

            if sibling_idx < len(level):
                sibling_hash = level[sibling_idx]
            else:
                sibling_hash = level[cur_idx]  # duplicate odd leaf

            audit_path.append({
                "position": "right" if is_right_sibling else "left",
                "hash": sibling_hash,
            })
            cur_idx //= 2

        return MerkleInclusionProof(
            leaf_hash=self.leaves[index],
            leaf_index=index,
            total_leaves=len(self.leaves),
            audit_path=audit_path,
            root_hash=self.root,
        )


def verify_merkle_proof(proof: MerkleInclusionProof) -> bool:
    """Verify Merkle inclusion proof against root hash."""
    current_hash = proof.leaf_hash
    for step in proof.audit_path:
        sibling = step["hash"]
        if step["position"] == "right":
            current_hash = _hash_pair(current_hash, sibling)
        else:
            current_hash = _hash_pair(sibling, current_hash)
    return current_hash == proof.root_hash
