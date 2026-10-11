"""Facts built from a registry record and by hand (SPEC section 6.1, 6.4, contract `Fact`)."""

from __future__ import annotations

import copy

import pytest
from domain_testkit import athlete_record

from app.domain.facts import manual_achievement_fact, plural_ru, result_from_place, years_label
from app.domain.fsp_mapping import facts_from_fsp
from app.domain.types import VERIFICATION_BY_SOURCE


def _by_key(facts: list) -> dict:
    return {f.key: f for f in facts}


def test_every_fact_is_verified_by_the_registry() -> None:
    facts = facts_from_fsp(athlete_record())
    assert facts
    for fact in facts:
        assert fact.source == "fsp"
        assert fact.verification == VERIFICATION_BY_SOURCE["fsp"] == "verified"


def test_results_become_achievements() -> None:
    facts = _by_key(facts_from_fsp(athlete_record()))
    first = facts["fsp:R1"]
    assert first.kind == "achievement"
    assert first.title == "Всероссийский чемпионат по алгоритмам — 3 место"
    assert first.evidence == "https://fsp.example/protocols/R1"
    assert first.value["result"] == "prize"
    assert first.value["document_url"] == "https://fsp.example/protocols/R1"
    assert first.value["year"] == 2024
    assert first.value["place"] == 3
    assert first.value["level"] == "national"
    assert first.value["discipline"] == "algorithmic"
    assert first.value["team_role"] is None
    assert facts["fsp:R2"].value["result"] == "prize"
    assert facts["fsp:R2"].value["team_name"] == "Граф магистралей"
    assert facts["fsp:R3"].value["result"] == "participant"
    assert facts["fsp:R4"].value["result"] == "participant"


def test_first_place_is_a_win() -> None:
    record = athlete_record()
    record["results"][0]["place"] = 1
    assert _by_key(facts_from_fsp(record))["fsp:R1"].value["result"] == "winner"


def test_the_senior_rank_becomes_one_fact() -> None:
    facts = facts_from_fsp(athlete_record())
    ranks = [f for f in facts if f.kind == "rank"]
    assert len(ranks) == 1
    rank = ranks[0]
    assert rank.key == "sport_rank"
    assert rank.title == "КМС · Алгоритмическое программирование"
    assert rank.value["rank"] == "kms"
    assert rank.value["discipline"] == "algorithmic"
    assert rank.value["order_no"] == "№ 118"


def test_discipline_skills_and_their_levels() -> None:
    facts = _by_key(facts_from_fsp(athlete_record()))
    # prize at a national level -> 3
    assert facts["algorithms"].kind == "skill"
    assert facts["algorithms"].value == {"level": 3}
    assert facts["algorithms"].title == "Алгоритмы и структуры данных"
    assert facts["product-development"].value == {"level": 3}
    assert "infosec" not in facts  # no results in this discipline


@pytest.mark.parametrize(
    ("level", "place", "expected"),
    [
        ("national", 1, 3),
        ("international", 3, 3),
        ("national", 7, 2),
        ("international", 40, 2),
        ("regional", 2, 2),
        ("district", 1, 2),
        ("regional", 4, 1),
        ("district", 9, 1),
        ("municipal", 1, 1),
    ],
)
def test_skill_level_by_result(level: str, place: int, expected: int) -> None:
    record = athlete_record()
    record["results"] = [record["results"][0]]
    record["results"][0]["competition"]["level"] = level
    record["results"][0]["place"] = place
    assert _by_key(facts_from_fsp(record))["algorithms"].value["level"] == expected


def test_best_result_of_a_discipline_sets_the_skill_level() -> None:
    record = athlete_record()
    record["results"] = [record["results"][3], record["results"][0]]  # regional 12th, national 3rd
    assert _by_key(facts_from_fsp(record))["algorithms"].value["level"] == 3


def test_captain_and_team_roles() -> None:
    facts = _by_key(facts_from_fsp(athlete_record()))
    assert facts["fsp_captain"].kind == "role"
    assert facts["fsp_captain"].title == "Капитан команды на соревнованиях ФСП"
    assert facts["fsp_team:backend"].title == "Роль в команде ФСП: backend-разработчик"
    assert set(facts["fsp_team:backend"].value) == {"reason"}
    assert "fsp_team:captain" not in facts


def test_roles_without_a_stack_hint_are_ignored() -> None:
    record = athlete_record()
    record["results"][2]["team_role"] = "designer"
    record["results"][3]["team_role"] = "member"
    keys = _by_key(facts_from_fsp(record))
    assert not [k for k in keys if k.startswith("fsp_team:")]


def test_an_athlete_without_results_gives_only_the_rank() -> None:
    record = athlete_record()
    record["results"] = []
    facts = facts_from_fsp(record)
    assert [f.kind for f in facts] == ["rank"]


def test_malformed_record_is_reported() -> None:
    record = athlete_record()
    broken = copy.deepcopy(record)
    del broken["results"][0]["competition"]["level"]
    with pytest.raises(ValueError):
        facts_from_fsp(broken)
    broken = copy.deepcopy(record)
    broken["ranks"][0]["rank"] = "gm"
    with pytest.raises(ValueError):
        facts_from_fsp(broken)


# --- manual achievements and labels ----------------------------------------------------------
def test_manual_achievement_fact() -> None:
    fact = manual_achievement_fact(
        "6f1e", "  Олимпиада   ВсОШ ", 2023, "regional", "prize", "algorithmic", None
    )
    assert fact.kind == "achievement"
    assert fact.key == "manual:6f1e"
    assert fact.title == "Олимпиада ВсОШ, 2023 — призёр"
    assert (fact.source, fact.verification) == ("self", "declared")
    assert fact.value["level"] == "regional"
    assert fact.value["result"] == "prize"
    assert fact.value["place"] is None
    assert fact.value["year"] == 2023
    assert fact.value["document_url"] is None


@pytest.mark.parametrize(
    ("result", "word"), [("winner", "победитель"), ("prize", "призёр"), ("participant", "участник")]
)
def test_manual_achievement_titles(result: str, word: str) -> None:
    fact = manual_achievement_fact("u", "CTF", 2024, "national", result, None, "https://x.y/d")
    assert fact.title == f"CTF, 2024 — {word}"
    assert fact.evidence == "https://x.y/d"


def test_manual_achievement_rejects_unknown_values() -> None:
    with pytest.raises(ValueError):
        manual_achievement_fact("u", "CTF", 2024, "national", "champion", None, None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        manual_achievement_fact("u", "CTF", 2024, "galactic", "winner", None, None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("years", "label"),
    [
        (0, "0 лет"),
        (0.5, "0,5 года"),
        (1, "1 год"),
        (1.5, "1,5 года"),
        (2, "2 года"),
        (3.97, "4 года"),
        (5, "5 лет"),
        (8, "8 лет"),
        (11, "11 лет"),
        (21, "21 год"),
        (22, "22 года"),
        (10.04, "10 лет"),
        (2.5, "2,5 года"),
    ],
)
def test_years_label_declension(years: float, label: str) -> None:
    assert years_label(years) == label


def test_plural_and_place_helpers() -> None:
    assert plural_ru(1, "год", "года", "лет") == "год"
    assert plural_ru(12, "год", "года", "лет") == "лет"
    assert result_from_place(1) == "winner"
    assert result_from_place(3) == "prize"
    assert result_from_place(4) == "participant"
