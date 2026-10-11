"""Turning a record of the FSP registry into verified profile facts (SPEC section 6.1)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.domain.facts import (
    TEAM_ROLE_FACT_TITLES,
    result_from_place,
    skill_fact,
    sport_rank_title,
)
from app.domain.ontology import DISCIPLINE_SKILL, DISCIPLINE_TITLES, LEVEL_TITLES
from app.domain.scoring_config import PRIZE_MAX_PLACE, RANK_ORDER
from app.domain.types import VERIFICATION_BY_SOURCE, FactData

_TOP_LEVELS = ("national", "international")
_MID_LEVELS = ("regional", "district")


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping or mapping[key] is None:
        raise ValueError(f"FSP record: missing {key!r} in {where}")
    return mapping[key]


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _year(value: Any) -> int | None:
    iso = _iso(value)
    if iso is None:
        return None
    try:
        return int(iso[:4])
    except ValueError as error:
        raise ValueError(f"FSP record: bad date {iso!r}") from error


def _skill_level(place: int, level: str) -> int:
    """3: prize at a national level; 2: prize at a regional level or any national start."""
    prize = place <= PRIZE_MAX_PLACE
    if prize and level in _TOP_LEVELS:
        return 3
    if (prize and level in _MID_LEVELS) or level in _TOP_LEVELS:
        return 2
    return 1


def _achievement_fact(raw: dict[str, Any]) -> FactData:
    result_id = _require(raw, "result_id", "result")
    competition = _require(raw, "competition", f"result {result_id}")
    place = int(_require(raw, "place", f"result {result_id}"))
    title = _require(competition, "title", f"result {result_id}")
    level = _require(competition, "level", f"result {result_id}")
    if level not in LEVEL_TITLES:
        raise ValueError(f"FSP record: unknown competition level {level!r} in result {result_id}")
    discipline = competition.get("discipline")
    if discipline is not None and discipline not in DISCIPLINE_TITLES:
        raise ValueError(f"FSP record: unknown discipline {discipline!r} in result {result_id}")
    protocol_url = raw.get("protocol_url")
    return FactData(
        kind="achievement",
        key=f"fsp:{result_id}",
        title=f"{title} — {place} место",
        value={
            "title": title,
            "discipline": discipline,
            "level": level,
            "place": place,
            "result": result_from_place(place),
            "date": _iso(competition.get("date_start")),
            "year": _year(competition.get("date_start")),
            "team_name": raw.get("team_name"),
            "team_role": raw.get("team_role"),
            "participants_total": competition.get("participants_total"),
            "document_url": protocol_url,
        },
        source="fsp",
        verification=VERIFICATION_BY_SOURCE["fsp"],
        evidence=protocol_url,
    )


def _rank_fact(ranks: list[dict[str, Any]]) -> FactData | None:
    """The senior rank; of two equal ranks the one assigned later."""
    best: dict[str, Any] | None = None
    for raw in ranks:
        rank = _require(raw, "rank", "rank")
        if rank not in RANK_ORDER:
            raise ValueError(f"FSP record: unknown sport rank {rank!r}")
        if best is None:
            best = raw
            continue
        key_new = (RANK_ORDER.index(rank), _iso(raw.get("assigned_at")) or "")
        key_best = (RANK_ORDER.index(best["rank"]), _iso(best.get("assigned_at")) or "")
        if key_new > key_best:
            best = raw
    if best is None:
        return None
    discipline = best.get("discipline")
    if discipline is not None and discipline not in DISCIPLINE_TITLES:
        raise ValueError(f"FSP record: unknown discipline {discipline!r} in rank")
    order_no = best.get("order_no")
    return FactData(
        kind="rank",
        key="sport_rank",
        title=sport_rank_title(best["rank"], discipline),
        value={
            "rank": best["rank"],
            "discipline": discipline,
            "assigned_at": _iso(best.get("assigned_at")),
            "order_no": order_no,
        },
        source="fsp",
        verification=VERIFICATION_BY_SOURCE["fsp"],
        evidence=order_no,
    )


def facts_from_fsp(athlete: dict) -> list[FactData]:
    """Facts of one athlete: results, the senior rank, discipline skills and team roles.

    All facts are `verified`. The order is stable: results as listed, rank, skills in the
    order the disciplines first appear, then the roles.
    """
    results: list[dict[str, Any]] = list(athlete.get("results") or [])
    facts: list[FactData] = [_achievement_fact(raw) for raw in results]

    rank = _rank_fact(list(athlete.get("ranks") or []))
    if rank is not None:
        facts.append(rank)

    # One skill per discipline that has results, at the best level reached there.
    best_by_discipline: dict[str, tuple[int, str | None]] = {}
    for raw in results:
        competition = raw["competition"]
        discipline = competition.get("discipline")
        if discipline not in DISCIPLINE_SKILL:
            continue
        level = _skill_level(int(raw["place"]), competition["level"])
        current = best_by_discipline.get(discipline)
        if current is None or level > current[0]:
            best_by_discipline[discipline] = (level, raw.get("protocol_url"))
    for discipline, (level, protocol_url) in best_by_discipline.items():
        facts.append(skill_fact(DISCIPLINE_SKILL[discipline], level, "fsp", evidence=protocol_url))

    roles: dict[str, None] = {}
    for raw in results:
        role = raw.get("team_role")
        if role is not None:
            roles.setdefault(role, None)
    if "captain" in roles:
        facts.append(
            FactData(
                kind="role",
                key="fsp_captain",
                title="Капитан команды на соревнованиях ФСП",
                value={"reason": "Капитан команды в результатах реестра ФСП"},
                source="fsp",
                verification=VERIFICATION_BY_SOURCE["fsp"],
            )
        )
    for role in roles:
        if role not in TEAM_ROLE_FACT_TITLES:
            continue
        facts.append(
            FactData(
                kind="role",
                key=f"fsp_team:{role}",
                title=f"Роль в команде ФСП: {TEAM_ROLE_FACT_TITLES[role]}",
                value={"reason": f"Командная роль «{role}» в результатах реестра ФСП"},
                source="fsp",
                verification=VERIFICATION_BY_SOURCE["fsp"],
            )
        )
    return facts
