"""Builders of profile facts and the Russian labels that go with them.

Every `FactData` carries a ready `title`: the domain decides how a fact is called, the
API and the frontend only show it.
"""

from __future__ import annotations

from typing import Any

from app.domain.ontology import (
    DISCIPLINE_TITLES,
    LEVEL_TITLES,
    SPORT_RANK_TITLES,
    skill_title,
)
from app.domain.scoring_config import PRIZE_MAX_PLACE
from app.domain.types import (
    VERIFICATION_BY_SOURCE,
    AchievementResult,
    CompetitionLevel,
    Discipline,
    FactData,
    Source,
)

RESULT_TITLES: dict[str, str] = {
    "winner": "победитель",
    "prize": "призёр",
    "participant": "участник",
}

# Facts of the "role" kind that the domain creates.
TEAM_ROLE_FACT_TITLES: dict[str, str] = {
    "backend": "backend-разработчик",
    "frontend": "frontend-разработчик",
    "ml": "ML-инженер",
    "analyst": "аналитик",
}


def plural_ru(number: int, one: str, few: str, many: str) -> str:
    """Russian plural form: 1 год, 2 года, 5 лет."""
    n = abs(number) % 100
    if 11 <= n <= 14:
        return many
    last = n % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many


def format_decimal(value: float, digits: int = 1) -> str:
    """1.5 -> "1,5"; 2.0 -> "2"."""
    text = f"{value:.{digits}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def years_label(years: float) -> str:
    """"1,5 года", "3 года", "5 лет": the number of years as people say it."""
    rounded = round(years, 1)
    if rounded == int(rounded):
        whole = int(rounded)
        return f"{whole} {plural_ru(whole, 'год', 'года', 'лет')}"
    return f"{format_decimal(rounded)} года"


def result_from_place(place: int) -> AchievementResult:
    """winner for the 1st place, prize for 2nd and 3rd, participant otherwise."""
    if place == 1:
        return "winner"
    if place <= PRIZE_MAX_PLACE:
        return "prize"
    return "participant"


def skill_fact(
    skill_id: str,
    level: int,
    source: Source,
    *,
    evidence: str | None = None,
    score: float | None = None,
) -> FactData:
    value: dict[str, Any] = {"level": level}
    if score is not None:
        value["score"] = score
    return FactData(
        kind="skill",
        key=skill_id,
        title=skill_title(skill_id),
        value=value,
        source=source,
        verification=VERIFICATION_BY_SOURCE[source],
        evidence=evidence,
    )


def experience_fact(
    years: float, positions: list[dict[str, Any]], evidence: str | None = None
) -> FactData:
    return FactData(
        kind="experience",
        key="total",
        title=f"Опыт в ИТ: {years_label(years)}",
        value={"years": years, "positions": positions},
        source="resume",
        verification=VERIFICATION_BY_SOURCE["resume"],
        evidence=evidence,
    )


def sport_rank_title(rank: str, discipline: str | None) -> str:
    title = SPORT_RANK_TITLES[rank]
    if discipline:
        return f"{title} · {DISCIPLINE_TITLES[discipline]}"
    return title


def manual_achievement_fact(
    uid: str,
    title: str,
    year: int,
    level: CompetitionLevel,
    result: AchievementResult,
    discipline: Discipline | None,
    document_url: str | None,
) -> FactData:
    """An achievement the candidate added by hand (olympiad, hackathon, CTF)."""
    if result not in RESULT_TITLES:
        raise ValueError(f"unknown achievement result: {result!r}")
    if level not in LEVEL_TITLES:
        raise ValueError(f"unknown competition level: {level!r}")
    if discipline is not None and discipline not in DISCIPLINE_TITLES:
        raise ValueError(f"unknown discipline: {discipline!r}")
    clean_title = " ".join(title.split())
    return FactData(
        kind="achievement",
        key=f"manual:{uid}",
        title=f"{clean_title}, {year} — {RESULT_TITLES[result]}",
        value={
            "title": clean_title,
            "discipline": discipline,
            "level": level,
            "place": None,
            "result": result,
            "date": None,
            "year": year,
            "team_name": None,
            "team_role": None,
            "participants_total": None,
            "document_url": document_url,
        },
        source="self",
        verification=VERIFICATION_BY_SOURCE["self"],
        evidence=document_url,
    )
