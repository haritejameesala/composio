"""
Authentication utilities: password hashing and JWT creation/verification.
No secrets are logged anywhere in this module.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from config import settings


# ─────────────────────────────────────────────────────────────────────────────
# Password helpers (using standard bcrypt library directly)
# ─────────────────────────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain* as a UTF-8 string."""
    pwd_bytes = plain.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the stored *hashed* value."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# JWT helpers
# ─────────────────────────────────────────────────────────────────────────────


def create_access_token(subject: str, is_admin: bool = False) -> str:
    """
    Create a signed JWT.

    :param subject: The user's internal UUID (stored as the ``sub`` claim).
    :param is_admin: Whether to include the ``admin`` claim.
    :returns: Encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "exp": expire,
        "admin": is_admin,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT.

    :returns: The payload dict, or ``None`` if the token is invalid/expired.
    """
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
