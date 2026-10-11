"""FSP linking (candidate side) and the public mock registry representation."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.base import ApiModel, InputModel
from app.schemas.candidate import CandidateProfile
from app.schemas.common import CompetitionLevel, Discipline, SportRank


class FspLinkRequest(InputModel):
    fsp_id: str = Field(min_length=1, max_length=64)


class FspLinkAthlete(ApiModel):
    fsp_id: str
    short_name: str
    region: str | None = None


class FspImported(ApiModel):
    achievements: int
    ranks: int
    skills: int
    roles: int


class FspLinkResult(ApiModel):
    athlete: FspLinkAthlete
    imported: FspImported
    profile: CandidateProfile


# --- public mock registry (birth date and athlete's city are never exposed) ----------------

CompetitionKind = Literal["championship", "cup", "junior_championship", "festival"]
CompetitionFormat = Literal["team", "individual"]
ResultTeamRole = Literal["captain", "backend", "frontend", "ml", "analyst", "designer", "member"]


class FspRankPublic(ApiModel):
    rank: SportRank
    discipline: Discipline
    assigned_at: date
    order_no: str


class FspCompetitionPublic(ApiModel):
    competition_id: str
    title: str
    discipline: Discipline
    level: CompetitionLevel
    kind: CompetitionKind
    date_start: date
    date_end: date
    city: str
    format: CompetitionFormat
    participants_total: int


class FspResultPublic(ApiModel):
    result_id: str
    competition: FspCompetitionPublic
    place: int
    team_name: str | None = None
    team_role: ResultTeamRole | None = None
    protocol_url: str


class FspAthletePublic(ApiModel):
    fsp_id: str
    short_name: str
    region: str | None = None
    ranks: list[FspRankPublic]
    results: list[FspResultPublic]
