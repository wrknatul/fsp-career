from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator

from app.core.timeutil import utcnow
from app.schemas.base import InputModel, check_http_url, optional_text, required_text
from app.schemas.common import AchievementResult, CompetitionLevel, Discipline

MIN_ACHIEVEMENT_YEAR = 1990


def _check_year(value: int) -> int:
    current = utcnow().year
    if not MIN_ACHIEVEMENT_YEAR <= value <= current:
        raise ValueError(f"Год должен быть от {MIN_ACHIEVEMENT_YEAR} до {current}")
    return value


Year = Annotated[int, AfterValidator(_check_year)]
Title = required_text(200, min_length=3)
DocumentUrl = Annotated[optional_text(500), AfterValidator(check_http_url)]


class AchievementCreate(InputModel):
    """`POST /candidate/achievements`: an achievement outside the FSP registry."""

    title: Title
    year: Year
    level: CompetitionLevel
    result: AchievementResult
    discipline: Discipline | None = None
    document_url: DocumentUrl = None
