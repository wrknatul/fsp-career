from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.routes import employer_offers as offers_routes
from app.models import Offer, Vacancy

from .test_employer_kit import (
    API,
    add_offer,
    add_vacancy,
    build_candidate,
    set_offer_status,
    skills,
)

URL = f"{API}/employer/offers"
SEARCH_URL = f"{API}/employer/search"
VACANCIES_URL = f"{API}/employer/vacancies"


@pytest.fixture()
def candidate(make_candidate):
    return build_candidate(
        make_candidate,
        skills("python", "fastapi", "postgresql", "docker"),
        full_name="Смирнов Алексей Игоревич",
        city="Казань",
        work_formats=["remote"],
    )


@pytest.fixture()
def vacancy(db, employer_user):
    return add_vacancy(db, employer_user.employer, title="Python-разработчик")


def send(client, headers, candidate_id: int, vacancy_id: int, **extra: Any):
    body = {"candidate_id": candidate_id, "vacancy_id": vacancy_id, "salary": 150_000, **extra}
    return client.post(URL, json=body, headers=headers)


def offers_in_db(db) -> int:
    return db.scalar(select(func.count()).select_from(Offer))


# --- create --------------------------------------------------------------------------------------


def test_create_offer(client, db, employer_user, employer_headers, candidate, vacancy):
    response = send(
        client, employer_headers, candidate.id, vacancy.id, message="Приглашаем в команду"
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {
        "id",
        "status",
        "salary",
        "message",
        "created_at",
        "responded_at",
        "candidate_comment",
        "vacancy",
        "candidate",
        "contacts",
    }
    assert body["status"] == "sent"
    assert body["salary"] == 150_000
    assert body["message"] == "Приглашаем в команду"
    assert body["responded_at"] is None
    assert body["candidate_comment"] is None
    assert body["contacts"] is None
    assert body["vacancy"] == {"id": vacancy.id, "title": "Python-разработчик"}
    assert body["candidate"]["id"] == candidate.id
    assert body["candidate"]["display_name"] == "Алексей С."

    row = db.get(Offer, body["id"])
    assert row.employer_id == employer_user.employer.id
    assert row.candidate_id == candidate.id
    assert row.vacancy_id == vacancy.id
    assert row.salary == 150_000
    assert row.status == "sent"
    assert row.responded_at is None


def test_create_offer_without_a_message(client, employer_headers, candidate, vacancy):
    response = send(client, employer_headers, candidate.id, vacancy.id)

    assert response.status_code == 201
    assert response.json()["message"] is None


def test_the_message_may_be_a_thousand_characters_long(
    client, employer_headers, candidate, vacancy
):
    response = send(client, employer_headers, candidate.id, vacancy.id, message="я" * 1000)

    assert response.status_code == 201
    assert len(response.json()["message"]) == 1000


def test_the_message_may_not_be_longer(
    client, db, employer_headers, candidate, vacancy, assert_error
):
    response = send(client, employer_headers, candidate.id, vacancy.id, message="я" * 1001)

    assert_error(response, 422, "VALIDATION_ERROR")
    assert offers_in_db(db) == 0


def test_offer_shows_up_in_the_vacancy_counter(client, employer_headers, candidate, vacancy):
    send(client, employer_headers, candidate.id, vacancy.id)

    vacancies = client.get(VACANCIES_URL, headers=employer_headers).json()

    assert [(v["id"], v["offers_count"]) for v in vacancies] == [(vacancy.id, 1)]


def test_offer_shows_up_in_the_search(client, employer_headers, candidate, vacancy):
    send(client, employer_headers, candidate.id, vacancy.id)

    items = client.post(SEARCH_URL, json={}, headers=employer_headers).json()["items"]

    assert [(i["candidate"]["id"], i["offer_status"]) for i in items] == [(candidate.id, "sent")]


# --- duplicates ----------------------------------------------------------------------------------


def test_a_second_offer_for_the_same_pair_is_refused(
    client, db, employer_headers, candidate, vacancy, assert_error
):
    first = send(client, employer_headers, candidate.id, vacancy.id)
    second = send(client, employer_headers, candidate.id, vacancy.id, salary=200_000)

    assert first.status_code == 201
    assert_error(second, 409, "OFFER_ALREADY_SENT")
    assert offers_in_db(db) == 1
    assert db.scalar(select(Offer.salary)) == 150_000


@pytest.mark.parametrize("status", ["accepted", "declined"])
def test_a_answered_offer_still_blocks_a_repeat(
    client, db, employer_user, employer_headers, candidate, vacancy, assert_error, status
):
    add_offer(db, employer_user.employer, candidate, vacancy, status=status)

    response = send(client, employer_headers, candidate.id, vacancy.id)

    assert_error(response, 409, "OFFER_ALREADY_SENT")


def test_the_same_candidate_may_get_offers_for_different_vacancies(
    client, db, employer_user, employer_headers, candidate, vacancy
):
    other = add_vacancy(db, employer_user.employer, title="Вторая вакансия")

    first = send(client, employer_headers, candidate.id, vacancy.id)
    second = send(client, employer_headers, candidate.id, other.id)

    assert (first.status_code, second.status_code) == (201, 201)


def test_the_same_vacancy_may_get_offers_to_different_candidates(
    client, employer_headers, candidate, vacancy, make_candidate
):
    another = build_candidate(make_candidate, skills("python", "fastapi", "postgresql"))

    first = send(client, employer_headers, candidate.id, vacancy.id)
    second = send(client, employer_headers, another.id, vacancy.id)

    assert (first.status_code, second.status_code) == (201, 201)


def test_a_lost_race_for_the_same_pair_is_a_conflict_not_a_500(
    client, db, employer_user, employer_headers, candidate, vacancy, assert_error, monkeypatch
):
    """The pre-check passes, then the unique constraint of the database says no."""
    add_offer(db, employer_user.employer, candidate, vacancy)
    real_check = offers_routes._offer_exists
    calls: list[int] = []

    def check_that_misses_the_first_time(session: Session, vacancy_id: int, candidate_id: int):
        calls.append(1)
        return False if len(calls) == 1 else real_check(session, vacancy_id, candidate_id)

    monkeypatch.setattr(offers_routes, "_offer_exists", check_that_misses_the_first_time)

    response = send(client, employer_headers, candidate.id, vacancy.id, salary=190_000)

    assert_error(response, 409, "OFFER_ALREADY_SENT")
    assert len(calls) == 2
    assert offers_in_db(db) == 1
    assert db.scalar(select(Offer.salary)) == 150_000


def test_the_session_is_usable_after_a_lost_race(
    client, db, employer_user, employer_headers, candidate, vacancy, monkeypatch
):
    add_offer(db, employer_user.employer, candidate, vacancy)
    real_check = offers_routes._offer_exists
    calls: list[int] = []

    def check_that_misses_the_first_time(session: Session, vacancy_id: int, candidate_id: int):
        calls.append(1)
        return False if len(calls) == 1 else real_check(session, vacancy_id, candidate_id)

    monkeypatch.setattr(offers_routes, "_offer_exists", check_that_misses_the_first_time)
    send(client, employer_headers, candidate.id, vacancy.id)
    monkeypatch.setattr(offers_routes, "_offer_exists", real_check)

    assert client.get(URL, headers=employer_headers).status_code == 200


def test_any_other_integrity_error_is_still_not_a_500(
    client, employer_headers, candidate, vacancy, assert_error, monkeypatch
):
    def failing_commit(self: Session) -> None:
        raise IntegrityError("INSERT INTO offers", {}, Exception("some other constraint"))

    monkeypatch.setattr(Session, "commit", failing_commit)

    response = send(client, employer_headers, candidate.id, vacancy.id)

    assert_error(response, 409, "CONFLICT")


# --- vacancy checks ------------------------------------------------------------------------------


def test_a_foreign_vacancy_is_not_found(
    client, db, employer_headers, candidate, make_employer, assert_error
):
    foreign = add_vacancy(db, make_employer(email="other.company@example.test"))

    response = send(client, employer_headers, candidate.id, foreign.id)

    assert_error(response, 404, "NOT_FOUND")
    assert offers_in_db(db) == 0


def test_a_missing_vacancy_is_not_found(client, db, employer_headers, candidate, assert_error):
    response = send(client, employer_headers, candidate.id, 987_654)

    assert_error(response, 404, "NOT_FOUND")
    assert offers_in_db(db) == 0


def test_foreign_and_missing_vacancies_look_the_same(
    client, db, employer_headers, candidate, make_employer, assert_error
):
    foreign = add_vacancy(db, make_employer(email="other.company@example.test"))

    one = assert_error(send(client, employer_headers, candidate.id, foreign.id), 404, "NOT_FOUND")
    two = assert_error(send(client, employer_headers, candidate.id, 987_654), 404, "NOT_FOUND")

    assert (one["message"], one["details"]) == (two["message"], two["details"])


def test_an_inactive_vacancy_takes_no_offers(
    client, db, employer_user, employer_headers, candidate, assert_error
):
    closed = add_vacancy(db, employer_user.employer, is_active=False)

    response = send(client, employer_headers, candidate.id, closed.id)

    assert_error(response, 409, "VACANCY_INACTIVE")
    assert offers_in_db(db) == 0


def test_a_closed_vacancy_can_be_reopened_and_then_takes_offers(
    client, db, employer_user, employer_headers, candidate
):
    closed = add_vacancy(db, employer_user.employer, is_active=False)
    client.patch(f"{VACANCIES_URL}/{closed.id}", json={"is_active": True}, headers=employer_headers)

    assert send(client, employer_headers, candidate.id, closed.id).status_code == 201


# --- candidate checks ----------------------------------------------------------------------------


def test_a_hidden_candidate_is_not_found(
    client, db, employer_headers, vacancy, make_candidate, assert_error
):
    hidden = build_candidate(
        make_candidate, skills("python", "fastapi", "postgresql"), visible=False
    )

    response = send(client, employer_headers, hidden.id, vacancy.id)

    assert_error(response, 404, "NOT_FOUND")
    assert offers_in_db(db) == 0


def test_a_missing_candidate_is_not_found(client, db, employer_headers, vacancy, assert_error):
    response = send(client, employer_headers, 987_654, vacancy.id)

    assert_error(response, 404, "NOT_FOUND")
    assert offers_in_db(db) == 0


def test_hidden_and_missing_candidates_look_the_same(
    client, employer_headers, vacancy, make_candidate, assert_error
):
    hidden = build_candidate(
        make_candidate, skills("python", "fastapi", "postgresql"), visible=False
    )

    one = assert_error(send(client, employer_headers, hidden.id, vacancy.id), 404, "NOT_FOUND")
    two = assert_error(send(client, employer_headers, 987_654, vacancy.id), 404, "NOT_FOUND")

    assert (one["message"], one["details"]) == (two["message"], two["details"])


def test_a_candidate_who_hid_the_profile_cannot_get_an_offer(
    client, db, employer_headers, candidate, vacancy, assert_error
):
    candidate.visible = False
    db.commit()

    assert_error(send(client, employer_headers, candidate.id, vacancy.id), 404, "NOT_FOUND")


# --- order of the checks -------------------------------------------------------------------------


def test_the_vacancy_is_checked_before_the_candidate(
    client, db, employer_headers, make_employer, make_candidate, assert_error
):
    foreign = add_vacancy(db, make_employer(email="other.company@example.test"))
    hidden = build_candidate(make_candidate, skills("python"), visible=False)

    body = assert_error(send(client, employer_headers, hidden.id, foreign.id), 404, "NOT_FOUND")

    assert "Вакансия" in body["message"]


def test_the_candidate_is_checked_before_the_vacancy_state(
    client, db, employer_user, employer_headers, make_candidate, assert_error
):
    closed = add_vacancy(db, employer_user.employer, is_active=False)
    hidden = build_candidate(make_candidate, skills("python"), visible=False)

    assert_error(send(client, employer_headers, hidden.id, closed.id), 404, "NOT_FOUND")


def test_the_vacancy_state_is_checked_before_duplicates(
    client, db, employer_user, employer_headers, candidate, assert_error
):
    closed = add_vacancy(db, employer_user.employer, is_active=False)
    add_offer(db, employer_user.employer, candidate, closed)

    assert_error(send(client, employer_headers, candidate.id, closed.id), 409, "VACANCY_INACTIVE")


# --- body ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("salary", [0, -1, -150_000, 100_000_001, "много", None, 1.5])
def test_the_salary_must_be_a_positive_amount(
    client, db, employer_headers, candidate, vacancy, assert_error, salary
):
    response = send(client, employer_headers, candidate.id, vacancy.id, salary=salary)

    assert_error(response, 422, "VALIDATION_ERROR")
    assert offers_in_db(db) == 0


@pytest.mark.parametrize("missing", ["candidate_id", "vacancy_id", "salary"])
def test_required_fields(client, employer_headers, candidate, vacancy, assert_error, missing):
    body = {"candidate_id": candidate.id, "vacancy_id": vacancy.id, "salary": 100_000}
    del body[missing]

    response = client.post(URL, json=body, headers=employer_headers)

    result = assert_error(response, 422, "VALIDATION_ERROR")
    assert [item["field"] for item in result["details"]["errors"]] == [missing]


@pytest.mark.parametrize("field", ["candidate_id", "vacancy_id"])
@pytest.mark.parametrize("value", [0, -3, 2**40, "abc"])
def test_ids_must_be_valid_database_ids(
    client, employer_headers, candidate, vacancy, assert_error, field, value
):
    body = {"candidate_id": candidate.id, "vacancy_id": vacancy.id, "salary": 100_000, field: value}

    assert_error(client.post(URL, json=body, headers=employer_headers), 422, "VALIDATION_ERROR")


# --- the list ------------------------------------------------------------------------------------


def test_the_list_is_empty_at_first(client, employer_headers):
    response = client.get(URL, headers=employer_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_the_list_holds_own_offers_newest_first(
    client, db, employer_user, employer_headers, candidate, make_candidate
):
    mine = employer_user.employer
    vacancy = add_vacancy(db, mine, title="Первая")
    second_vacancy = add_vacancy(db, mine, title="Вторая")
    other_candidate = build_candidate(make_candidate, skills("python", "fastapi", "postgresql"))
    first = add_offer(db, mine, candidate, vacancy, salary=100_000)
    second = add_offer(db, mine, other_candidate, vacancy, salary=110_000)
    third = add_offer(db, mine, candidate, second_vacancy, salary=120_000)

    response = client.get(URL, headers=employer_headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [third.id, second.id, first.id]
    assert [item["salary"] for item in body] == [120_000, 110_000, 100_000]
    assert [item["vacancy"]["title"] for item in body] == ["Вторая", "Первая", "Первая"]
    assert [item["candidate"]["id"] for item in body] == [
        candidate.id,
        other_candidate.id,
        candidate.id,
    ]


def test_the_list_does_not_show_offers_of_other_employers(
    client, db, employer_user, employer_headers, candidate, make_employer
):
    other = make_employer(email="other.company@example.test")
    their_vacancy = add_vacancy(db, other)
    add_offer(db, other, candidate, their_vacancy)
    own = add_offer(db, employer_user.employer, candidate, add_vacancy(db, employer_user.employer))

    body = client.get(URL, headers=employer_headers).json()

    assert [item["id"] for item in body] == [own.id]


def test_the_list_gives_contacts_only_for_accepted_offers(
    client, db, employer_user, employer_headers, candidate, make_candidate
):
    mine = employer_user.employer
    vacancy = add_vacancy(db, mine)
    accepted_candidate = build_candidate(
        make_candidate,
        skills("python", "fastapi", "postgresql"),
        email="accepted.person@example.test",
        telegram="@accepted_person",
        phone="+7 900 111-22-33",
    )
    declined_candidate = build_candidate(
        make_candidate, skills("python", "fastapi", "postgresql"), telegram="@declined_person"
    )
    add_offer(db, mine, candidate, vacancy, status="sent")
    add_offer(db, mine, accepted_candidate, vacancy, status="accepted")
    add_offer(db, mine, declined_candidate, vacancy, status="declined")

    body = client.get(URL, headers=employer_headers).json()

    by_status = {item["status"]: item for item in body}
    assert by_status["sent"]["contacts"] is None
    assert by_status["declined"]["contacts"] is None
    assert by_status["accepted"]["contacts"] == {
        "email": "accepted.person@example.test",
        "telegram": "@accepted_person",
        "phone": "+7 900 111-22-33",
    }


def test_the_list_shows_the_answer_of_the_candidate(
    client, db, employer_user, employer_headers, candidate, vacancy
):
    offer = add_offer(db, employer_user.employer, candidate, vacancy)
    set_offer_status(db, offer, "declined", "Спасибо, не сейчас")

    item = client.get(URL, headers=employer_headers).json()[0]

    assert item["status"] == "declined"
    assert item["candidate_comment"] == "Спасибо, не сейчас"


def test_created_offer_is_the_first_in_the_list(client, employer_headers, candidate, vacancy):
    created = send(client, employer_headers, candidate.id, vacancy.id).json()

    listed = client.get(URL, headers=employer_headers).json()

    assert listed == [created]


def test_deleting_a_vacancy_removes_its_offers_from_the_list(
    client, db, employer_user, employer_headers, candidate, vacancy
):
    add_offer(db, employer_user.employer, candidate, vacancy)
    db.delete(db.get(Vacancy, vacancy.id))
    db.commit()

    assert client.get(URL, headers=employer_headers).json() == []


# --- access --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "body"),
    [("get", None), ("post", {"candidate_id": 1, "vacancy_id": 1, "salary": 1000})],
)
def test_offer_routes_need_a_token(client, assert_error, method, body):
    assert_error(client.request(method, URL, json=body), 401, "UNAUTHORIZED")


@pytest.mark.parametrize(
    ("method", "body"),
    [("get", None), ("post", {"candidate_id": 1, "vacancy_id": 1, "salary": 1000})],
)
def test_offer_routes_are_closed_to_candidates(
    client, candidate_headers, assert_error, method, body
):
    response = client.request(method, URL, json=body, headers=candidate_headers)

    assert_error(response, 403, "FORBIDDEN")
