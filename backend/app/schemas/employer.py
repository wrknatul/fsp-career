"""Employer side: profile, category matrix, search and candidate cards."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field

from app.domain.types import (
    MatchComponents,
    MissingSkill,
    ParsedQuery,
    TopAchievement,
)
from app.domain.types import MatchQuery as DomainMatchQuery
from app.schemas.base import (
    ApiModel,
    DbId,
    InputModel,
    OptStr100,
    OptStr2000,
    Salary,
    UTCDatetime,
    unique_list,
)
from app.schemas.common import (
    Category,
    Discipline,
    Fact,
    Grade,
    OfferStatus,
    SkillEvidence,
    SportRank,
    Stack,
    TeamRole,
    User,
    WorkFormat,
)
from app.schemas.vacancies import SkillIds, WorkFormats

# --- profile -------------------------------------------------------------------------------


class EmployerProfile(ApiModel):
    id: int
    user: User
    company_name: str
    about: str | None = None
    website: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_telegram: str | None = None
    verified: bool


# --- category matrix -----------------------------------------------------------------------


class MatrixCell(ApiModel):
    stack: Stack
    grade: Grade
    count: int
    fsp_verified: int


class StackCount(ApiModel):
    stack: Stack
    count: int


class GradeCount(ApiModel):
    grade: Grade
    count: int


class TeamRoleCount(ApiModel):
    team_role: TeamRole
    count: int


class WorkFormatCount(ApiModel):
    work_format: WorkFormat
    count: int


class DisciplineCount(ApiModel):
    discipline: Discipline
    count: int


class CategoryMatrix(ApiModel):
    total_candidates: int
    # Only cells with count > 0.
    cells: list[MatrixCell]
    by_stack: list[StackCount]
    by_grade: list[GradeCount]
    by_team_role: list[TeamRoleCount]
    by_work_format: list[WorkFormatCount]
    by_discipline: list[DisciplineCount]
    fsp_verified_total: int


# --- search --------------------------------------------------------------------------------

_Stacks = Annotated[list[Stack], Field(max_length=10), AfterValidator(unique_list)]
_Grades = Annotated[list[Grade], Field(max_length=4), AfterValidator(unique_list)]
_TeamRoles = Annotated[list[TeamRole], Field(max_length=6), AfterValidator(unique_list)]
_Disciplines = Annotated[list[Discipline], Field(max_length=5), AfterValidator(unique_list)]


class MatchQuery(InputModel):
    """Contract `MatchQuery` (the domain `MatchQuery` has no `vacancy_id`, `limit`, `offset`).

    Unknown skill ids must be rejected by the route with VALIDATION_ERROR.
    """

    stacks: _Stacks = Field(default_factory=list)
    grades: _Grades = Field(default_factory=list)
    team_roles: _TeamRoles = Field(default_factory=list)
    work_formats: WorkFormats = Field(default_factory=list)
    city: OptStr100 = None
    skills_required: SkillIds = Field(default_factory=list)
    skills_optional: SkillIds = Field(default_factory=list)
    strict_skills: bool = False
    fsp_verified_only: bool = False
    confirmed_only: bool = False
    disciplines: _Disciplines = Field(default_factory=list)
    salary_max: Salary | None = None
    text: OptStr2000 = None
    # Own vacancy: its fields supplement the query.
    vacancy_id: DbId | None = None
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=500)

    def to_domain(self) -> DomainMatchQuery:
        """The filter part of the query, as the matcher understands it."""
        return DomainMatchQuery(
            **self.model_dump(exclude={"vacancy_id", "limit", "offset"}),
        )


class CandidateBrief(ApiModel):
    id: int
    # "Алексей С."; the full name only after this employer's offer is accepted.
    display_name: str
    city: str | None = None
    category: Category
    salary_expectation: int | None = None
    relocation: bool
    fsp_linked: bool
    sport_rank: SportRank | None = None
    # Passed through `redact_contacts`.
    about: str | None = None


class CandidateMatch(ApiModel):
    candidate: CandidateBrief
    # 0..100 with one decimal; null for a query without skills and text.
    score: float | None = None
    components: MatchComponents
    matched_skills: list[SkillEvidence]
    missing_skills: list[MissingSkill]
    top_achievements: list[TopAchievement]
    reasons: list[str]
    # This employer's latest offer to the candidate.
    offer_status: OfferStatus | None = None


class SearchResponse(ApiModel):
    total: int
    limit: int
    offset: int
    items: list[CandidateMatch]
    parsed_query: ParsedQuery | None = None


# --- candidate card ------------------------------------------------------------------------


class Contacts(ApiModel):
    email: str
    telegram: str | None = None
    phone: str | None = None


class CardOffer(ApiModel):
    id: int
    vacancy_id: int
    vacancy_title: str
    status: OfferStatus
    salary: int
    created_at: UTCDatetime


class CandidateCard(CandidateBrief):
    # `title` and `evidence` are passed through `redact_contacts`.
    facts: list[Fact]
    work_formats: list[WorkFormat]
    # Only after this employer's offer is accepted.
    contacts: Contacts | None = None
    # Only this employer's offers.
    offers: list[CardOffer]
