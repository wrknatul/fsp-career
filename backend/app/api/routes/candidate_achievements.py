"""Achievements the candidate adds by hand (`/candidate/achievements`, SPEC section 6.4)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentCandidate, DbSession
from app.core.errors import AppError, error_responses
from app.domain import facts as domain_facts
from app.models import ProfileFact
from app.schemas.achievements import AchievementCreate
from app.schemas.base import MAX_INT
from app.schemas.candidate import CandidateProfile
from app.services.profile import (
    build_profile,
    commit_profile,
    recompute_candidate,
    upsert_fact,
)

router = APIRouter(prefix="/candidate", tags=["Соискатель"])


@router.post(
    "/achievements",
    response_model=CandidateProfile,
    status_code=201,
    summary="Добавить достижение",
    description=(
        "Добавляет достижение вне реестра ФСП: олимпиаду, хакатон, CTF. Факт помечается "
        "«Заявлено соискателем» — не подтверждено, вклад в грейд — 35% от такого же "
        "подтверждённого результата. Категория пересчитывается."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
            409: "CONFLICT — профиль одновременно изменён другим запросом",
            422: "VALIDATION_ERROR — данные не прошли проверку",
        }
    ),
)
def add_achievement(
    body: AchievementCreate, candidate: CurrentCandidate, db: DbSession
) -> CandidateProfile:
    fact = domain_facts.manual_achievement_fact(
        str(uuid.uuid4()),
        body.title,
        body.year,
        body.level,
        body.result,
        body.discipline,
        body.document_url,
    )
    upsert_fact(db, candidate, fact)
    recompute_candidate(db, candidate)
    commit_profile(db)
    return build_profile(db, candidate)


@router.delete(
    "/achievements/{fact_id}",
    response_model=CandidateProfile,
    summary="Удалить достижение",
    description=(
        "Удаляет достижение, добавленное вручную. Факты из реестра ФСП, теста и резюме так "
        "удалить нельзя: для них — отвязка ФСП, удаление резюме. Чужой, несуществующий и "
        "не созданный соискателем факт одинаково дают `NOT_FOUND`. Категория пересчитывается."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
            404: "NOT_FOUND — такого достижения нет или оно не добавлено вручную",
            409: "CONFLICT — профиль одновременно изменён другим запросом",
            422: "VALIDATION_ERROR — идентификатор достижения не число",
        }
    ),
)
def delete_achievement(
    fact_id: int, candidate: CurrentCandidate, db: DbSession
) -> CandidateProfile:
    fact = None
    if 0 < fact_id <= MAX_INT:
        fact = db.scalar(
            select(ProfileFact).where(
                ProfileFact.id == fact_id,
                ProfileFact.candidate_id == candidate.id,
                ProfileFact.kind == "achievement",
                ProfileFact.source == "self",
            )
        )
    if fact is None:
        raise AppError("NOT_FOUND", "Достижение не найдено", 404)
    db.delete(fact)
    db.flush()
    db.expire(candidate, ["facts"])
    recompute_candidate(db, candidate)
    commit_profile(db)
    return build_profile(db, candidate)
