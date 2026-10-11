"""Matching: hard filters, the score formula, ranking and reasons (SPEC section 7.7)."""

from __future__ import annotations

import pytest
from domain_testkit import experience, fsp_achievement, skill, snapshot

from app.domain.embedding import embed
from app.domain.facts import manual_achievement_fact
from app.domain.matcher import parse_query_text, rank, score
from app.domain.types import CandidatePrefs, CandidateSnapshot, FactData, MatchQuery


def remote(**extra) -> CandidatePrefs:
    return CandidatePrefs(work_formats=["remote"], **extra)


def backend_facts() -> list[FactData]:
    return [
        skill("python", "test", 2),
        skill("fastapi", "resume", 2),
        skill("postgresql", "resume", 2),
        skill("docker", "resume", 2),
        experience(3),
    ]


def frontend_facts() -> list[FactData]:
    return [
        skill("react", "test", 2),
        skill("typescript", "resume", 2),
        skill("html-css", "resume", 2),
        experience(2),
    ]


def candidate(cid: int = 1, facts: list[FactData] | None = None, **kwargs) -> CandidateSnapshot:
    return snapshot(cid, backend_facts() if facts is None else facts, **kwargs)


def passes(query: MatchQuery, cand: CandidateSnapshot) -> bool:
    return score(query, cand, None) is not None


# --- hard filters --------------------------------------------------------------------------------
def test_invisible_candidate_never_matches() -> None:
    assert passes(MatchQuery(), candidate())
    assert not passes(MatchQuery(), candidate(visible=False))


def test_candidate_without_a_stack_never_matches() -> None:
    assert not passes(MatchQuery(), candidate(facts=[]))
    assert not passes(MatchQuery(), candidate(facts=[skill("git")]))


def test_stack_filter() -> None:
    cand = candidate()
    assert cand.category.stack == "backend"
    assert passes(MatchQuery(stacks=["backend"]), cand)
    assert passes(MatchQuery(stacks=["frontend", "backend"]), cand)
    assert not passes(MatchQuery(stacks=["frontend"]), cand)
    assert not passes(MatchQuery(stacks=["fullstack"]), cand)


def test_fullstack_candidate_passes_backend_and_frontend_filters() -> None:
    facts = [skill(s, "fsp", 2) for s in ("python", "fastapi", "react", "javascript")]
    cand = candidate(facts=facts)
    assert cand.category.stack == "fullstack"
    assert passes(MatchQuery(stacks=["backend"]), cand)
    assert passes(MatchQuery(stacks=["frontend"]), cand)
    assert passes(MatchQuery(stacks=["fullstack"]), cand)
    assert not passes(MatchQuery(stacks=["mobile"]), cand)
    assert not passes(MatchQuery(stacks=["devops", "qa"]), cand)


def test_grade_and_team_role_filters() -> None:
    cand = candidate()
    assert (cand.category.grade, cand.category.team_role) == ("middle", "developer")
    assert passes(MatchQuery(grades=["middle", "senior"]), cand)
    assert not passes(MatchQuery(grades=["junior"]), cand)
    assert passes(MatchQuery(team_roles=["developer"]), cand)
    assert not passes(MatchQuery(team_roles=["lead", "qa"]), cand)


def test_work_format_filter() -> None:
    cand = candidate(prefs=CandidatePrefs(work_formats=["remote", "hybrid"]))
    assert passes(MatchQuery(work_formats=["remote"]), cand)
    assert passes(MatchQuery(work_formats=["office", "hybrid"]), cand)
    assert not passes(MatchQuery(work_formats=["office"]), cand)


def test_candidate_without_formats_passes_the_format_filter() -> None:
    cand = candidate()
    assert cand.category.work_formats == []
    assert passes(MatchQuery(work_formats=["office"]), cand)


def test_city_filter() -> None:
    cand = candidate(city="Казань", prefs=CandidatePrefs(city="Казань"))
    assert passes(MatchQuery(city="Казань"), cand)
    assert passes(MatchQuery(city="  казань "), cand)
    assert not passes(MatchQuery(city="Москва"), cand)
    assert passes(MatchQuery(), cand)


def test_city_filter_with_relocation() -> None:
    cand = candidate(city="Казань", relocation=True)
    assert passes(MatchQuery(city="Москва"), cand)
    nobody = candidate(city=None)
    assert not passes(MatchQuery(city="Москва"), nobody)


def test_city_filter_with_remote_on_both_sides() -> None:
    cand = candidate(city="Казань", prefs=CandidatePrefs(work_formats=["remote", "office"]))
    assert passes(MatchQuery(city="Москва", work_formats=["remote"]), cand)
    assert not passes(MatchQuery(city="Москва", work_formats=["office"]), cand)
    assert not passes(MatchQuery(city="Москва"), cand)  # the query does not say "remote"
    office_only = candidate(city="Казань", prefs=CandidatePrefs(work_formats=["office"]))
    assert not passes(MatchQuery(city="Москва", work_formats=["remote"]), office_only)


def test_fsp_verified_only() -> None:
    plain = candidate()
    with_result = candidate(facts=[*backend_facts(), fsp_achievement("R1", "regional", 5)])
    manual_only = candidate(
        facts=[
            *backend_facts(),
            manual_achievement_fact("u", "ICPC", 2023, "national", "winner", None, None),
        ]
    )
    query = MatchQuery(fsp_verified_only=True)
    assert not passes(query, plain)
    assert not passes(query, manual_only)
    assert passes(query, with_result)


def test_confirmed_only() -> None:
    resume_only = candidate(facts=[skill("python"), skill("fastapi"), experience(3)])
    query = MatchQuery(confirmed_only=True)
    assert not passes(query, resume_only)
    assert passes(query, candidate())  # one test is enough
    assert passes(query, candidate(facts=[skill("python", "fsp", 3), skill("fastapi", "fsp", 3)]))


def test_discipline_filter() -> None:
    cand = candidate(facts=[*backend_facts(), fsp_achievement("R1", "national", 2)])
    assert passes(MatchQuery(disciplines=["algorithmic"]), cand)
    assert passes(MatchQuery(disciplines=["product", "algorithmic"]), cand)
    assert not passes(MatchQuery(disciplines=["product"]), cand)
    assert not passes(MatchQuery(disciplines=["algorithmic"]), candidate())
    manual = manual_achievement_fact("u", "ICPC", 2023, "national", "winner", "algorithmic", None)
    manual_only = candidate(facts=[*backend_facts(), manual])
    assert not passes(MatchQuery(disciplines=["algorithmic"]), manual_only)


def test_salary_filter() -> None:
    cand = candidate(salary=200_000)
    assert passes(MatchQuery(salary_max=200_000), cand)
    assert passes(MatchQuery(salary_max=300_000), cand)
    assert not passes(MatchQuery(salary_max=150_000), cand)
    assert passes(MatchQuery(salary_max=1), candidate(salary=None))


def test_strict_skills_need_evidence_of_at_least_0_4() -> None:
    cand = candidate()  # python 0.68 (test), docker 0.44 (resume)
    assert passes(MatchQuery(skills_required=["python", "docker"], strict_skills=True), cand)
    assert not passes(
        MatchQuery(skills_required=["python", "kubernetes"], strict_skills=True), cand
    )
    assert passes(MatchQuery(skills_required=["python", "kubernetes"]), cand)
    weak = candidate(facts=[skill("python", "resume", 1), skill("fastapi", "test", 1)])  # 0.33
    assert not passes(MatchQuery(skills_required=["python"], strict_skills=True), weak)
    assert passes(MatchQuery(skills_required=["fastapi"], strict_skills=True), weak)
    # optional skills are never strict
    assert passes(MatchQuery(skills_optional=["kubernetes"], strict_skills=True), cand)


# --- the formula ---------------------------------------------------------------------------------
def test_skill_component_prefers_required_skills() -> None:
    cand = candidate(facts=[skill("python", "test", 3), skill("docker", "resume", 2)])  # 0.85, 0.44
    only_required = score(MatchQuery(skills_required=["python"]), cand, None)
    only_optional = score(MatchQuery(skills_optional=["docker"]), cand, None)
    assert only_required and only_optional
    assert only_required.components.skill == pytest.approx(0.85)  # avg over required
    assert only_optional.components.skill == pytest.approx(0.44)  # avg over optional

    both = score(
        MatchQuery(skills_required=["python"], skills_optional=["docker", "kubernetes"]), cand, None
    )
    assert both and both.components.skill == pytest.approx(0.8 * 0.85 + 0.2 * (0.44 + 0) / 2)


def test_required_skill_outweighs_an_optional_one() -> None:
    has_required = candidate(1, [skill("python", "resume", 2), skill("fastapi", "resume", 2)])
    has_optional = candidate(2, [skill("docker", "resume", 2), skill("fastapi", "resume", 2)])
    query = MatchQuery(skills_required=["python"], skills_optional=["docker"])
    a = score(query, has_required, None)
    b = score(query, has_optional, None)
    assert a and b
    assert a.components.skill == pytest.approx(0.8 * 0.44)
    assert b.components.skill == pytest.approx(0.2 * 0.44)
    assert a.components.skill > b.components.skill


def test_a_skill_listed_twice_is_counted_once() -> None:
    cand = candidate()
    twice = score(MatchQuery(skills_required=["python"], skills_optional=["python"]), cand, None)
    once = score(MatchQuery(skills_required=["python"]), cand, None)
    assert twice and once
    assert twice.components == once.components


def test_score_uses_all_four_components() -> None:
    cand = candidate(facts=[*backend_facts(), fsp_achievement("R1", "national", 1)])
    vec = embed("python backend fastapi")
    result = score(MatchQuery(skills_required=["python", "fastapi"]), cand, vec)
    assert result and result.score is not None
    parts = result.components
    assert parts.skill is not None and parts.text is not None
    expected = 100 * (0.45 * parts.skill + 0.25 * parts.text + 0.20 * parts.track_record
                      + 0.10 * parts.confidence)
    assert result.score == pytest.approx(expected, abs=0.06)
    assert 0 <= result.score <= 100


def test_track_record_and_confidence_components() -> None:
    cand = candidate(facts=[*backend_facts(), fsp_achievement("R1", "national", 1)])
    # registry result 14 points -> 0.5 x 14/40; experience 3 years with one test -> 0.8 x 33
    category = cand.category
    expected_track = 0.5 * min(1, category.achievement_points / 40) + 0.5 * min(
        1, category.experience_points / 40
    )
    result = score(MatchQuery(skills_required=["python"]), cand, None)
    assert result
    assert result.components.track_record == pytest.approx(expected_track, abs=1e-4)
    assert result.components.track_record == pytest.approx(0.5 * 0.35 + 0.5 * 0.66, abs=1e-3)
    assert result.components.confidence == pytest.approx(category.confidence_index / 100)
    assert result.components.confidence == 0.75


def test_weights_are_renormalised_without_text() -> None:
    cand = candidate()
    result = score(MatchQuery(skills_required=["python"]), cand, None)
    assert result and result.score is not None
    parts = result.components
    assert parts.text is None
    weighted = 0.45 * parts.skill + 0.20 * parts.track_record + 0.10 * parts.confidence
    assert result.score == pytest.approx(100 * weighted / 0.75, abs=0.06)


def test_weights_are_renormalised_without_skills() -> None:
    cand = candidate()
    result = score(MatchQuery(text="python backend"), cand, embed("python backend"))
    assert result and result.score is not None
    parts = result.components
    assert parts.skill is None
    assert parts.text is not None and parts.text > 0
    weighted = 0.25 * parts.text + 0.20 * parts.track_record + 0.10 * parts.confidence
    assert result.score == pytest.approx(100 * weighted / 0.55, abs=0.06)


def test_text_component_is_never_negative() -> None:
    cand = candidate()
    cand.embedding = [-x for x in embed("python backend fastapi docker")]
    result = score(MatchQuery(text="x"), cand, embed("python backend fastapi docker"))
    assert result and result.components.text == 0.0


def test_no_skills_and_no_text_means_no_score() -> None:
    result = score(MatchQuery(stacks=["backend"]), candidate(), None)
    assert result
    assert result.score is None
    assert result.components.skill is None
    assert result.components.text is None
    assert result.components.track_record > 0


def test_a_query_vector_without_features_is_no_text() -> None:
    result = score(MatchQuery(text="и в на"), candidate(), embed("и в на"))
    assert result and result.score is None and result.components.text is None


def test_score_is_rounded_to_one_decimal() -> None:
    result = score(MatchQuery(skills_required=["python", "fastapi"]), candidate(), None)
    assert result and result.score is not None
    assert result.score == round(result.score, 1)


# --- ranking -------------------------------------------------------------------------------------
def test_rank_orders_by_score_then_id() -> None:
    strong = candidate(5, [skill("python", "test", 3), skill("fastapi", "test", 3), experience(5)])
    weak = candidate(2, [skill("python", "resume", 1), skill("fastapi", "resume", 1)])
    twin_a = candidate(9, [skill("python", "resume", 2), skill("fastapi", "resume", 2)])
    twin_b = candidate(7, [skill("python", "resume", 2), skill("fastapi", "resume", 2)])
    query = MatchQuery(skills_required=["python", "fastapi"])
    ranked = rank(query, [weak, twin_a, strong, twin_b])
    assert [r.candidate_id for r in ranked] == [5, 7, 9, 2]
    assert ranked[1].score == ranked[2].score
    scores = [r.score for r in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rank_breaks_score_ties_by_confidence_before_id() -> None:
    plain = candidate(1, [skill("python", "fsp", 1), skill("fastapi", "fsp", 1)])
    # same evidence in the skills, but more confirmation -> higher confidence
    confirmed = candidate(
        2,
        [
            skill("python", "fsp", 1),
            skill("fastapi", "fsp", 1),
            fsp_achievement("R", "municipal", 30),
        ],
    )
    ranked = rank(MatchQuery(skills_required=["python", "fastapi"]), [plain, confirmed])
    assert ranked[0].candidate_id == 2


def test_rank_drops_candidates_that_fail_filters() -> None:
    hidden = candidate(3, frontend_facts(), visible=False)
    ranked = rank(
        MatchQuery(stacks=["frontend"], skills_required=["react"]),
        [candidate(1), candidate(2, frontend_facts()), hidden],
    )
    assert [r.candidate_id for r in ranked] == [2]


def test_rank_without_score_sorts_by_track_record_confidence_id() -> None:
    star = candidate(
        4, [*backend_facts(), fsp_achievement("R1", "international", 1), experience(6)]
    )
    mid = candidate(3, backend_facts())
    same_a = candidate(8, [skill("python"), skill("fastapi"), experience(2)])
    same_b = candidate(6, [skill("python"), skill("fastapi"), experience(2)])
    ranked = rank(MatchQuery(), [same_a, mid, same_b, star])
    assert all(r.score is None for r in ranked)
    assert [r.candidate_id for r in ranked] == [4, 3, 6, 8]
    key = lambda r: (-r.components.track_record, -r.components.confidence, r.candidate_id)  # noqa: E731
    assert ranked == sorted(ranked, key=key)


def test_rank_uses_the_text_of_the_query() -> None:
    backend = candidate(1, backend_facts(), about="Люблю backend и Python")
    frontend = candidate(2, frontend_facts(), about="Люблю интерфейсы и React")
    ranked = rank(MatchQuery(text="нужен python backend разработчик"), [frontend, backend])
    assert [r.candidate_id for r in ranked] == [1, 2]
    assert ranked[0].components.text > ranked[1].components.text
    assert ranked[0].score > ranked[1].score


def test_rank_of_nothing() -> None:
    assert rank(MatchQuery(skills_required=["python"]), []) == []


# --- explanation ---------------------------------------------------------------------------------
def test_matched_and_missing_skills() -> None:
    cand = candidate()
    query = MatchQuery(
        skills_required=["python", "fastapi", "kubernetes", "terraform"],
        skills_optional=["docker", "kafka"],
    )
    result = score(query, cand, None)
    assert result
    assert [m.skill for m in result.matched_skills] == ["python", "fastapi", "docker"]
    assert result.matched_skills[0].verification == "tested"
    assert result.matched_skills[0].title == "Python"
    assert [(m.skill, m.title) for m in result.missing_skills] == [
        ("kubernetes", "Kubernetes"),
        ("terraform", "Terraform"),
    ]  # only required skills can be missing


def test_unknown_skill_id_does_not_break_scoring() -> None:
    result = score(MatchQuery(skills_required=["python", "cobol"]), candidate(), None)
    assert result
    assert [(m.skill, m.title) for m in result.missing_skills] == [("cobol", "cobol")]


def test_reasons_example_phrases() -> None:
    facts = [
        skill("python", "test", 2),
        skill("fastapi", "resume", 2),
        skill("postgresql", "resume", 2),
        experience(3),
        fsp_achievement("R1", "national", 3),
    ]
    cand = candidate(facts=facts)
    query = MatchQuery(skills_required=["python", "fastapi", "postgresql", "kubernetes"])
    result = score(query, cand, None)
    assert result
    assert result.reasons == [
        "Совпало 3 из 4 обязательных навыков",
        "Python подтверждён тестом",
        "Призовое место на всероссийских соревнованиях ФСП",
        "Не хватает: Kubernetes",
    ]


def test_reasons_are_between_two_and_four() -> None:
    cands = [candidate(1), candidate(2, frontend_facts()), candidate(3, [skill("react", "fsp", 3)])]
    queries = [
        MatchQuery(),
        MatchQuery(skills_required=["kubernetes"]),
        MatchQuery(skills_required=["python", "docker", "kubernetes", "terraform", "ansible"]),
        MatchQuery(skills_optional=["react"], text="react frontend"),
        MatchQuery(text="python backend", skills_required=["python"]),
    ]
    for query in queries:
        vec = embed(query.text) if query.text else None
        for cand in cands:
            result = score(query, cand, vec)
            if result is None:
                continue
            assert 2 <= len(result.reasons) <= 4, (query, cand.id, result.reasons)
            assert all(isinstance(r, str) and r for r in result.reasons)
            assert len(set(result.reasons)) == len(result.reasons)


def test_reasons_for_prize_levels() -> None:
    def prize_reason(level: str, place: int) -> list[str]:
        cand = candidate(facts=[*backend_facts(), fsp_achievement("R", level, place)])
        result = score(MatchQuery(skills_required=["python"]), cand, None)
        assert result
        return [r for r in result.reasons if "ФСП" in r]

    assert prize_reason("international", 1) == ["Призовое место на международных соревнованиях ФСП"]
    assert prize_reason("regional", 2) == ["Призовое место на региональных соревнованиях ФСП"]
    assert prize_reason("district", 3) == ["Призовое место на окружных соревнованиях ФСП"]
    assert prize_reason("national", 7) == []


def test_reasons_mention_registry_confirmed_skills() -> None:
    cand = candidate(facts=[skill("algorithms", "fsp", 3), skill("python", "fsp", 3)])
    result = score(MatchQuery(skills_required=["algorithms", "python"]), cand, None)
    assert result
    assert "Алгоритмы и структуры данных и Python подтверждены результатами ФСП" in result.reasons


def test_top_achievements() -> None:
    facts = [
        *backend_facts(),
        fsp_achievement("A", "regional", 1, title="Региональный", year=2022),
        fsp_achievement("B", "international", 2, title="Международный", year=2024),
        fsp_achievement("C", "national", 1, title="Всероссийский", year=2023),
        fsp_achievement("D", "municipal", 1, title="Городской", year=2021),
        manual_achievement_fact("u", "ICPC", 2023, "national", "winner", None, None),
    ]
    result = score(MatchQuery(skills_required=["python"]), candidate(facts=facts), None)
    assert result
    top = result.top_achievements
    assert [t.title for t in top] == ["Международный", "Всероссийский", "Региональный"]
    assert top[0].level == "international"
    assert top[0].place == 2
    assert top[0].year == 2024
    assert top[0].verification == "verified"
    no_achievements = score(MatchQuery(skills_required=["python"]), candidate(), None)
    assert no_achievements and no_achievements.top_achievements == []


# --- query text ----------------------------------------------------------------------------------
def test_parse_query_text() -> None:
    parsed = parse_query_text("Ищем middle python разработчика с fastapi и docker")
    assert parsed.skills == ["python", "fastapi", "docker"]
    assert parsed.stack == "backend"
    assert parsed.grade == "middle"


@pytest.mark.parametrize(
    ("text", "stack", "grade", "skills"),
    [
        ("senior frontend react", "frontend", "senior", ["react"]),
        ("джуниор тестировщик", "qa", "junior", []),
        ("стажёр в мобильную разработку", "mobile", "intern", []),
        ("fullstack разработчик, python и react", "fullstack", None, ["python", "react"]),
        ("Ведущий бэкенд-разработчик на Java", "backend", "senior", ["java"]),
        ("девопс инженер, kubernetes, terraform", "devops", None, ["kubernetes", "terraform"]),
        ("Не senior. Нужен middle", None, "middle", []),
        ("не senior, а middle", None, None, []),  # "не" is within four words of both
        ("go to market", None, None, []),
        ("", None, None, []),
        ("python", None, None, ["python"]),
        ("python fastapi", "backend", None, ["python", "fastapi"]),
        ("аналитик данных, sql, pandas", "analyst", None, ["data-analysis", "sql", "pandas"]),
    ],
)
def test_parse_query_text_hints(
    text: str, stack: str | None, grade: str | None, skills: list[str]
) -> None:
    parsed = parse_query_text(text)
    assert parsed.stack == stack
    assert parsed.grade == grade
    assert parsed.skills == skills
