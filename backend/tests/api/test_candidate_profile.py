"""`GET` and `PATCH /candidate/profile`."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.timeutil import utcnow
from app.domain.facts import experience_fact, skill_fact
from app.models import Candidate, ProfileFact, User
from app.services.profile import (
    build_profile,
    recompute_candidate,
    replace_facts,
    upsert_fact,
)

API = "/api/v1"
URL = f"{API}/candidate/profile"


def reload_candidate(db, candidate_id: int) -> Candidate:
    db.expire_all()
    return db.get(Candidate, candidate_id)


# --- reading ---------------------------------------------------------------------------------


def test_empty_profile_is_readable(client, candidate_user, candidate_headers):
    response = client.get(URL, headers=candidate_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == candidate_user.candidate.id
    assert body["user"] == {
        "id": candidate_user.id,
        "email": "candidate@example.test",
        "role": "candidate",
        "full_name": "Иванов Иван Иванович",
    }
    assert body["birth_date"] is None
    assert body["city"] is None
    assert body["work_formats"] == []
    assert body["relocation"] is False
    assert body["salary_expectation"] is None
    assert body["about"] is None
    assert body["visible"] is True
    assert body["fsp"] is None
    assert body["resume"] is None
    assert body["facts"] == []
    assert body["updated_at"]
    category = body["category"]
    assert category["stack"] is None
    assert category["grade"] is None
    assert category["label"] == "Категория не определена"
    assert category["confidence_index"] == 0


def test_null_category_reads_as_categorize_of_nothing_with_the_prefs(
    client, make_candidate, headers_for
):
    candidate = make_candidate(work_formats=["remote", "hybrid"], category=None)

    body = client.get(URL, headers=headers_for(candidate.user)).json()

    assert body["category"]["label"] == "Категория не определена"
    assert body["category"]["work_formats"] == ["remote", "hybrid"]


def test_profile_lists_facts_with_sources(client, make_candidate, headers_for):
    candidate = make_candidate(
        facts=[
            skill_fact("python", 2, "resume", evidence="Python"),
            skill_fact("sql", 1, "test"),
        ]
    )

    body = client.get(URL, headers=headers_for(candidate.user)).json()

    assert [(f["key"], f["source"], f["verification"]) for f in body["facts"]] == [
        ("python", "resume", "parsed"),
        ("sql", "test", "tested"),
    ]
    assert body["facts"][0]["evidence"] == "Python"
    assert body["facts"][0]["value"] == {"level": 2}


def test_profile_requires_a_token(client):
    response = client.get(URL)

    assert response.status_code == 401


def test_employer_cannot_use_candidate_routes(client, employer_headers, assert_error):
    assert_error(client.get(URL, headers=employer_headers), 403, "FORBIDDEN")
    response = client.patch(URL, json={"city": "Казань"}, headers=employer_headers)
    assert_error(response, 403, "FORBIDDEN")


def test_a_candidate_sees_only_their_own_profile(client, make_candidate, headers_for):
    first = make_candidate(email="first@example.test", city="Казань")
    second = make_candidate(email="second@example.test", city="Омск")

    assert client.get(URL, headers=headers_for(first.user)).json()["city"] == "Казань"
    assert client.get(URL, headers=headers_for(second.user)).json()["city"] == "Омск"


# --- changing --------------------------------------------------------------------------------


def test_patch_changes_the_questionnaire(client, db, candidate_user, candidate_headers):
    payload = {
        "birth_date": "2001-02-03",
        "city": "Казань",
        "work_formats": ["remote", "hybrid"],
        "relocation": True,
        "salary_expectation": 150000,
        "about": "Пишу на Python",
        "telegram": "@ivan_dev",
        "phone": "+7 900 111-22-33",
        "visible": False,
    }

    response = client.patch(URL, json=payload, headers=candidate_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert {key: body[key] for key in payload} == payload
    candidate = reload_candidate(db, candidate_user.candidate.id)
    assert candidate.city == "Казань"
    assert candidate.birth_date == date(2001, 2, 3)
    assert candidate.work_formats == ["remote", "hybrid"]
    assert candidate.visible is False
    assert candidate.salary_expectation == 150000


def test_patch_changes_the_account_name(client, db, candidate_user, candidate_headers):
    response = client.patch(URL, json={"full_name": "  Петров   Пётр "}, headers=candidate_headers)

    assert response.status_code == 200, response.text
    assert response.json()["user"]["full_name"] == "Петров   Пётр"
    db.expire_all()
    assert db.get(User, candidate_user.id).full_name == "Петров   Пётр"


def test_patch_touches_only_the_sent_fields(client, make_candidate, headers_for):
    candidate = make_candidate(city="Казань", salary_expectation=100000, about="о себе")

    body = client.patch(
        URL, json={"city": "Омск", "unknown_field": 1}, headers=headers_for(candidate.user)
    ).json()

    assert body["city"] == "Омск"
    assert body["salary_expectation"] == 100000
    assert body["about"] == "о себе"


def test_patch_with_null_clears_nullable_fields(client, make_candidate, headers_for):
    candidate = make_candidate(
        city="Казань", salary_expectation=100000, about="о себе", birth_date=date(2001, 1, 1)
    )

    response = client.patch(
        URL,
        json={"city": None, "salary_expectation": None, "about": None, "birth_date": None},
        headers=headers_for(candidate.user),
    )

    body = response.json()
    assert response.status_code == 200, response.text
    assert (body["city"], body["salary_expectation"], body["about"], body["birth_date"]) == (
        None,
        None,
        None,
        None,
    )


def test_patch_with_an_empty_body_changes_nothing(client, make_candidate, headers_for):
    candidate = make_candidate(city="Казань")

    response = client.patch(URL, json={}, headers=headers_for(candidate.user))

    assert response.status_code == 200
    assert response.json()["city"] == "Казань"


@pytest.mark.parametrize(
    "payload",
    [
        {"work_formats": ["moon"]},
        {"work_formats": None},
        {"work_formats": ["remote", "remote", "office", "hybrid"]},
        {"salary_expectation": 0},
        {"salary_expectation": -5},
        {"relocation": None},
        {"visible": None},
        {"full_name": "   "},
        {"full_name": None},
        {"birth_date": "2999-01-01"},
        {"birth_date": "вчера"},
        {"about": "я" * 2001},
    ],
)
def test_patch_rejects_bad_values(client, candidate_headers, assert_error, payload):
    response = client.patch(URL, json=payload, headers=candidate_headers)

    assert_error(response, 422, "VALIDATION_ERROR")


def test_patch_recomputes_the_category_and_the_vector(
    client, db, make_candidate, headers_for
):
    candidate = make_candidate(
        facts=[
            skill_fact("python", 2, "resume"),
            skill_fact("fastapi", 2, "resume"),
            experience_fact(3.0, [], None),
        ],
        category=None,
    )
    assert candidate.category is None
    assert candidate.embedding is None

    body = client.patch(
        URL,
        json={"work_formats": ["remote"], "about": "Люблю backend"},
        headers=headers_for(candidate.user),
    ).json()

    assert body["category"]["stack"] == "backend"
    assert body["category"]["work_formats"] == ["remote"]
    assert body["category"]["label"].startswith("Backend")
    assert "Удалённо" in body["category"]["label"]
    stored = reload_candidate(db, candidate.id)
    assert stored.category["stack"] == "backend"
    assert stored.category == body["category"]
    assert isinstance(stored.embedding, list)
    assert len(stored.embedding) == 384
    assert any(stored.embedding)


def test_patch_moves_updated_at_forward(client, db, make_candidate, headers_for):
    candidate = make_candidate()
    before = utcnow()

    body = client.patch(URL, json={"city": "Казань"}, headers=headers_for(candidate.user)).json()

    stored = reload_candidate(db, candidate.id)
    assert stored.updated_at >= before
    assert body["updated_at"].startswith(stored.updated_at.strftime("%Y-%m-%dT%H:%M:%S"))


# --- the lock while an FSP id is linked ------------------------------------------------------


@pytest.fixture()
def linked(make_candidate):
    return make_candidate(
        full_name="Смирнов Алексей Игоревич",
        birth_date=date(2003, 5, 14),
        city="Казань",
        fsp_id="FSP-2024-00117",
        fsp_linked_at=utcnow(),
    )


def test_name_is_locked_while_fsp_is_linked(client, db, linked, headers_for, assert_error):
    response = client.patch(
        URL, json={"full_name": "Другой Человек"}, headers=headers_for(linked.user)
    )

    assert_error(response, 409, "FSP_LINKED_LOCKED")
    db.expire_all()
    assert db.get(User, linked.user.id).full_name == "Смирнов Алексей Игоревич"


def test_birth_date_is_locked_while_fsp_is_linked(client, db, linked, headers_for, assert_error):
    response = client.patch(
        URL, json={"birth_date": "2003-05-15"}, headers=headers_for(linked.user)
    )

    assert_error(response, 409, "FSP_LINKED_LOCKED")
    assert reload_candidate(db, linked.id).birth_date == date(2003, 5, 14)


def test_a_rejected_patch_applies_nothing(client, db, linked, headers_for, assert_error):
    response = client.patch(
        URL,
        json={"city": "Москва", "full_name": "Другой Человек"},
        headers=headers_for(linked.user),
    )

    assert_error(response, 409, "FSP_LINKED_LOCKED")
    assert reload_candidate(db, linked.id).city == "Казань"


def test_the_other_fields_stay_editable_while_fsp_is_linked(client, db, linked, headers_for):
    response = client.patch(
        URL, json={"city": "Москва", "about": "Новый текст"}, headers=headers_for(linked.user)
    )

    assert response.status_code == 200, response.text
    assert response.json()["fsp"]["fsp_id"] == "FSP-2024-00117"
    assert reload_candidate(db, linked.id).city == "Москва"


@pytest.mark.parametrize(
    "body",
    [
        {"full_name": "Смирнов Алексей Игоревич"},
        {"birth_date": "2003-05-14"},
        {"full_name": "Смирнов Алексей Игоревич", "birth_date": "2003-05-14", "city": "Омск"},
    ],
    ids=["same-name", "same-birth-date", "both-with-another-field"],
)
def test_resending_the_same_name_or_birth_date_is_still_locked(
    client, db, linked, headers_for, assert_error, body
):
    # SPEC 6.1: any PATCH that carries `full_name` or `birth_date` is refused while FSP is linked,
    # even with the value the profile already has. The rest of the body is not applied.
    response = client.patch(URL, json=body, headers=headers_for(linked.user))

    assert_error(response, 409, "FSP_LINKED_LOCKED")
    assert reload_candidate(db, linked.id).city == "Казань"


def test_the_same_name_and_birth_date_are_accepted_after_unlinking(
    client, db, linked, headers_for
):
    headers = headers_for(linked.user)
    assert client.delete(f"{API}/candidate/fsp/link", headers=headers).status_code == 200

    response = client.patch(
        URL,
        json={"full_name": "Смирнов Алексей Игоревич", "birth_date": "2003-05-14", "city": "Омск"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["city"] == "Омск"


def test_name_is_editable_without_a_link(client, make_candidate, headers_for):
    candidate = make_candidate(birth_date=date(2003, 5, 14))

    response = client.patch(
        URL,
        json={"full_name": "Новое Имя", "birth_date": "2003-05-15"},
        headers=headers_for(candidate.user),
    )

    assert response.status_code == 200, response.text
    assert response.json()["user"]["full_name"] == "Новое Имя"


def test_only_one_row_is_changed(client, db, make_candidate, headers_for):
    first = make_candidate(email="a@example.test", city="Казань")
    second = make_candidate(email="b@example.test", city="Омск")

    client.patch(URL, json={"city": "Тула"}, headers=headers_for(first.user))

    cities = dict(db.execute(select(Candidate.id, Candidate.city)).all())
    assert cities == {first.id: "Тула", second.id: "Омск"}


# --- the profile service ---------------------------------------------------------------------


def keys(db, candidate_id: int) -> list[tuple[str, str, str]]:
    db.expire_all()
    rows = db.scalars(
        select(ProfileFact).where(ProfileFact.candidate_id == candidate_id).order_by(ProfileFact.id)
    )
    return [(row.source, row.kind, row.key) for row in rows]


def test_replace_facts_swaps_one_source_only(db, make_candidate):
    candidate = make_candidate(
        facts=[
            skill_fact("python", 2, "resume"),
            skill_fact("sql", 2, "resume"),
            skill_fact("python", 3, "test"),
        ]
    )

    replace_facts(db, candidate, "resume", [skill_fact("git", 1, "resume")])
    db.commit()

    assert keys(db, candidate.id) == [("test", "skill", "python"), ("resume", "skill", "git")]


def test_replace_facts_keeps_the_first_of_two_equal_keys(db, make_candidate):
    candidate = make_candidate()

    replace_facts(
        db,
        candidate,
        "resume",
        [skill_fact("python", 1, "resume"), skill_fact("python", 2, "resume")],
    )
    db.commit()

    rows = list(db.scalars(select(ProfileFact).where(ProfileFact.candidate_id == candidate.id)))
    assert [(row.key, row.value["level"]) for row in rows] == [("python", 1)]


def test_replace_facts_refuses_a_fact_of_another_source(db, make_candidate):
    candidate = make_candidate()

    with pytest.raises(ValueError, match="source"):
        replace_facts(db, candidate, "resume", [skill_fact("python", 1, "test")])


def test_replace_facts_with_nothing_clears_the_source(db, make_candidate):
    candidate = make_candidate(facts=[skill_fact("python", 2, "resume")])

    replace_facts(db, candidate, "resume", [])
    db.commit()

    assert keys(db, candidate.id) == []


def test_upsert_fact_inserts_then_updates(db, make_candidate):
    candidate = make_candidate()

    assert upsert_fact(db, candidate, skill_fact("python", 1, "test")) is True
    assert upsert_fact(db, candidate, skill_fact("python", 2, "test", score=0.9)) is True
    db.commit()

    rows = list(db.scalars(select(ProfileFact).where(ProfileFact.candidate_id == candidate.id)))
    assert [(row.key, row.value) for row in rows] == [("python", {"level": 2, "score": 0.9})]


def test_upsert_fact_can_keep_the_higher_level(db, make_candidate):
    candidate = make_candidate(facts=[skill_fact("python", 2, "test")])

    def attempt(level: int) -> bool:
        fact = skill_fact("python", level, "test")
        return upsert_fact(db, candidate, fact, keep_higher_level=True)

    assert attempt(1) is False
    assert attempt(2) is False
    assert attempt(3) is True
    db.commit()

    rows = list(db.scalars(select(ProfileFact).where(ProfileFact.candidate_id == candidate.id)))
    assert [row.value["level"] for row in rows] == [3]


def test_upsert_fact_does_not_mix_sources(db, make_candidate):
    candidate = make_candidate(facts=[skill_fact("python", 3, "test")])

    upsert_fact(db, candidate, skill_fact("python", 1, "resume"))
    db.commit()

    assert keys(db, candidate.id) == [("test", "skill", "python"), ("resume", "skill", "python")]


def test_a_lost_race_on_a_fact_is_a_conflict_not_a_500(db, make_candidate, monkeypatch):
    fact = skill_fact("python", 2, "test")
    candidate = make_candidate(facts=[fact])
    # The lookup does not see the row that a parallel request has just written.
    monkeypatch.setattr(db, "scalar", lambda *args, **kwargs: None)

    with pytest.raises(AppError) as error:
        upsert_fact(db, candidate, fact)

    assert (error.value.error_code, error.value.status_code) == ("CONFLICT", 409)


def test_recompute_stores_category_vector_and_time(db, make_candidate):
    candidate = make_candidate(
        facts=[skill_fact("python", 3, "test"), skill_fact("fastapi", 3, "test")],
        about="Пишу сервисы",
    )
    before = candidate.updated_at

    category = recompute_candidate(db, candidate)
    db.commit()

    assert category.stack == "backend"
    assert candidate.category == category.model_dump()
    assert len(candidate.embedding) == 384
    assert candidate.updated_at > before
    # Same input, same vector: the embedding is stable between recomputations.
    first = list(candidate.embedding)
    recompute_candidate(db, candidate)
    assert candidate.embedding == first


def test_recompute_of_an_empty_profile_is_the_undefined_category(db, make_candidate):
    candidate = make_candidate(work_formats=["remote"], city="Казань")

    category = recompute_candidate(db, candidate)

    assert category.stack is None
    assert category.label == "Категория не определена"
    assert category.work_formats == ["remote"]
    assert candidate.category["stack"] is None


def test_build_profile_reads_a_stored_category(db, make_candidate):
    candidate = make_candidate(
        facts=[skill_fact("python", 3, "test"), skill_fact("fastapi", 3, "test")]
    )
    recompute_candidate(db, candidate)
    db.commit()

    profile = build_profile(db, candidate)

    assert profile.category.stack == "backend"
    assert profile.category.model_dump() == candidate.category
    assert [fact.key for fact in profile.facts] == ["python", "fastapi"]
    assert profile.fsp is None
    assert profile.resume is None


def test_build_profile_treats_an_unreadable_stored_category_as_stale(db, make_candidate):
    candidate = make_candidate(
        facts=[skill_fact("python", 3, "test"), skill_fact("fastapi", 3, "test")],
        category={"stack": "not-a-stack"},
    )

    profile = build_profile(db, candidate)

    assert profile.category.stack == "backend"
