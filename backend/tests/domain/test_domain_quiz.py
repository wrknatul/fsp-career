"""Express tests: integrity of the question bank, determinism and grading (SPEC section 6.3)."""

from __future__ import annotations

import re
from typing import Any

import pytest

from app.domain import quiz
from app.domain.ontology import is_known_skill, read_json
from app.domain.types import QuestionPublic

TEST_SKILLS = ["python", "javascript", "sql", "algorithms"]


def _bank() -> dict[str, dict[str, Any]]:
    return {t["skill"]: t for t in read_json("questions.json")["tests"]}


def _correct_text(skill: str, question_id: str) -> str:
    question = next(q for q in _bank()[skill]["questions"] if q["id"] == question_id)
    return question["options"][question["correct"]]


def _answers(
    skill: str, session: list[QuestionPublic], correct_difficulties: list[int]
) -> dict[str, int]:
    """Answers that are right for exactly the listed difficulties (one question each)."""
    remaining = list(correct_difficulties)
    answers: dict[str, int] = {}
    for question in session:
        right = _correct_text(skill, question.id)
        right_index = question.options.index(right)
        if question.difficulty in remaining:
            remaining.remove(question.difficulty)
            answers[question.id] = right_index
        else:
            answers[question.id] = (right_index + 1) % len(question.options)
    assert not remaining
    return answers


# --- bank integrity ------------------------------------------------------------------------------
def test_bank_has_four_tests_of_nine_questions() -> None:
    bank = _bank()
    assert sorted(bank) == sorted(TEST_SKILLS)
    for skill, test in bank.items():
        assert is_known_skill(skill)
        questions = test["questions"]
        assert len(questions) == 9, skill
        for difficulty in (1, 2, 3):
            assert sum(1 for q in questions if q["difficulty"] == difficulty) == 3, skill


def test_the_correct_option_is_not_given_away_by_its_length() -> None:
    """Questions with spelled-out options: the right one is never the single longest."""
    for skill, test in _bank().items():
        for question in test["questions"]:
            lengths = [len(option) for option in question["options"]]
            if max(lengths) <= 20:
                continue  # short options (numbers, names, O-notation): nothing to compare
            longest = max(lengths)
            correct_is_unique_longest = (
                lengths[question["correct"]] == longest and lengths.count(longest) == 1
            )
            assert not correct_is_unique_longest, (skill, question["id"], lengths)


def test_code_in_questions_uses_balanced_markdown_fences() -> None:
    """The page splits text on ``` blocks and `inline code`: an odd number of marks breaks it."""
    for test in _bank().values():
        for question in test["questions"]:
            for text in (question["text"], *question["options"]):
                assert text.count("```") % 2 == 0, question["id"]
                outside_blocks = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
                for line in outside_blocks.split("\n"):
                    assert line.count("`") % 2 == 0, (question["id"], line)


def test_every_question_is_well_formed() -> None:
    seen_ids: set[str] = set()
    for skill, test in _bank().items():
        for number, question in enumerate(test["questions"], start=1):
            assert question["id"] == f"{skill}-{number:02d}"
            assert question["id"] not in seen_ids
            seen_ids.add(question["id"])
            assert set(question) == {"id", "difficulty", "text", "options", "correct"}
            assert len(question["options"]) == 4
            assert len(set(question["options"])) == 4, question["id"]
            assert question["correct"] in range(4)
            assert question["text"].strip()
            assert all(option.strip() for option in question["options"])


def test_list_tests() -> None:
    tests = quiz.list_tests()
    assert [t.skill for t in tests] == TEST_SKILLS
    for test in tests:
        assert test.questions_per_session == 6
        assert test.time_limit_seconds == 480
        assert test.title
        assert test.description


# --- sessions ------------------------------------------------------------------------------------
@pytest.mark.parametrize("skill", TEST_SKILLS)
def test_session_has_two_questions_per_difficulty(skill: str) -> None:
    session = quiz.build_session(skill, seed=12345)
    assert len(session) == 6
    assert sorted(q.difficulty for q in session) == [1, 1, 2, 2, 3, 3]
    assert len({q.id for q in session}) == 6
    assert all(q.id.startswith(skill) for q in session)


def test_session_is_deterministic() -> None:
    assert quiz.build_session("python", 777) == quiz.build_session("python", 777)


def test_different_seeds_give_different_sets_and_orders() -> None:
    sessions = [quiz.build_session("python", seed) for seed in range(1, 31)]
    id_sets = {frozenset(q.id for q in s) for s in sessions}
    option_orders = {tuple(tuple(q.options) for q in s) for s in sessions}
    assert len(id_sets) > 1
    assert len(option_orders) > 20


def test_options_are_a_permutation_of_the_bank() -> None:
    bank = {q["id"]: q for q in _bank()["sql"]["questions"]}
    for question in quiz.build_session("sql", 99):
        assert sorted(question.options) == sorted(bank[question.id]["options"])


def test_public_question_does_not_reveal_the_answer() -> None:
    for question in quiz.build_session("javascript", 5):
        dumped = question.model_dump()
        assert set(dumped) == {"id", "text", "difficulty", "options"}
        assert "correct" not in dumped


def test_unknown_test_is_reported_explicitly() -> None:
    assert quiz.has_test("python")
    assert not quiz.has_test("cobol")
    with pytest.raises(quiz.UnknownTestError):
        quiz.build_session("cobol", 1)
    with pytest.raises(quiz.UnknownTestError):
        quiz.grade_session("cobol", 1, {})


# --- grading -------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("right", "weight", "level", "title"),
    [
        ([1, 1, 2, 3], 7, 0, "Не сдан"),
        ([1, 1, 3, 3], 8, 1, "Базовый"),
        ([1, 2, 3, 3], 9, 1, "Базовый"),
        ([2, 2, 3, 3], 10, 2, "Уверенный"),
        ([1, 2, 2, 3, 3], 11, 2, "Уверенный"),
        ([1, 1, 2, 2, 3, 3], 12, 3, "Продвинутый"),
    ],
)
def test_level_thresholds_on_the_boundaries(
    right: list[int], weight: int, level: int, title: str
) -> None:
    seed = 4242
    session = quiz.build_session("algorithms", seed)
    outcome = quiz.grade_session("algorithms", seed, _answers("algorithms", session, right))
    assert outcome.weight == weight
    assert outcome.level == level
    assert outcome.level_title == title
    assert outcome.passed is (level > 0)
    assert outcome.correct == len(right)
    assert outcome.total == 6
    assert outcome.score == pytest.approx(weight / 12, abs=1e-4)


def test_passed_test_returns_a_ready_fact() -> None:
    seed = 31
    session = quiz.build_session("python", seed)
    outcome = quiz.grade_session("python", seed, _answers("python", session, [1, 1, 2, 2, 3, 3]))
    fact = outcome.fact
    assert fact is not None
    assert (fact.kind, fact.key, fact.source, fact.verification) == (
        "skill",
        "python",
        "test",
        "tested",
    )
    assert fact.title == "Python"
    assert fact.value == {"level": 3, "score": 1.0}


def test_failed_test_has_no_fact() -> None:
    session = quiz.build_session("sql", 8)
    outcome = quiz.grade_session("sql", 8, _answers("sql", session, [1, 1]))
    assert outcome.level == 0
    assert outcome.fact is None


def test_unanswered_questions_count_as_wrong() -> None:
    outcome = quiz.grade_session("python", 3, {})
    assert (outcome.weight, outcome.correct, outcome.total, outcome.level) == (0, 0, 6, 0)
    assert outcome.fact is None


def test_partial_answers_are_graded() -> None:
    seed = 3
    session = quiz.build_session("python", seed)
    answers = _answers("python", session, [3, 3])
    partial = {q.id: answers[q.id] for q in session if q.difficulty == 3}
    outcome = quiz.grade_session("python", seed, partial)
    assert outcome.weight == 6
    assert outcome.correct == 2


def test_answer_for_a_foreign_question_raises() -> None:
    session = quiz.build_session("python", 11)
    in_session = {q.id for q in session}
    foreign = next(
        q["id"] for q in _bank()["python"]["questions"] if q["id"] not in in_session
    )
    with pytest.raises(ValueError):
        quiz.grade_session("python", 11, {foreign: 0})
    with pytest.raises(ValueError):
        quiz.grade_session("python", 11, {"sql-01": 0})


def test_out_of_range_choice_is_just_wrong() -> None:
    session = quiz.build_session("python", 11)
    outcome = quiz.grade_session("python", 11, {session[0].id: 9, session[1].id: -1})
    assert outcome.correct == 0


def test_grading_restores_the_same_shuffle_for_the_same_seed() -> None:
    # The client sees the options of seed 1000; grading with another seed gives other results.
    seed = 1000
    session = quiz.build_session("python", seed)
    answers = _answers("python", session, [1, 1, 2, 2, 3, 3])
    assert quiz.grade_session("python", seed, answers).level == 3
    other = [
        quiz.grade_session("python", s, answers).weight
        for s in range(1, 300)
        if s != seed and {q.id for q in quiz.build_session("python", s)} == {q.id for q in session}
    ]
    assert other  # some other seed picks the same questions
    assert any(weight < 12 for weight in other)  # but shuffles the options differently
