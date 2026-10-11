from __future__ import annotations

from typing import Literal

from app.schemas.base import ApiModel
from app.schemas.common import (
    CompetitionLevel,
    Discipline,
    Grade,
    Source,
    SportRank,
    Stack,
    TeamRole,
    Verification,
    WorkFormat,
)


class StackItem(ApiModel):
    id: Stack
    title: str


class GradeItem(ApiModel):
    id: Grade
    title: str


class TeamRoleItem(ApiModel):
    id: TeamRole
    title: str


class WorkFormatItem(ApiModel):
    id: WorkFormat
    title: str


class SourceItem(ApiModel):
    id: Source
    title: str


class VerificationItem(ApiModel):
    id: Verification
    title: str
    weight: float


class DisciplineItem(ApiModel):
    id: Discipline
    title: str


class CompetitionLevelItem(ApiModel):
    id: CompetitionLevel
    title: str


class SportRankItem(ApiModel):
    id: SportRank
    title: str


class SkillItem(ApiModel):
    id: str
    title: str
    stacks: list[str]


class Dictionaries(ApiModel):
    stacks: list[StackItem]
    grades: list[GradeItem]
    team_roles: list[TeamRoleItem]
    work_formats: list[WorkFormatItem]
    sources: list[SourceItem]
    verifications: list[VerificationItem]
    disciplines: list[DisciplineItem]
    competition_levels: list[CompetitionLevelItem]
    sport_ranks: list[SportRankItem]
    skills: list[SkillItem]
    cities: list[str]
    fsp_registry_mode: Literal["mock", "live"]
