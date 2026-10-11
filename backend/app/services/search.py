"""Employer-side views of candidates: snapshots, matrix, search, cards and offers.

Everything an employer sees about a candidate goes through this module, so the privacy rules
live in one place (SPEC section 8):

* until this employer has an *accepted* offer to the candidate, the name is shortened
  (`redaction.display_name`) and every free text that the candidate controls (`about`, the
  titles, evidence and values of facts, the grade explanations, the reasons, the offer
  comment) passes `redact_contacts` and `scrub_personal`, so contacts, the full name and the
  birth date are gone even when typed into a text;
* contacts (e-mail, telegram, phone) are shown only after an accepted offer; the birth date,
  the resume text and the registration data are never shown;
* a candidate who hid the profile is not found by search or card; in the offer list that
  employer already has, the candidate is reduced to the shortened name until acceptance.

The module does not import `app.services.profile`: a candidate snapshot is assembled here
from `candidates.category`, `candidates.embedding` and `profile_facts`.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app import schemas
from app.core.errors import AppError, field_validation_error
from app.domain import matcher, ontology, redaction
from app.domain.categorizer import categorize
from app.domain.scoring_config import EMBEDDING_DIM, RANK_ORDER
from app.domain.types import (
    CandidatePrefs,
    CandidateSnapshot,
    Categorization,
    FactData,
    TopAchievement,
)
from app.domain.types import MatchQuery as DomainMatchQuery
from app.models import Candidate, Employer, Offer, ProfileFact, Vacancy

logger = logging.getLogger(__name__)

WORK_FORMATS: tuple[str, ...] = tuple(ontology.WORK_FORMAT_TITLES)


# --- errors ------------------------------------------------------------------------------------


def candidate_not_found() -> AppError:
    """The same answer for a missing and for a hidden candidate: they must be indistinguishable."""
    return AppError("NOT_FOUND", "Кандидат не найден", 404)


def vacancy_not_found() -> AppError:
    """The same answer for a missing and for somebody else's vacancy."""
    return AppError("NOT_FOUND", "Вакансия не найдена", 404)


# --- snapshots ---------------------------------------------------------------------------------


def fact_data(row: ProfileFact) -> FactData | None:
    """The domain view of a stored fact; None (and a log line) for a row the domain rejects."""
    try:
        return FactData(
            kind=row.kind,
            key=row.key,
            title=row.title,
            value=row.value if isinstance(row.value, dict) else {},
            source=row.source,
            verification=row.verification,
            evidence=row.evidence,
        )
    except ValidationError:
        logger.warning("Profile fact %s does not match the domain type: skipped", row.id)
        return None


def facts_of(candidate: Candidate) -> list[FactData]:
    return [data for row in candidate.facts if (data := fact_data(row)) is not None]


def candidate_prefs(candidate: Candidate) -> CandidatePrefs:
    stored = candidate.work_formats or []
    return CandidatePrefs(
        city=candidate.city,
        work_formats=[name for name in WORK_FORMATS if name in stored],
        relocation=bool(candidate.relocation),
        salary_expectation=candidate.salary_expectation,
    )


def category_of(candidate: Candidate, facts: list[FactData]) -> Categorization:
    """The stored category; `NULL` ("not computed yet") means `categorize([], prefs)`."""
    stored = candidate.category
    if stored is None:
        return categorize([], candidate_prefs(candidate))
    try:
        return Categorization.model_validate(stored)
    except ValidationError:
        logger.warning("Candidate %s: stored category is invalid, recomputed", candidate.id)
        return categorize(facts, candidate_prefs(candidate))


def vector_of(candidate: Candidate) -> list[float]:
    """The stored text vector; empty when it is missing or has a foreign shape."""
    raw = candidate.embedding
    if not isinstance(raw, list) or len(raw) != EMBEDDING_DIM:
        return []
    try:
        return [float(value) for value in raw]
    except (TypeError, ValueError):
        return []


def snapshot_of(candidate: Candidate) -> CandidateSnapshot:
    facts = facts_of(candidate)
    return CandidateSnapshot(
        id=candidate.id,
        facts=facts,
        category=category_of(candidate, facts),
        embedding=vector_of(candidate),
        city=candidate.city,
        relocation=bool(candidate.relocation),
        salary_expectation=candidate.salary_expectation,
        visible=bool(candidate.visible),
    )


def load_snapshots(db: Session) -> list[CandidateSnapshot]:
    """Every candidate who allowed to be shown (`visible = true`), by id.

    Filtering and ranking happen in Python, never in SQL over JSON columns.
    """
    statement = (
        select(Candidate)
        .where(Candidate.visible.is_(True))
        .options(selectinload(Candidate.facts))
        .order_by(Candidate.id)
    )
    return [snapshot_of(candidate) for candidate in db.scalars(statement)]


def eligible(snapshots: Iterable[CandidateSnapshot]) -> list[CandidateSnapshot]:
    """Candidates the employer may find: visible and with a defined stack.

    The category matrix and the search use this very selection, so their numbers agree.
    """
    return [s for s in snapshots if s.visible and s.category.stack is not None]


# --- offers of this employer to candidates -----------------------------------------------------


def unlocked_candidate_ids(
    db: Session, employer: Employer, candidate_ids: Iterable[int]
) -> set[int]:
    """Candidates to whom this employer has an accepted offer: their data is open to it."""
    ids = set(candidate_ids)
    if not ids:
        return set()
    statement = select(Offer.candidate_id).where(
        Offer.employer_id == employer.id,
        Offer.status == "accepted",
        Offer.candidate_id.in_(sorted(ids)),
    )
    return set(db.scalars(statement))


def latest_offer_statuses(
    db: Session, employer: Employer, candidate_ids: Iterable[int]
) -> dict[int, str]:
    """The status of this employer's latest offer to each candidate."""
    ids = set(candidate_ids)
    if not ids:
        return {}
    statement = (
        select(Offer.candidate_id, Offer.status)
        .where(Offer.employer_id == employer.id, Offer.candidate_id.in_(sorted(ids)))
        .order_by(Offer.created_at.desc(), Offer.id.desc())
    )
    latest: dict[int, str] = {}
    for candidate_id, status in db.execute(statement):
        latest.setdefault(candidate_id, status)
    return latest


# --- privacy -----------------------------------------------------------------------------------


Hide = Callable[[str | None], str | None]


def _hider(candidate: Candidate) -> Hide:
    """The text filter for what this candidate typed or what was cut out of their documents.

    `redact_contacts` takes e-mails, phones, @nicknames and links by their shape; the candidate's
    own full name, birth date, nickname, phone and e-mail are then taken out by value
    (`scrub_personal`), because "Смирнов Алексей Игоревич" and "14.05.2003" have no shape.
    """

    def hide(text: str | None) -> str | None:
        return redaction.scrub_personal(
            redaction.redact_contacts(text),
            full_name=candidate.user.full_name,
            birth_date=candidate.birth_date,
            telegram=candidate.telegram,
            phone=candidate.phone,
            email=candidate.user.email,
        )

    return hide


def _hide_json(value: Any, hide: Hide) -> Any:
    """`hide` over every string value inside a JSON value."""
    if isinstance(value, str):
        return hide(value)
    if isinstance(value, dict):
        return {key: _hide_json(item, hide) for key, item in value.items()}
    if isinstance(value, list):
        return [_hide_json(item, hide) for item in value]
    return value


def _hide_category(category: Categorization, hide: Hide) -> Categorization:
    """The category with private data removed from the grade explanations.

    The explanation of a manual achievement is its title, which the candidate typed.
    """
    rows = [
        row.model_copy(update={"label": hide(row.label) or ""})
        for row in category.grade_explanations
    ]
    return category.model_copy(update={"grade_explanations": rows})


def sport_rank_of(facts: Iterable[FactData]) -> str | None:
    """The senior sport rank among the facts."""
    best: str | None = None
    for fact in facts:
        rank = fact.value.get("rank") if fact.kind == "rank" else None
        if not isinstance(rank, str) or rank not in RANK_ORDER:
            continue
        if best is None or RANK_ORDER.index(rank) > RANK_ORDER.index(best):
            best = rank
    return best


def _brief(
    candidate: Candidate,
    facts: list[FactData],
    category: Categorization,
    *,
    unlocked: bool,
    concealed: bool = False,
) -> schemas.CandidateBrief:
    """The short view; `concealed` (a hidden profile, no accepted offer) leaves only the name."""
    salary = candidate.salary_expectation
    relocation = bool(candidate.relocation)
    fsp_linked = candidate.fsp_id is not None
    rank = sport_rank_of(facts)
    if unlocked:
        name, city, about = candidate.user.full_name, candidate.city, candidate.about
    else:
        hide = _hider(candidate)
        # The shortened name ("Алексей С.") is what the employer may see: it is not scrubbed.
        name = redaction.redact_contacts(redaction.display_name(candidate.user.full_name)) or ""
        city = hide(candidate.city)
        about = hide(candidate.about)
        category = _hide_category(category, hide)
        if concealed:
            city = about = salary = rank = None
            relocation = fsp_linked = False
            category = categorize([], CandidatePrefs())
    return schemas.CandidateBrief(
        id=candidate.id,
        display_name=name,
        city=city,
        category=category,
        salary_expectation=salary,
        relocation=relocation,
        fsp_linked=fsp_linked,
        sport_rank=rank,
        about=about,
    )


def candidate_brief(
    db: Session,
    candidate: Candidate,
    employer: Employer,
    *,
    category: Categorization | None = None,
    unlocked: bool | None = None,
) -> schemas.CandidateBrief:
    """The short candidate view with the privacy rules applied for this employer.

    `category` and `unlocked` can be passed when the caller has them already (the search does,
    for a whole page at once); otherwise they are looked up.
    """
    facts = facts_of(candidate)
    if category is None:
        category = category_of(candidate, facts)
    if unlocked is None:
        unlocked = candidate.id in unlocked_candidate_ids(db, employer, [candidate.id])
    return _brief(candidate, facts, category, unlocked=unlocked)


def _fact_view(row: ProfileFact, *, hide: Hide | None) -> schemas.Fact | None:
    """A fact for the employer; `hide` is the text filter for a closed candidate, None if open."""
    value = row.value if isinstance(row.value, dict) else {}
    try:
        return schemas.Fact(
            id=row.id,
            kind=row.kind,
            key=row.key,
            title=(hide(row.title) or "") if hide else row.title,
            value=_hide_json(value, hide) if hide else value,
            source=row.source,
            verification=row.verification,
            evidence=hide(row.evidence) if hide else row.evidence,
            created_at=row.created_at,
        )
    except ValidationError:
        logger.warning("Profile fact %s does not match the contract type: skipped", row.id)
        return None


def candidate_card(
    db: Session,
    candidate: Candidate,
    employer: Employer,
    *,
    category: Categorization | None = None,
) -> schemas.CandidateCard:
    """The full candidate card for this employer (SPEC section 8 privacy rules)."""
    facts = facts_of(candidate)
    if category is None:
        category = category_of(candidate, facts)
    unlocked = candidate.id in unlocked_candidate_ids(db, employer, [candidate.id])
    brief = _brief(candidate, facts, category, unlocked=unlocked)

    fact_hide = None if unlocked else _hider(candidate)
    views = (_fact_view(row, hide=fact_hide) for row in candidate.facts)
    contacts = None
    if unlocked:
        contacts = schemas.Contacts(
            email=candidate.user.email, telegram=candidate.telegram, phone=candidate.phone
        )
    offers = db.scalars(
        select(Offer)
        .options(joinedload(Offer.vacancy))
        .where(Offer.employer_id == employer.id, Offer.candidate_id == candidate.id)
        .order_by(Offer.created_at.desc(), Offer.id.desc())
    )
    return schemas.CandidateCard(
        **dict(brief),
        facts=[view for view in views if view is not None],
        work_formats=candidate_prefs(candidate).work_formats,
        contacts=contacts,
        offers=[
            schemas.CardOffer(
                id=offer.id,
                vacancy_id=offer.vacancy_id,
                vacancy_title=offer.vacancy.title,
                status=offer.status,
                salary=offer.salary,
                created_at=offer.created_at,
            )
            for offer in offers
        ],
    )


def load_candidates(db: Session, candidate_ids: Iterable[int]) -> dict[int, Candidate]:
    """Candidates with their user and facts, by id (no visibility filter)."""
    ids = set(candidate_ids)
    if not ids:
        return {}
    statement = (
        select(Candidate)
        .options(joinedload(Candidate.user), selectinload(Candidate.facts))
        .where(Candidate.id.in_(sorted(ids)))
    )
    return {candidate.id: candidate for candidate in db.scalars(statement)}


def employer_offers_view(
    db: Session, employer: Employer, offers: Sequence[Offer]
) -> list[schemas.EmployerOffer]:
    """`EmployerOffer`s for the given offers of this employer, in the given order.

    A candidate who hid the profile after the offer stays in the list under the shortened name
    only (no city, "about", salary or category) until the offer is accepted.
    """
    candidates = load_candidates(db, (offer.candidate_id for offer in offers))
    unlocked = unlocked_candidate_ids(db, employer, candidates)
    briefs: dict[int, schemas.CandidateBrief] = {}
    result: list[schemas.EmployerOffer] = []
    for offer in offers:
        candidate = candidates.get(offer.candidate_id)
        if candidate is None:
            continue
        if candidate.id not in briefs:
            facts = facts_of(candidate)
            briefs[candidate.id] = _brief(
                candidate,
                facts,
                category_of(candidate, facts),
                unlocked=candidate.id in unlocked,
                concealed=not candidate.visible,
            )
        accepted = offer.status == "accepted"
        contacts = None
        if accepted:
            contacts = schemas.Contacts(
                email=candidate.user.email, telegram=candidate.telegram, phone=candidate.phone
            )
        result.append(
            schemas.EmployerOffer(
                id=offer.id,
                status=offer.status,
                salary=offer.salary,
                message=offer.message,
                created_at=offer.created_at,
                responded_at=offer.responded_at,
                candidate_comment=offer.candidate_comment
                if accepted
                else _hider(candidate)(offer.candidate_comment),
                vacancy=schemas.EmployerOfferVacancy(
                    id=offer.vacancy_id, title=offer.vacancy.title
                ),
                candidate=briefs[candidate.id],
                contacts=contacts,
            )
        )
    return result


# --- category matrix ---------------------------------------------------------------------------


def _fsp_results(facts: Iterable[FactData]) -> list[FactData]:
    return [f for f in facts if f.kind == "achievement" and f.source == "fsp"]


def _ordered(counter: Counter[str], order: Iterable[str]) -> list[tuple[str, int]]:
    return [(name, counter[name]) for name in order if counter[name] > 0]


def category_matrix(
    snapshots: Iterable[CandidateSnapshot],
    *,
    team_role: str | None = None,
    work_format: str | None = None,
) -> schemas.CategoryMatrix:
    """Counts of candidates by stack and grade, plus the slices (SPEC section 9).

    The pool is `eligible()`; `team_role` and `work_format` narrow it with the same rules as
    the search filters (a candidate with no work formats passes the format filter).
    """
    pool = eligible(snapshots)
    if team_role is not None:
        pool = [s for s in pool if s.category.team_role == team_role]
    if work_format is not None:
        pool = [
            s for s in pool if not s.category.work_formats or work_format in s.category.work_formats
        ]

    cells: Counter[tuple[str, str]] = Counter()
    verified_cells: Counter[tuple[str, str]] = Counter()
    by_stack: Counter[str] = Counter()
    by_grade: Counter[str] = Counter()
    by_team_role: Counter[str] = Counter()
    by_work_format: Counter[str] = Counter()
    by_discipline: Counter[str] = Counter()
    verified_total = 0

    for snapshot in pool:
        category = snapshot.category
        results = _fsp_results(snapshot.facts)
        by_stack[category.stack] += 1
        if category.grade is not None:
            by_grade[category.grade] += 1
            cells[(category.stack, category.grade)] += 1
            if results:
                verified_cells[(category.stack, category.grade)] += 1
        if category.team_role is not None:
            by_team_role[category.team_role] += 1
        for name in set(category.work_formats):
            by_work_format[name] += 1
        disciplines = {d for f in results if isinstance(d := f.value.get("discipline"), str)}
        for name in disciplines & set(ontology.DISCIPLINE_TITLES):
            by_discipline[name] += 1
        if results:
            verified_total += 1

    return schemas.CategoryMatrix(
        total_candidates=len(pool),
        cells=[
            schemas.MatrixCell(
                stack=stack,
                grade=grade,
                count=cells[(stack, grade)],
                fsp_verified=verified_cells[(stack, grade)],
            )
            for stack in ontology.STACK_TITLES
            for grade in ontology.GRADE_TITLES
            if cells[(stack, grade)] > 0
        ],
        by_stack=[
            schemas.StackCount(stack=name, count=count)
            for name, count in _ordered(by_stack, ontology.STACK_TITLES)
        ],
        by_grade=[
            schemas.GradeCount(grade=name, count=count)
            for name, count in _ordered(by_grade, ontology.GRADE_TITLES)
        ],
        by_team_role=[
            schemas.TeamRoleCount(team_role=name, count=count)
            for name, count in _ordered(by_team_role, ontology.TEAM_ROLE_TITLES)
        ],
        by_work_format=[
            schemas.WorkFormatCount(work_format=name, count=count)
            for name, count in _ordered(by_work_format, ontology.WORK_FORMAT_TITLES)
        ],
        by_discipline=[
            schemas.DisciplineCount(discipline=name, count=count)
            for name, count in _ordered(by_discipline, ontology.DISCIPLINE_TITLES)
        ],
        fsp_verified_total=verified_total,
    )


# --- search ------------------------------------------------------------------------------------


def _unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _unknown_skills(skill_ids: Iterable[str]) -> list[str]:
    return [skill for skill in skill_ids if not ontology.is_known_skill(skill)]


def _merge_vacancy(query: DomainMatchQuery, vacancy: Vacancy) -> DomainMatchQuery:
    """SPEC 7.7 "vacancy -> query": the vacancy fills what the request left empty.

    Lists and scalars given in the request win; skills of both are joined; the vacancy text
    (title and description) is added after the request text.
    """
    required_in_vacancy = list(vacancy.skills_required or [])
    optional_in_vacancy = list(vacancy.skills_optional or [])
    unknown = _unknown_skills([*required_in_vacancy, *optional_in_vacancy])
    if unknown:
        raise field_validation_error(
            [(["body", "vacancy_id"], f"В вакансии есть неизвестные навыки: {', '.join(unknown)}")]
        )
    required = _unique([*query.skills_required, *required_in_vacancy])
    optional = [
        skill
        for skill in _unique([*query.skills_optional, *optional_in_vacancy])
        if skill not in required
    ]
    texts = [
        text
        for text in (query.text, f"{vacancy.title}\n{vacancy.description}")
        if text and text.strip()
    ]
    return query.model_copy(
        update={
            "stacks": query.stacks or [vacancy.stack],
            "grades": query.grades or [vacancy.grade],
            "team_roles": query.team_roles or ([vacancy.team_role] if vacancy.team_role else []),
            "work_formats": query.work_formats or list(vacancy.work_formats or []),
            "city": query.city or vacancy.city,
            "skills_required": required,
            "skills_optional": optional,
            "salary_max": query.salary_max if query.salary_max is not None else vacancy.salary_to,
            "text": "\n".join(texts) or None,
        }
    )


def build_query(db: Session, employer: Employer, body: schemas.MatchQuery) -> DomainMatchQuery:
    """The domain query behind a search request.

    * unknown skill ids -> 422 `VALIDATION_ERROR`;
    * `vacancy_id` (must be this employer's vacancy, otherwise 404 `NOT_FOUND`) supplements the
      request with the fields of the vacancy;
    * skills found in `text` by `matcher.parse_query_text` are added to `skills_optional`.
    """
    errors: list[tuple[list[str | int], str]] = []
    for field in ("skills_required", "skills_optional"):
        unknown = _unknown_skills(getattr(body, field))
        if unknown:
            errors.append((["body", field], f"Неизвестные навыки: {', '.join(unknown)}"))
    if errors:
        raise field_validation_error(errors)

    query = body.to_domain()
    if body.vacancy_id is not None:
        vacancy = db.scalar(
            select(Vacancy).where(Vacancy.id == body.vacancy_id, Vacancy.employer_id == employer.id)
        )
        if vacancy is None:
            raise vacancy_not_found()
        query = _merge_vacancy(query, vacancy)

    if body.text:
        taken = {*query.skills_required, *query.skills_optional}
        from_text = matcher.parse_query_text(body.text).skills
        found = [skill for skill in from_text if skill not in taken]
        query = query.model_copy(update={"skills_optional": [*query.skills_optional, *found]})
    return query


def search_candidates(
    db: Session, employer: Employer, body: schemas.MatchQuery
) -> schemas.SearchResponse:
    """Run a search: filters, ranking, one page of results with the privacy rules applied."""
    query = build_query(db, employer, body)
    snapshots = eligible(load_snapshots(db))
    ranked = matcher.rank(query, snapshots)
    page = ranked[body.offset : body.offset + body.limit]

    categories = {snapshot.id: snapshot.category for snapshot in snapshots}
    candidates = load_candidates(db, (result.candidate_id for result in page))
    unlocked = unlocked_candidate_ids(db, employer, candidates)
    statuses = latest_offer_statuses(db, employer, candidates)

    items: list[schemas.CandidateMatch] = []
    for result in page:
        candidate = candidates.get(result.candidate_id)
        if candidate is None:
            continue
        is_open = candidate.id in unlocked
        achievements: list[TopAchievement] = result.top_achievements
        reasons: list[str] = result.reasons
        if not is_open:
            hide = _hider(candidate)
            achievements = [
                item.model_copy(update={"title": hide(item.title) or ""}) for item in achievements
            ]
            reasons = [hide(reason) or "" for reason in reasons]
        items.append(
            schemas.CandidateMatch(
                candidate=_brief(
                    candidate, facts_of(candidate), categories[candidate.id], unlocked=is_open
                ),
                score=result.score,
                components=result.components,
                matched_skills=result.matched_skills,
                missing_skills=result.missing_skills,
                top_achievements=achievements,
                reasons=reasons,
                offer_status=statuses.get(candidate.id),
            )
        )
    return schemas.SearchResponse(
        total=len(ranked),
        limit=body.limit,
        offset=body.offset,
        items=items,
        parsed_query=matcher.parse_query_text(body.text) if body.text else None,
    )
