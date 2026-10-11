"""Express tests: list, start, submit (`/candidate/tests`, SPEC section 6.3).

A session is a row of `test_sessions`. Its questions are never stored: they are rebuilt from a
seed derived from the session id and the server secret, so the client can neither predict the
questions of a future session nor receive the correct answers.
"""

from __future__ import annotations

import hashlib
import hmac
from collections import defaultdict
from datetime import datetime, timedelta
from typing import cast

from fastapi import APIRouter, Response
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from app.api.deps import AppSettings, CurrentCandidate, DbSession
from app.core.config import Settings
from app.core.errors import AppError, error_responses, field_validation_error
from app.core.timeutil import as_utc, utcnow
from app.domain import quiz
from app.domain.scoring_config import QUIZ_LEVEL_TITLES
from app.domain.types import TestDef
from app.models import QuizSession
from app.schemas.base import MAX_INT
from app.schemas.quiz import (
    TestBestResult,
    TestInfo,
    TestResult,
    TestSession,
    TestSubmitRequest,
)
from app.services.profile import (
    build_profile,
    commit_profile,
    recompute_candidate,
    upsert_fact,
)

router = APIRouter(prefix="/candidate", tags=["Соискатель"])


def session_seed(secret: str, session_id: int) -> int:
    """`int(HMAC_SHA256(JWT_SECRET, str(session_id)).hexdigest()[:12], 16)` (SPEC 6.3)."""
    digest = hmac.new(
        secret.encode("utf-8"), str(session_id).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return int(digest[:12], 16)


def _test_not_found() -> AppError:
    return AppError("TEST_NOT_FOUND", "Такой тест или сессия не найдены", 404)


def _find_test(skill: str) -> TestDef:
    for test in quiz.list_tests():
        if test.skill == skill:
            return test
    raise _test_not_found()


def _open_session(sessions: list[QuizSession], now: datetime) -> QuizSession | None:
    """The newest session that is neither submitted nor expired."""
    for session in sorted(sessions, key=lambda s: s.id, reverse=True):
        if session.submitted_at is None and as_utc(session.expires_at) > now:
            return session
    return None


def _cooldown_until(
    sessions: list[QuizSession], settings: Settings, now: datetime
) -> datetime | None:
    """When the pause after the latest attempt ends; None if there is no pause."""
    if not sessions:
        return None
    last = max(sessions, key=lambda s: (as_utc(s.started_at), s.id))
    until = as_utc(last.started_at) + timedelta(minutes=settings.TEST_COOLDOWN_MINUTES)
    return until if until > now else None


def _best_result(sessions: list[QuizSession]) -> TestBestResult | None:
    passed = [s for s in sessions if s.submitted_at is not None and (s.level or 0) >= 1]
    if not passed:
        return None
    best = max(passed, key=lambda s: (s.level or 0, s.score or 0.0, s.id))
    level = best.level or 0
    return TestBestResult(
        level=level,  # type: ignore[arg-type]
        level_title=QUIZ_LEVEL_TITLES[level],
        score=best.score or 0.0,
        submitted_at=best.submitted_at,  # type: ignore[arg-type]
    )


def _session_view(session: QuizSession, test: TestDef, settings: Settings) -> TestSession:
    return TestSession(
        session_id=session.id,
        skill=session.skill,
        title=test.title,
        started_at=session.started_at,
        expires_at=session.expires_at,
        questions=quiz.build_session(session.skill, session_seed(settings.JWT_SECRET, session.id)),
    )


@router.get(
    "/tests",
    response_model=list[TestInfo],
    summary="Экспресс-тесты",
    description=(
        "Список экспресс-тестов (по 6 вопросов, 8 минут) с лучшим результатом соискателя, "
        "открытой сессией, если она есть, и временем, когда тест можно пройти снова. "
        "Экспресс-проверка из 6 вопросов — ориентир, а не аттестация."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
        }
    ),
)
def get_tests(
    candidate: CurrentCandidate, db: DbSession, settings: AppSettings
) -> list[TestInfo]:
    now = utcnow()
    by_skill: dict[str, list[QuizSession]] = defaultdict(list)
    for session in db.scalars(
        select(QuizSession).where(QuizSession.candidate_id == candidate.id).order_by(QuizSession.id)
    ):
        by_skill[session.skill].append(session)

    infos: list[TestInfo] = []
    for test in quiz.list_tests():
        sessions = by_skill.get(test.skill, [])
        active = _open_session(sessions, now)
        # An open session is returned by `start` regardless of the pause.
        available_at = None if active is not None else _cooldown_until(sessions, settings, now)
        infos.append(
            TestInfo(
                skill=test.skill,
                title=test.title,
                description=test.description,
                questions_per_session=test.questions_per_session,
                time_limit_seconds=test.time_limit_seconds,
                best_result=_best_result(sessions),
                active_session_id=active.id if active is not None else None,
                available_at=available_at,
            )
        )
    return infos


@router.post(
    "/tests/{skill}/start",
    response_model=TestSession,
    status_code=201,
    summary="Начать тест",
    description=(
        "Создаёт сессию теста по навыку (201): 6 вопросов от лёгких к сложным, 8 минут, "
        "лимит проверяется на сервере. Верные ответы не отдаются. Если по навыку уже есть "
        "открытая неистёкшая сессия, возвращается она же с теми же вопросами (200). Новую "
        "сессию можно начать не раньше чем через паузу после начала предыдущей."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
            404: "TEST_NOT_FOUND — нет теста по этому навыку",
            409: "TEST_COOLDOWN — действует пауза (`details.available_at`); "
            "CONFLICT — данные одновременно изменены другим запросом",
            422: "VALIDATION_ERROR — некорректный адрес запроса",
        }
    ),
)
def start_test(
    skill: str,
    response: Response,
    candidate: CurrentCandidate,
    db: DbSession,
    settings: AppSettings,
) -> TestSession:
    test = _find_test(skill)
    now = utcnow()
    sessions = list(
        db.scalars(
            select(QuizSession)
            .where(QuizSession.candidate_id == candidate.id, QuizSession.skill == skill)
            .order_by(QuizSession.id)
        )
    )

    open_session = _open_session(sessions, now)
    if open_session is not None:
        response.status_code = 200
        return _session_view(open_session, test, settings)

    available_at = _cooldown_until(sessions, settings, now)
    if available_at is not None:
        raise AppError(
            "TEST_COOLDOWN",
            "Повторно пройти этот тест можно позже",
            409,
            {"available_at": available_at},
        )

    session = QuizSession(
        candidate_id=candidate.id,
        skill=skill,
        started_at=now,
        expires_at=now + timedelta(seconds=test.time_limit_seconds),
    )
    db.add(session)
    commit_profile(db)
    return _session_view(session, test, settings)


@router.post(
    "/tests/sessions/{session_id}/submit",
    response_model=TestResult,
    summary="Сдать тест",
    description=(
        "Принимает ответы (`id вопроса → индекс варианта` в том порядке, в котором варианты "
        "пришли клиенту), проверяет их и возвращает результат. Неотвеченные вопросы считаются "
        "неверными. Уровень по сумме весов верных ответов: 12 — «Продвинутый», от 10 — "
        "«Уверенный», от 8 — «Базовый», иначе «Не сдан». Сданный тест добавляет навык "
        "«Подтверждено тестом» (существующий факт обновляется, только если уровень выше) и "
        "пересчитывает категорию. После истечения времени сессии результат не принимается."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
            404: "TEST_NOT_FOUND — сессии нет или она чужая",
            409: "TEST_ALREADY_SUBMITTED — сессия уже сдана; "
            "TEST_SESSION_EXPIRED — время сессии вышло (`details.available_at` — когда можно "
            "начать тест снова; `null`, если пауза уже не действует); "
            "CONFLICT — профиль одновременно изменён другим запросом",
            422: "VALIDATION_ERROR — в ответах есть вопрос, которого нет в сессии",
        }
    ),
)
def submit_test(
    session_id: int,
    body: TestSubmitRequest,
    candidate: CurrentCandidate,
    db: DbSession,
    settings: AppSettings,
) -> TestResult:
    session = db.get(QuizSession, session_id) if 0 < session_id <= MAX_INT else None
    if session is None or session.candidate_id != candidate.id:
        raise _test_not_found()
    if session.submitted_at is not None:
        raise AppError("TEST_ALREADY_SUBMITTED", "Эта сессия теста уже сдана", 409)
    now = utcnow()
    if now > as_utc(session.expires_at):
        # The pause counts from `started_at` of the latest session whatever its outcome (SPEC
        # 6.3), so a new `start` may be refused: tell when it will be possible instead of
        # promising a restart.
        same_skill = list(
            db.scalars(
                select(QuizSession).where(
                    QuizSession.candidate_id == candidate.id, QuizSession.skill == session.skill
                )
            )
        )
        raise AppError(
            "TEST_SESSION_EXPIRED",
            "Время на тест вышло, результат не засчитан",
            409,
            {"available_at": _cooldown_until(same_skill, settings, now)},
        )

    try:
        outcome = quiz.grade_session(
            session.skill, session_seed(settings.JWT_SECRET, session.id), body.answers
        )
    except quiz.UnknownTestError as exc:
        raise _test_not_found() from exc
    except ValueError as exc:
        raise field_validation_error(
            [(["body", "answers"], "Среди ответов есть вопрос, которого нет в этой сессии")]
        ) from exc

    # Close the session with a conditional UPDATE: of two parallel submits only one wins.
    closed = cast(
        CursorResult,
        db.execute(
            update(QuizSession)
            .where(QuizSession.id == session.id, QuizSession.submitted_at.is_(None))
            .values(
                submitted_at=now,
                score=outcome.score,
                level=outcome.level,
                answers=dict(body.answers),
            )
            .execution_options(synchronize_session=False)
        ),
    )
    if closed.rowcount == 0:
        raise AppError("TEST_ALREADY_SUBMITTED", "Эта сессия теста уже сдана", 409)

    # A failed test creates no fact; a retake that is not better leaves the old fact alone.
    if outcome.fact is not None:
        if upsert_fact(db, candidate, outcome.fact, keep_higher_level=True):
            recompute_candidate(db, candidate)
    commit_profile(db)

    return TestResult(
        session_id=session.id,
        skill=session.skill,
        score=outcome.score,
        level=outcome.level,
        passed=outcome.passed,
        correct=outcome.correct,
        total=outcome.total,
        level_title=outcome.level_title,
        profile=build_profile(db, candidate),
    )
