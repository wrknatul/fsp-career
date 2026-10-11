from __future__ import annotations

from typing import Annotated, Self

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from app.schemas.base import (
    ApiModel,
    InputModel,
    OptStr100,
    PatchModel,
    Salary,
    UTCDatetime,
    required_text,
    unique_list,
)
from app.schemas.common import Grade, Stack, TeamRole, WorkFormat

SkillId = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=64)
]
SkillIds = Annotated[list[SkillId], Field(max_length=30), AfterValidator(unique_list)]
WorkFormats = Annotated[list[WorkFormat], Field(max_length=3), AfterValidator(unique_list)]
VacancyTitle = required_text(200, min_length=2)
VacancyDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]


def _check_salary_range(salary_from: int | None, salary_to: int | None) -> None:
    if salary_from is not None and salary_to is not None and salary_from > salary_to:
        raise ValueError("Нижняя граница зарплаты не может быть выше верхней")


class Vacancy(ApiModel):
    id: int
    title: str
    description: str
    stack: Stack
    grade: Grade
    team_role: TeamRole | None = None
    skills_required: list[str]
    skills_optional: list[str]
    work_formats: list[WorkFormat]
    city: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    is_active: bool
    created_at: UTCDatetime
    offers_count: int


class VacancyInput(InputModel):
    """`POST /employer/vacancies`. Skill ids are checked against the ontology by the route."""

    title: VacancyTitle
    description: VacancyDescription
    stack: Stack
    grade: Grade
    team_role: TeamRole | None = None
    skills_required: SkillIds = Field(default_factory=list)
    skills_optional: SkillIds = Field(default_factory=list)
    work_formats: WorkFormats = Field(default_factory=list)
    city: OptStr100 = None
    salary_from: Salary | None = None
    salary_to: Salary | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _salary_range(self) -> Self:
        _check_salary_range(self.salary_from, self.salary_to)
        return self


class VacancyPatch(PatchModel):
    """`PATCH /employer/vacancies/{id}`: a partial `VacancyInput`.

    Only fields in `model_fields_set` are applied. The range check below sees just the fields
    of this body, so the route must re-check `salary_from <= salary_to` on the merged values.
    """

    non_nullable = frozenset(
        {
            "title",
            "description",
            "stack",
            "grade",
            "skills_required",
            "skills_optional",
            "work_formats",
            "is_active",
        }
    )

    title: VacancyTitle | None = None
    description: VacancyDescription | None = None
    stack: Stack | None = None
    grade: Grade | None = None
    team_role: TeamRole | None = None
    skills_required: SkillIds | None = None
    skills_optional: SkillIds | None = None
    work_formats: WorkFormats | None = None
    city: OptStr100 = None
    salary_from: Salary | None = None
    salary_to: Salary | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _salary_range(self) -> Self:
        _check_salary_range(self.salary_from, self.salary_to)
        return self
