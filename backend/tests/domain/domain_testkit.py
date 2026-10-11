"""Builders shared by the domain tests (facts, candidates, a registry record)."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.domain.categorizer import categorize
from app.domain.embedding import embed, profile_text
from app.domain.facts import experience_fact, skill_fact
from app.domain.types import (
    VERIFICATION_BY_SOURCE,
    CandidatePrefs,
    CandidateSnapshot,
    FactData,
)

TODAY = date(2026, 10, 10)


def skill(skill_id: str, source: str = "resume", level: int = 2) -> FactData:
    return skill_fact(skill_id, level, source)  # type: ignore[arg-type]


def experience(years: float) -> FactData:
    return experience_fact(years, [])


def fsp_achievement(
    result_id: str,
    level: str,
    place: int,
    *,
    discipline: str = "algorithmic",
    title: str | None = None,
    year: int = 2025,
) -> FactData:
    name = title or f"Соревнование {result_id}"
    result = "winner" if place == 1 else "prize" if place <= 3 else "participant"
    return FactData(
        kind="achievement",
        key=f"fsp:{result_id}",
        title=f"{name} — {place} место",
        value={
            "title": name,
            "discipline": discipline,
            "level": level,
            "place": place,
            "result": result,
            "date": f"{year}-04-10",
            "year": year,
            "team_name": None,
            "team_role": None,
            "participants_total": 100,
            "document_url": f"https://fsp.example/protocols/{result_id}",
        },
        source="fsp",
        verification=VERIFICATION_BY_SOURCE["fsp"],
        evidence=f"https://fsp.example/protocols/{result_id}",
    )


def role_fact(key: str, source: str = "fsp") -> FactData:
    return FactData(
        kind="role",
        key=key,
        title=key,
        value={"reason": "test"},
        source=source,  # type: ignore[arg-type]
        verification=VERIFICATION_BY_SOURCE[source],  # type: ignore[arg-type]
    )


def snapshot(
    candidate_id: int,
    facts: list[FactData],
    *,
    prefs: CandidatePrefs | None = None,
    about: str | None = None,
    resume_text: str | None = None,
    city: str | None = None,
    relocation: bool = False,
    salary: int | None = None,
    visible: bool = True,
) -> CandidateSnapshot:
    """A candidate the way the API builds one: category and vector from the facts."""
    prefs = prefs or CandidatePrefs(city=city, relocation=relocation, salary_expectation=salary)
    category = categorize(facts, prefs)
    return CandidateSnapshot(
        id=candidate_id,
        facts=facts,
        category=category,
        embedding=embed(profile_text(facts, category, about, resume_text)),
        city=city,
        relocation=relocation,
        salary_expectation=salary,
        visible=visible,
    )


def athlete_record() -> dict[str, Any]:
    """A registry record shaped like SPEC 6.1 (all values invented)."""

    def competition(
        cid: str, title: str, discipline: str, level: str, start: str, fmt: str
    ) -> dict[str, Any]:
        return {
            "competition_id": cid,
            "title": title,
            "discipline": discipline,
            "level": level,
            "kind": "championship",
            "date_start": start,
            "date_end": start,
            "city": "Москва",
            "format": fmt,
            "participants_total": 120,
        }

    return {
        "fsp_id": "FSP-2024-00117",
        "full_name": "Смирнов Алексей Игоревич",
        "birth_date": "2003-05-14",
        "region": "Республика Татарстан",
        "city": "Казань",
        "ranks": [
            {"rank": "first", "discipline": "algorithmic", "assigned_at": "2023-02-01",
             "order_no": "№ 41"},
            {"rank": "kms", "discipline": "algorithmic", "assigned_at": "2024-03-01",
             "order_no": "№ 118"},
        ],
        "results": [
            {
                "result_id": "R1",
                "competition": competition(
                    "C1", "Всероссийский чемпионат по алгоритмам", "algorithmic", "national",
                    "2024-04-10", "individual",
                ),
                "place": 3,
                "team_name": None,
                "team_role": None,
                "protocol_url": "https://fsp.example/protocols/R1",
            },
            {
                "result_id": "R2",
                "competition": competition(
                    "C2", "Всероссийский хакатон", "product", "national", "2024-06-10", "team"
                ),
                "place": 2,
                "team_name": "Граф магистралей",
                "team_role": "captain",
                "protocol_url": "https://fsp.example/protocols/R2",
            },
            {
                "result_id": "R3",
                "competition": competition(
                    "C3", "Кубок федерального округа", "product", "district", "2023-11-10", "team"
                ),
                "place": 4,
                "team_name": "Граф магистралей",
                "team_role": "backend",
                "protocol_url": "https://fsp.example/protocols/R3",
            },
            {
                "result_id": "R4",
                "competition": competition(
                    "C4", "Региональный чемпионат", "algorithmic", "regional", "2023-03-10",
                    "individual",
                ),
                "place": 12,
                "team_name": None,
                "team_role": None,
                "protocol_url": "https://fsp.example/protocols/R4",
            },
        ],
    }
