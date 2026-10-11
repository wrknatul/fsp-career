"""Candidate profile service (SPEC sections 5 and 6).

One place that turns database rows into domain input (`FactData`, `CandidatePrefs`), keeps the
stored category and text vector fresh, and assembles the `CandidateProfile` every candidate
route answers with.

Routes own the transaction: these helpers flush but never commit (except `commit_profile`,
which is the commit with an explicit answer for a lost race).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.timeutil import utcnow
from app.domain import categorizer, embedding
from app.domain.types import CandidatePrefs, Categorization, FactData
from app.models import Candidate, ProfileFact
from app.schemas.candidate import CandidateProfile, FspInfo, ResumeInfo
from app.schemas.common import Fact, User


def load_fact_rows(db: Session, candidate: Candidate) -> list[ProfileFact]:
    """Stored facts of a candidate, oldest first (straight from the database)."""
    return list(
        db.scalars(
            select(ProfileFact)
            .where(ProfileFact.candidate_id == candidate.id)
            .order_by(ProfileFact.id)
        )
    )


def to_fact_data(row: ProfileFact) -> FactData:
    """A stored fact as the domain sees it."""
    return FactData(
        kind=row.kind,  # type: ignore[arg-type]
        key=row.key,
        title=row.title,
        value=dict(row.value or {}),
        source=row.source,  # type: ignore[arg-type]
        verification=row.verification,  # type: ignore[arg-type]
        evidence=row.evidence,
    )


def candidate_prefs(candidate: Candidate) -> CandidatePrefs:
    """The self-reported settings of the questionnaire that affect the category."""
    return CandidatePrefs(
        city=candidate.city,
        work_formats=list(candidate.work_formats or []),  # type: ignore[arg-type]
        relocation=bool(candidate.relocation),
        salary_expectation=candidate.salary_expectation,
    )


def recompute_candidate(db: Session, candidate: Candidate) -> Categorization:
    """Rebuild `category` and `embedding` from the stored facts and settings.

    Call it after any change of facts, questionnaire fields, `about` or the resume text.
    The caller commits.
    """
    facts = [to_fact_data(row) for row in load_fact_rows(db, candidate)]
    categorization = categorizer.categorize(facts, candidate_prefs(candidate))
    text = embedding.profile_text(
        facts, categorization, candidate.about, candidate.resume_text
    )
    # JSON columns do not track in-place changes: always assign a new value.
    candidate.category = categorization.model_dump()
    candidate.embedding = embedding.embed(text)
    candidate.updated_at = utcnow()
    return categorization


def _new_row(candidate: Candidate, fact: FactData) -> ProfileFact:
    return ProfileFact(
        candidate_id=candidate.id,
        kind=fact.kind,
        key=fact.key,
        title=fact.title,
        value=dict(fact.value),
        source=fact.source,
        verification=fact.verification,
        evidence=fact.evidence,
    )


def replace_facts(
    db: Session, candidate: Candidate, source: str, facts: Iterable[FactData]
) -> None:
    """Delete every fact of `source` and store `facts` instead (used for `fsp` and `resume`).

    A repeated (kind, key) in `facts` keeps its first occurrence, so the unique key
    (candidate, kind, key, source) cannot be violated by the input itself.
    """
    db.execute(
        delete(ProfileFact).where(
            ProfileFact.candidate_id == candidate.id, ProfileFact.source == source
        )
    )
    seen: set[tuple[str, str]] = set()
    for fact in facts:
        if fact.source != source:
            raise ValueError(
                f"fact {fact.kind}:{fact.key} has source {fact.source!r}, not {source!r}"
            )
        identity = (fact.kind, fact.key)
        if identity in seen:
            continue
        seen.add(identity)
        db.add(_new_row(candidate, fact))
    flush_or_conflict(db)
    db.expire(candidate, ["facts"])


def _skill_level(value: dict[str, Any] | None) -> int:
    try:
        return int((value or {}).get("level", 0))
    except (TypeError, ValueError):
        return 0


def upsert_fact(
    db: Session, candidate: Candidate, fact: FactData, *, keep_higher_level: bool = False
) -> bool:
    """Insert the fact or update the one with the same (kind, key, source).

    With `keep_higher_level` an existing fact whose `value.level` is not lower than the new one
    stays untouched (a worse retake never lowers a result). Returns True if anything changed.
    """
    existing = db.scalar(
        select(ProfileFact).where(
            ProfileFact.candidate_id == candidate.id,
            ProfileFact.kind == fact.kind,
            ProfileFact.key == fact.key,
            ProfileFact.source == fact.source,
        )
    )
    if existing is None:
        db.add(_new_row(candidate, fact))
    else:
        if keep_higher_level and _skill_level(existing.value) >= _skill_level(fact.value):
            return False
        existing.title = fact.title
        existing.value = dict(fact.value)
        existing.verification = fact.verification
        existing.evidence = fact.evidence
    flush_or_conflict(db)
    db.expire(candidate, ["facts"])
    return True


def _lost_race() -> AppError:
    return AppError(
        "CONFLICT",
        "Профиль изменился одновременно из другого запроса. Повторите действие",
        409,
    )


def flush_or_conflict(db: Session) -> None:
    """Flush; a lost race on a unique key becomes a clear 409, never a 500."""
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _lost_race() from exc


def commit_profile(db: Session) -> None:
    """Commit; a lost race on a unique key becomes a clear 409, never a 500."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _lost_race() from exc


def current_category(
    candidate: Candidate, facts: list[FactData] | None = None
) -> Categorization:
    """The stored category; SQL NULL means "not computed" and reads as `categorize([], prefs)`.

    A stored value the current domain can no longer read is recomputed from `facts`.
    """
    prefs = candidate_prefs(candidate)
    if candidate.category is None:
        return categorizer.categorize([], prefs)
    try:
        return Categorization.model_validate(candidate.category)
    except ValidationError:
        return categorizer.categorize(facts or [], prefs)


def build_profile(db: Session, candidate: Candidate) -> CandidateProfile:
    """The `CandidateProfile` of the contract, built from the database."""
    rows = load_fact_rows(db, candidate)
    category = current_category(candidate, [to_fact_data(row) for row in rows])
    fsp = None
    if candidate.fsp_id is not None:
        fsp = FspInfo(
            fsp_id=candidate.fsp_id,
            linked_at=candidate.fsp_linked_at or candidate.updated_at,
            region=candidate.fsp_region,
        )
    resume = None
    if candidate.resume_parsed_at is not None:
        resume = ResumeInfo(
            filename=candidate.resume_filename,
            parsed_at=candidate.resume_parsed_at,
            chars=len(candidate.resume_text or ""),
        )
    return CandidateProfile(
        id=candidate.id,
        user=User.model_validate(candidate.user),
        birth_date=candidate.birth_date,
        city=candidate.city,
        work_formats=list(candidate.work_formats or []),
        relocation=bool(candidate.relocation),
        salary_expectation=candidate.salary_expectation,
        about=candidate.about,
        telegram=candidate.telegram,
        phone=candidate.phone,
        visible=bool(candidate.visible),
        fsp=fsp,
        resume=resume,
        category=category,
        facts=[Fact.model_validate(row) for row in rows],
        updated_at=candidate.updated_at,
    )
