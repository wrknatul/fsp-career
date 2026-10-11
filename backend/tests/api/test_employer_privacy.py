"""What an employer may and may not learn about a candidate (SPEC section 8).

Every check looks for substrings in the raw text of the response, so a private value cannot
hide in a field the test did not think of.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pytest

from app.domain.facts import experience_fact, manual_achievement_fact, skill_fact
from app.domain.redaction import redact_contacts

from .test_employer_kit import (
    API,
    add_offer,
    add_vacancy,
    build_candidate,
    fsp_rank,
    fsp_result,
    set_offer_status,
    skills,
)

SEARCH_URL = f"{API}/employer/search"
OFFERS_URL = f"{API}/employer/offers"

FULL_NAME = "Секретов Игнатий Петрович"
ABOUT = "Пишите: +7 900 123-45-67, ignatiy.about@mail.ru или @ignatiy_about"
COMMENT = "Спасибо! Звоните +7 900 555-66-77 или пишите reply.person@mail.ru"
RESUME = (
    "PRIVATE-RESUME-MARKER Секретов Игнатий Петрович\n"
    "ignatiy.resume@mail.ru, +7 900 777-88-99\n"
    "Разработчик Python, 2023 — 2024"
)

# Values that must never reach an employer who has no accepted offer to the candidate.
CONTACT_LEAKS = [
    "ignatiy.secret@example.test",
    "ignatiy.about@mail.ru",
    "ignatiy.evidence@mail.ru",
    "ignatiy.resume@mail.ru",
    "ignatiy.position@mail.ru",
    "hack.owner@mail.ru",
    "reply.person@mail.ru",
    "ignatiy_tg_secret",
    "ignatiy_about",
    "pos_nick",
    "911 222-33-44",
    "9112223344",
    "900 123-45-67",
    "900 555-66-77",
    "900 777-88-99",
    "vk.com/ignatiy_profile",
]
NAME_LEAKS = ["Секретов", "Петрович", "Секретов Игнатий", "Игнатий Петрович", FULL_NAME]
# Never shown, not even to an employer with an accepted offer.
NEVER_LEAKS = ["2001-02-03", "03.02.2001", "PRIVATE-RESUME-MARKER", "ignatiy.resume@mail.ru"]

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
FORBIDDEN_KEYS = {"birth_date", "resume_text", "resume_filename", "password_hash", "consent_at"}


@pytest.fixture()
def secret(make_candidate):
    """A candidate who typed contact data into every free-text place."""
    facts = [
        *skills("python", "fastapi", "postgresql", "docker"),
        skill_fact("sql", 2, "resume", evidence="Из резюме: ignatiy.evidence@mail.ru"),
        experience_fact(
            1.5,
            [
                {
                    "title": "Разработчик, tg @pos_nick",
                    "company": "ООО ignatiy.position@mail.ru",
                    "period": "2023 — 2024",
                    "years": 1.5,
                }
            ],
        ),
        manual_achievement_fact(
            "11111111-1111-1111-1111-111111111111",
            "Хакатон, пишите на hack.owner@mail.ru",
            2024,
            "national",
            "winner",
            None,
            "https://vk.com/ignatiy_profile",
        ),
        fsp_result("p1", "national", 2, "algorithmic", title="Всероссийская олимпиада"),
        fsp_rank("kms"),
    ]
    return build_candidate(
        make_candidate,
        facts,
        about=ABOUT,
        resume_text=RESUME,
        email="ignatiy.secret@example.test",
        full_name=FULL_NAME,
        phone="+7 911 222-33-44",
        telegram="@ignatiy_tg_secret",
        birth_date=date(2001, 2, 3),
        city="Казань",
        work_formats=["remote"],
        salary_expectation=130_000,
        fsp_id="FSP-2024-00117",
    )


@pytest.fixture()
def vacancy(db, employer_user):
    return add_vacancy(db, employer_user.employer, title="Python-разработчик")


@pytest.fixture()
def other_employer(make_employer, headers_for):
    employer = make_employer(email="other.company@example.test", company_name="Чужая компания")
    return employer, headers_for(employer.user)


def card_url(candidate) -> str:
    return f"{API}/employer/candidates/{candidate.id}"


def walk(value: Any):
    """Every key and every string in a JSON value."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)
    elif isinstance(value, str):
        yield value


def assert_never_shown(response) -> None:
    """Nothing here is shown to an employer in any state: birth date, resume, internal keys."""
    assert response.status_code in (200, 201), response.text
    for leak in NEVER_LEAKS:
        assert leak not in response.text, f"leaked {leak!r}"
    keys = {item for item in walk(response.json()) if item in FORBIDDEN_KEYS}
    assert not keys, keys


def assert_private(response) -> None:
    """The response carries no contact data, no full name and nothing that is never shown."""
    assert_never_shown(response)
    text = response.text
    for leak in CONTACT_LEAKS + NAME_LEAKS:
        assert leak not in text, f"leaked {leak!r}"
    assert EMAIL.search(text) is None, f"an e-mail address is shown: {EMAIL.search(text)}"


def search_everything(client, headers) -> list[Any]:
    """Several different searches, so every code path that builds a brief is covered."""
    queries: list[dict[str, Any]] = [
        {},
        {"stacks": ["backend"], "grades": ["middle", "junior"]},
        {"text": "Python FastAPI разработчик"},
        {"skills_required": ["python", "docker"], "text": "хакатон олимпиада"},
        {"fsp_verified_only": True, "disciplines": ["algorithmic"]},
    ]
    return [client.post(SEARCH_URL, json=body, headers=headers) for body in queries]


# --- before an accepted offer --------------------------------------------------------------------


def test_the_search_hides_private_data(client, employer_headers, secret):
    for response in search_everything(client, employer_headers):
        assert_private(response)
        items = response.json()["items"]
        assert [item["candidate"]["id"] for item in items] == [secret.id]


def test_the_search_shows_the_short_name_and_redacted_text(client, employer_headers, secret):
    items = client.post(SEARCH_URL, json={}, headers=employer_headers).json()["items"]

    brief = items[0]["candidate"]
    assert brief["display_name"] == "Игнатий С."
    assert brief["about"] == redact_contacts(ABOUT)
    assert brief["about"].count("[скрыто]") == 3
    assert brief["city"] == "Казань"
    assert brief["salary_expectation"] == 130_000


def test_grade_explanations_do_not_repeat_the_typed_titles(client, employer_headers, secret):
    category = client.post(SEARCH_URL, json={}, headers=employer_headers).json()["items"][0][
        "candidate"
    ]["category"]

    labels = [row["label"] for row in category["grade_explanations"]]
    assert any("Хакатон" in label for label in labels)
    assert not any("hack.owner" in label for label in labels)


def test_top_achievements_do_not_repeat_the_typed_titles(client, employer_headers, secret):
    item = client.post(SEARCH_URL, json={}, headers=employer_headers).json()["items"][0]

    titles = [achievement["title"] for achievement in item["top_achievements"]]
    assert any(title.startswith("Хакатон") for title in titles)
    assert not any("hack.owner" in title for title in titles)


def test_the_card_hides_private_data(client, employer_headers, secret):
    response = client.get(card_url(secret), headers=employer_headers)

    assert_private(response)
    body = response.json()
    assert body["display_name"] == "Игнатий С."
    assert body["contacts"] is None
    assert body["about"] == redact_contacts(ABOUT)


def test_the_card_redacts_titles_evidence_and_values_of_facts(client, employer_headers, secret):
    facts = client.get(card_url(secret), headers=employer_headers).json()["facts"]

    by_key = {fact["key"]: fact for fact in facts}
    sql = by_key["sql"]
    assert sql["evidence"] == "Из резюме: [скрыто]"
    manual = next(fact for fact in facts if fact["key"].startswith("manual:"))
    assert manual["title"] == "Хакатон, пишите на [скрыто], 2024 — победитель"
    assert manual["value"]["title"] == "Хакатон, пишите на [скрыто]"
    assert manual["value"]["document_url"] == "[скрыто]"
    assert manual["evidence"] == "[скрыто]"
    experience = by_key["total"]
    assert experience["value"]["positions"][0]["title"] == "Разработчик, tg [скрыто]"
    assert experience["value"]["positions"][0]["company"] == "ООО [скрыто]"


def test_the_card_keeps_facts_that_hold_no_contacts_unchanged(client, employer_headers, secret):
    facts = client.get(card_url(secret), headers=employer_headers).json()["facts"]

    python = next(fact for fact in facts if fact["key"] == "python")
    assert python["title"] == "Python"
    assert python["value"] == {"level": 2}
    assert (python["source"], python["verification"]) == ("resume", "parsed")
    rank = next(fact for fact in facts if fact["kind"] == "rank")
    assert rank["value"]["rank"] == "kms"
    assert rank["value"]["order_no"] == "№ 118"


def test_a_created_offer_hides_private_data(client, employer_headers, secret, vacancy):
    response = client.post(
        OFFERS_URL,
        json={"candidate_id": secret.id, "vacancy_id": vacancy.id, "salary": 150_000},
        headers=employer_headers,
    )

    assert_private(response)
    assert response.json()["contacts"] is None
    assert response.json()["candidate"]["display_name"] == "Игнатий С."


def test_the_offer_list_hides_private_data_of_a_sent_offer(
    client, db, employer_user, employer_headers, secret, vacancy
):
    add_offer(db, employer_user.employer, secret, vacancy, status="sent")

    response = client.get(OFFERS_URL, headers=employer_headers)

    assert_private(response)
    assert response.json()[0]["contacts"] is None


def test_the_comment_is_redacted_until_the_offer_is_accepted(
    client, db, employer_user, employer_headers, secret, vacancy
):
    offer = add_offer(db, employer_user.employer, secret, vacancy, status="sent")
    set_offer_status(db, offer, "declined", COMMENT)

    response = client.get(OFFERS_URL, headers=employer_headers)

    assert_private(response)
    item = response.json()[0]
    assert item["status"] == "declined"
    assert item["candidate_comment"] == "Спасибо! Звоните [скрыто] или пишите [скрыто]"
    assert item["contacts"] is None


def test_a_declined_offer_does_not_open_the_candidate(
    client, db, employer_user, employer_headers, secret, vacancy
):
    offer = add_offer(db, employer_user.employer, secret, vacancy, status="sent")
    set_offer_status(db, offer, "declined", COMMENT)

    for response in (
        client.get(card_url(secret), headers=employer_headers),
        client.get(OFFERS_URL, headers=employer_headers),
        *search_everything(client, employer_headers),
    ):
        assert_private(response)
    assert client.get(card_url(secret), headers=employer_headers).json()["contacts"] is None


def test_the_error_for_a_hidden_candidate_reveals_nothing(client, db, employer_headers, secret):
    secret.visible = False
    db.commit()

    response = client.get(card_url(secret), headers=employer_headers)

    assert response.status_code == 404
    assert_error_text_is_private(response.text)


def test_the_offer_list_shows_only_the_name_of_a_candidate_who_hid_the_profile(
    client, db, employer_user, employer_headers, secret, vacancy
):
    add_offer(db, employer_user.employer, secret, vacancy, status="sent")
    secret.visible = False
    secret.relocation = True
    db.commit()

    response = client.get(OFFERS_URL, headers=employer_headers)

    assert_private(response)
    item = response.json()[0]
    assert item["status"] == "sent"
    assert item["vacancy"] == {"id": vacancy.id, "title": "Python-разработчик"}
    assert item["contacts"] is None
    assert item["candidate"] == {
        "id": secret.id,
        "display_name": "Игнатий С.",
        "city": None,
        "category": item["candidate"]["category"],
        "salary_expectation": None,
        "relocation": False,
        "fsp_linked": False,
        "sport_rank": None,
        "about": None,
    }
    category = item["candidate"]["category"]
    assert category["stack"] is None and category["grade"] is None
    assert category["label"] == "Категория не определена"
    assert category["top_skills"] == [] and category["grade_explanations"] == []
    for value in ("Казань", "130000", "kms", "python", "FSP-2024-00117"):
        assert value not in response.text, f"leaked {value!r}"


def test_the_offer_list_shows_the_profile_again_when_it_is_shown_again(
    client, db, employer_user, employer_headers, secret, vacancy
):
    add_offer(db, employer_user.employer, secret, vacancy, status="sent")
    secret.visible = False
    db.commit()
    assert client.get(OFFERS_URL, headers=employer_headers).json()[0]["candidate"]["city"] is None

    secret.visible = True
    db.commit()

    candidate = client.get(OFFERS_URL, headers=employer_headers).json()[0]["candidate"]
    assert candidate["city"] == "Казань"
    assert candidate["salary_expectation"] == 130_000
    assert candidate["fsp_linked"] is True
    assert candidate["category"]["stack"] == "backend"


def test_a_declined_offer_does_not_reveal_a_candidate_who_hid_the_profile(
    client, db, employer_user, employer_headers, secret, vacancy
):
    offer = add_offer(db, employer_user.employer, secret, vacancy, status="sent")
    set_offer_status(db, offer, "declined", COMMENT)
    secret.visible = False
    db.commit()

    response = client.get(OFFERS_URL, headers=employer_headers)

    assert_private(response)
    assert response.json()[0]["candidate"]["about"] is None
    assert response.json()[0]["candidate"]["city"] is None


def assert_error_text_is_private(text: str) -> None:
    for leak in CONTACT_LEAKS + NEVER_LEAKS + NAME_LEAKS:
        assert leak not in text


# --- after an accepted offer ---------------------------------------------------------------------


@pytest.fixture()
def accepted(db, employer_user, secret, vacancy):
    offer = add_offer(db, employer_user.employer, secret, vacancy, status="sent")
    set_offer_status(db, offer, "accepted", COMMENT)
    return offer


def test_the_card_opens_after_the_offer_is_accepted(client, employer_headers, secret, accepted):
    response = client.get(card_url(secret), headers=employer_headers)

    assert_never_shown(response)
    body = response.json()
    assert body["display_name"] == FULL_NAME
    assert body["about"] == ABOUT
    assert body["contacts"] == {
        "email": "ignatiy.secret@example.test",
        "telegram": "@ignatiy_tg_secret",
        "phone": "+7 911 222-33-44",
    }


def test_the_birth_date_and_the_resume_stay_closed_even_after_acceptance(
    client, employer_headers, secret, accepted
):
    responses = [
        client.get(card_url(secret), headers=employer_headers),
        client.get(OFFERS_URL, headers=employer_headers),
        *search_everything(client, employer_headers),
    ]

    for response in responses:
        assert_never_shown(response)


def test_facts_are_not_redacted_after_acceptance(client, employer_headers, secret, accepted):
    facts = client.get(card_url(secret), headers=employer_headers).json()["facts"]

    by_key = {fact["key"]: fact for fact in facts}
    assert by_key["sql"]["evidence"] == "Из резюме: ignatiy.evidence@mail.ru"
    manual = next(fact for fact in facts if fact["key"].startswith("manual:"))
    assert manual["title"] == "Хакатон, пишите на hack.owner@mail.ru, 2024 — победитель"
    assert manual["value"]["document_url"] == "https://vk.com/ignatiy_profile"


def test_the_offer_list_opens_after_acceptance(client, employer_headers, secret, accepted):
    item = client.get(OFFERS_URL, headers=employer_headers).json()[0]

    assert item["status"] == "accepted"
    assert item["candidate"]["display_name"] == FULL_NAME
    assert item["candidate"]["about"] == ABOUT
    assert item["candidate_comment"] == COMMENT
    assert item["contacts"] == {
        "email": "ignatiy.secret@example.test",
        "telegram": "@ignatiy_tg_secret",
        "phone": "+7 911 222-33-44",
    }


def test_the_search_shows_the_full_name_after_acceptance(
    client, employer_headers, secret, accepted
):
    for response in search_everything(client, employer_headers):
        brief = response.json()["items"][0]["candidate"]
        assert brief["display_name"] == FULL_NAME
        assert brief["about"] == ABOUT
        assert "contacts" not in brief


def test_a_second_offer_to_an_open_candidate_shows_the_full_name(
    client, db, employer_user, employer_headers, secret, accepted
):
    second = add_vacancy(db, employer_user.employer, title="Вторая вакансия")

    response = client.post(
        OFFERS_URL,
        json={"candidate_id": secret.id, "vacancy_id": second.id, "salary": 160_000},
        headers=employer_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["candidate"]["display_name"] == FULL_NAME
    # The contacts belong to an accepted offer; this one is only sent.
    assert body["status"] == "sent"
    assert body["contacts"] is None


def test_the_card_lists_every_offer_of_this_employer(
    client, db, employer_user, employer_headers, secret, accepted
):
    second = add_vacancy(db, employer_user.employer, title="Вторая вакансия")
    add_offer(db, employer_user.employer, secret, second, status="sent", salary=170_000)

    offers = client.get(card_url(secret), headers=employer_headers).json()["offers"]

    assert [(o["vacancy_title"], o["status"], o["salary"]) for o in offers] == [
        ("Вторая вакансия", "sent", 170_000),
        ("Python-разработчик", "accepted", 150_000),
    ]


# --- other employers stay locked out -------------------------------------------------------------


def test_another_employer_still_sees_nothing_private(client, accepted, secret, other_employer):
    _, headers = other_employer

    for response in (
        client.get(card_url(secret), headers=headers),
        *search_everything(client, headers),
    ):
        assert_private(response)
    assert client.get(card_url(secret), headers=headers).json()["contacts"] is None


def test_another_employer_does_not_see_the_offer_of_the_first(
    client, accepted, secret, other_employer
):
    _, headers = other_employer

    assert client.get(OFFERS_URL, headers=headers).json() == []
    card = client.get(card_url(secret), headers=headers).json()
    assert card["offers"] == []
    items = client.post(SEARCH_URL, json={}, headers=headers).json()["items"]
    assert items[0]["offer_status"] is None


def test_another_employer_with_a_sent_offer_gets_no_contacts(
    client, db, accepted, secret, other_employer
):
    employer, headers = other_employer
    their_vacancy = add_vacancy(db, employer, title="Их вакансия")
    add_offer(db, employer, secret, their_vacancy, status="sent")

    for response in (
        client.get(card_url(secret), headers=headers),
        client.get(OFFERS_URL, headers=headers),
    ):
        assert_private(response)


def test_a_candidate_who_hid_the_profile_disappears_even_after_acceptance(
    client, db, employer_headers, secret, accepted
):
    secret.visible = False
    db.commit()

    assert client.get(card_url(secret), headers=employer_headers).status_code == 404
    assert client.post(SEARCH_URL, json={}, headers=employer_headers).json()["items"] == []


def test_the_offer_list_keeps_the_open_data_of_an_accepted_candidate_who_hid_the_profile(
    client, db, employer_headers, secret, accepted
):
    secret.visible = False
    db.commit()

    item = client.get(OFFERS_URL, headers=employer_headers).json()[0]

    assert item["candidate"]["display_name"] == FULL_NAME
    assert item["candidate"]["city"] == "Казань"
    assert item["candidate"]["category"]["stack"] == "backend"
    assert item["contacts"]["email"] == "ignatiy.secret@example.test"
