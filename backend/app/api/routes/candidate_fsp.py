"""Linking the profile to the FSP registry (`/candidate/fsp/link`, SPEC section 6.1).

The check order of the link is fixed: complete profile, rate limit, the id exists, the id is
free, ФИО and birth date match. Every attempt that passed the first check is written to
`link_attempts` (and committed at once, so it survives the error answers that follow).
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentCandidate, DbSession
from app.core.errors import AppError, error_responses
from app.core.timeutil import utcnow
from app.domain import fsp_mapping
from app.fsp_registry.client import FspRegistryClient, get_registry, short_name
from app.models import Candidate, LinkAttempt
from app.schemas.candidate import CandidateProfile
from app.schemas.fsp import FspImported, FspLinkAthlete, FspLinkRequest, FspLinkResult
from app.services.profile import (
    build_profile,
    commit_profile,
    recompute_candidate,
    replace_facts,
)

router = APIRouter(prefix="/candidate", tags=["Соискатель"])

LINK_ATTEMPTS_LIMIT = 5
LINK_ATTEMPTS_WINDOW = timedelta(hours=1)


def normalize_name(value: str | None) -> str:
    """Name for comparison: one Unicode form, no case, "ё" = "е", whitespace collapsed.

    NFKC composes a decomposed "ё" / "й" (letter + combining mark, as some keyboards and
    copy-paste produce) into the single code point the registry stores.
    """
    composed = unicodedata.normalize("NFKC", value or "")
    return " ".join(composed.casefold().replace("ё", "е").split())


def _identity_matches(candidate: Candidate, athlete: dict[str, Any]) -> bool:
    if normalize_name(candidate.user.full_name) != normalize_name(athlete.get("full_name")):
        return False
    try:
        registry_birth = date.fromisoformat(str(athlete["birth_date"]))
    except (KeyError, ValueError):
        # A record we cannot check against is never a match.
        return False
    return candidate.birth_date == registry_birth


def _find_owner(db: Session, fsp_id: str) -> Candidate | None:
    return db.scalar(select(Candidate).where(Candidate.fsp_id == fsp_id))


def _already_linked(linked_to_you: bool, message: str | None = None) -> AppError:
    return AppError(
        "FSP_ALREADY_LINKED",
        message
        or (
            "Этот ФСП ID уже привязан к вашему профилю"
            if linked_to_you
            else "Этот ФСП ID уже привязан к другому пользователю"
        ),
        409,
        {"linked_to_you": linked_to_you},
    )


def _check_rate_limit(db: Session, user_id: int) -> None:
    window_start = utcnow() - LINK_ATTEMPTS_WINDOW
    recent = list(
        db.scalars(
            select(LinkAttempt.created_at)
            .where(LinkAttempt.user_id == user_id, LinkAttempt.created_at > window_start)
            .order_by(LinkAttempt.created_at)
        )
    )
    if len(recent) >= LINK_ATTEMPTS_LIMIT:
        # The limit lifts when the fifth most recent attempt leaves the window.
        available_at = recent[len(recent) - LINK_ATTEMPTS_LIMIT] + LINK_ATTEMPTS_WINDOW
        raise AppError(
            "RATE_LIMITED",
            "Слишком много попыток привязки ФСП ID. Повторите позже",
            429,
            {"limit": LINK_ATTEMPTS_LIMIT, "available_at": available_at},
        )


@router.post(
    "/fsp/link",
    response_model=FspLinkResult,
    summary="Привязать ФСП ID",
    description=(
        "Привязывает профиль к записи реестра ФСП по ФСП ID и совпадению ФИО и даты рождения "
        "(без учёта регистра, «ё» = «е», лишние пробелы не считаются). Результаты, разряд и "
        "навыки дисциплин попадают в профиль как подтверждённые ФСП факты, категория "
        "пересчитывается. В демо реестр смоделирован; в рабочей версии — вход через аккаунт "
        "ФСП. Не больше 5 попыток в час. Порядок проверок: заполнены ФИО и дата рождения, "
        "лимит попыток, ID есть в реестре, ID свободен, ФИО и дата рождения совпали."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
            404: "FSP_ATHLETE_NOT_FOUND — такого ФСП ID нет в реестре",
            409: "PROFILE_INCOMPLETE — в профиле нет ФИО или даты рождения; "
            "FSP_ALREADY_LINKED — ID уже привязан (`details.linked_to_you`); "
            "FSP_IDENTITY_MISMATCH — ФИО или дата рождения не совпали с реестром",
            422: "VALIDATION_ERROR — данные не прошли проверку",
            429: "RATE_LIMITED — больше 5 попыток привязки за час",
            503: "FSP_REGISTRY_UNAVAILABLE — реестр недоступен или его запись повреждена",
        }
    ),
)
def link_fsp(
    body: FspLinkRequest,
    candidate: CurrentCandidate,
    db: DbSession,
    registry: Annotated[FspRegistryClient, Depends(get_registry)],
) -> FspLinkResult:
    user = candidate.user

    # 1. The data the registry is compared with must be there.
    if not user.full_name.strip() or candidate.birth_date is None:
        raise AppError(
            "PROFILE_INCOMPLETE",
            "Для привязки ФСП заполните ФИО и дату рождения в профиле",
            409,
        )

    # 2. Rate limit. The attempt is committed at once: the errors below must not undo it.
    _check_rate_limit(db, user.id)
    db.add(LinkAttempt(user_id=user.id, created_at=utcnow()))
    db.commit()

    # 3. The id exists.
    athlete = registry.get_athlete(body.fsp_id)
    if athlete is None:
        raise AppError("FSP_ATHLETE_NOT_FOUND", "Спортсмен с таким ФСП ID не найден", 404)
    fsp_id = str(athlete["fsp_id"])

    # 4. The id is free.
    owner = _find_owner(db, fsp_id)
    if owner is not None:
        raise _already_linked(owner.id == candidate.id)
    if candidate.fsp_id is not None:
        raise _already_linked(
            True,
            "К вашему профилю уже привязан другой ФСП ID. Сначала отвяжите его",
        )

    # 5. ФИО and birth date match (the answer never says which one did not).
    if not _identity_matches(candidate, athlete):
        raise AppError(
            "FSP_IDENTITY_MISMATCH",
            "ФИО или дата рождения в профиле не совпадают с записью реестра. "
            "Проверьте данные профиля",
            409,
        )

    try:
        facts = fsp_mapping.facts_from_fsp(athlete)
    except (ValueError, KeyError, TypeError) as exc:
        raise AppError(
            "FSP_REGISTRY_UNAVAILABLE",
            "Не удалось прочитать запись реестра ФСП",
            503,
        ) from exc

    try:
        candidate.fsp_id = fsp_id
        candidate.fsp_linked_at = utcnow()
        candidate.fsp_region = athlete.get("region")
        # Flush the link on its own: only the unique `fsp_id` can fail here.
        db.flush()
        replace_facts(db, candidate, "fsp", facts)
        recompute_candidate(db, candidate)
        db.commit()
    except IntegrityError as exc:
        # Somebody linked the same id between the check above and this commit.
        db.rollback()
        owner = _find_owner(db, fsp_id)
        if owner is None:
            raise AppError(
                "CONFLICT",
                "Профиль изменился одновременно из другого запроса. Повторите действие",
                409,
            ) from exc
        raise _already_linked(owner.id == candidate.id) from exc

    imported = Counter(fact.kind for fact in facts)
    return FspLinkResult(
        athlete=FspLinkAthlete(
            fsp_id=fsp_id,
            short_name=short_name(str(athlete.get("full_name") or "")),
            region=athlete.get("region"),
        ),
        imported=FspImported(
            achievements=imported["achievement"],
            ranks=imported["rank"],
            skills=imported["skill"],
            roles=imported["role"],
        ),
        profile=build_profile(db, candidate),
    )


@router.delete(
    "/fsp/link",
    response_model=CandidateProfile,
    summary="Отвязать ФСП ID",
    description=(
        "Снимает привязку к реестру ФСП и удаляет все факты с источником «Реестр ФСП»: "
        "результаты, разряд, навыки дисциплин и роли. Категория пересчитывается, ФИО и дату "
        "рождения снова можно менять. Если ФСП не был привязан, профиль возвращается без "
        "изменений."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
            409: "CONFLICT — профиль одновременно изменён другим запросом",
        }
    ),
)
def unlink_fsp(candidate: CurrentCandidate, db: DbSession) -> CandidateProfile:
    if candidate.fsp_id is not None:
        candidate.fsp_id = None
        candidate.fsp_linked_at = None
        candidate.fsp_region = None
        replace_facts(db, candidate, "fsp", [])
        recompute_candidate(db, candidate)
        commit_profile(db)
    return build_profile(db, candidate)
