"""`GET /candidate/offers` and `POST /candidate/offers/{id}/respond`."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.timeutil import utcnow
from app.models import Offer, Vacancy

API = "/api/v1"
URL = f"{API}/candidate/offers"


@pytest.fixture()
def company(make_employer):
    return make_employer(
        email="hr@orbita.example.test",
        company_name="Орбита Софт",
        about="Разработка сервисов",
        website="https://orbita.example.test",
        contact_name="Мария Кузнецова",
        contact_email="hr@orbita.example.test",
        contact_telegram="@orbita_hr",
        verified=True,
    )


@pytest.fixture()
def make_offer(db):
    """``make_offer(employer, candidate, ...)`` -> an `Offer` row with its own vacancy."""

    def factory(
        employer,
        candidate,
        *,
        title: str = "Python-разработчик",
        salary: int = 180000,
        status: str = "sent",
        message: str | None = "Приглашаем в команду",
        created_ago: timedelta = timedelta(0),
    ) -> Offer:
        vacancy = Vacancy(
            employer_id=employer.id,
            title=title,
            description="Пишем сервисы на Python",
            stack="backend",
            grade="middle",
            team_role="developer",
            skills_required=["python"],
            skills_optional=["docker"],
            work_formats=["remote", "hybrid"],
            city="Казань",
            salary_from=150000,
            salary_to=220000,
            is_active=True,
        )
        db.add(vacancy)
        db.flush()
        offer = Offer(
            employer_id=employer.id,
            candidate_id=candidate.id,
            vacancy_id=vacancy.id,
            salary=salary,
            message=message,
            status=status,
            created_at=utcnow() - created_ago,
        )
        db.add(offer)
        db.commit()
        return offer

    return factory


@pytest.fixture()
def me(candidate_user, candidate_headers):
    return candidate_user.candidate, candidate_headers


def respond(client, headers, offer_id, decision="accept", **extra):
    return client.post(
        f"{URL}/{offer_id}/respond", json={"decision": decision, **extra}, headers=headers
    )


def reload(db, offer):
    db.expire_all()
    return db.get(Offer, offer.id)


# --- the inbox -------------------------------------------------------------------------------


def test_empty_inbox(client, me):
    _, headers = me

    response = client.get(URL, headers=headers)

    assert response.status_code == 200
    assert response.json() == []


def test_inbox_lists_offers_newest_first(client, me, company, make_offer):
    candidate, headers = me
    old = make_offer(company, candidate, title="Старая вакансия", created_ago=timedelta(days=3))
    new = make_offer(company, candidate, title="Новая вакансия", created_ago=timedelta(hours=1))
    middle = make_offer(company, candidate, title="Средняя вакансия", created_ago=timedelta(days=1))

    response = client.get(URL, headers=headers)

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [new.id, middle.id, old.id]


def test_offer_shape(client, me, company, make_offer):
    candidate, headers = me
    offer = make_offer(company, candidate)

    item = client.get(URL, headers=headers).json()[0]

    assert item["id"] == offer.id
    assert item["status"] == "sent"
    assert item["salary"] == 180000
    assert item["message"] == "Приглашаем в команду"
    assert item["created_at"]
    assert item["responded_at"] is None
    assert item["candidate_comment"] is None
    assert item["vacancy"] == {
        "id": offer.vacancy_id,
        "title": "Python-разработчик",
        "description": "Пишем сервисы на Python",
        "stack": "backend",
        "grade": "middle",
        "work_formats": ["remote", "hybrid"],
        "city": "Казань",
        "salary_from": 150000,
        "salary_to": 220000,
    }
    assert item["company"] == {
        "name": "Орбита Софт",
        "about": "Разработка сервисов",
        "website": "https://orbita.example.test",
        "verified": True,
    }
    assert item["employer_contacts"] is None


def test_unverified_company_is_marked(client, me, make_employer, make_offer):
    candidate, headers = me
    shady = make_employer(email="shady@example.test", company_name="Ромашка", verified=False)
    make_offer(shady, candidate)

    item = client.get(URL, headers=headers).json()[0]

    assert item["company"]["verified"] is False


def test_inbox_has_only_my_offers(client, me, company, make_offer, make_candidate):
    candidate, headers = me
    other = make_candidate(email="other@example.test")
    mine = make_offer(company, candidate)
    make_offer(company, other, title="Чужая вакансия")

    items = client.get(URL, headers=headers).json()

    assert [item["id"] for item in items] == [mine.id]


def test_contacts_are_hidden_until_accepted(client, me, company, make_offer):
    candidate, headers = me
    make_offer(company, candidate, status="sent", title="Ждёт ответа")
    make_offer(company, candidate, status="declined", title="Отклонён")
    make_offer(company, candidate, status="accepted", title="Принят")

    items = {item["vacancy"]["title"]: item for item in client.get(URL, headers=headers).json()}

    assert items["Ждёт ответа"]["employer_contacts"] is None
    assert items["Отклонён"]["employer_contacts"] is None
    assert items["Принят"]["employer_contacts"] == {
        "contact_name": "Мария Кузнецова",
        "contact_email": "hr@orbita.example.test",
        "contact_telegram": "@orbita_hr",
    }


# --- answering -------------------------------------------------------------------------------


def test_accept_opens_the_employers_contacts(client, db, me, company, make_offer):
    candidate, headers = me
    offer = make_offer(company, candidate)

    response = respond(client, headers, offer.id, "accept", comment="Спасибо, согласен")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == offer.id
    assert body["status"] == "accepted"
    assert body["responded_at"]
    assert body["candidate_comment"] == "Спасибо, согласен"
    assert body["employer_contacts"] == {
        "contact_name": "Мария Кузнецова",
        "contact_email": "hr@orbita.example.test",
        "contact_telegram": "@orbita_hr",
    }
    assert body["salary"] == 180000
    assert body["vacancy"]["title"] == "Python-разработчик"
    stored = reload(db, offer)
    assert stored.status == "accepted"
    assert stored.responded_at is not None
    assert stored.candidate_comment == "Спасибо, согласен"
    after = client.get(URL, headers=headers).json()[0]
    assert after["status"] == "accepted"
    assert after["employer_contacts"] == body["employer_contacts"]


def test_decline_keeps_the_contacts_closed(client, db, me, company, make_offer):
    candidate, headers = me
    offer = make_offer(company, candidate)

    response = respond(client, headers, offer.id, "decline", comment="Уже нашёл работу")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "declined"
    assert body["employer_contacts"] is None
    assert body["candidate_comment"] == "Уже нашёл работу"
    assert body["responded_at"]
    assert reload(db, offer).status == "declined"


def test_the_comment_is_optional(client, me, company, make_offer):
    candidate, headers = me
    offer = make_offer(company, candidate)

    body = respond(client, headers, offer.id, "accept").json()

    assert body["candidate_comment"] is None


def test_a_blank_comment_is_stored_as_none(client, me, company, make_offer):
    candidate, headers = me
    offer = make_offer(company, candidate)

    body = respond(client, headers, offer.id, "decline", comment="   ").json()

    assert body["candidate_comment"] is None


def test_the_comment_may_be_500_characters(client, me, company, make_offer):
    candidate, headers = me
    offer = make_offer(company, candidate)

    assert respond(client, headers, offer.id, "accept", comment="я" * 500).status_code == 200


@pytest.mark.parametrize("first", ["accept", "decline"])
@pytest.mark.parametrize("second", ["accept", "decline"])
def test_a_second_answer_is_refused(
    client, db, me, company, make_offer, assert_error, first, second
):
    candidate, headers = me
    offer = make_offer(company, candidate)
    assert respond(client, headers, offer.id, first, comment="первый").status_code == 200
    answered_at = reload(db, offer).responded_at

    response = respond(client, headers, offer.id, second, comment="второй")

    assert_error(response, 409, "OFFER_ALREADY_RESPONDED")
    stored = reload(db, offer)
    assert stored.status == ("accepted" if first == "accept" else "declined")
    assert stored.candidate_comment == "первый"
    assert stored.responded_at == answered_at


def test_somebody_elses_offer_is_not_found(
    client, db, me, company, make_offer, make_candidate, assert_error
):
    _, headers = me
    other = make_candidate(email="other@example.test")
    foreign = make_offer(company, other)

    response = respond(client, headers, foreign.id, "accept")

    assert_error(response, 404, "NOT_FOUND")
    stored = reload(db, foreign)
    assert stored.status == "sent"
    assert stored.responded_at is None


def test_somebody_elses_answered_offer_looks_like_a_missing_one(
    client, me, company, make_offer, make_candidate, assert_error
):
    """Whether a foreign offer exists and is answered must not be visible."""
    _, headers = me
    other = make_candidate(email="other@example.test")
    foreign = make_offer(company, other, status="accepted")

    assert_error(respond(client, headers, foreign.id), 404, "NOT_FOUND")


@pytest.mark.parametrize("offer_id", [0, 424242, 10**15])
def test_no_such_offer(client, me, assert_error, offer_id):
    _, headers = me

    assert_error(respond(client, headers, offer_id), 404, "NOT_FOUND")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"decision": "maybe"},
        {"decision": "accept", "comment": "я" * 501},
        {"decision": None},
        {"decision": 1},
    ],
)
def test_bad_answers_are_refused(client, db, me, company, make_offer, assert_error, body):
    candidate, headers = me
    offer = make_offer(company, candidate)

    response = client.post(f"{URL}/{offer.id}/respond", json=body, headers=headers)

    assert_error(response, 422, "VALIDATION_ERROR")
    assert reload(db, offer).status == "sent"


def test_each_offer_is_answered_on_its_own(client, db, me, company, make_offer):
    candidate, headers = me
    first = make_offer(company, candidate, title="Первая")
    second = make_offer(company, candidate, title="Вторая")

    respond(client, headers, first.id, "accept")

    assert reload(db, first).status == "accepted"
    assert reload(db, second).status == "sent"
    assert respond(client, headers, second.id, "decline").status_code == 200


# --- access ----------------------------------------------------------------------------------


def test_offers_are_for_candidates(client, employer_headers, assert_error):
    assert_error(client.get(URL, headers=employer_headers), 403, "FORBIDDEN")
    assert_error(respond(client, employer_headers, 1), 403, "FORBIDDEN")


def test_offers_need_a_token(client):
    assert client.get(URL).status_code == 401
    assert client.post(f"{URL}/1/respond", json={"decision": "accept"}).status_code == 401
