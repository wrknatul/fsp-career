from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from app.schemas.base import (
    ApiModel,
    BirthDate,
    OptStr32,
    OptStr64,
    OptStr100,
    OptStr2000,
    PatchModel,
    Salary,
    Str200,
    UTCDatetime,
    unique_list,
)
from app.schemas.common import Category, Fact, User, WorkFormat

WorkFormats = Annotated[
    list[WorkFormat],
    Field(max_length=3),
    AfterValidator(unique_list),
]


class FspInfo(ApiModel):
    fsp_id: str
    linked_at: UTCDatetime
    region: str | None = None


class ResumeInfo(ApiModel):
    filename: str | None = None
    parsed_at: UTCDatetime
    parser: Literal["rules"] = "rules"
    chars: int


class CandidateProfile(ApiModel):
    id: int
    user: User
    birth_date: date | None = None
    city: str | None = None
    work_formats: list[WorkFormat]
    relocation: bool
    salary_expectation: int | None = None
    about: str | None = None
    telegram: str | None = None
    phone: str | None = None
    visible: bool
    fsp: FspInfo | None = None
    resume: ResumeInfo | None = None
    category: Category
    facts: list[Fact]
    updated_at: UTCDatetime


class CandidateProfileUpdate(PatchModel):
    """`PATCH /candidate/profile`: any subset of fields.

    `full_name` and `birth_date` cannot be changed while an FSP id is linked (the route
    answers FSP_LINKED_LOCKED). Nullable fields may be sent as `null` to clear them.
    """

    non_nullable = frozenset({"full_name", "work_formats", "relocation", "visible"})

    full_name: Str200 | None = None
    birth_date: BirthDate | None = None
    city: OptStr100 = None
    work_formats: WorkFormats | None = None
    relocation: bool | None = None
    salary_expectation: Salary | None = None
    about: OptStr2000 = None
    telegram: OptStr64 = None
    phone: OptStr32 = None
    visible: bool | None = None
