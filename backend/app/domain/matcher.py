"""Matching candidates to an employer's query (SPEC section 7.7)."""

from __future__ import annotations

from functools import lru_cache

from app.domain import scoring_config as cfg
from app.domain.categorizer import (
    choose_stack,
    fsp_result_points,
    manual_result_points,
    skill_evidence,
)
from app.domain.embedding import cosine, embed
from app.domain.facts import years_label
from app.domain.ontology import (
    CONCRETE_STACKS,
    LEVEL_TITLES,
    AliasPattern,
    compile_aliases,
    find_skills,
    is_known_skill,
    load_ontology,
    norm_key,
    scan_mentions,
    skill_title,
)
from app.domain.types import (
    CandidateSnapshot,
    FactData,
    MatchComponents,
    MatchQuery,
    MatchResult,
    MissingSkill,
    ParsedQuery,
    SkillEvidence,
    TopAchievement,
)

# Words that hint at a stack or a grade in a free-text query. They are hints only.
_STACK_WORDS: dict[str, list[str]] = {
    "backend": ["backend", "back-end", "back end", "бэкенд", "бекенд", "бэкэнд", "бэк-энд"],
    "frontend": ["frontend", "front-end", "front end", "фронтенд", "фронтэнд", "фронт-энд"],
    "fullstack": ["fullstack", "full-stack", "full stack", "фулстек", "фуллстек", "фулстэк"],
    "mobile": ["mobile", "мобильн"],
    "ml": ["ml", "data science", "data scientist", "дата сайенс", "дата-сайенс"],
    "devops": ["devops", "девопс", "sre", "инфраструктур"],
    "security": ["security", "безопасност", "пентестер", "pentester"],
    "embedded": ["embedded", "встраиваем", "робототехник", "микроконтроллер"],
    "qa": ["qa", "sdet", "тестировщик", "тестирован"],
    "analyst": ["analyst", "аналитик"],
}
_GRADE_WORDS: dict[str, list[str]] = {
    "intern": ["intern", "internship", "стажер", "стажировка"],
    "junior": ["junior", "джуниор", "джун", "младш", "начинающ"],
    "middle": ["middle", "миддл", "мидл"],
    "senior": ["senior", "сеньор", "синьор", "старш", "ведущ"],
}

_LEVEL_ADJECTIVES: dict[str, str] = {
    "municipal": "муниципальных",
    "regional": "региональных",
    "district": "окружных",
    "national": "всероссийских",
    "international": "международных",
}
_LEVEL_RANK = {level: index for index, level in enumerate(LEVEL_TITLES)}


@lru_cache(maxsize=1)
def _hint_patterns() -> tuple[dict[str, AliasPattern], dict[str, AliasPattern]]:
    def build(words: dict[str, list[str]]) -> dict[str, AliasPattern]:
        built: dict[str, AliasPattern] = {}
        for key, aliases in words.items():
            pattern = compile_aliases(aliases)
            if pattern is not None:
                built[key] = pattern
        return built

    return build(_STACK_WORDS), build(_GRADE_WORDS)


def _first_hint(text: str, patterns: dict[str, AliasPattern], order: tuple[str, ...]) -> str | None:
    mentions = scan_mentions(text, patterns)
    if not mentions:
        return None
    return min(mentions, key=lambda m: (m.start, order.index(m.key))).key


def _stack_from_skills(skills: list[str]) -> str | None:
    """A stack hint from skills alone; None when it is not clear-cut."""
    ontology = load_ontology()
    totals = dict.fromkeys(CONCRETE_STACKS, 0.0)
    for skill_id in skills:
        for stack, tier in ontology.by_id[skill_id].stacks.items():
            totals[stack] += cfg.CORE_WEIGHT if tier == "core" else cfg.SECONDARY_WEIGHT
    stack = choose_stack(totals)
    if stack is None or stack == "fullstack":
        return stack
    leaders = [name for name, score in totals.items() if abs(score - totals[stack]) < 1e-9]
    if len(leaders) > 1 or totals[stack] < cfg.FULLSTACK_MIN_SCORE:
        return None
    return stack


def parse_query_text(text: str) -> ParsedQuery:
    """Skills, and hints for the stack and the grade, found in the text of a query."""
    skills = find_skills(text or "")
    stack_patterns, grade_patterns = _hint_patterns()
    stack = _first_hint(text or "", stack_patterns, tuple(_STACK_WORDS))
    if stack is None:
        stack = _stack_from_skills(skills)
    grade = _first_hint(text or "", grade_patterns, tuple(_GRADE_WORDS))
    return ParsedQuery(skills=skills, stack=stack, grade=grade)  # type: ignore[arg-type]


# --- filters -------------------------------------------------------------------------------------
def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _fsp_achievements(facts: list[FactData]) -> list[FactData]:
    return [f for f in facts if f.kind == "achievement" and f.source == "fsp"]


def _stack_passes(wanted: list[str], stack: str) -> bool:
    if not wanted or stack in wanted:
        return True
    return stack == "fullstack" and ("backend" in wanted or "frontend" in wanted)


def _city_passes(query: MatchQuery, cand: CandidateSnapshot) -> bool:
    if not query.city or cand.relocation:
        return True
    if cand.city and norm_key(cand.city) == norm_key(query.city):
        return True
    return "remote" in query.work_formats and "remote" in cand.category.work_formats


def _passes_filters(
    query: MatchQuery,
    cand: CandidateSnapshot,
    evidence: dict[str, SkillEvidence],
    required: list[str],
) -> bool:
    category = cand.category
    if not cand.visible or category.stack is None:
        return False
    if not _stack_passes(list(query.stacks), category.stack):
        return False
    if query.grades and category.grade not in query.grades:
        return False
    if query.team_roles and category.team_role not in query.team_roles:
        return False
    if (
        query.work_formats
        and category.work_formats
        and not set(query.work_formats) & set(category.work_formats)
    ):
        return False
    if not _city_passes(query, cand):
        return False
    if query.fsp_verified_only and not _fsp_achievements(cand.facts):
        return False
    if query.confirmed_only and not any(
        f.verification in ("verified", "tested") for f in cand.facts
    ):
        return False
    if query.disciplines and not any(
        f.value.get("discipline") in query.disciplines for f in _fsp_achievements(cand.facts)
    ):
        return False
    if (
        query.salary_max is not None
        and cand.salary_expectation is not None
        and cand.salary_expectation > query.salary_max
    ):
        return False
    if query.strict_skills:
        for skill_id in required:
            item = evidence.get(skill_id)
            if item is None or item.evidence < cfg.STRICT_SKILL_MIN_EVIDENCE:
                return False
    return True


# --- score ---------------------------------------------------------------------------------------
def _average(skills: list[str], evidence: dict[str, SkillEvidence]) -> float:
    return sum(evidence[s].evidence if s in evidence else 0.0 for s in skills) / len(skills)


def _skill_component(
    required: list[str], optional: list[str], evidence: dict[str, SkillEvidence]
) -> float | None:
    if required and optional:
        return cfg.SKILL_REQUIRED_SHARE * _average(
            required, evidence
        ) + cfg.SKILL_OPTIONAL_SHARE * _average(optional, evidence)
    if required:
        return _average(required, evidence)
    if optional:
        return _average(optional, evidence)
    return None


def _track_record(cand: CandidateSnapshot) -> float:
    category = cand.category
    results = min(1.0, category.achievement_points / cfg.TRACK_POINTS_SCALE)
    experience = min(1.0, category.experience_points / cfg.TRACK_POINTS_SCALE)
    return cfg.TRACK_SHARE * results + (1.0 - cfg.TRACK_SHARE) * experience


def _combine(components: MatchComponents) -> float | None:
    """Weighted mean of the components that exist (weights renormalised)."""
    parts: list[tuple[float, float]] = [
        (cfg.MATCH_WEIGHT_TRACK, components.track_record),
        (cfg.MATCH_WEIGHT_CONFIDENCE, components.confidence),
    ]
    if components.skill is not None:
        parts.append((cfg.MATCH_WEIGHT_SKILL, components.skill))
    if components.text is not None:
        parts.append((cfg.MATCH_WEIGHT_TEXT, components.text))
    if components.skill is None and components.text is None:
        return None
    return 100.0 * sum(w * v for w, v in parts) / sum(w for w, _ in parts)


def _achievement_points(fact: FactData) -> float:
    return fsp_result_points(fact) if fact.source == "fsp" else manual_result_points(fact)


def _top_achievements(facts: list[FactData]) -> list[TopAchievement]:
    ranked = sorted(
        (f for f in facts if f.kind == "achievement" and f.value.get("level") in LEVEL_TITLES),
        key=lambda f: (
            -_achievement_points(f),
            -(f.value["year"] if isinstance(f.value.get("year"), int) else 0),
            f.key,
        ),
    )
    result: list[TopAchievement] = []
    for fact in ranked[: cfg.TOP_ACHIEVEMENTS_LIMIT]:
        place = fact.value.get("place")
        year = fact.value.get("year")
        result.append(
            TopAchievement(
                title=str(fact.value.get("title") or fact.title),
                level=fact.value["level"],
                place=place if isinstance(place, int) else None,
                year=year if isinstance(year, int) else None,
                verification=fact.verification,
            )
        )
    return result


def _join_titles(items: list[SkillEvidence]) -> str:
    titles = [item.title for item in items[:2]]
    return " и ".join(titles) if len(titles) == 2 else titles[0]


def _confirmation_reasons(matched: list[SkillEvidence]) -> list[str]:
    reasons: list[str] = []
    tested = [m for m in matched if m.verification == "tested"]
    verified = [m for m in matched if m.verification == "verified"]
    if tested:
        verb = "подтверждены" if len(tested) > 1 else "подтверждён"
        reasons.append(f"{_join_titles(tested)} {verb} тестом")
    if verified:
        verb = "подтверждены" if len(verified) > 1 else "подтверждён"
        reasons.append(f"{_join_titles(verified)} {verb} результатами ФСП")
    return reasons


def _prize_reason(facts: list[FactData]) -> str | None:
    best: str | None = None
    for fact in _fsp_achievements(facts):
        place = fact.value.get("place")
        level = fact.value.get("level")
        if not isinstance(place, int) or place > cfg.PRIZE_MAX_PLACE or level not in _LEVEL_RANK:
            continue
        if best is None or _LEVEL_RANK[level] > _LEVEL_RANK[best]:
            best = level
    if best is None:
        return None
    return f"Призовое место на {_LEVEL_ADJECTIVES[best]} соревнованиях ФСП"


def _reasons(
    cand: CandidateSnapshot,
    required: list[str],
    optional: list[str],
    evidence: dict[str, SkillEvidence],
    matched: list[SkillEvidence],
    missing: list[MissingSkill],
    components: MatchComponents,
) -> list[str]:
    positives: list[str] = []
    wanted = required or optional
    found = sum(1 for s in wanted if s in evidence)
    if found:
        noun = "обязательных навыков" if required else "навыков"
        positives.append(f"Совпало {found} из {len(wanted)} {noun}")
    positives.extend(_confirmation_reasons(matched))
    prize = _prize_reason(cand.facts)
    if prize:
        positives.append(prize)
    if components.text is not None and components.text >= cfg.REASON_TEXT_MIN:
        positives.append(f"Совпадение с текстом запроса: {round(components.text * 100)}%")

    tail: list[str] = []
    if missing:
        names = ", ".join(m.title for m in missing[: cfg.REASON_MISSING_SHOWN])
        tail.append(f"Не хватает: {names}")
    reasons = positives[: cfg.REASONS_MAX - len(tail)] + tail

    fallbacks = [
        f"Категория: {cand.category.label}",
        f"Опыт в ИТ: {years_label(cand.category.experience_years)}"
        if cand.category.experience_years > 0
        else "",
        f"Индекс подтверждённости: {cand.category.confidence_index} из 100",
    ]
    for line in fallbacks:
        if len(reasons) >= cfg.REASONS_MIN:
            break
        if line and line not in reasons:
            reasons.insert(len(reasons) - len(tail), line)
    return reasons


def _title_of(skill_id: str) -> str:
    return skill_title(skill_id) if is_known_skill(skill_id) else skill_id


def score(
    query: MatchQuery, cand: CandidateSnapshot, query_vec: list[float] | None
) -> MatchResult | None:
    """Score one candidate; None when the candidate fails a hard filter.

    `query_vec` is the embedding of the query text (None when the query has no text).
    """
    required = _unique(list(query.skills_required))
    optional = [s for s in _unique(list(query.skills_optional)) if s not in required]
    evidence = skill_evidence(cand.facts)
    if not _passes_filters(query, cand, evidence, required):
        return None

    skill = _skill_component(required, optional, evidence)
    text: float | None = None
    if query_vec is not None and any(query_vec):
        text = max(0.0, cosine(query_vec, cand.embedding))
    track = _track_record(cand)
    confidence = cand.category.confidence_index / 100.0

    components = MatchComponents(
        skill=None if skill is None else round(skill, cfg.COMPONENT_DECIMALS),
        text=None if text is None else round(text, cfg.COMPONENT_DECIMALS),
        track_record=round(track, cfg.COMPONENT_DECIMALS),
        confidence=round(confidence, cfg.COMPONENT_DECIMALS),
    )
    total = _combine(
        MatchComponents(skill=skill, text=text, track_record=track, confidence=confidence)
    )

    wanted = required + optional
    matched = [evidence[s] for s in wanted if s in evidence]
    missing = [MissingSkill(skill=s, title=_title_of(s)) for s in required if s not in evidence]
    return MatchResult(
        candidate_id=cand.id,
        score=None if total is None else round(total, cfg.SCORE_DECIMALS),
        components=components,
        matched_skills=matched,
        missing_skills=missing,
        top_achievements=_top_achievements(cand.facts),
        reasons=_reasons(cand, required, optional, evidence, matched, missing, components),
    )


def rank(query: MatchQuery, candidates: list[CandidateSnapshot]) -> list[MatchResult]:
    """All candidates that pass the filters, best first.

    With a score: by score, then confidence, then id. Without one (a query with neither
    skills nor text): by track record, then confidence, then id.
    """
    query_vec = embed(query.text) if query.text and query.text.strip() else None
    results = [r for c in candidates if (r := score(query, c, query_vec)) is not None]

    def key(result: MatchResult) -> tuple[float, float, int]:
        primary = result.components.track_record if result.score is None else result.score
        return (-primary, -result.components.confidence, result.candidate_id)

    return sorted(results, key=key)
