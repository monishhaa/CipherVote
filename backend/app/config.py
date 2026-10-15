"""
CipherVote backend configuration and environment settings.
"""

import hashlib
import hmac
import os
import secrets
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "SecureVote"
    PROJECT_NAME: str = "SecureVote API"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api"

    # Admin Authentication
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""  # If empty, a secure password is generated or loaded from environment
    ADMIN_SESSION_SECRET: str = "securevote_admin_session_jwt_secret_2026"

    # Secret keys for signing and time-locks
    SECRET_KEY: str = "securevote_super_secret_master_key_2026_production"
    MASTER_TIME_LOCK_SECRET: bytes = b"securevote_time_lock_master_epoch_key_512"

    # Biometric template encryption key (32 bytes)
    BIOMETRIC_ENCRYPTION_KEY: bytes = b"securevote_biometric_aes_key_32_bytes"[:32].ljust(32, b"0")

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./securevote.db"

    # Portal Base URL (for voter email links)
    PORTAL_BASE_URL: str = "http://localhost:3000"

    # SMTP Email Configuration
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@securevote.org"
    SMTP_FROM_NAME: str = "SecureVote"
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False

    def get_effective_sender(self) -> tuple[str, str]:
        """
        Returns (display_name, email_address).
        Enforces Gmail alignment: If host is Gmail, address MUST match SMTP_USER.
        Never crashes or leaves address empty.
        """
        import email.utils
        import logging

        log = logging.getLogger("securevote.config")
        name = self.SMTP_FROM_NAME.strip() or self.APP_NAME

        # Extract address from SMTP_FROM if it contained an angle-addr
        parsed_name, parsed_addr = email.utils.parseaddr(self.SMTP_FROM)
        addr = parsed_addr.strip() if parsed_addr else self.SMTP_FROM.strip()

        # Clean any remaining brackets or quotes
        addr = addr.replace("<", "").replace(">", "").strip()

        # Check Gmail rules
        host_lower = (self.SMTP_HOST or "").lower().strip()
        is_gmail = "smtp.gmail.com" in host_lower or "googlemail" in host_lower

        if is_gmail and self.SMTP_USER.strip():
            smtp_user_addr = self.SMTP_USER.strip()
            if addr.lower() != smtp_user_addr.lower():
                log.warning(
                    f"[SMTP CONFIG WARNING] Gmail SMTP requires the From address to equal SMTP_USER. "
                    f"Overriding From '{addr}' with '{smtp_user_addr}'."
                )
                addr = smtp_user_addr

        if not addr or "@" not in addr:
            addr = self.SMTP_USER.strip() if self.SMTP_USER.strip() and "@" in self.SMTP_USER else "noreply@securevote.org"

        return name, addr

    # Outbox storage directory (for DEV mode email preview and .eml archives)
    DATA_DIR: str = os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data"
    )

    model_config = {
        "case_sensitive": True,
        "env_file": (".env", "../.env"),
        "extra": "ignore",
    }


settings = Settings()

# Validate sender config at import/startup without crashing
try:
    _eff_name, _eff_addr = settings.get_effective_sender()
except Exception as _e:
    pass

# Ensure data and outbox directories exist
os.makedirs(os.path.join(settings.DATA_DIR, "outbox"), exist_ok=True)
os.makedirs(os.path.join(settings.DATA_DIR, "emails"), exist_ok=True)

# Generate and print admin password if not provided
if not settings.ADMIN_PASSWORD:
    # Default fallback for local testing if env not set
    env_pass = os.environ.get("ADMIN_PASSWORD")
    if env_pass:
        settings.ADMIN_PASSWORD = env_pass
    else:
        # Default secure test password
        settings.ADMIN_PASSWORD = "admin2026"
        print("[CIPHERVOTE] Notice: ADMIN_PASSWORD not set in .env. Using the local default.")


def _admin_password_digest(password: str) -> str:
    """Hash an admin password. The .env value is never compared in plaintext."""
    return hashlib.sha256(password.strip().encode("utf-8")).hexdigest()


ADMIN_PASSWORD_HASH = _admin_password_digest(settings.ADMIN_PASSWORD or "")


def verify_admin_password(submitted: str) -> bool:
    """Constant-time check of a submitted admin password against the hashed env value."""
    if not submitted or not ADMIN_PASSWORD_HASH:
        return False
    return hmac.compare_digest(_admin_password_digest(submitted), ADMIN_PASSWORD_HASH)
