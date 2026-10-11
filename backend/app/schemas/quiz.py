"""Express tests (`/candidate/tests`).

The `Test*` classes carry `__test__ = False` so pytest does not try to collect them when a
test module imports them.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from app.domain.types import QuestionPublic
from app.schemas.base import ApiModel, InputModel, UTCDatetime
from app.schemas.candidate import CandidateProfile


class TestBestResult(ApiModel):
    __test__ = False

    level: Literal[1, 2, 3]
    level_title: str
    score: float
    submitted_at: UTCDatetime


class TestInfo(ApiModel):
    __test__ = False

    skill: str
    title: str
    description: str
    questions_per_session: int
    time_limit_seconds: int
    best_result: TestBestResult | None = None
    # An open, not yet expired session exists.
    active_session_id: int | None = None
    # Not null while the pause between attempts is in effect.
    available_at: UTCDatetime | None = None


class TestSession(ApiModel):
    __test__ = False

    session_id: int
    skill: str
    title: str
    started_at: UTCDatetime
    expires_at: UTCDatetime
    # Never contains the correct answers.
    questions: list[QuestionPublic]


class TestSubmitRequest(InputModel):
    # question id -> index of the chosen option in the order the options were sent
    answers: Annotated[
        dict[
            Annotated[str, Field(min_length=1, max_length=64)],
            Annotated[int, Field(ge=0, le=20)],
        ],
        Field(max_length=50),
    ]


class TestResult(ApiModel):
    __test__ = False

    session_id: int
    skill: str
    # Share of the total weight answered correctly, 0..1.
    score: float
    level: Literal[0, 1, 2, 3]
    passed: bool
    correct: int
    total: int
    # "Не сдан" | "Базовый" | "Уверенный" | "Продвинутый"
    level_title: str
    profile: CandidateProfile
