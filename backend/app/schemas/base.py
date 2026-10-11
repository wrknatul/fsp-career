"""Base classes and shared field types for request and response models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, ClassVar, Self
from urllib.parse import urlparse

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.timeutil import as_utc, utcnow

# Columns are 32-bit integers on PostgreSQL: larger values would be a DataError, not a 422.
MAX_INT = 2_147_483_647
MAX_SALARY = 100_000_000


class ApiModel(BaseModel):
    """Response model: can be built straight from ORM rows.

    Every key is always present in the JSON body (nullable ones carry `null`), so the OpenAPI
    schema lists fields with defaults as required too, as the contract's TypeScript types do.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_serialization_defaults_required=True,
    )


def _check_text(value: Any, depth: int = 0) -> None:
    if isinstance(value, str):
        # NUL is refused by PostgreSQL, lone surrogates cannot be encoded to UTF-8.
        if any(ch == "\x00" or "\ud800" <= ch <= "\udfff" for ch in value):
            raise ValueError("Недопустимые символы в тексте")
    elif depth < 3 and isinstance(value, list | tuple):
        for item in value:
            _check_text(item, depth + 1)
    elif depth < 3 and isinstance(value, dict):
        for key, item in value.items():
            _check_text(key, depth + 1)
            _check_text(item, depth + 1)


class InputModel(BaseModel):
    """Request body. Unknown fields are ignored; unsafe characters are rejected."""

    model_config = ConfigDict(extra="ignore")

    @field_validator("*", mode="after")
    @classmethod
    def _reject_unsafe_text(cls, value: Any) -> Any:
        _check_text(value)
        return value


class PatchModel(InputModel):
    """Partial update: only fields present in the body are applied (`model_fields_set`).

    Fields listed in `non_nullable` may be omitted but may not be sent as `null`.
    """

    non_nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_explicit_null(self) -> Self:
        bad = sorted(
            name
            for name in self.model_fields_set
            if name in self.non_nullable and getattr(self, name) is None
        )
        if bad:
            raise ValueError(f"Поле не может быть null: {', '.join(bad)}")
        return self


def _blank_to_none(value: str | None) -> str | None:
    return value or None


def required_text(max_length: int, min_length: int = 1) -> Any:
    """A stripped string with a length range (checked after stripping)."""
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length),
    ]


def optional_text(max_length: int) -> Any:
    """A stripped string or null; a blank string becomes null."""
    return Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, max_length=max_length),
        AfterValidator(_blank_to_none),
    ]


Str200 = required_text(200)
Str255 = required_text(255)
OptStr32 = optional_text(32)
OptStr64 = optional_text(64)
OptStr100 = optional_text(100)
OptStr200 = optional_text(200)
OptStr300 = optional_text(300)
OptStr500 = optional_text(500)
OptStr1000 = optional_text(1000)
OptStr2000 = optional_text(2000)
OptStr5000 = optional_text(5000)

UTCDatetime = Annotated[datetime, AfterValidator(as_utc)]
DbId = Annotated[int, Field(gt=0, le=MAX_INT)]
Salary = Annotated[int, Field(gt=0, le=MAX_SALARY)]


def _check_birth_date(value: date) -> date:
    if value < date(1900, 1, 1) or value > utcnow().date():
        raise ValueError("Некорректная дата рождения")
    return value


BirthDate = Annotated[date, AfterValidator(_check_birth_date)]


def unique_list(values: list[Any]) -> list[Any]:
    """Drop duplicates, keep first-seen order."""
    return list(dict.fromkeys(values))


def check_http_url(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or " " in value:
        raise ValueError("Ссылка должна начинаться с http:// или https://")
    return value
