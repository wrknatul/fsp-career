"""Stack, grade, team role and confidence index of a candidate (SPEC sections 7.1-7.5)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.domain import scoring_config as cfg
from app.domain.facts import format_decimal, years_label
from app.domain.ontology import (
    CONCRETE_STACKS,
    GRADE_TITLES,
    STACK_TITLES,
    TEAM_ROLE_TITLES,
    WORK_FORMAT_TITLES,
    is_known_skill,
    load_ontology,
    skill_title,
)
from app.domain.types import (
    CandidatePrefs,
    Categorization,
    ConfidenceItem,
    Explanation,
    FactData,
    SkillEvidence,
    StackScore,
)

UNDEFINED_LABEL = "Категория не определена"

NOTE_NO_EXPERIENCE = (
    "Спортивные результаты учтены, но без опыта работы грейд не выше Junior"
)
NOTE_SENIOR_GATE = "Для Senior нужен опыт от 3 лет и подтверждение тестом или ФСП"
NOTE_UNCONFIRMED = (
    "Грейд основан на опыте из резюме без подтверждения. "
    "Пройдите тест — опыт будет засчитан полнее"
)

_CONFIRMING = ("verified", "tested")
_GRADE_ORDER = ("intern", "junior", "middle", "senior")


# --- helpers -------------------------------------------------------------------------------------
def _number(value: Any) -> float:
    """A float from a JSON value; anything that is not a number counts as zero."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)


def _skill_level(fact: FactData) -> int:
    level = int(_number(fact.value.get("level", 1)))
    return min(3, max(1, level))


def _verification_rank(verification: str) -> int:
    return cfg.VERIFICATION_ORDER.index(verification)


def place_factor(place: int | None, result: str | None = None) -> float:
    """1st place 1.0, 2nd-3rd 0.8, 4th-10th 0.5, everything else 0.25."""
    if place is None:
        place = {"winner": 1, "prize": 2}.get(result or "", cfg.TOP_MAX_PLACE + 1)
    if place == 1:
        return cfg.FSP_PLACE_FACTOR_WINNER
    if place <= cfg.PRIZE_MAX_PLACE:
        return cfg.FSP_PLACE_FACTOR_PRIZE
    if place <= cfg.TOP_MAX_PLACE:
        return cfg.FSP_PLACE_FACTOR_TOP
    return cfg.FSP_PLACE_FACTOR_OTHER


def fsp_result_points(fact: FactData) -> float:
    """base[level] x place_factor for an achievement from the registry."""
    base = cfg.FSP_LEVEL_BASE.get(str(fact.value.get("level")), 0.0)
    raw_place = fact.value.get("place")
    place = int(raw_place) if isinstance(raw_place, int | float) else None
    return base * place_factor(place, fact.value.get("result"))


def manual_result_points(fact: FactData) -> float:
    """base[level] x f x 0.35 for an achievement the candidate declared."""
    base = cfg.FSP_LEVEL_BASE.get(str(fact.value.get("level")), 0.0)
    factor = cfg.MANUAL_RESULT_FACTOR.get(str(fact.value.get("result")), 0.0)
    return base * factor * cfg.MANUAL_DISCOUNT


def experience_raw_points(years: float) -> float:
    fast = min(years, cfg.EXPERIENCE_FAST_YEARS)
    slow = max(0.0, min(years, cfg.EXPERIENCE_MAX_YEARS) - cfg.EXPERIENCE_FAST_YEARS)
    return cfg.EXPERIENCE_FAST_RATE * fast + cfg.EXPERIENCE_SLOW_RATE * slow


# --- 7.1 skill evidence --------------------------------------------------------------------------
def _fact_strength(fact: FactData) -> tuple[float, float]:
    """w(f) = verification weight x level factor; the weight alone breaks ties."""
    weight = cfg.VERIFICATION_WEIGHT[fact.verification]
    return (weight * cfg.LEVEL_FACTOR[_skill_level(fact)], weight)


def skill_evidence(facts: Iterable[FactData]) -> dict[str, SkillEvidence]:
    """E(s) for every known skill that has at least one skill fact.

    E = min(1, strongest w + 0.1 x (distinct sources - 1)), w = verification x level factor.
    """
    groups: dict[str, list[FactData]] = {}
    for fact in facts:
        if fact.kind == "skill" and is_known_skill(fact.key):
            groups.setdefault(fact.key, []).append(fact)

    result: dict[str, SkillEvidence] = {}
    for skill_id, group in groups.items():
        best = max(group, key=_fact_strength)
        sources = {fact.source for fact in group}
        evidence = min(
            cfg.EVIDENCE_CAP,
            _fact_strength(best)[0] + cfg.EXTRA_SOURCE_BONUS * (len(sources) - 1),
        )
        result[skill_id] = SkillEvidence(
            skill=skill_id,
            title=skill_title(skill_id),
            evidence=round(evidence, 4),
            best_source=best.source,
            verification=best.verification,
        )
    return result


# --- 7.2 stack -----------------------------------------------------------------------------------
def stack_totals(
    evidence: dict[str, SkillEvidence], facts: Iterable[FactData]
) -> dict[str, float]:
    """S(k) for the nine concrete stacks (zero scores included)."""
    ontology = load_ontology()
    totals = dict.fromkeys(CONCRETE_STACKS, 0.0)
    for skill_id, item in evidence.items():
        for stack, tier in ontology.by_id[skill_id].stacks.items():
            weight = cfg.CORE_WEIGHT if tier == "core" else cfg.SECONDARY_WEIGHT
            totals[stack] += item.evidence * weight

    # A team role from the registry nudges the same stack, but only if it already has a score.
    hinted = {
        fact.key.split(":", 1)[1]
        for fact in facts
        if fact.kind == "role" and fact.key.startswith("fsp_team:")
    }
    for role in hinted:
        if role in totals and totals[role] > 0:
            totals[role] += cfg.FSP_TEAM_BONUS
    return {stack: min(cfg.STACK_SCORE_CAP, score) for stack, score in totals.items()}


def choose_stack(totals: dict[str, float]) -> str | None:
    backend, frontend = totals["backend"], totals["frontend"]
    low, high = min(backend, frontend), max(backend, frontend)
    if (
        low >= cfg.FULLSTACK_MIN_SCORE - cfg.SCORE_EPSILON
        and low >= cfg.FULLSTACK_RATIO * high - cfg.SCORE_EPSILON
    ):
        return "fullstack"
    best: str | None = None
    best_score = 0.0
    floor = cfg.STACK_MIN_SCORE - cfg.SCORE_EPSILON
    for stack in CONCRETE_STACKS:  # official order breaks ties
        score = totals[stack]
        if score >= floor and score > best_score + cfg.SCORE_EPSILON:
            best, best_score = stack, score
    return best


def _stack_confirmed(stack: str, facts: Iterable[FactData]) -> bool:
    """The stack has a core skill proved by the registry or by a test."""
    ontology = load_ontology()
    wanted = ("backend", "frontend") if stack == "fullstack" else (stack,)
    core: set[str] = set()
    for name in wanted:
        core.update(ontology.core_skills(name))
    return any(
        fact.kind == "skill" and fact.key in core and fact.verification in _CONFIRMING
        for fact in facts
    )


# --- 7.3 grade -----------------------------------------------------------------------------------
def _grade_for_points(points: float) -> str:
    if points >= cfg.GRADE_SENIOR_FROM:
        return "senior"
    if points >= cfg.GRADE_MIDDLE_FROM:
        return "middle"
    if points >= cfg.GRADE_JUNIOR_FROM:
        return "junior"
    return "intern"


def _dedupe(facts: Iterable[FactData]) -> list[FactData]:
    """Keep one fact per (kind, key, source): the stable first one."""
    seen: dict[tuple[str, str, str], FactData] = {}
    for fact in facts:
        seen.setdefault((fact.kind, fact.key, fact.source), fact)
    return list(seen.values())


def _cap_row(name: str, cap: float, total: float) -> Explanation:
    return Explanation(
        label=f"Потолок: не больше {format_decimal(cap)} баллов за {name}",
        points=round(cap - total, 2),
        source=None,
        verification=None,
    )


def _row(label: str, points: float, fact: FactData) -> Explanation:
    return Explanation(
        label=label,
        points=round(points, 2),
        source=fact.source,
        verification=fact.verification,
    )


class _Grade:
    """Result of the points calculation: rows and the groups that feed other fields."""

    def __init__(self) -> None:
        self.rows: list[Explanation] = []
        self.years = 0.0
        self.experience_points = 0.0
        self.achievement_points = 0.0
        self.fsp_points_by_discipline: dict[str, float] = {}

    @property
    def total(self) -> float:
        return round(sum(row.points for row in self.rows), 1)


def _grade_points(facts: list[FactData]) -> _Grade:
    grade = _Grade()

    # Experience: the best figure among the experience facts, trusted by passed tests.
    years, years_fact = 0.0, None
    for fact in facts:
        if fact.kind == "experience" and _number(fact.value.get("years")) > years:
            years, years_fact = _number(fact.value.get("years")), fact
    grade.years = years

    tests = [f for f in _dedupe(facts) if f.kind == "skill" and f.source == "test"]
    if years_fact is not None:
        trust = cfg.EXPERIENCE_TRUST_BY_TESTS[min(len(tests), 2)]
        points = trust * experience_raw_points(years)
        grade.experience_points = round(points, 2)
        trust_text = f"{trust:.1f}".replace(".", ",")
        grade.rows.append(
            _row(f"Опыт в ИТ: {years_label(years)}, доверие {trust_text}", points, years_fact)
        )

    # Express tests, at most 30 points in total.
    test_total = 0.0
    for fact in tests:
        level = _skill_level(fact)
        points = cfg.TEST_POINTS[level]
        test_total += points
        title = f"Тест: {fact.title}, {cfg.QUIZ_LEVEL_TITLES[level]}"
        grade.rows.append(_row(title, points, fact))
    if test_total > cfg.TEST_POINTS_CAP:
        grade.rows.append(_cap_row("экспресс-тесты", cfg.TEST_POINTS_CAP, test_total))

    # Results from the registry, at most 40 points in total.
    fsp_total = 0.0
    for fact in _dedupe(facts):
        if fact.kind != "achievement" or fact.source != "fsp":
            continue
        points = fsp_result_points(fact)
        fsp_total += points
        discipline = fact.value.get("discipline")
        if isinstance(discipline, str):
            by_discipline = grade.fsp_points_by_discipline
            by_discipline[discipline] = by_discipline.get(discipline, 0.0) + points
        grade.rows.append(_row(fact.title, points, fact))
    if fsp_total > cfg.FSP_POINTS_CAP:
        grade.rows.append(_cap_row("результаты ФСП", cfg.FSP_POINTS_CAP, fsp_total))
    fsp_after_cap = min(fsp_total, cfg.FSP_POINTS_CAP)

    # The senior rank.
    rank_points, rank_fact = 0.0, None
    for fact in facts:
        if fact.kind != "rank":
            continue
        points = cfg.RANK_POINTS.get(str(fact.value.get("rank")), 0.0)
        if points > rank_points:
            rank_points, rank_fact = points, fact
    if rank_fact is not None:
        grade.rows.append(_row(rank_fact.title, rank_points, rank_fact))
    grade.achievement_points = round(fsp_after_cap + rank_points, 2)

    # Achievements added by hand, worth 35% of the registry value, at most 10 points.
    manual_total = 0.0
    for fact in _dedupe(facts):
        if fact.kind != "achievement" or fact.source != "self":
            continue
        points = manual_result_points(fact)
        manual_total += points
        grade.rows.append(_row(fact.title, points, fact))
    if manual_total > cfg.MANUAL_POINTS_CAP:
        grade.rows.append(
            _cap_row("достижения, указанные вручную", cfg.MANUAL_POINTS_CAP, manual_total)
        )
    return grade


def _apply_gates(
    points_grade: str, years: float, confirmed: bool
) -> tuple[str, str | None]:
    """Gates change the grade, never the points. Returns the grade and the note."""
    grade, note = points_grade, None
    if grade == "senior" and (years < cfg.GATE_SENIOR_MIN_YEARS or not confirmed):
        grade, note = "middle", NOTE_SENIOR_GATE
    if years < cfg.GATE_NO_EXPERIENCE_YEARS and _GRADE_ORDER.index(grade) > 1:
        grade, note = "junior", NOTE_NO_EXPERIENCE
    if note is None and _GRADE_ORDER.index(grade) >= 2 and not confirmed:
        note = NOTE_UNCONFIRMED
    return grade, note


# --- 7.4 team role -------------------------------------------------------------------------------
def _team_role(
    stack: str, facts: list[FactData], years: float, algorithmic_points: float
) -> tuple[str, str | None]:
    """Returns the role and the source that proves it (only `lead` has one)."""
    if years >= cfg.LEAD_MIN_YEARS and any(
        f.kind == "role" and f.key == "resume_lead" for f in facts
    ):
        return "lead", "resume"
    if (
        algorithmic_points >= cfg.RESEARCHER_ALGORITHMIC_POINTS and years < cfg.RESEARCHER_MAX_YEARS
    ) or stack == "ml":
        return "researcher", None
    if stack in ("devops", "qa", "analyst"):
        return stack, None
    return "developer", None


# --- 7.5 confidence ------------------------------------------------------------------------------
def _confidence(facts: list[FactData]) -> tuple[int, list[ConfidenceItem]]:
    has_fsp = any(f.kind == "achievement" and f.source == "fsp" for f in facts)
    passed = sum(1 for f in _dedupe(facts) if f.kind == "skill" and f.source == "test")
    fsp_points = cfg.CONFIDENCE_FSP_POINTS if has_fsp else 0
    test_points = cfg.CONFIDENCE_TEST_POINTS * min(cfg.CONFIDENCE_MAX_TESTS, passed)
    test_max = cfg.CONFIDENCE_TEST_POINTS * cfg.CONFIDENCE_MAX_TESTS
    items = [
        ConfidenceItem(
            label="Результаты в реестре ФСП",
            points=fsp_points,
            max=cfg.CONFIDENCE_FSP_POINTS,
            done=has_fsp,
        ),
        ConfidenceItem(
            label="Экспресс-тесты (до двух)",
            points=test_points,
            max=test_max,
            done=test_points >= test_max,
        ),
    ]
    return fsp_points + test_points, items


# --- label ---------------------------------------------------------------------------------------
def _formats_label(work_formats: Iterable[str]) -> str:
    chosen = [f for f in WORK_FORMAT_TITLES if f in set(work_formats)]
    if not chosen:
        return ""
    titles = [WORK_FORMAT_TITLES[f] for f in chosen]
    return ", ".join([titles[0], *(t.lower() for t in titles[1:])])


def build_label(
    stack: str | None,
    grade: str | None,
    team_role: str | None,
    work_formats: Iterable[str],
) -> str:
    if stack is None or grade is None or team_role is None:
        return UNDEFINED_LABEL
    parts = [STACK_TITLES[stack], GRADE_TITLES[grade], TEAM_ROLE_TITLES[team_role]]
    formats = _formats_label(work_formats)
    if formats:
        parts.append(formats)
    return " · ".join(parts)


# --- entry point ---------------------------------------------------------------------------------
def categorize(facts: list[FactData], prefs: CandidatePrefs) -> Categorization:
    """Compute the whole category of a candidate from facts and settings."""
    evidence = skill_evidence(facts)
    totals = stack_totals(evidence, facts)
    stack = choose_stack(totals)
    work_formats = [f for f in WORK_FORMAT_TITLES if f in set(prefs.work_formats)]

    points = _grade_points(facts)
    confirmed = any(f.verification in _CONFIRMING for f in facts)
    confidence_index, confidence_items = _confidence(facts)

    grade: str | None = None
    note: str | None = None
    team_role: str | None = None
    role_source: str | None = None
    if stack is not None:
        grade, note = _apply_gates(_grade_for_points(points.total), points.years, confirmed)
        team_role, role_source = _team_role(
            stack,
            facts,
            points.years,
            points.fsp_points_by_discipline.get("algorithmic", 0.0),
        )

    top_skills = sorted(
        evidence.values(),
        key=lambda e: (-e.evidence, _verification_rank(e.verification), e.skill),
    )[: cfg.TOP_SKILLS_LIMIT]

    return Categorization(
        stack=stack,  # type: ignore[arg-type]
        stack_confirmed=stack is not None and _stack_confirmed(stack, facts),
        grade=grade,  # type: ignore[arg-type]
        grade_confirmed=confirmed,
        team_role=team_role,  # type: ignore[arg-type]
        team_role_source=role_source,  # type: ignore[arg-type]
        work_formats=work_formats,  # type: ignore[arg-type]
        label=build_label(stack, grade, team_role, work_formats),
        grade_points=points.total,
        grade_explanations=points.rows,
        grade_note=note,
        experience_years=round(points.years, cfg.EXPERIENCE_DECIMALS),
        experience_points=points.experience_points,
        achievement_points=points.achievement_points,
        stack_scores=[
            StackScore(stack=name, score=round(score, 3))  # type: ignore[arg-type]
            for name, score in sorted(
                ((n, s) for n, s in totals.items() if s > 0),
                key=lambda item: (-item[1], CONCRETE_STACKS.index(item[0])),
            )
        ],
        top_skills=top_skills,
        confidence_index=confidence_index,
        confidence_breakdown=confidence_items,
    )
