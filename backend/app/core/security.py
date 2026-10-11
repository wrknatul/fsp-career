"""Password hashing (bcrypt) and access tokens (JWT HS256)."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from typing import Any

import bcrypt
import jwt

from app.core.config import Settings
from app.core.timeutil import utcnow

JWT_ALGORITHM = "HS256"
# bcrypt only looks at the first 72 bytes; the library refuses longer input.
PASSWORD_MIN_BYTES = 8
PASSWORD_MAX_BYTES = 72


def password_byte_length(password: str) -> int:
    return len(password.encode("utf-8"))


def hash_password(password: str, rounds: int) -> str:
    """Hash a password; raises ValueError for passwords above 72 bytes."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check; any malformed input simply does not match."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, UnicodeError):
        # Too long (>72 bytes), lone surrogates or a corrupted stored hash.
        return False


@lru_cache(maxsize=4)
def _dummy_hash(rounds: int) -> str:
    return hash_password("not-a-real-password", rounds)


def burn_password_check(password: str, rounds: int) -> None:
    """Spend the same time as a real check, so unknown e-mails are not detectable."""
    verify_password(password, _dummy_hash(rounds))


def create_access_token(user_id: int, role: str, settings: Settings) -> str:
    now = utcnow()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_TTL_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Validate signature and expiry; raises jwt.PyJWTError for any problem."""
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
