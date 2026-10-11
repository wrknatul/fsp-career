from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import CurrentEmployer, DbSession
from app.core.errors import AppError, error_responses
from app.models import Candidate, Offer, Vacancy
from app.schemas import EmployerOffer, OfferCreate
from app.services import search

router = APIRouter(prefix="/employer", tags=["Работодатель"])

_AUTH_ERRORS = {
    401: "UNAUTHORIZED — нет токена, он неверный или истёк",
    403: "FORBIDDEN — маршрут только для работодателей",
}


def _already_sent() -> AppError:
    return AppError(
        "OFFER_ALREADY_SENT", "Оффер этому кандидату по этой вакансии уже отправлен", 409
    )


def _offer_exists(db: Session, vacancy_id: int, candidate_id: int) -> bool:
    statement = select(Offer.id).where(
        Offer.vacancy_id == vacancy_id, Offer.candidate_id == candidate_id
    )
    return db.scalar(statement) is not None


@router.post(
    "/offers",
    status_code=201,
    response_model=EmployerOffer,
    summary="Отправить оффер кандидату",
    description=(
        "Оффер с зарплатой по своей активной вакансии. Кандидат не откликается сам: он видит "
        "оффер во входящих и принимает или отклоняет его. Проверки по порядку: вакансия "
        "(своя) → кандидат (виден работодателям) → вакансия активна → оффера по этой паре "
        "ещё нет. Контакты в оффер не копируются: стороны увидят их после принятия."
    ),
    responses=error_responses(
        {
            **_AUTH_ERRORS,
            404: "NOT_FOUND — вакансии нет или она чужая; кандидата нет или он скрыт",
            409: "VACANCY_INACTIVE — вакансия закрыта; "
            "OFFER_ALREADY_SENT — оффер по этой паре уже есть",
            422: "VALIDATION_ERROR — тело не прошло проверку (например, зарплата не больше нуля)",
        }
    ),
)
def create_offer(body: OfferCreate, employer: CurrentEmployer, db: DbSession) -> EmployerOffer:
    vacancy = db.scalar(
        select(Vacancy).where(Vacancy.id == body.vacancy_id, Vacancy.employer_id == employer.id)
    )
    if vacancy is None:
        raise search.vacancy_not_found()
    candidate = db.scalar(
        select(Candidate).where(Candidate.id == body.candidate_id, Candidate.visible.is_(True))
    )
    if candidate is None:
        raise search.candidate_not_found()
    if not vacancy.is_active:
        raise AppError(
            "VACANCY_INACTIVE", "Вакансия закрыта: оффер по ней отправить нельзя", 409
        )
    vacancy_id, candidate_id = vacancy.id, candidate.id
    if _offer_exists(db, vacancy_id, candidate_id):
        raise _already_sent()

    offer = Offer(
        employer_id=employer.id,
        candidate_id=candidate_id,
        vacancy_id=vacancy_id,
        salary=body.salary,
        message=body.message,
        status="sent",
    )
    db.add(offer)
    try:
        db.commit()
    except IntegrityError as error:
        # A double click or a parallel request: the pair was taken between the check and now.
        db.rollback()
        if _offer_exists(db, vacancy_id, candidate_id):
            raise _already_sent() from error
        if db.get(Vacancy, vacancy_id) is None:
            raise search.vacancy_not_found() from error
        if db.get(Candidate, candidate_id) is None:
            raise search.candidate_not_found() from error
        raise
    return search.employer_offers_view(db, employer, [offer])[0]


@router.get(
    "/offers",
    response_model=list[EmployerOffer],
    summary="Мои офферы",
    description=(
        "Офферы текущего работодателя, новые сверху. Пока оффер не принят, кандидат показан с "
        "сокращённым именем, а комментарий кандидата очищен от контактов. У принятого оффера "
        "есть `contacts` кандидата и полное имя."
    ),
    responses=error_responses(_AUTH_ERRORS),
)
def list_offers(employer: CurrentEmployer, db: DbSession) -> list[EmployerOffer]:
    offers = list(
        db.scalars(
            select(Offer)
            .options(joinedload(Offer.vacancy))
            .where(Offer.employer_id == employer.id)
            .order_by(Offer.created_at.desc(), Offer.id.desc())
        )
    )
    return search.employer_offers_view(db, employer, offers)
