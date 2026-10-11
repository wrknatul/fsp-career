"""Offers: the candidate's inbox, the employer's outbox and the bodies that change them."""

from __future__ import annotations

from typing import Literal

from app.schemas.base import (
    ApiModel,
    DbId,
    InputModel,
    OptStr500,
    OptStr1000,
    Salary,
    UTCDatetime,
)
from app.schemas.common import Grade, OfferStatus, Stack, WorkFormat
from app.schemas.employer import CandidateBrief, Contacts

# --- candidate side ------------------------------------------------------------------------


class OfferVacancy(ApiModel):
    id: int
    title: str
    description: str
    stack: Stack
    grade: Grade
    work_formats: list[WorkFormat]
    city: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None


class OfferCompany(ApiModel):
    name: str
    about: str | None = None
    website: str | None = None
    verified: bool


class EmployerContacts(ApiModel):
    contact_name: str | None = None
    contact_email: str | None = None
    contact_telegram: str | None = None


class CandidateOffer(ApiModel):
    id: int
    status: OfferStatus
    salary: int
    message: str | None = None
    created_at: UTCDatetime
    responded_at: UTCDatetime | None = None
    candidate_comment: str | None = None
    vacancy: OfferVacancy
    company: OfferCompany
    # Only after the offer is accepted.
    employer_contacts: EmployerContacts | None = None


class OfferRespondRequest(InputModel):
    decision: Literal["accept", "decline"]
    comment: OptStr500 = None


# --- employer side -------------------------------------------------------------------------


class OfferCreate(InputModel):
    """`POST /employer/offers`."""

    candidate_id: DbId
    vacancy_id: DbId
    salary: Salary
    message: OptStr1000 = None


class EmployerOfferVacancy(ApiModel):
    id: int
    title: str


class EmployerOffer(ApiModel):
    id: int
    status: OfferStatus
    salary: int
    message: str | None = None
    created_at: UTCDatetime
    responded_at: UTCDatetime | None = None
    # Passed through `redact_contacts` until the offer is accepted.
    candidate_comment: str | None = None
    vacancy: EmployerOfferVacancy
    candidate: CandidateBrief
    # Only when the offer is accepted.
    contacts: Contacts | None = None
