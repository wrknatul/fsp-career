"""Pydantic models of the whole API contract (docs/API_CONTRACT.md).

Class names equal the contract type names. `Category`, `Explanation` and `SkillEvidence`
are the domain classes, reused as is.
"""

from app.schemas.achievements import AchievementCreate
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.schemas.candidate import (
    CandidateProfile,
    CandidateProfileUpdate,
    FspInfo,
    ResumeInfo,
)
from app.schemas.common import Category, Explanation, Fact, SkillEvidence, User
from app.schemas.employer import (
    CandidateBrief,
    CandidateCard,
    CandidateMatch,
    CardOffer,
    CategoryMatrix,
    Contacts,
    DisciplineCount,
    EmployerProfile,
    GradeCount,
    MatchQuery,
    MatrixCell,
    SearchResponse,
    StackCount,
    TeamRoleCount,
    WorkFormatCount,
)
from app.schemas.fsp import (
    FspAthletePublic,
    FspCompetitionPublic,
    FspImported,
    FspLinkAthlete,
    FspLinkRequest,
    FspLinkResult,
    FspRankPublic,
    FspResultPublic,
)
from app.schemas.health import HealthResponse
from app.schemas.offers import (
    CandidateOffer,
    EmployerContacts,
    EmployerOffer,
    EmployerOfferVacancy,
    OfferCompany,
    OfferCreate,
    OfferRespondRequest,
    OfferVacancy,
)
from app.schemas.quiz import (
    TestBestResult,
    TestInfo,
    TestResult,
    TestSession,
    TestSubmitRequest,
)
from app.schemas.reference import Dictionaries
from app.schemas.resume import ResumeDemo, ResumeExtracted, ResumeParseResult
from app.schemas.vacancies import Vacancy, VacancyInput, VacancyPatch

__all__ = [
    "AchievementCreate",
    "AuthResponse",
    "CandidateBrief",
    "CandidateCard",
    "CandidateMatch",
    "CandidateOffer",
    "CandidateProfile",
    "CandidateProfileUpdate",
    "CardOffer",
    "Category",
    "CategoryMatrix",
    "Contacts",
    "Dictionaries",
    "DisciplineCount",
    "EmployerContacts",
    "EmployerOffer",
    "EmployerOfferVacancy",
    "EmployerProfile",
    "Explanation",
    "Fact",
    "FspAthletePublic",
    "FspCompetitionPublic",
    "FspImported",
    "FspInfo",
    "FspLinkAthlete",
    "FspLinkRequest",
    "FspLinkResult",
    "FspRankPublic",
    "FspResultPublic",
    "GradeCount",
    "HealthResponse",
    "LoginRequest",
    "MatchQuery",
    "MatrixCell",
    "OfferCompany",
    "OfferCreate",
    "OfferRespondRequest",
    "OfferVacancy",
    "RegisterRequest",
    "ResumeDemo",
    "ResumeExtracted",
    "ResumeInfo",
    "ResumeParseResult",
    "SearchResponse",
    "SkillEvidence",
    "StackCount",
    "TeamRoleCount",
    "TestBestResult",
    "TestInfo",
    "TestResult",
    "TestSession",
    "TestSubmitRequest",
    "User",
    "Vacancy",
    "VacancyInput",
    "VacancyPatch",
    "WorkFormatCount",
]
