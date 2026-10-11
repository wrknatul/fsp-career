"""Stack, grade, role and confidence of a candidate (SPEC sections 7.1-7.5)."""

from __future__ import annotations

import pytest
from domain_testkit import (
    athlete_record,
    experience,
    fsp_achievement,
    role_fact,
    skill,
)

from app.domain.categorizer import categorize, skill_evidence
from app.domain.facts import manual_achievement_fact
from app.domain.fsp_mapping import facts_from_fsp
from app.domain.types import CandidatePrefs, FactData

PREFS = CandidatePrefs(work_formats=["remote", "hybrid"])
BACKEND_SKILLS = [skill("python"), skill("fastapi")]  # two resume skills: S(backend) = 0.88
FIVE_WINS = [fsp_achievement(f"W{i}", "national", 1) for i in range(5)]


def _sum_of_explanations(category) -> float:
    return round(sum(e.points for e in category.grade_explanations), 1)


# --- the six reference cases of SPEC 7.3 ---------------------------------------------------------
def test_reference_ten_years_from_a_resume_without_tests() -> None:
    category = categorize([*BACKEND_SKILLS, experience(10)], PREFS)
    assert category.grade_points == 46.8
    assert category.grade == "middle"
    assert category.grade_confirmed is False
    assert category.grade_note == (
        "Грейд основан на опыте из резюме без подтверждения. "
        "Пройдите тест — опыт будет засчитан полнее"
    )


def test_reference_five_years_without_tests() -> None:
    category = categorize([*BACKEND_SKILLS, experience(5)], PREFS)
    assert category.grade_points == 30.6
    assert category.grade == "junior"
    assert category.grade_note is None


def test_reference_five_years_and_one_test() -> None:
    category = categorize([*BACKEND_SKILLS, experience(5), skill("python", "test", 2)], PREFS)
    assert category.grade_points == 50.8
    assert category.grade == "middle"
    assert category.grade_confirmed is True
    assert category.grade_note is None


def test_reference_eight_years_and_two_perfect_tests() -> None:
    facts = [
        *BACKEND_SKILLS,
        experience(8),
        skill("python", "test", 3),
        skill("algorithms", "test", 3),
    ]
    category = categorize(facts, PREFS)
    assert category.grade_points == 108
    assert category.grade == "senior"
    assert category.grade_confirmed is True
    assert category.grade_note is None


def test_reference_student_with_two_international_wins() -> None:
    facts = [
        skill("algorithms", "fsp", 3),
        fsp_achievement("A", "international", 1),
        fsp_achievement("B", "international", 1),
    ]
    category = categorize(facts, PREFS)
    assert category.grade_points == 40
    assert category.stack == "backend"
    assert category.grade == "junior"  # 40 points say middle, the gate says junior
    assert category.grade_note == (
        "Спортивные результаты учтены, но без опыта работы грейд не выше Junior"
    )
    assert category.achievement_points == 40


def test_reference_one_year_and_a_perfect_test() -> None:
    category = categorize([*BACKEND_SKILLS, experience(1), skill("python", "test", 3)], PREFS)
    assert category.grade_points == 24.6
    assert category.grade == "junior"
    assert [e.points for e in category.grade_explanations] == [9.6, 15.0]


@pytest.mark.parametrize(
    "facts",
    [
        [*BACKEND_SKILLS, experience(10)],
        [*BACKEND_SKILLS, experience(1.37), skill("python", "test", 2), skill("sql", "test", 3)],
        [skill("algorithms", "fsp", 3), *FIVE_WINS],
        [
            *BACKEND_SKILLS,
            experience(2.6),
            manual_achievement_fact("u1", "ВсОШ", 2022, "regional", "prize", None, None),
            manual_achievement_fact("u2", "ICPC", 2023, "international", "winner", None, None),
            manual_achievement_fact("u3", "CTF", 2023, "national", "winner", None, None),
            manual_achievement_fact("u4", "Хакатон", 2024, "national", "participant", None, None),
        ],
        facts_from_fsp(athlete_record()),
    ],
)
def test_explanations_always_sum_to_the_points(facts: list[FactData]) -> None:
    category = categorize(facts, PREFS)
    assert _sum_of_explanations(category) == category.grade_points
    assert category.grade_explanations


def test_gates_change_the_grade_but_not_the_points() -> None:
    wins = [fsp_achievement(f"W{i}", "national", 1) for i in range(3)]
    gated = categorize([skill("algorithms", "fsp", 3), *wins], PREFS)
    assert gated.grade_points == 40  # capped
    assert gated.grade == "junior"
    assert gated.grade_explanations[-1].points == pytest.approx(-2)


# --- explanations --------------------------------------------------------------------------------
def test_experience_explanation_text() -> None:
    category = categorize([*BACKEND_SKILLS, experience(1.5)], PREFS)
    experience_row = category.grade_explanations[0]
    assert experience_row.label == "Опыт в ИТ: 1,5 года, доверие 0,6"
    assert experience_row.points == 10.8
    assert (experience_row.source, experience_row.verification) == ("resume", "parsed")
    assert category.experience_points == 10.8
    assert category.experience_years == 1.5


def test_one_row_per_contribution() -> None:
    facts = [
        *BACKEND_SKILLS,
        experience(3),
        skill("python", "test", 2),
        fsp_achievement("R1", "national", 3, title="Чемпионат"),
        FactData(
            kind="rank",
            key="sport_rank",
            title="КМС · Алгоритмическое программирование",
            value={"rank": "kms", "discipline": "algorithmic"},
            source="fsp",
            verification="verified",
        ),
        manual_achievement_fact("u1", "ВсОШ", 2022, "regional", "prize", None, None),
    ]
    category = categorize(facts, PREFS)
    labels = [e.label for e in category.grade_explanations]
    assert labels == [
        "Опыт в ИТ: 3 года, доверие 0,8",
        "Тест: Python, Уверенный",
        "Чемпионат — 3 место",
        "КМС · Алгоритмическое программирование",
        "ВсОШ, 2022 — призёр",
    ]
    points = [e.points for e in category.grade_explanations]
    assert points == [pytest.approx(26.4), 10.0, pytest.approx(11.2), 14.0, pytest.approx(1.4)]
    assert category.achievement_points == pytest.approx(25.2)  # registry result + rank only


def test_caps_add_a_negative_row() -> None:
    results = [fsp_achievement(str(i), "international", 1) for i in range(3)]  # 60 points
    category = categorize([skill("algorithms", "fsp", 3), *results], PREFS)
    cap = category.grade_explanations[-1]
    assert cap.label == "Потолок: не больше 40 баллов за результаты ФСП"
    assert cap.points == -20
    assert cap.source is None
    assert category.grade_points == 40
    assert category.achievement_points == 40


def test_test_and_manual_caps() -> None:
    tests = [skill(name, "test", 3) for name in ("python", "sql", "algorithms", "javascript")]
    category = categorize(tests, PREFS)
    assert category.grade_points == 30
    assert category.grade_explanations[-1].label == (
        "Потолок: не больше 30 баллов за экспресс-тесты"
    )
    manual = [
        manual_achievement_fact(f"u{i}", f"ICPC {i}", 2023, "international", "winner", None, None)
        for i in range(2)
    ]  # 2 x 7 points
    capped = categorize([*BACKEND_SKILLS, *manual], PREFS)
    assert capped.grade_points == 10
    assert "10 баллов" in capped.grade_explanations[-1].label


def test_manual_achievement_is_worth_35_percent() -> None:
    fact = manual_achievement_fact("u", "ICPC", 2023, "national", "winner", None, None)
    category = categorize([*BACKEND_SKILLS, fact], PREFS)
    assert category.grade_points == pytest.approx(4.9, abs=0.05)  # 14 x 1.0 x 0.35
    assert category.grade_explanations[0].verification == "declared"
    assert category.grade_confirmed is False


def test_trust_in_experience_grows_with_tests() -> None:
    def experience_points(*tests: str) -> float:
        facts = [*BACKEND_SKILLS, experience(2), *(skill(t, "test", 1) for t in tests)]
        return categorize(facts, PREFS).experience_points

    assert experience_points() == pytest.approx(14.4)
    assert experience_points("python") == pytest.approx(19.2)
    assert experience_points("python", "sql") == pytest.approx(24.0)
    assert experience_points("python", "sql", "algorithms") == pytest.approx(24.0)


# --- skills and stack ----------------------------------------------------------------------------
def test_skill_evidence_formula() -> None:
    facts = [
        skill("python", "resume", 2),  # 0.55 x 0.8 = 0.44
        skill("sql", "resume", 1),  # 0.55 x 0.6 = 0.33
        skill("docker", "test", 1),  # 0.85 x 0.6 = 0.51
        skill("git", "fsp", 3),  # 1.0
        skill("redis", "self", 2),  # 0.35 x 0.8 = 0.28
    ]
    evidence = skill_evidence(facts)
    assert evidence["python"].evidence == pytest.approx(0.44)
    assert evidence["sql"].evidence == pytest.approx(0.33)
    assert evidence["docker"].evidence == pytest.approx(0.51)
    assert evidence["git"].evidence == pytest.approx(1.0)
    assert evidence["redis"].evidence == pytest.approx(0.28)
    assert evidence["python"].best_source == "resume"
    assert evidence["docker"].verification == "tested"
    assert evidence["python"].title == "Python"


def test_a_test_is_always_stronger_than_a_resume() -> None:
    assert skill_evidence([skill("python", "test", 1)])["python"].evidence > 0.44


def test_second_source_adds_a_bonus_and_the_best_source_wins() -> None:
    evidence = skill_evidence([skill("python", "resume", 2), skill("python", "test", 2)])
    item = evidence["python"]
    assert item.evidence == pytest.approx(0.68 + 0.1)
    assert (item.best_source, item.verification) == ("test", "tested")
    capped = skill_evidence([skill("python", "fsp", 3), skill("python", "test", 3)])
    assert capped["python"].evidence == 1.0


def test_unknown_skills_are_ignored() -> None:
    fact = FactData(
        kind="skill",
        key="cobol",
        title="COBOL",
        value={"level": 2},
        source="resume",
        verification="parsed",
    )
    assert skill_evidence([fact]) == {}


def test_stack_from_the_registry_alone_is_backend() -> None:
    category = categorize(facts_from_fsp(athlete_record()), PREFS)
    assert category.stack == "backend"
    assert category.stack_confirmed is True
    scores = {s.stack: s.score for s in category.stack_scores}
    assert scores["backend"] == pytest.approx(2.0)  # 1.0 + 0.5 + the 0.5 hint of fsp_team:backend
    assert list(scores) == sorted(scores, key=lambda k: -scores[k])
    assert all(v > 0 for v in scores.values())
    assert "fullstack" not in scores


def test_team_role_hint_needs_an_existing_score() -> None:
    assert categorize([role_fact("fsp_team:backend")], PREFS).stack is None
    with_skill = categorize([skill("python", "resume", 1), role_fact("fsp_team:backend")], PREFS)
    without = categorize([skill("python", "resume", 1)], PREFS)
    assert with_skill.stack == "backend"
    assert without.stack is None  # 0.33 < 0.5


def test_fullstack_needs_both_halves() -> None:
    fullstack = categorize(
        [skill("python", "fsp", 2), skill("fastapi", "fsp", 2), skill("react", "fsp", 2),
         skill("javascript", "fsp", 2)],
        PREFS,
    )
    assert fullstack.stack == "fullstack"
    assert fullstack.stack_confirmed is True
    assert fullstack.team_role == "developer"
    assert "fullstack" not in {s.stack for s in fullstack.stack_scores}


def test_unbalanced_backend_and_frontend_is_not_fullstack() -> None:
    category = categorize(
        [skill(s, "fsp", 3) for s in ("java", "spring", "go", "php")] + [skill("react", "fsp", 3)],
        PREFS,
    )
    assert category.stack == "backend"  # S(frontend) = 1.0 is below 60% of S(backend) = 3.0


def test_weak_frontend_is_not_fullstack() -> None:
    category = categorize(
        [skill("python", "fsp", 3), skill("fastapi", "fsp", 3), skill("react", "resume", 2)],
        PREFS,
    )
    assert category.stack == "backend"


def test_tie_goes_to_the_first_stack_in_the_dictionary() -> None:
    category = categorize([skill("python", "fsp", 3)], PREFS)  # backend and ml both 1.0
    assert category.stack == "backend"


def test_stack_score_is_capped() -> None:
    skills = [skill(s, "fsp", 3) for s in ("java", "spring", "go", "php", "csharp", "nodejs")]
    scores = {s.stack: s.score for s in categorize(skills, PREFS).stack_scores}
    assert scores["backend"] == 3.0


def test_stack_needs_half_a_point() -> None:
    assert categorize([skill("python", "resume", 2)], PREFS).stack is None  # 0.44
    with_git = categorize([skill("python", "resume", 2), skill("git", "resume", 2)], PREFS)
    assert with_git.stack is None  # git belongs to no stack
    assert categorize([skill("python", "test", 1)], PREFS).stack == "backend"  # 0.51


def test_stack_confirmed_needs_a_core_skill_proved_by_a_test_or_the_registry() -> None:
    resume_only = categorize(BACKEND_SKILLS, PREFS)
    assert resume_only.stack == "backend"
    assert resume_only.stack_confirmed is False
    secondary_only = categorize(
        [skill("redis", "test", 3), skill("kafka", "test", 3), skill("mongodb", "test", 3)], PREFS
    )
    assert secondary_only.stack == "backend"
    assert secondary_only.stack_confirmed is False  # redis, kafka, mongodb are secondary
    assert categorize([*BACKEND_SKILLS, skill("python", "test", 1)], PREFS).stack_confirmed is True


# --- empty profile -------------------------------------------------------------------------------
def test_empty_profile() -> None:
    category = categorize([], CandidatePrefs(work_formats=["office"]))
    assert category.stack is None
    assert category.grade is None
    assert category.team_role is None
    assert category.team_role_source is None
    assert category.label == "Категория не определена"
    assert category.grade_confirmed is False
    assert category.grade_points == 0
    assert category.grade_explanations == []
    assert category.stack_scores == []
    assert category.top_skills == []
    assert category.confidence_index == 0
    assert category.work_formats == ["office"]
    assert len(category.confidence_breakdown) == 2


def test_without_a_stack_there_is_no_grade() -> None:
    category = categorize([experience(6), skill("git", "resume", 2)], PREFS)
    assert category.stack is None
    assert category.grade is None
    assert category.label == "Категория не определена"
    assert category.experience_years == 6


# --- team role -----------------------------------------------------------------------------------
def test_lead_needs_the_resume_fact_and_three_years() -> None:
    lead = role_fact("resume_lead", "resume")
    category = categorize([*BACKEND_SKILLS, experience(3), lead], PREFS)
    assert category.team_role == "lead"
    assert category.team_role_source == "resume"
    assert "Тимлид" in category.label
    short = categorize([*BACKEND_SKILLS, experience(2.9), lead], PREFS)
    assert short.team_role == "developer"
    assert short.team_role_source is None
    no_fact = categorize([*BACKEND_SKILLS, experience(8)], PREFS)
    assert no_fact.team_role == "developer"


def test_researcher_by_algorithmic_results_without_experience() -> None:
    facts = [
        skill("algorithms", "fsp", 3),
        fsp_achievement("A", "national", 1, discipline="algorithmic"),  # 14
        fsp_achievement("B", "national", 3, discipline="algorithmic"),  # 11.2
    ]
    assert categorize(facts, PREFS).team_role == "researcher"
    with_experience = categorize([*facts, experience(2)], PREFS)
    assert with_experience.team_role == "developer"
    other_discipline = [
        skill("algorithms", "fsp", 3),
        fsp_achievement("A", "national", 1, discipline="product"),
        fsp_achievement("B", "national", 3, discipline="product"),
    ]
    assert categorize(other_discipline, PREFS).team_role == "developer"
    weak = [skill("algorithms", "fsp", 3), fsp_achievement("A", "national", 1)]  # 14 < 20
    assert categorize(weak, PREFS).team_role == "developer"


def test_researcher_for_the_ml_stack() -> None:
    category = categorize([skill("pytorch", "test", 3), skill("sklearn", "test", 3)], PREFS)
    assert category.stack == "ml"
    assert category.team_role == "researcher"


@pytest.mark.parametrize(
    ("skills", "stack", "role"),
    [
        (("docker", "kubernetes"), "devops", "devops"),
        (("testing", "selenium"), "qa", "qa"),
        (("data-analysis", "bi-tools"), "analyst", "analyst"),
        (("react", "typescript"), "frontend", "developer"),
        (("kotlin", "android"), "mobile", "developer"),
        (("infosec", "pentest"), "security", "developer"),
        (("cpp", "microcontrollers"), "embedded", "developer"),
    ],
)
def test_role_follows_the_stack(skills: tuple[str, ...], stack: str, role: str) -> None:
    category = categorize([skill(s, "fsp", 3) for s in skills], PREFS)
    assert category.stack == stack
    assert category.team_role == role


# --- confidence index ----------------------------------------------------------------------------
def test_confidence_index() -> None:
    assert categorize(BACKEND_SKILLS, PREFS).confidence_index == 0  # resume does not count
    one_test = categorize([*BACKEND_SKILLS, skill("python", "test", 1)], PREFS)
    assert one_test.confidence_index == 25
    two_tests = categorize(
        [*BACKEND_SKILLS, skill("python", "test", 1), skill("sql", "test", 1)], PREFS
    )
    assert two_tests.confidence_index == 50
    three_tests = categorize(
        [skill(s, "test", 1) for s in ("python", "sql", "algorithms")], PREFS
    )
    assert three_tests.confidence_index == 50
    registry = categorize(facts_from_fsp(athlete_record()), PREFS)
    assert registry.confidence_index == 50
    everything = categorize(
        [*facts_from_fsp(athlete_record()), skill("python", "test", 1), skill("sql", "test", 1)],
        PREFS,
    )
    assert everything.confidence_index == 100


def test_confidence_breakdown_rows() -> None:
    category = categorize([*BACKEND_SKILLS, skill("python", "test", 1)], PREFS)
    registry, tests = category.confidence_breakdown
    assert (registry.label, registry.points, registry.max, registry.done) == (
        "Результаты в реестре ФСП",
        0,
        50,
        False,
    )
    assert (tests.label, tests.points, tests.max, tests.done) == (
        "Экспресс-тесты (до двух)",
        25,
        50,
        False,
    )
    full = categorize(
        [*facts_from_fsp(athlete_record()), skill("python", "test", 1), skill("sql", "test", 1)],
        PREFS,
    )
    assert [(i.points, i.done) for i in full.confidence_breakdown] == [(50, True), (50, True)]
    assert sum(i.points for i in full.confidence_breakdown) == full.confidence_index


def test_manual_achievement_does_not_raise_confidence() -> None:
    fact = manual_achievement_fact("u", "ICPC", 2023, "national", "winner", None, None)
    assert categorize([*BACKEND_SKILLS, fact], PREFS).confidence_index == 0


# --- label and the rest ----------------------------------------------------------------------
def test_label() -> None:
    facts = [*BACKEND_SKILLS, experience(5), skill("python", "test", 2)]
    assert categorize(facts, PREFS).label == "Backend · Middle · Разработчик · Удалённо, гибрид"
    assert categorize(facts, CandidatePrefs()).label == "Backend · Middle · Разработчик"
    office = CandidatePrefs(work_formats=["hybrid", "office", "remote"])
    assert categorize(facts, office).label == (
        "Backend · Middle · Разработчик · Удалённо, офис, гибрид"
    )
    assert categorize(facts, office).work_formats == ["remote", "office", "hybrid"]
    junior = categorize(BACKEND_SKILLS, CandidatePrefs(work_formats=["office"]))
    assert junior.label == "Backend · Стажёр · Разработчик · Офис"


def test_top_skills_are_at_most_eight_and_sorted() -> None:
    names = ["python", "java", "go", "php", "sql", "git", "docker", "redis", "kafka", "nginx"]
    facts = [skill(n, "resume", 1 + i % 2) for i, n in enumerate(names)]
    facts.append(skill("python", "test", 3))
    category = categorize(facts, PREFS)
    assert len(category.top_skills) == 8
    values = [s.evidence for s in category.top_skills]
    assert values == sorted(values, reverse=True)
    assert category.top_skills[0].skill == "python"


def test_categorize_is_deterministic_and_does_not_touch_its_input() -> None:
    facts = [*BACKEND_SKILLS, experience(4), skill("python", "test", 2)]
    snapshot = [f.model_copy(deep=True) for f in facts]
    first = categorize(facts, PREFS)
    again = categorize(facts, PREFS)
    reordered = categorize(list(reversed(facts)), PREFS)
    assert first.model_dump() == again.model_dump()
    for field in ("stack", "grade", "team_role", "label", "grade_points", "confidence_index"):
        assert getattr(first, field) == getattr(reordered, field), field
    assert facts == snapshot
