"""Application settings read from environment variables (SPEC section 8)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

APP_VERSION = "0.1.0"

# Deliberately obvious, never to be used outside local development.
# Kept at 32+ bytes so HS256 libraries do not complain about a short key.
DEFAULT_JWT_SECRET = "dev-only-insecure-jwt-secret-change-me-0123456789"

# Placeholders that must never reach a public server: the built-in value above and the
# `change-me-...` line of `.env.example`. Same list as `backend/entrypoint.sh`.
PLACEHOLDER_JWT_SECRET_PREFIXES = ("dev-only-", "change-me")
# HS256 wants a key of at least 32 bytes (PyJWT warns below that).
MIN_JWT_SECRET_BYTES = 32

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8088",
    "http://127.0.0.1:8088",
]


def normalize_database_url(url: str) -> str:
    """Make a plain PostgreSQL URL use the installed psycopg 3 driver."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    DATABASE_URL: str = "sqlite:///./dev.sqlite3"
    JWT_SECRET: str = DEFAULT_JWT_SECRET
    JWT_TTL_MINUTES: int = Field(default=720, gt=0)
    # Comma-separated list or a JSON array.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS)
    )
    SEED_DEMO_DATA: bool = True
    TEST_COOLDOWN_MINUTES: int = Field(default=1440, ge=0)
    MAX_UPLOAD_BYTES: int = Field(default=2_097_152, gt=0)
    FSP_REGISTRY_MODE: Literal["mock", "live"] = "mock"
    FSP_MOCK_ROUTES_ENABLED: bool = True
    # Not part of SPEC section 8: lets the test suite hash passwords quickly.
    BCRYPT_ROUNDS: int = Field(default=12, ge=4, le=16)

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_url(cls, value: str) -> str:
        return normalize_database_url(value.strip())

    @field_validator("JWT_SECRET")
    @classmethod
    def _require_jwt_secret(cls, value: str) -> str:
        # An empty key makes PyJWT fail on every sign-in, after the user row is already saved:
        # refuse to start instead of answering 500 to every registration.
        if not value.strip():
            raise ValueError(
                "JWT_SECRET must not be empty: set a long random string (openssl rand -hex 32)"
            )
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                return json.loads(text)
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @property
    def uses_default_jwt_secret(self) -> bool:
        """True when the key is the built-in one, a placeholder or too short for HS256."""
        secret = self.JWT_SECRET
        return (
            secret == DEFAULT_JWT_SECRET
            or secret.lower().startswith(PLACEHOLDER_JWT_SECRET_PREFIXES)
            or len(secret.encode("utf-8")) < MIN_JWT_SECRET_BYTES
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
