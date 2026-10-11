"""Shared contract types (docs/API_CONTRACT.md, "Общие типы")."""

from __future__ import annotations

from typing import Any, Literal

from app.domain.types import (
    AchievementResult,
    Categorization,
    CompetitionLevel,
    Discipline,
    Explanation,
    FactKind,
    Grade,
    SkillEvidence,
    Source,
    SportRank,
    Stack,
    TeamRole,
    Verification,
    WorkFormat,
)
from app.schemas.base import ApiModel, UTCDatetime

Role = Literal["candidate", "employer"]
OfferStatus = Literal["sent", "accepted", "declined"]

# The contract type `Category` is the domain `Categorization`, reused as is.
Category = Categorization

__all__ = [
    "AchievementResult",
    "Category",
    "CompetitionLevel",
    "Discipline",
    "Explanation",
    "Fact",
    "FactKind",
    "Grade",
    "OfferStatus",
    "Role",
    "SkillEvidence",
    "Source",
    "SportRank",
    "Stack",
    "TeamRole",
    "User",
    "Verification",
    "WorkFormat",
]


class User(ApiModel):
    id: int
    email: str
    role: Role
    full_name: str


class Fact(ApiModel):
    """A profile fact as the API shows it (the domain one is `FactData`)."""

    id: int
    kind: FactKind
    key: str
    title: str
    value: dict[str, Any]
    source: Source
    verification: Verification
    evidence: str | None
    created_at: UTCDatetime
