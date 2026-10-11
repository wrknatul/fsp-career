from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import AfterValidator, Field, StrictBool, StringConstraints

from app.core.security import PASSWORD_MAX_BYTES, PASSWORD_MIN_BYTES
from app.schemas.base import ApiModel, InputModel, OptStr200, Str200
from app.schemas.common import Role, User

_EMAIL_MAX_LENGTH = 254


def _check_email(value: str) -> str:
    """Deliberately simple: `email-validator` rejects reserved zones such as `.test`,
    which the demo accounts use."""
    local, at, domain = value.partition("@")
    if (
        not at
        or not local
        or "@" in domain
        or any(ch.isspace() for ch in value)
        or "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
        or ".." in domain
    ):
        raise ValueError("Некорректный адрес электронной почты")
    return value


Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, min_length=3, max_length=_EMAIL_MAX_LENGTH
    ),
    AfterValidator(_check_email),
]


LoginEmail = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, min_length=1, max_length=_EMAIL_MAX_LENGTH
    ),
]


def _check_password(value: str) -> str:
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("Недопустимые символы в пароле") from exc
    if not PASSWORD_MIN_BYTES <= size <= PASSWORD_MAX_BYTES:
        raise ValueError(
            f"Пароль должен занимать от {PASSWORD_MIN_BYTES} до {PASSWORD_MAX_BYTES} байт "
            "(кириллическая буква — 2 байта)"
        )
    return value


Password = Annotated[str, AfterValidator(_check_password)]


class RegisterRequest(InputModel):
    email: Email
    password: Password
    role: Role
    full_name: Str200
    # Deliberately untyped: the contract says "consent is not `true`" -> CONSENT_REQUIRED, so
    # `null`, `"true"` or `1` must reach the route (which checks `is not True`) instead of
    # failing validation with a different error code.
    consent: Annotated[
        Any,
        Field(
            description="Должно быть `true`; любое другое значение даёт CONSENT_REQUIRED.",
            json_schema_extra={"type": "boolean"},
        ),
    ] = False
    # Candidates only: whether employers may see the profile (becomes `candidates.visible`).
    show_profile: StrictBool = False
    # Required for employers.
    company_name: OptStr200 = None


class LoginRequest(InputModel):
    # No format check on purpose: an unknown address is just INVALID_CREDENTIALS.
    email: LoginEmail
    # Not length-checked in bytes: a wrong-length password simply does not match.
    password: Annotated[str, Field(min_length=1, max_length=1024)]


class AuthResponse(ApiModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: User
