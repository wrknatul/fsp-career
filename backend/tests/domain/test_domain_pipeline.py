"""The domain functions working together: the demo scenario of SPEC section 3, no database."""

from __future__ import annotations

import pytest
from domain_testkit import TODAY, athlete_record, snapshot

from app.domain import quiz
from app.domain.categorizer import categorize
from app.domain.facts import manual_achievement_fact
from app.domain.fsp_mapping import facts_from_fsp
from app.domain.matcher import rank
from app.domain.ontology import read_json
from app.domain.resume_parser import parse_resume
from app.domain.types import CandidatePrefs, FactData, MatchQuery

DEMO_RESUME = """Смирнов Алексей Игоревич
Backend-разработчик (Python)
Казань

Формат работы: удалённо или гибрид
Желаемая зарплата: от 120 000 ₽

Опыт работы
Младший backend-разработчик, ООО «Вектор Софт»
10.2025 — н.в.
Разрабатываю API на Python и FastAPI, PostgreSQL, Docker, Git.

Стажёр-программист, ООО «Вектор Софт»
04.2025 — 09.2025
Учился писать сервисы на Python.

Образование
Казанский федеральный университет, 2021 — 2025
"""


def _demo_athlete() -> dict:
    """The demo athlete: 2 national prizes, 2 district and 2 regional results, KMS."""
    record = athlete_record()
    template = record["results"][2]

    def extra(rid: str, level: str, place: int, discipline: str) -> dict:
        result = {**template, "result_id": rid, "place": place, "team_role": None}
        result["competition"] = {
            **template["competition"],
            "competition_id": f"C-{rid}",
            "title": f"Соревнование {rid}",
            "level": level,
            "discipline": discipline,
        }
        return result

    record["results"] = [
        record["results"][0],
        record["results"][1],
        extra("R5", "district", 5, "product"),
        extra("R6", "district", 9, "product"),
        extra("R7", "regional", 1, "product"),
        extra("R8", "regional", 6, "product"),
    ]
    return record


def test_the_demo_scenario_step_by_step() -> None:
    prefs = CandidatePrefs(work_formats=["remote", "hybrid"])

    # 1. nothing is known yet
    empty = categorize([], prefs)
    assert empty.label == "Категория не определена"

    # 2. the registry is linked: Backend, Junior, with the explanation about experience
    fsp_facts = facts_from_fsp(_demo_athlete())
    assert len([f for f in fsp_facts if f.kind == "achievement"]) == 6
    linked = categorize(fsp_facts, prefs)
    assert linked.stack == "backend"
    assert linked.grade == "junior"
    assert linked.grade_note == (
        "Спортивные результаты учтены, но без опыта работы грейд не выше Junior"
    )
    assert linked.grade_points >= 35  # the points alone would give middle
    assert linked.grade_confirmed is True
    assert linked.stack_confirmed is True
    assert linked.confidence_index == 50

    # 3. the resume: skills, 1.5 years of experience, formats, city
    parsed = parse_resume(DEMO_RESUME, TODAY)
    assert parsed.experience_years == pytest.approx(1.5, abs=0.05)
    assert {s.skill for s in parsed.skills} >= {"python", "fastapi", "postgresql", "docker", "git"}
    assert parsed.work_formats == ["remote", "hybrid"]
    assert parsed.city == "Казань"
    assert parsed.salary_expectation == 120000
    with_resume = categorize([*fsp_facts, *parsed.facts], prefs)
    assert with_resume.grade == "middle"
    assert with_resume.grade_note is None
    assert with_resume.experience_years == pytest.approx(1.5, abs=0.05)
    assert with_resume.grade_points > linked.grade_points

    # 4. an express test: more trust in the experience, more points
    seed = 2024
    session = quiz.build_session("python", seed)
    bank = {q["id"]: q for q in _bank_questions("python")}
    answers = {
        q.id: q.options.index(bank[q.id]["options"][bank[q.id]["correct"]]) for q in session
    }
    outcome = quiz.grade_session("python", seed, answers)
    assert outcome.level == 3 and outcome.fact is not None
    tested = categorize([*fsp_facts, *parsed.facts, outcome.fact], prefs)
    assert tested.grade_points > with_resume.grade_points
    assert tested.experience_points > with_resume.experience_points
    assert tested.confidence_index == 75
    assert any("Тест: Python" in e.label for e in tested.grade_explanations)

    # 5. an olympiad by hand: declared, worth 35%
    olympiad = manual_achievement_fact("u1", "ВсОШ", 2022, "national", "prize", None, None)
    declared = categorize([*fsp_facts, *parsed.facts, outcome.fact, olympiad], prefs)
    assert declared.grade_points == pytest.approx(tested.grade_points + 14 * 0.8 * 0.35, abs=0.06)
    assert declared.confidence_index == tested.confidence_index  # declared facts do not count


def _bank_questions(skill: str) -> list[dict]:
    tests = read_json("questions.json")["tests"]
    return next(t for t in tests if t["skill"] == skill)["questions"]


def test_search_finds_the_demo_candidate_with_an_explanation() -> None:
    prefs = CandidatePrefs(work_formats=["remote", "hybrid"], city="Казань")
    fsp_facts = facts_from_fsp(_demo_athlete())
    parsed = parse_resume(DEMO_RESUME, TODAY)
    facts: list[FactData] = [*fsp_facts, *parsed.facts]
    demo = snapshot(1, facts, prefs=prefs, city="Казань", salary=120000, resume_text=DEMO_RESUME)
    resume_only = snapshot(2, parsed.facts, prefs=prefs, city="Казань")
    no_stack = snapshot(3, [f for f in parsed.facts if f.kind != "skill"])  # no skills -> no stack

    query = MatchQuery(
        stacks=["backend"],
        skills_required=["python", "postgresql"],
        skills_optional=["kubernetes"],
        text="python backend разработчик fastapi",
    )
    ranked = rank(query, [resume_only, no_stack, demo])
    assert [r.candidate_id for r in ranked] == [1, 2]
    best = ranked[0]
    assert best.score is not None and 0 < best.score <= 100
    assert best.score > (ranked[1].score or 0)
    assert 2 <= len(best.reasons) <= 4
    assert "Совпало 2 из 2 обязательных навыков" in best.reasons
    assert any("ФСП" in reason for reason in best.reasons)
    assert [m.skill for m in best.missing_skills] == []

    only_fsp = rank(MatchQuery(fsp_verified_only=True), [resume_only, demo])
    assert [r.candidate_id for r in only_fsp] == [1]
    assert only_fsp[0].score is None  # no skills and no text: no score
