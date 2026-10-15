"""
Cryptographic Password Hashing, Session Token Generation, and Rate Limiting.
"""

import base64
import hashlib
import hmac
import os
import time
from typing import Dict, Optional, Tuple
from fastapi import Header, HTTPException, status
from app.config import settings

# In-memory rate-limiter: tracking attempts by key (IP or identifier)
_login_attempts: Dict[str, list] = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 60


def check_rate_limit(key: str) -> None:
    """Enforce rate limiting on authentication attempts."""
    now = time.time()
    clean_key = key.strip().lower()
    attempts = _login_attempts.get(clean_key, [])
    # Filter attempts within lockout window
    recent = [t for t in attempts if now - t < LOCKOUT_SECONDS]
    _login_attempts[clean_key] = recent

    if len(recent) >= MAX_FAILED_ATTEMPTS:
        remaining = int(LOCKOUT_SECONDS - (now - recent[0]))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please wait {max(1, remaining)} seconds before trying again.",
        )


def record_failed_attempt(key: str) -> None:
    """Record a failed authentication attempt for rate limiting."""
    now = time.time()
    clean_key = key.strip().lower()
    attempts = _login_attempts.get(clean_key, [])
    attempts.append(now)
    _login_attempts[clean_key] = attempts


def reset_rate_limit(key: str) -> None:
    """Clear failed attempts upon successful login."""
    clean_key = key.strip().lower()
    if clean_key in _login_attempts:
        del _login_attempts[clean_key]


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with cryptographically random salt."""
    salt = os.urandom(16)
    iterations = 100_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_b64 = base64.b64encode(salt).decode("utf-8")
    hash_b64 = base64.b64encode(derived).decode("utf-8")
    return f"pbkdf2_sha256${iterations}${salt_b64}${hash_b64}"


def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    """Verify plaintext password against stored salted hash."""
    if not stored_hash or not stored_hash.startswith("pbkdf2_sha256$"):
        return False
    try:
        parts = stored_hash.split("$")
        if len(parts) != 4:
            return False
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2].encode("utf-8"))
        expected_hash = base64.b64decode(parts[3].encode("utf-8"))
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(derived, expected_hash)
    except Exception:
        return False


def generate_voter_session_token(voter_id: str, email: str) -> str:
    """Generate signed HMAC session token for registered voter."""
    ts = str(int(time.time()))
    payload = f"{voter_id.lower()}:{email.lower()}:{ts}"
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"securevote_voter_{payload}_{sig}"


def verify_voter_token_str(token: str) -> Optional[Tuple[str, str]]:
    """Validate voter session token format and cryptographic signature."""
    if not token or not token.startswith("securevote_voter_"):
        # Backwards compatibility for voter_ tokens
        if token.startswith("voter_"):
            parts = token.replace("voter_", "").split("_")
            if len(parts) == 2:
                payload, signature = parts[0], parts[1]
                expected_sig = hmac.new(
                    settings.SECRET_KEY.encode("utf-8"),
                    payload.encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
                if hmac.compare_digest(signature, expected_sig):
                    user_email = payload.split(":", 1)
                    return user_email[0], user_email[1] if len(user_email) > 1 else ""
        return None

    try:
        parts = token.replace("securevote_voter_", "").split("_")
        if len(parts) != 2:
            return None
        payload, signature = parts[0], parts[1]
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        bits = payload.split(":")
        if len(bits) >= 2:
            return bits[0], bits[1]
        return None
    except Exception:
        return None


async def require_voter(authorization: Optional[str] = Header(None)) -> str:
    """
    FastAPI dependency enforcing Voter role authentication.
    Strictly rejects admin session tokens with 403 Forbidden.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Voter authentication required. Please log in with your Voter ID and password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.replace("Bearer ", "").strip()

    # Reject if an admin token is passed
    if "admin" in token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role mismatch: Administrator credentials cannot access voter account endpoints.",
        )

    voter_info = verify_voter_token_str(token)
    if not voter_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired voter session. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return voter_info[0]  # voter_id
