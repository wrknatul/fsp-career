from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentEmployer, DbSession
from app.core.errors import error_responses
from app.models import Candidate
from app.schemas import CandidateCard, CategoryMatrix, MatchQuery, SearchResponse
from app.schemas.base import MAX_INT
from app.schemas.common import TeamRole, WorkFormat
from app.services import search

router = APIRouter(prefix="/employer", tags=["Работодатель"])

_AUTH_ERRORS = {
    401: "UNAUTHORIZED — нет токена, он неверный или истёк",
    403: "FORBIDDEN — маршрут только для работодателей",
}


@router.get(
    "/categories",
    response_model=CategoryMatrix,
    summary="Матрица категорий «стек × грейд»",
    description=(
        "Сколько кандидатов в каждой категории. Считаются только кандидаты, которые разрешили "
        "показ профиля и у которых определён стек, — тот же отбор, что и в поиске. "
        "Параметры `team_role` и `work_format` сужают отбор по тем же правилам, что фильтры "
        "поиска (кандидат без указанных форматов работы подходит под любой формат). "
        "В `cells` попадают только непустые ячейки; `fsp_verified` — сколько кандидатов в ячейке "
        "имеют результаты в реестре ФСП. Кандидат со стеком `fullstack` считается в своей "
        "ячейке, а поиск по стеку `backend` или `frontend` находит и его."
    ),
    responses=error_responses(
        {**_AUTH_ERRORS, 422: "VALIDATION_ERROR — недопустимое значение фильтра"}
    ),
)
def get_category_matrix(
    employer: CurrentEmployer,
    db: DbSession,
    team_role: Annotated[
        TeamRole | None, Query(description="Только кандидаты с этой ролью в команде")
    ] = None,
    work_format: Annotated[
        WorkFormat | None, Query(description="Только кандидаты с этим форматом работы")
    ] = None,
) -> CategoryMatrix:
    snapshots = search.load_snapshots(db)
    return search.category_matrix(snapshots, team_role=team_role, work_format=work_format)


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Поиск кандидатов",
    description=(
        "Жёсткие фильтры (стек, грейд, роль, формат работы, город, зарплата, только с "
        "результатами ФСП, только подтверждённые, дисциплины, обязательные навыки) и "
        "ранжирование по оценке 0–100: навыки, совпадение с текстом запроса, спортивные и "
        "рабочие достижения, индекс подтверждённости. Без навыков и текста оценки нет "
        "(`score = null`), порядок — по достижениям. Навыки, найденные в `text`, добавляются "
        "к необязательным; что именно найдено, видно в `parsed_query`. `vacancy_id` — своя "
        "вакансия: её поля дополняют незаполненные поля запроса. Кандидаты показываются "
        "без контактов и с сокращённым именем, пока оффер не принят."
    ),
    responses=error_responses(
        {
            **_AUTH_ERRORS,
            404: "NOT_FOUND — вакансии нет или она чужая",
            422: "VALIDATION_ERROR — тело не прошло проверку, неизвестный id навыка или "
            "offset больше 500",
        }
    ),
)
def search_candidates(body: MatchQuery, employer: CurrentEmployer, db: DbSession) -> SearchResponse:
    return search.search_candidates(db, employer, body)


@router.get(
    "/candidates/{candidate_id}",
    response_model=CandidateCard,
    summary="Карточка кандидата",
    description=(
        "Профиль кандидата: категория с объяснением, факты с источниками и уровнем "
        "подтверждения, офферы этого работодателя. Пока оффер не принят, имя сокращено, а "
        "в «о себе» и подписях фактов контакты скрыты (`[скрыто]`); после принятия оффера "
        "видны полное имя и `contacts`. Скрытый кандидат и несуществующий неразличимы: "
        "в обоих случаях `NOT_FOUND`."
    ),
    responses=error_responses(
        {
            **_AUTH_ERRORS,
            404: "NOT_FOUND — кандидата нет или он скрыл профиль",
            422: "VALIDATION_ERROR — идентификатор кандидата не число",
        }
    ),
)
def get_candidate_card(
    candidate_id: int, employer: CurrentEmployer, db: DbSession
) -> CandidateCard:
    if not 0 < candidate_id <= MAX_INT:
        raise search.candidate_not_found()
    candidate = db.get(Candidate, candidate_id)
    if candidate is None or not candidate.visible:
        raise search.candidate_not_found()
    return search.candidate_card(db, candidate, employer)
