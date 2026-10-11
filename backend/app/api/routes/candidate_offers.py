"""The candidate's inbox of offers and the answer to an offer (`/candidate/offers`)."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import joinedload

from app.api.deps import CurrentCandidate, DbSession
from app.core.errors import AppError, error_responses
from app.core.timeutil import utcnow
from app.models import Offer
from app.schemas.base import MAX_INT
from app.schemas.offers import (
    CandidateOffer,
    EmployerContacts,
    OfferCompany,
    OfferRespondRequest,
    OfferVacancy,
)

router = APIRouter(prefix="/candidate", tags=["Соискатель"])


def _offer_view(offer: Offer) -> CandidateOffer:
    employer = offer.employer
    contacts = None
    if offer.status == "accepted":
        # Contacts are not copied into the offer: they are read from the employer on demand
        # and only once the candidate has accepted.
        contacts = EmployerContacts(
            contact_name=employer.contact_name,
            contact_email=employer.contact_email,
            contact_telegram=employer.contact_telegram,
        )
    return CandidateOffer(
        id=offer.id,
        status=offer.status,  # type: ignore[arg-type]
        salary=offer.salary,
        message=offer.message,
        created_at=offer.created_at,
        responded_at=offer.responded_at,
        candidate_comment=offer.candidate_comment,
        vacancy=OfferVacancy.model_validate(offer.vacancy),
        company=OfferCompany(
            name=employer.company_name,
            about=employer.about,
            website=employer.website,
            verified=bool(employer.verified),
        ),
        employer_contacts=contacts,
    )


@router.get(
    "/offers",
    response_model=list[CandidateOffer],
    summary="Входящие офферы",
    description=(
        "Офферы работодателей текущему соискателю, новые сверху: зарплата, сообщение, "
        "вакансия и компания (с отметкой, проверена ли она). Контакты работодателя "
        "(`employer_contacts`) приходят только у принятого оффера."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
        }
    ),
)
def get_offers(candidate: CurrentCandidate, db: DbSession) -> list[CandidateOffer]:
    offers = db.scalars(
        select(Offer)
        .where(Offer.candidate_id == candidate.id)
        .options(joinedload(Offer.vacancy), joinedload(Offer.employer))
        .order_by(Offer.created_at.desc(), Offer.id.desc())
    ).unique()
    return [_offer_view(offer) for offer in offers]


@router.post(
    "/offers/{offer_id}/respond",
    response_model=CandidateOffer,
    summary="Ответить на оффер",
    description=(
        "Принять (`accept`) или отклонить (`decline`) оффер, необязательно с комментарием до "
        "500 символов. Ответить можно один раз: статус меняется условным обновлением из "
        "`sent`, повторный ответ — `OFFER_ALREADY_RESPONDED`. После принятия работодатель "
        "видит контакты и полное ФИО соискателя, а соискатель — контакты работодателя."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
            404: "NOT_FOUND — оффера нет или он адресован другому соискателю",
            409: "OFFER_ALREADY_RESPONDED — на оффер уже ответили",
            422: "VALIDATION_ERROR — данные не прошли проверку",
        }
    ),
)
def respond_to_offer(
    offer_id: int, body: OfferRespondRequest, candidate: CurrentCandidate, db: DbSession
) -> CandidateOffer:
    not_found = AppError("NOT_FOUND", "Оффер не найден", 404)
    if not 0 < offer_id <= MAX_INT:
        raise not_found

    # One conditional UPDATE decides the race between two answers (and a foreign offer
    # matches no row at all).
    updated = cast(
        CursorResult,
        db.execute(
            update(Offer)
            .where(
                Offer.id == offer_id,
                Offer.candidate_id == candidate.id,
                Offer.status == "sent",
            )
            .values(
                status="accepted" if body.decision == "accept" else "declined",
                candidate_comment=body.comment,
                responded_at=utcnow(),
            )
            .execution_options(synchronize_session=False)
        ),
    )
    if updated.rowcount == 0:
        mine = db.scalar(
            select(Offer.id).where(Offer.id == offer_id, Offer.candidate_id == candidate.id)
        )
        if mine is None:
            raise not_found
        raise AppError("OFFER_ALREADY_RESPONDED", "На этот оффер вы уже ответили", 409)
    db.commit()

    offer = db.scalars(
        select(Offer)
        .where(Offer.id == offer_id)
        .options(joinedload(Offer.vacancy), joinedload(Offer.employer))
        .execution_options(populate_existing=True)
    ).unique().one()
    return _offer_view(offer)
