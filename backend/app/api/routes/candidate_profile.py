"""Candidate questionnaire: read and change the profile (`/candidate/profile`)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentCandidate, DbSession
from app.core.errors import AppError, error_responses
from app.schemas.candidate import CandidateProfile, CandidateProfileUpdate
from app.services.profile import (
    build_profile,
    commit_profile,
    recompute_candidate,
)

router = APIRouter(prefix="/candidate", tags=["Соискатель"])

# Questionnaire fields that are stored on the `candidates` row as they are.
_PLAIN_FIELDS = (
    "city",
    "work_formats",
    "relocation",
    "salary_expectation",
    "about",
    "telegram",
    "phone",
    "visible",
)


def _same_text(a: str | None, b: str | None) -> bool:
    return " ".join((a or "").split()) == " ".join((b or "").split())


@router.get(
    "/profile",
    response_model=CandidateProfile,
    summary="Профиль соискателя",
    description=(
        "Анкета текущего соискателя целиком: данные, привязка ФСП, резюме, категория с "
        "объяснением, индекс подтверждённости и все факты профиля с источниками. "
        "Пока ничего не заполнено, категория — «Категория не определена»."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
            404: "NOT_FOUND — у пользователя нет профиля соискателя",
        }
    ),
)
def get_profile(candidate: CurrentCandidate, db: DbSession) -> CandidateProfile:
    return build_profile(db, candidate)


@router.patch(
    "/profile",
    response_model=CandidateProfile,
    summary="Изменить анкету",
    description=(
        "Частичное обновление: меняются только присланные поля; `null` очищает поле, где это "
        "разрешено (город, зарплатные ожидания, «о себе», контакты, дата рождения). "
        "`full_name` меняет имя аккаунта. Пока к профилю привязан ФСП ID, запрос с `full_name` "
        "или `birth_date` отклоняется целиком (даже с прежним значением): сначала отвяжите ФСП. "
        "После изменения категория и текстовый вектор пересчитываются. "
        "Флаг `visible` разрешает или запрещает показ профиля работодателям."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
            404: "NOT_FOUND — у пользователя нет профиля соискателя",
            409: "FSP_LINKED_LOCKED — в запросе есть ФИО или дата рождения при привязанном ФСП; "
            "CONFLICT — профиль одновременно изменён другим запросом",
            422: "VALIDATION_ERROR — данные не прошли проверку",
        }
    ),
)
def update_profile(
    body: CandidateProfileUpdate, candidate: CurrentCandidate, db: DbSession
) -> CandidateProfile:
    changes = body.model_dump(exclude_unset=True)

    # SPEC 6.1: while FSP is linked, any PATCH that carries either field is refused, even with
    # the current value. Nothing of the rest of the body is applied.
    if candidate.fsp_id is not None and ("full_name" in changes or "birth_date" in changes):
        raise AppError(
            "FSP_LINKED_LOCKED",
            "ФИО и дату рождения нельзя изменить, пока привязан ФСП ID. Сначала отвяжите ФСП",
            409,
        )

    if "full_name" in changes and not _same_text(changes["full_name"], candidate.user.full_name):
        candidate.user.full_name = changes["full_name"]
    if "birth_date" in changes:
        candidate.birth_date = changes["birth_date"]
    for field in _PLAIN_FIELDS:
        if field in changes:
            setattr(candidate, field, changes[field])

    recompute_candidate(db, candidate)
    commit_profile(db)
    return build_profile(db, candidate)
