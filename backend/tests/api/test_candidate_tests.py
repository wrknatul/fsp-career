"""Express tests: `GET /candidate/tests`, `start` and `submit` (SPEC section 6.3)."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.timeutil import utcnow
from app.domain import quiz
from app.models import ProfileFact, QuizSession

API = "/api/v1"
TESTS_URL = f"{API}/candidate/tests"

QUESTIONS_JSON = Path(__file__).resolve().parents[2] / "app" / "domain" / "data" / "questions.json"
BANK = {
    question["id"]: question
    for test in json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))["tests"]
    for question in test["questions"]
}


def answers_for(session: dict, wrong: tuple[int, ...] = ()) -> dict[str, int]:
    """Right answers for a session; one question per entry of `wrong` (by difficulty) is missed.

    The right option is found in the bank (`questions.json`), then located in the order the
    options were sent to the client.
    """
    pending = list(wrong)
    answers: dict[str, int] = {}
    for question in session["questions"]:
        bank = BANK[question["id"]]
        right = question["options"].index(bank["options"][bank["correct"]])
        if question["difficulty"] in pending:
            pending.remove(question["difficulty"])
            answers[question["id"]] = (right + 1) % len(question["options"])
        else:
            answers[question["id"]] = right
    return answers


def start(client, headers, skill: str = "python"):
    return client.post(f"{TESTS_URL}/{skill}/start", headers=headers)


def submit(client, headers, session_id, answers):
    return client.post(
        f"{TESTS_URL}/sessions/{session_id}/submit", json={"answers": answers}, headers=headers
    )


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def stored_test_facts(db, candidate_id: int, skill: str = "python") -> list[ProfileFact]:
    db.expire_all()
    return list(
        db.scalars(
            select(ProfileFact).where(
                ProfileFact.candidate_id == candidate_id,
                ProfileFact.source == "test",
                ProfileFact.key == skill,
            )
        )
    )



def move_session(
    db, session_id: int, *, started_minutes_ago: float, expires_in_seconds: float
) -> None:
    """Shift a session in time (a negative `expires_in_seconds` makes it expired)."""
    session = db.get(QuizSession, session_id)
    session.started_at = utcnow() - timedelta(minutes=started_minutes_ago)
    session.expires_at = utcnow() + timedelta(seconds=expires_in_seconds)
    db.commit()


@pytest.fixture()
def me(candidate_user, candidate_headers):
    return candidate_user.candidate, candidate_headers


@pytest.fixture()
def no_cooldown(api_app, settings):
    api_app.state.settings = settings.model_copy(update={"TEST_COOLDOWN_MINUTES": 0})


# --- the list --------------------------------------------------------------------------------


def test_list_of_tests_for_a_new_candidate(client, me):
    _, headers = me

    response = client.get(TESTS_URL, headers=headers)

    assert response.status_code == 200, response.text
    tests = response.json()
    assert [t["skill"] for t in tests] == [t.skill for t in quiz.list_tests()]
    assert {t["skill"] for t in tests} == {"python", "javascript", "sql", "algorithms"}
    for item in tests:
        assert item["title"]
        assert item["description"]
        assert item["questions_per_session"] == 6
        assert item["time_limit_seconds"] == 480
        assert item["best_result"] is None
        assert item["active_session_id"] is None
        assert item["available_at"] is None


def test_list_shows_the_open_session(client, me):
    _, headers = me
    session_id = start(client, headers, "sql").json()["session_id"]

    tests = {t["skill"]: t for t in client.get(TESTS_URL, headers=headers).json()}

    assert tests["sql"]["active_session_id"] == session_id
    assert tests["sql"]["available_at"] is None
    assert tests["python"]["active_session_id"] is None


# --- starting --------------------------------------------------------------------------------


def test_start_creates_a_session(client, db, me):
    candidate, headers = me

    response = start(client, headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"session_id", "skill", "title", "started_at", "expires_at", "questions"}
    assert body["skill"] == "python"
    assert body["title"]
    assert parse_time(body["expires_at"]) - parse_time(body["started_at"]) == timedelta(seconds=480)
    questions = body["questions"]
    assert len(questions) == 6
    assert [q["difficulty"] for q in questions] == [1, 1, 2, 2, 3, 3]
    assert len({q["id"] for q in questions}) == 6
    for question in questions:
        assert set(question) == {"id", "text", "difficulty", "options"}
        assert len(question["options"]) == 4
        assert len(set(question["options"])) == 4
    db.expire_all()
    row = db.get(QuizSession, body["session_id"])
    assert row.candidate_id == candidate.id
    assert row.skill == "python"
    assert row.submitted_at is None
    assert row.score is None
    assert row.level is None


def test_the_answer_key_is_never_sent(client, me):
    _, headers = me

    response = start(client, headers)

    assert '"correct"' not in response.text
    for question in response.json()["questions"]:
        assert set(question) == {"id", "text", "difficulty", "options"}
    # The list view and the open-session view do not carry a key either.
    assert '"correct"' not in start(client, headers).text
    assert '"correct"' not in client.get(TESTS_URL, headers=headers).text


def test_starting_again_returns_the_same_session(client, db, me):
    _, headers = me
    first = start(client, headers)

    second = start(client, headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    assert db.scalar(select(func.count()).select_from(QuizSession)) == 1


def test_questions_follow_the_documented_seed(client, settings, me):
    _, headers = me

    body = start(client, headers, "algorithms").json()

    digest = hmac.new(
        settings.JWT_SECRET.encode(), str(body["session_id"]).encode(), hashlib.sha256
    ).hexdigest()
    seed = int(digest[:12], 16)
    expected = [question.model_dump() for question in quiz.build_session("algorithms", seed)]
    assert body["questions"] == expected


def test_sessions_get_different_questions_or_order(client, no_cooldown, me):
    _, headers = me
    first = start(client, headers).json()
    submit(client, headers, first["session_id"], {})

    second = start(client, headers).json()

    assert second["session_id"] != first["session_id"]
    assert [q["options"] for q in second["questions"]] != [q["options"] for q in first["questions"]]


def test_unknown_skill(client, me, assert_error):
    _, headers = me

    assert_error(start(client, headers, "cobol"), 404, "TEST_NOT_FOUND")
    assert_error(start(client, headers, "PYTHON"), 404, "TEST_NOT_FOUND")


def test_tests_are_for_candidates(client, employer_headers, assert_error):
    assert_error(client.get(TESTS_URL, headers=employer_headers), 403, "FORBIDDEN")
    assert_error(start(client, employer_headers), 403, "FORBIDDEN")
    assert_error(submit(client, employer_headers, 1, {}), 403, "FORBIDDEN")


def test_tests_need_a_token(client):
    assert client.get(TESTS_URL).status_code == 401
    assert client.post(f"{TESTS_URL}/python/start").status_code == 401
    assert client.post(f"{TESTS_URL}/sessions/1/submit", json={"answers": {}}).status_code == 401


# --- submitting: every level -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("skill", "wrong", "weight", "level", "level_title"),
    [
        ("python", (), 12, 3, "Продвинутый"),
        ("javascript", (1,), 11, 2, "Уверенный"),
        ("sql", (1, 1), 10, 2, "Уверенный"),
        ("algorithms", (3,), 9, 1, "Базовый"),
        ("python", (2, 2), 8, 1, "Базовый"),
        ("javascript", (3, 2), 7, 0, "Не сдан"),
        ("sql", (1, 1, 2, 2, 3, 3), 0, 0, "Не сдан"),
    ],
)
def test_every_level(client, db, me, skill, wrong, weight, level, level_title):
    candidate, headers = me
    session = start(client, headers, skill).json()

    response = submit(client, headers, session["session_id"], answers_for(session, wrong))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == session["session_id"]
    assert body["skill"] == skill
    assert body["level"] == level
    assert body["level_title"] == level_title
    assert body["passed"] is (level > 0)
    assert body["total"] == 6
    assert body["correct"] == 6 - len(wrong)
    assert body["score"] == pytest.approx(weight / 12, abs=1e-4)

    db.expire_all()
    row = db.get(QuizSession, session["session_id"])
    assert row.submitted_at is not None
    assert row.level == level
    assert row.score == pytest.approx(weight / 12, abs=1e-4)
    assert row.answers == answers_for(session, wrong)

    facts = stored_test_facts(db, candidate.id, skill)
    profile_facts = [f for f in body["profile"]["facts"] if f["source"] == "test"]
    if level == 0:
        assert facts == []
        assert profile_facts == []
        assert body["profile"]["category"]["confidence_index"] == 0
    else:
        assert len(facts) == 1
        fact = facts[0]
        assert (fact.kind, fact.verification) == ("skill", "tested")
        assert fact.value["level"] == level
        assert fact.value["score"] == pytest.approx(weight / 12, abs=1e-4)
        assert [(f["key"], f["verification"]) for f in profile_facts] == [(skill, "tested")]
        assert profile_facts[0]["value"]["level"] == level
        assert body["profile"]["category"]["confidence_index"] == 25
        assert body["profile"]["category"]["grade_confirmed"] is True


def test_a_passed_python_test_shapes_the_category(client, db, me):
    candidate, headers = me
    session = start(client, headers).json()

    body = submit(client, headers, session["session_id"], answers_for(session)).json()

    category = body["profile"]["category"]
    assert category["stack"] == "backend"
    assert category["stack_confirmed"] is True
    assert category["top_skills"][0]["skill"] == "python"
    assert category["top_skills"][0]["verification"] == "tested"
    db.expire_all()
    assert candidate.category == category
    assert len(candidate.embedding) == 384


def test_unanswered_questions_are_wrong(client, me):
    _, headers = me
    session = start(client, headers).json()
    full = answers_for(session)
    partial = dict(list(full.items())[:4])  # the first four are 1, 1, 2, 2: weight 6

    body = submit(client, headers, session["session_id"], partial).json()

    assert body["correct"] == 4
    assert body["score"] == pytest.approx(0.5)
    assert body["level"] == 0


def test_an_out_of_range_option_counts_as_wrong(client, me):
    _, headers = me
    session = start(client, headers).json()
    answers = answers_for(session)
    first = session["questions"][0]["id"]
    answers[first] = 9

    body = submit(client, headers, session["session_id"], answers).json()

    assert body["correct"] == 5
    assert body["level"] == 2


@pytest.mark.parametrize("answers", [{"python-01": -1}, {"python-01": 21}, {"python-01": "a"}])
def test_bad_answer_values(client, me, assert_error, answers):
    _, headers = me
    session = start(client, headers).json()

    assert_error(submit(client, headers, session["session_id"], answers), 422, "VALIDATION_ERROR")


def test_the_body_must_have_answers(client, me, assert_error):
    _, headers = me
    session_id = start(client, headers).json()["session_id"]

    response = client.post(f"{TESTS_URL}/sessions/{session_id}/submit", json={}, headers=headers)

    assert_error(response, 422, "VALIDATION_ERROR")


# --- submitting: refusals --------------------------------------------------------------------


def test_foreign_question_is_a_validation_error_and_the_session_stays_open(
    client, db, me, assert_error
):
    candidate, headers = me
    session = start(client, headers).json()
    answers = answers_for(session)

    for foreign in ("nope-01", "sql-01"):
        response = submit(client, headers, session["session_id"], {**answers, foreign: 0})
        body = assert_error(response, 422, "VALIDATION_ERROR")
        assert body["details"]["errors"][0]["field"] == "answers"

    db.expire_all()
    assert db.get(QuizSession, session["session_id"]).submitted_at is None
    assert stored_test_facts(db, candidate.id) == []
    assert submit(client, headers, session["session_id"], answers).status_code == 200


def test_expired_session(client, db, me, assert_error):
    candidate, headers = me
    session = start(client, headers).json()
    move_session(db, session["session_id"], started_minutes_ago=9, expires_in_seconds=-1)

    response = submit(client, headers, session["session_id"], answers_for(session))

    assert_error(response, 409, "TEST_SESSION_EXPIRED")
    db.expire_all()
    assert db.get(QuizSession, session["session_id"]).submitted_at is None
    assert stored_test_facts(db, candidate.id) == []


def test_expired_session_does_not_promise_a_restart_and_says_when_it_is_possible(
    client, db, me, assert_error
):
    _, headers = me
    session = start(client, headers).json()
    move_session(db, session["session_id"], started_minutes_ago=9, expires_in_seconds=-1)

    body = assert_error(
        submit(client, headers, session["session_id"], answers_for(session)),
        409,
        "TEST_SESSION_EXPIRED",
    )

    assert "заново" not in body["message"]
    # The same moment `start` reports: the pause (SPEC 6.3) counts from the started session.
    refused = assert_error(start(client, headers), 409, "TEST_COOLDOWN")
    assert body["details"]["available_at"] == refused["details"]["available_at"]
    assert parse_time(body["details"]["available_at"]) > utcnow()


def test_expired_session_without_a_pause_has_a_null_available_at(
    client, db, no_cooldown, me, assert_error
):
    _, headers = me
    session = start(client, headers).json()
    move_session(db, session["session_id"], started_minutes_ago=9, expires_in_seconds=-1)

    body = assert_error(
        submit(client, headers, session["session_id"], answers_for(session)),
        409,
        "TEST_SESSION_EXPIRED",
    )

    assert body["details"] == {"available_at": None}
    assert start(client, headers).status_code == 201


def test_a_session_just_inside_its_time_is_accepted(client, db, me):
    _, headers = me
    session = start(client, headers).json()
    move_session(db, session["session_id"], started_minutes_ago=7, expires_in_seconds=30)

    assert submit(client, headers, session["session_id"], answers_for(session)).status_code == 200


def test_submitting_twice(client, db, me, assert_error):
    candidate, headers = me
    session = start(client, headers).json()
    assert submit(client, headers, session["session_id"], answers_for(session)).status_code == 200
    first_fact = stored_test_facts(db, candidate.id)[0].value

    response = submit(client, headers, session["session_id"], answers_for(session, (1, 1, 2, 2)))

    assert_error(response, 409, "TEST_ALREADY_SUBMITTED")
    assert stored_test_facts(db, candidate.id)[0].value == first_fact
    db.expire_all()
    assert db.get(QuizSession, session["session_id"]).level == 3


def test_submitting_an_expired_and_submitted_session_says_already_submitted(
    client, db, me, assert_error
):
    _, headers = me
    session = start(client, headers).json()
    submit(client, headers, session["session_id"], {})
    move_session(db, session["session_id"], started_minutes_ago=30, expires_in_seconds=-1200)

    response = submit(client, headers, session["session_id"], {})

    assert_error(response, 409, "TEST_ALREADY_SUBMITTED")


def test_somebody_elses_session(client, make_candidate, headers_for, db, me, assert_error):
    owner, owner_headers = me
    session = start(client, owner_headers).json()
    other = make_candidate(email="other@example.test")

    response = submit(client, headers_for(other.user), session["session_id"], answers_for(session))

    assert_error(response, 404, "TEST_NOT_FOUND")
    db.expire_all()
    assert db.get(QuizSession, session["session_id"]).submitted_at is None
    assert stored_test_facts(db, other.id) == []


@pytest.mark.parametrize("session_id", [0, 999, 10**12])
def test_no_such_session(client, me, assert_error, session_id):
    _, headers = me

    assert_error(submit(client, headers, session_id, {}), 404, "TEST_NOT_FOUND")


# --- the pause between attempts --------------------------------------------------------------


def test_pause_after_a_submitted_test(client, db, me, assert_error):
    _, headers = me
    session = start(client, headers).json()
    submit(client, headers, session["session_id"], answers_for(session))

    response = start(client, headers)

    body = assert_error(response, 409, "TEST_COOLDOWN")
    available_at = parse_time(body["details"]["available_at"])
    started_at = parse_time(session["started_at"])
    assert available_at - started_at == timedelta(minutes=1440)
    listed = {t["skill"]: t for t in client.get(TESTS_URL, headers=headers).json()}["python"]
    assert parse_time(listed["available_at"]) == available_at
    assert listed["active_session_id"] is None
    assert db.scalar(select(func.count()).select_from(QuizSession)) == 1


def test_pause_after_a_failed_test_too(client, me, assert_error):
    _, headers = me
    session = start(client, headers).json()
    submit(client, headers, session["session_id"], {})

    assert_error(start(client, headers), 409, "TEST_COOLDOWN")


def test_pause_after_an_expired_session(client, db, me, assert_error):
    _, headers = me
    session = start(client, headers).json()
    move_session(db, session["session_id"], started_minutes_ago=9, expires_in_seconds=-60)

    assert_error(start(client, headers), 409, "TEST_COOLDOWN")


def test_pause_is_per_skill_and_per_candidate(client, make_candidate, headers_for, me):
    _, headers = me
    session = start(client, headers, "python").json()
    submit(client, headers, session["session_id"], {})
    other = make_candidate(email="other@example.test")

    assert start(client, headers, "sql").status_code == 201
    assert start(client, headers_for(other.user), "python").status_code == 201


def test_pause_ends_after_the_configured_time(client, db, me, assert_error):
    _, headers = me
    session = start(client, headers).json()
    submit(client, headers, session["session_id"], {})

    move_session(db, session["session_id"], started_minutes_ago=1439, expires_in_seconds=-60)
    assert_error(start(client, headers), 409, "TEST_COOLDOWN")

    move_session(db, session["session_id"], started_minutes_ago=1441, expires_in_seconds=-60)
    response = start(client, headers)
    assert response.status_code == 201
    assert response.json()["session_id"] != session["session_id"]


def test_pause_comes_from_the_settings(client, api_app, settings, me):
    _, headers = me
    api_app.state.settings = settings.model_copy(update={"TEST_COOLDOWN_MINUTES": 10})
    session = start(client, headers).json()
    submit(client, headers, session["session_id"], {})

    body = start(client, headers)

    assert body.status_code == 409
    available_at = parse_time(body.json()["details"]["available_at"])
    assert available_at - parse_time(session["started_at"]) == timedelta(minutes=10)


def test_an_expired_session_is_not_returned_as_open(client, db, no_cooldown, me):
    _, headers = me
    session = start(client, headers).json()
    move_session(db, session["session_id"], started_minutes_ago=9, expires_in_seconds=-60)

    listed = {t["skill"]: t for t in client.get(TESTS_URL, headers=headers).json()}["python"]
    fresh = start(client, headers)

    assert listed["active_session_id"] is None
    assert fresh.status_code == 201
    assert fresh.json()["session_id"] != session["session_id"]


# --- retakes ---------------------------------------------------------------------------------


def test_a_worse_retake_does_not_lower_the_fact(client, db, no_cooldown, me):
    candidate, headers = me
    first = start(client, headers).json()
    submit(client, headers, first["session_id"], answers_for(first))
    fact_id = stored_test_facts(db, candidate.id)[0].id

    second = start(client, headers).json()
    body = submit(client, headers, second["session_id"], answers_for(second, (2, 2))).json()

    assert body["level"] == 1
    assert body["passed"] is True
    facts = stored_test_facts(db, candidate.id)
    assert [(f.id, f.value["level"]) for f in facts] == [(fact_id, 3)]
    assert [f["value"]["level"] for f in body["profile"]["facts"] if f["source"] == "test"] == [3]
    listed = {t["skill"]: t for t in client.get(TESTS_URL, headers=headers).json()}["python"]
    assert listed["best_result"]["level"] == 3
    assert listed["best_result"]["level_title"] == "Продвинутый"
    assert listed["best_result"]["score"] == 1.0


def test_a_failed_retake_leaves_the_fact_alone(client, db, no_cooldown, me):
    candidate, headers = me
    first = start(client, headers).json()
    submit(client, headers, first["session_id"], answers_for(first, (2, 2)))
    second = start(client, headers).json()

    body = submit(client, headers, second["session_id"], {}).json()

    assert body["level"] == 0
    assert [f.value["level"] for f in stored_test_facts(db, candidate.id)] == [1]


def test_a_better_retake_raises_the_fact(client, db, no_cooldown, me):
    candidate, headers = me
    first = start(client, headers).json()
    submit(client, headers, first["session_id"], answers_for(first, (2, 2)))
    fact_id = stored_test_facts(db, candidate.id)[0].id
    second = start(client, headers).json()

    body = submit(client, headers, second["session_id"], answers_for(second)).json()

    assert body["level"] == 3
    facts = stored_test_facts(db, candidate.id)
    assert [(f.id, f.value["level"]) for f in facts] == [(fact_id, 3)]
    assert facts[0].value["score"] == 1.0
    listed = {t["skill"]: t for t in client.get(TESTS_URL, headers=headers).json()}["python"]
    assert listed["best_result"]["level"] == 3


def test_an_equal_retake_changes_nothing(client, db, no_cooldown, me):
    candidate, headers = me
    first = start(client, headers).json()
    submit(client, headers, first["session_id"], answers_for(first, (1,)))
    before = stored_test_facts(db, candidate.id)[0]
    before_state = (before.id, dict(before.value), before.created_at)
    second = start(client, headers).json()

    submit(client, headers, second["session_id"], answers_for(second, (1, 1)))

    after = stored_test_facts(db, candidate.id)[0]
    assert (after.id, dict(after.value), after.created_at) == before_state


def test_best_result_is_the_best_of_several(client, no_cooldown, me):
    _, headers = me
    for wrong in ((2, 2), (1,), (3, 3)):
        session = start(client, headers, "sql").json()
        submit(client, headers, session["session_id"], answers_for(session, wrong))

    listed = {t["skill"]: t for t in client.get(TESTS_URL, headers=headers).json()}["sql"]

    assert listed["best_result"]["level"] == 2
    assert listed["best_result"]["level_title"] == "Уверенный"
    assert listed["best_result"]["submitted_at"]


def test_two_passed_tests_raise_the_trust_in_the_experience(client, db, me):
    candidate, headers = me
    for skill in ("python", "sql"):
        session = start(client, headers, skill).json()
        body = submit(client, headers, session["session_id"], answers_for(session)).json()

    assert body["profile"]["category"]["confidence_index"] == 50
    tested = {f["key"] for f in body["profile"]["facts"] if f["source"] == "test"}
    assert tested == {"python", "sql"}
