from __future__ import annotations

from collections.abc import Iterable

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentEmployer, DbSession
from app.core.errors import error_responses, field_validation_error
from app.domain import ontology
from app.models import Employer, Offer, Vacancy
from app.schemas.base import MAX_INT
from app.schemas.vacancies import Vacancy as VacancyOut
from app.schemas.vacancies import VacancyInput, VacancyPatch
from app.services.search import vacancy_not_found

router = APIRouter(prefix="/employer", tags=["Работодатель"])

_SKILL_FIELDS = ("skills_required", "skills_optional")
_SALARY_RANGE_MESSAGE = "Нижняя граница зарплаты не может быть выше верхней"


def _check_skills(values: dict[str, object]) -> None:
    """Every skill id of the given fields must be in the ontology (422 `VALIDATION_ERROR`)."""
    errors: list[tuple[list[str | int], str]] = []
    for field in _SKILL_FIELDS:
        skills = values.get(field)
        if not isinstance(skills, list):
            continue
        unknown = [skill for skill in skills if not ontology.is_known_skill(skill)]
        if unknown:
            errors.append((["body", field], f"Неизвестные навыки: {', '.join(unknown)}"))
    if errors:
        raise field_validation_error(errors)


def _offers_counts(db: Session, employer: Employer, vacancy_ids: Iterable[int]) -> dict[int, int]:
    ids = set(vacancy_ids)
    if not ids:
        return {}
    statement = (
        select(Offer.vacancy_id, func.count(Offer.id))
        .where(Offer.employer_id == employer.id, Offer.vacancy_id.in_(sorted(ids)))
        .group_by(Offer.vacancy_id)
    )
    return {vacancy_id: count for vacancy_id, count in db.execute(statement)}


def _view(vacancy: Vacancy, offers_count: int) -> VacancyOut:
    return VacancyOut(
        id=vacancy.id,
        title=vacancy.title,
        description=vacancy.description,
        stack=vacancy.stack,
        grade=vacancy.grade,
        team_role=vacancy.team_role,
        skills_required=list(vacancy.skills_required or []),
        skills_optional=list(vacancy.skills_optional or []),
        work_formats=list(vacancy.work_formats or []),
        city=vacancy.city,
        salary_from=vacancy.salary_from,
        salary_to=vacancy.salary_to,
        is_active=vacancy.is_active,
        created_at=vacancy.created_at,
        offers_count=offers_count,
    )


def _own_vacancy(db: Session, employer: Employer, vacancy_id: int) -> Vacancy:
    """The employer's vacancy; a missing and a foreign one are the same 404."""
    if not 0 < vacancy_id <= MAX_INT:
        raise vacancy_not_found()
    vacancy = db.scalar(
        select(Vacancy).where(Vacancy.id == vacancy_id, Vacancy.employer_id == employer.id)
    )
    if vacancy is None:
        raise vacancy_not_found()
    return vacancy


@router.get(
    "/vacancies",
    response_model=list[VacancyOut],
    summary="Мои вакансии",
    description=(
        "Вакансии текущего работодателя, новые сверху. В поле `offers_count` — сколько офферов "
        "уже отправлено по вакансии (в любом статусе)."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для работодателей",
        }
    ),
)
def list_vacancies(employer: CurrentEmployer, db: DbSession) -> list[VacancyOut]:
    vacancies = list(
        db.scalars(
            select(Vacancy)
            .where(Vacancy.employer_id == employer.id)
            .order_by(Vacancy.created_at.desc(), Vacancy.id.desc())
        )
    )
    counts = _offers_counts(db, employer, (vacancy.id for vacancy in vacancies))
    return [_view(vacancy, counts.get(vacancy.id, 0)) for vacancy in vacancies]


@router.post(
    "/vacancies",
    status_code=201,
    response_model=VacancyOut,
    summary="Создать вакансию",
    description=(
        "Заводит вакансию работодателя. Вакансия нужна для оффера и может подмешиваться в "
        "поисковый запрос (`vacancy_id`). Идентификаторы навыков проверяются по онтологии: "
        "неизвестный навык — `VALIDATION_ERROR`."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для работодателей",
            422: "VALIDATION_ERROR — тело не прошло проверку или неизвестный id навыка",
        }
    ),
)
def create_vacancy(body: VacancyInput, employer: CurrentEmployer, db: DbSession) -> VacancyOut:
    values = body.model_dump()
    _check_skills(values)
    vacancy = Vacancy(employer_id=employer.id, **values)
    db.add(vacancy)
    db.commit()
    return _view(vacancy, 0)


@router.patch(
    "/vacancies/{vacancy_id}",
    response_model=VacancyOut,
    summary="Изменить вакансию",
    description=(
        "Частичное обновление: меняются только переданные поля. Так же закрывается вакансия "
        "(`is_active: false`): по закрытой вакансии оффер отправить нельзя. Чужая или "
        "несуществующая вакансия — `NOT_FOUND`."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для работодателей",
            404: "NOT_FOUND — вакансии нет или она чужая",
            422: "VALIDATION_ERROR — тело не прошло проверку, неизвестный id навыка или "
            "нижняя граница зарплаты выше верхней",
        }
    ),
)
def update_vacancy(
    vacancy_id: int, body: VacancyPatch, employer: CurrentEmployer, db: DbSession
) -> VacancyOut:
    vacancy = _own_vacancy(db, employer, vacancy_id)
    changes = body.model_dump(exclude_unset=True)
    _check_skills(changes)

    # The body validator saw only its own fields: check the range on the merged values.
    salary_from = changes.get("salary_from", vacancy.salary_from)
    salary_to = changes.get("salary_to", vacancy.salary_to)
    if salary_from is not None and salary_to is not None and salary_from > salary_to:
        raise field_validation_error([(["body", "salary_from"], _SALARY_RANGE_MESSAGE)])

    for name, value in changes.items():
        # JSON columns do not track in-place changes: always assign a new list.
        setattr(vacancy, name, list(value) if isinstance(value, list) else value)
    db.commit()
    counts = _offers_counts(db, employer, [vacancy.id])
    return _view(vacancy, counts.get(vacancy.id, 0))
