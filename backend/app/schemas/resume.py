from __future__ import annotations

from typing import Literal

from app.domain.types import ParsedPosition, ParsedSkill
from app.schemas.base import ApiModel
from app.schemas.candidate import CandidateProfile
from app.schemas.common import WorkFormat


class ResumeExtracted(ApiModel):
    skills: list[ParsedSkill]
    experience_years: float
    positions: list[ParsedPosition]
    work_formats: list[WorkFormat]
    city: str | None = None
    salary_expectation: int | None = None
    is_lead: bool


class ResumeParseResult(ApiModel):
    parser: Literal["rules"] = "rules"
    extracted: ResumeExtracted
    # Which empty profile fields were filled from the resume.
    applied_prefs: list[str]
    profile: CandidateProfile


class ResumeDemo(ApiModel):
    text: str
