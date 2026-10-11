"""Frozen domain types shared by every backend zone.

This module is the seam between the pure domain package and the API layer.
Do not change field names or literals here: the API contract
(docs/API_CONTRACT.md) and the frontend types mirror them one to one.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Stack = Literal[
    "backend",
    "frontend",
    "fullstack",
    "mobile",
    "ml",
    "devops",
    "security",
    "embedded",
    "qa",
    "analyst",
]
Grade = Literal["intern", "junior", "middle", "senior"]
TeamRole = Literal["lead", "developer", "researcher", "devops", "qa", "analyst"]
WorkFormat = Literal["remote", "office", "hybrid"]
Source = Literal["fsp", "test", "resume", "self"]
Verification = Literal["verified", "tested", "parsed", "declared"]
FactKind = Literal["skill", "experience", "achievement", "rank", "role"]
Discipline = Literal["algorithmic", "product", "security", "robotics", "uav"]
CompetitionLevel = Literal["municipal", "regional", "district", "national", "international"]
SportRank = Literal["third", "second", "first", "kms", "ms"]
AchievementResult = Literal["winner", "prize", "participant"]

# Verification level is fully determined by the source of a fact.
VERIFICATION_BY_SOURCE: dict[str, str] = {
    "fsp": "verified",
    "test": "tested",
    "resume": "parsed",
    "self": "declared",
}


class FactData(BaseModel):
    """A profile fact as the domain sees it (no database identity)."""

    kind: FactKind
    key: str
    title: str
    value: dict[str, Any] = Field(default_factory=dict)
    source: Source
    verification: Verification
    evidence: str | None = None


class CandidatePrefs(BaseModel):
    """Self-reported settings of a candidate that affect categorization."""

    city: str | None = None
    work_formats: list[WorkFormat] = Field(default_factory=list)
    relocation: bool = False
    salary_expectation: int | None = None


class Explanation(BaseModel):
    label: str
    points: float
    source: Source | None = None
    verification: Verification | None = None


class StackScore(BaseModel):
    stack: Stack
    score: float


class SkillEvidence(BaseModel):
    skill: str
    title: str
    evidence: float
    best_source: Source
    verification: Verification


class ConfidenceItem(BaseModel):
    label: str
    points: int
    max: int
    done: bool


class Categorization(BaseModel):
    """Result of categorize(); serialized as the contract type `Category`."""

    stack: Stack | None = None
    stack_confirmed: bool = False
    grade: Grade | None = None
    grade_confirmed: bool = False
    team_role: TeamRole | None = None
    team_role_source: Source | None = None
    work_formats: list[WorkFormat] = Field(default_factory=list)
    label: str = "Категория не определена"
    grade_points: float = 0.0
    grade_explanations: list[Explanation] = Field(default_factory=list)
    grade_note: str | None = None
    experience_years: float = 0.0
    experience_points: float = 0.0
    achievement_points: float = 0.0
    stack_scores: list[StackScore] = Field(default_factory=list)
    top_skills: list[SkillEvidence] = Field(default_factory=list)
    confidence_index: int = 0
    confidence_breakdown: list[ConfidenceItem] = Field(default_factory=list)


class ParsedSkill(BaseModel):
    skill: str
    title: str
    level: Literal[1, 2]


class ParsedPosition(BaseModel):
    title: str
    company: str | None = None
    period: str
    years: float
    is_it: bool


class ParsedResume(BaseModel):
    parser: Literal["rules"] = "rules"
    skills: list[ParsedSkill] = Field(default_factory=list)
    experience_years: float = 0.0
    positions: list[ParsedPosition] = Field(default_factory=list)
    work_formats: list[WorkFormat] = Field(default_factory=list)
    city: str | None = None
    salary_expectation: int | None = None
    is_lead: bool = False
    # Facts ready to be stored with source="resume".
    facts: list[FactData] = Field(default_factory=list)


class ParsedQuery(BaseModel):
    """What was recognized in a free-text employer query (hint, not a filter)."""

    skills: list[str] = Field(default_factory=list)
    stack: Stack | None = None
    grade: Grade | None = None


class TestDef(BaseModel):
    skill: str
    title: str
    description: str
    questions_per_session: int = 6
    time_limit_seconds: int = 480


class QuestionPublic(BaseModel):
    """A question as sent to the client: never contains the correct answer."""

    id: str
    text: str
    difficulty: Literal[1, 2, 3]
    options: list[str]


class QuizOutcome(BaseModel):
    score: float  # share of the total weight answered correctly, 0..1
    weight: int  # sum of difficulties of correct answers, 0..12
    level: Literal[0, 1, 2, 3]
    passed: bool
    correct: int
    total: int
    level_title: str
    # Ready-to-store fact (source="test"); None when the test is not passed.
    fact: FactData | None = None


class MatchQuery(BaseModel):
    stacks: list[Stack] = Field(default_factory=list)
    grades: list[Grade] = Field(default_factory=list)
    team_roles: list[TeamRole] = Field(default_factory=list)
    work_formats: list[WorkFormat] = Field(default_factory=list)
    city: str | None = None
    skills_required: list[str] = Field(default_factory=list)
    skills_optional: list[str] = Field(default_factory=list)
    strict_skills: bool = False
    fsp_verified_only: bool = False
    confirmed_only: bool = False
    disciplines: list[Discipline] = Field(default_factory=list)
    salary_max: int | None = None
    text: str | None = None


class CandidateSnapshot(BaseModel):
    """Everything the matcher needs to know about one candidate."""

    id: int
    facts: list[FactData]
    category: Categorization
    embedding: list[float] = Field(default_factory=list)
    city: str | None = None
    relocation: bool = False
    salary_expectation: int | None = None
    visible: bool = True


class MissingSkill(BaseModel):
    skill: str
    title: str


class TopAchievement(BaseModel):
    title: str
    level: CompetitionLevel
    place: int | None = None
    year: int | None = None
    verification: Verification


class MatchComponents(BaseModel):
    skill: float | None = None
    text: float | None = None
    track_record: float = 0.0
    confidence: float = 0.0


class MatchResult(BaseModel):
    candidate_id: int
    score: float | None = None  # 0..100, one decimal; None for filter-only queries
    components: MatchComponents
    matched_skills: list[SkillEvidence] = Field(default_factory=list)
    missing_skills: list[MissingSkill] = Field(default_factory=list)
    top_achievements: list[TopAchievement] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
