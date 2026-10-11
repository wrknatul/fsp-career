"""Express tests: choosing questions, shuffling options and grading (SPEC section 6.3).

The choice of questions and the order of options depend only on `seed`, and they are
computed from SHA-256 digests rather than from `random`, so a session started yesterday
is restored identically by tomorrow's build.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.domain.facts import skill_fact
from app.domain.ontology import read_json
from app.domain.scoring_config import (
    QUIZ_DIFFICULTIES,
    QUIZ_LEVEL_THRESHOLDS,
    QUIZ_LEVEL_TITLES,
    QUIZ_QUESTIONS_PER_LEVEL,
    QUIZ_SCORE_DECIMALS,
    QUIZ_TIME_LIMIT_SECONDS,
)
from app.domain.types import QuestionPublic, QuizOutcome, TestDef

_OPTIONS_PER_QUESTION = 4


class UnknownTestError(LookupError):
    """There is no express test for this skill (the API answers TEST_NOT_FOUND)."""


@dataclass(frozen=True)
class _Question:
    id: str
    difficulty: int
    text: str
    options: tuple[str, ...]
    correct: int


@dataclass(frozen=True)
class _Test:
    skill: str
    title: str
    description: str
    questions: tuple[_Question, ...]


def _parse_question(raw: dict[str, Any]) -> _Question:
    options = tuple(raw["options"])
    if len(options) != _OPTIONS_PER_QUESTION or not 0 <= raw["correct"] < len(options):
        raise ValueError(f"questions.json: malformed question {raw.get('id')!r}")
    return _Question(
        id=raw["id"],
        difficulty=raw["difficulty"],
        text=raw["text"],
        options=options,
        correct=raw["correct"],
    )


@lru_cache(maxsize=1)
def _load_tests() -> dict[str, _Test]:
    tests: dict[str, _Test] = {}
    for raw in read_json("questions.json")["tests"]:
        tests[raw["skill"]] = _Test(
            skill=raw["skill"],
            title=raw["title"],
            description=raw["description"],
            questions=tuple(_parse_question(q) for q in raw["questions"]),
        )
    return tests


def _get_test(skill: str) -> _Test:
    test = _load_tests().get(skill)
    if test is None:
        raise UnknownTestError(f"no express test for skill {skill!r}")
    return test


def _digest(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest()[:16], 16)


def has_test(skill: str) -> bool:
    return skill in _load_tests()


def list_tests() -> list[TestDef]:
    return [
        TestDef(
            skill=test.skill,
            title=test.title,
            description=test.description,
            questions_per_session=QUIZ_QUESTIONS_PER_LEVEL * len(QUIZ_DIFFICULTIES),
            time_limit_seconds=QUIZ_TIME_LIMIT_SECONDS,
        )
        for test in _load_tests().values()
    ]


def _assemble(skill: str, seed: int) -> list[tuple[_Question, list[int]]]:
    """The questions of a session with, for each, the order of its options.

    `order[i]` is the index in the bank of the option shown at position `i`.
    """
    test = _get_test(skill)
    session: list[tuple[_Question, list[int]]] = []
    for difficulty in QUIZ_DIFFICULTIES:
        pool = [q for q in test.questions if q.difficulty == difficulty]
        pool.sort(key=lambda q: _digest(seed, skill, q.id))
        for question in pool[:QUIZ_QUESTIONS_PER_LEVEL]:
            order = sorted(
                range(len(question.options)),
                key=lambda i, q=question: _digest(seed, skill, q.id, "option", i),
            )
            session.append((question, order))
    return session


def build_session(skill: str, seed: int) -> list[QuestionPublic]:
    """Questions for the client: easy to hard, options shuffled, no correct answer."""
    return [
        QuestionPublic(
            id=question.id,
            text=question.text,
            difficulty=question.difficulty,  # type: ignore[arg-type]
            options=[question.options[i] for i in order],
        )
        for question, order in _assemble(skill, seed)
    ]


def _level_for(weight: int) -> int:
    for minimum, level in QUIZ_LEVEL_THRESHOLDS:
        if weight >= minimum:
            return level
    return 0


def grade_session(skill: str, seed: int, answers: dict[str, int]) -> QuizOutcome:
    """Grade the answers of a session.

    `answers` maps a question id to the index of the chosen option in the order the client
    saw. An id that is not in the session raises ValueError; an unanswered question (or an
    index outside the options) counts as wrong.
    """
    session = _assemble(skill, seed)
    known = {question.id for question, _ in session}
    foreign = sorted(set(answers) - known)
    if foreign:
        raise ValueError(f"questions are not in this session: {', '.join(foreign)}")

    weight = 0
    correct_count = 0
    for question, order in session:
        chosen = answers.get(question.id)
        if isinstance(chosen, bool) or not isinstance(chosen, int):
            continue
        if 0 <= chosen < len(order) and order[chosen] == question.correct:
            weight += question.difficulty
            correct_count += 1

    max_weight = sum(question.difficulty for question, _ in session)
    level = _level_for(weight)
    score = round(weight / max_weight, QUIZ_SCORE_DECIMALS)
    level_title = QUIZ_LEVEL_TITLES[level]
    fact = None
    if level > 0:
        fact = skill_fact(
            skill,
            level,
            "test",
            evidence=f"Экспресс-тест: {correct_count} из {len(session)}, уровень «{level_title}»",
            score=score,
        )
    return QuizOutcome(
        score=score,
        weight=weight,
        level=level,  # type: ignore[arg-type]
        passed=level > 0,
        correct=correct_count,
        total=len(session),
        level_title=level_title,
        fact=fact,
    )
