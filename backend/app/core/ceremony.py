"""
Stateful All-Trustees Unlock Ceremony Engine & Real-time WebSocket/Presence Hub.

Enforces:
1. Presence tracking: Heartbeat every 5s. Absent if no heartbeat for 15s.
2. N-of-N presence: Submissions blocked unless ALL N trustees are currently active and present.
3. Strict sequential order: Positions 1 through N must be submitted in exact order.
4. Window timer: Configurable (default 5 min). Expiry resets the round.
5. Error & Tamper reset: Wrong code, out-of-order entry, mid-round disconnect, or expiry resets all accepted slots with broadcast explanation.
6. Lockout: 3 consecutive wrong codes locks the trustee slot for 10 minutes.
7. Verification & Unlock: Constant-time commitment check -> 30-min authenticated session + in-memory decrypted key share.
8. Post-Unlock Validation Console: Independent verification, partial ElGamal decryptions with DLEQ proofs, memory wipe on approval.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import WebSocket

from app.core.crypto.crockford import parse_and_validate_trustee_code
from app.core.crypto.trustee_security import (
    verify_trustee_code,
    decrypt_share_at_rest,
    verify_full_passphrase_commitment,
)
from app.core.crypto.elgamal import Ciphertext
from app.core.crypto.constants import G, P, Q, get_random_scalar, mod_inverse
from app.core.crypto.shamir import TrusteeShare, compute_partial_decryption

logger = logging.getLogger("securevote.ceremony")
logger.setLevel(logging.INFO)

HEARTBEAT_TIMEOUT_SECONDS = 15
SESSION_DURATION_SECONDS = 30 * 60  # 30 minutes


class CeremonyState:
    def __init__(self, election_id: str, num_trustees: int, window_minutes: int = 5):
        self.election_id = election_id
        self.num_trustees = num_trustees
        self.window_seconds = window_minutes * 60
        self.status = "WAITING"  # WAITING, IN_PROGRESS, UNLOCKED, COMPLETED
        self.accepted_positions: Set[int] = set()
        self.accepted_codes: Dict[int, str] = {}  # {pos: norm_code}
        self.round_started_at: Optional[float] = None
        self.round_expires_at: Optional[float] = None
        self.reset_reason: Optional[str] = None
        
        # Trustee Presence: {pos: {"last_seen": float, "token_hash": str, "name": str, "email": str}}
        self.trustees: Dict[int, Dict[str, Any]] = {}
        # Active WebSockets: {pos: set(WebSocket)}
        self.websockets: Dict[int, Set[WebSocket]] = {i: set() for i in range(1, num_trustees + 1)}
        
        # Lockout tracking: {pos: {"failed_count": int, "locked_until": float}}
        self.lockouts: Dict[int, Dict[str, Any]] = {i: {"failed_count": 0, "locked_until": 0.0} for i in range(1, num_trustees + 1)}
        
        # In-memory unlocked sessions: {token_hash: {"pos": int, "expires_at": float, "decrypted_share": int}}
        self.unlocked_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Event Log: list of {"time": str, "type": str, "message": str, "position": Optional[int]}
        self.event_log: List[Dict[str, Any]] = []

    def log_event(self, event_type: str, message: str, position: Optional[int] = None):
        entry = {
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "type": event_type,
            "message": message,
            "position": position,
        }
        self.event_log.append(entry)
        if len(self.event_log) > 100:
            self.event_log.pop(0)

    def is_trustee_locked(self, position: int) -> Tuple[bool, int]:
        now = time.time()
        lock_info = self.lockouts.get(position, {"failed_count": 0, "locked_until": 0.0})
        if lock_info["locked_until"] > now:
            remaining = int(lock_info["locked_until"] - now)
            return True, remaining
        return False, 0

    def record_failed_attempt(self, position: int):
        now = time.time()
        info = self.lockouts.setdefault(position, {"failed_count": 0, "locked_until": 0.0})
        info["failed_count"] += 1
        if info["failed_count"] >= 3:
            info["locked_until"] = now + 600  # 10 minute lockout
            self.log_event("LOCKOUT", f"Trustee #{position} locked out for 10 minutes due to 3 failed attempts.", position)
        else:
            self.log_event("CODE_REJECTED", f"Incorrect code entered for Trustee #{position} ({info['failed_count']}/3 attempts).", position)

    def reset_failed_attempts(self, position: int):
        if position in self.lockouts:
            self.lockouts[position]["failed_count"] = 0
            self.lockouts[position]["locked_until"] = 0.0

    def record_presence(self, position: int, token_hash: str, name: str, email: str):
        now = time.time()
        was_present = self.is_present(position)
        self.trustees[position] = {
            "last_seen": now,
            "token_hash": token_hash,
            "name": name,
            "email": email,
        }
        if not was_present:
            self.log_event("JOINED", f"Trustee #{position} ({name}) connected.", position)

    def is_present(self, position: int) -> bool:
        info = self.trustees.get(position)
        if not info:
            return False
        return (time.time() - info["last_seen"]) < HEARTBEAT_TIMEOUT_SECONDS

    def get_present_count(self) -> int:
        return sum(1 for pos in range(1, self.num_trustees + 1) if self.is_present(pos))

    def all_trustees_present(self) -> bool:
        return all(self.is_present(pos) for pos in range(1, self.num_trustees + 1))

    def check_active_round_timeout_and_disconnects(self) -> bool:
        """
        Periodically called: checks if active round expired or if a trustee disconnected mid-round.
        Returns True if a reset occurred.
        """
        if self.status not in ("IN_PROGRESS",):
            return False

        now = time.time()
        # 1. Check window expiration
        if self.round_expires_at and now > self.round_expires_at:
            self.reset_round("Round window expired before all codes were submitted.")
            return True

        # 2. Check if any trustee disconnected mid-round
        for pos in range(1, self.num_trustees + 1):
            if not self.is_present(pos):
                self.reset_round(f"Trustee #{pos} disconnected during the active unlock round.")
                return True

        return False

    def reset_round(self, reason: str):
        self.status = "WAITING"
        self.accepted_positions.clear()
        self.accepted_codes.clear()
        self.round_started_at = None
        self.round_expires_at = None
        self.reset_reason = reason
        self.log_event("ROUND_RESET", f"Ceremony round reset: {reason}")

    def to_public_dict(self, viewer_position: Optional[int] = None) -> Dict[str, Any]:
        now = time.time()
        remaining_seconds = 0
        if self.round_expires_at and self.status == "IN_PROGRESS":
            remaining_seconds = max(0, int(self.round_expires_at - now))

        slots = []
        for pos in range(1, self.num_trustees + 1):
            t_info = self.trustees.get(pos, {})
            is_pres = self.is_present(pos)
            is_acc = pos in self.accepted_positions
            locked, lock_rem = self.is_trustee_locked(pos)
            slots.append({
                "position": pos,
                "name": t_info.get("name", f"Trustee {pos}"),
                "is_present": is_pres,
                "is_accepted": is_acc,
                "is_locked": locked,
                "lockout_remaining_seconds": lock_rem,
                "is_you": (pos == viewer_position),
            })

        # Next expected position in strict 1..N order
        next_pos = None
        if self.status != "UNLOCKED" and self.status != "COMPLETED":
            for pos in range(1, self.num_trustees + 1):
                if pos not in self.accepted_positions:
                    next_pos = pos
                    break

        return {
            "election_id": self.election_id,
            "num_trustees": self.num_trustees,
            "status": self.status,
            "all_present": self.all_trustees_present(),
            "present_count": self.get_present_count(),
            "next_expected_position": next_pos,
            "accepted_count": len(self.accepted_positions),
            "remaining_seconds": remaining_seconds,
            "window_seconds": self.window_seconds,
            "reset_reason": self.reset_reason,
            "slots": slots,
            "event_log": self.event_log[-15:],
        }


# Global In-Memory Registry for Election Ceremonies
_CEREMONIES: Dict[str, CeremonyState] = {}


def get_or_create_ceremony(election_id: str, num_trustees: int, window_minutes: int = 5) -> CeremonyState:
    if election_id not in _CEREMONIES:
        _CEREMONIES[election_id] = CeremonyState(election_id, num_trustees, window_minutes)
    else:
        # Update parameters if needed
        state = _CEREMONIES[election_id]
        state.num_trustees = num_trustees
        state.window_seconds = window_minutes * 60
    return _CEREMONIES[election_id]


def get_ceremony_state(election_id: str) -> Optional[CeremonyState]:
    return _CEREMONIES.get(election_id)


async def broadcast_ceremony_state(state: CeremonyState):
    """Pushes live ceremony updates to all connected WebSockets."""
    for pos, sockets in state.websockets.items():
        payload = json.dumps(state.to_public_dict(viewer_position=pos))
        to_remove = set()
        for ws in sockets:
            try:
                await ws.send_text(payload)
            except Exception:
                to_remove.add(ws)
        sockets.difference_update(to_remove)
