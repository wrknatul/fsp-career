"""`POST` and `DELETE /candidate/fsp/link` (SPEC section 6.1)."""

from __future__ import annotations

import unicodedata
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.api.routes import candidate_fsp
from app.core.timeutil import utcnow
from app.domain.facts import manual_achievement_fact, skill_fact
from app.models import Candidate, LinkAttempt, ProfileFact

API = "/api/v1"
LINK = f"{API}/candidate/fsp/link"
DEMO_ID = "FSP-2024-00117"
DEMO_NAME = "Смирнов Алексей Игоревич"
DEMO_BIRTH = date(2003, 5, 14)
JUNIOR_NOTE = "Спортивные результаты учтены, но без опыта работы грейд не выше Junior"


@pytest.fixture()
def demo(make_candidate, headers_for):
    """The demo candidate (not linked) and the headers to call the API as them."""
    candidate = make_candidate(
        email="alexey@example.test", full_name=DEMO_NAME, birth_date=DEMO_BIRTH
    )
    return candidate, headers_for(candidate.user)


def link(client, headers, fsp_id: str = DEMO_ID):
    return client.post(LINK, json={"fsp_id": fsp_id}, headers=headers)


def attempts(db, user_id: int) -> int:
    query = select(func.count()).select_from(LinkAttempt).where(LinkAttempt.user_id == user_id)
    return db.scalar(query)


def fsp_facts(db, candidate_id: int) -> list[ProfileFact]:
    db.expire_all()
    return list(
        db.scalars(
            select(ProfileFact).where(
                ProfileFact.candidate_id == candidate_id, ProfileFact.source == "fsp"
            )
        )
    )


# --- success ---------------------------------------------------------------------------------


def test_demo_athlete_is_linked(client, db, demo):
    candidate, headers = demo

    response = link(client, headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["athlete"] == {
        "fsp_id": DEMO_ID,
        "short_name": "Смирнов А. И.",
        "region": "Республика Татарстан",
    }
    assert body["imported"] == {"achievements": 6, "ranks": 1, "skills": 2, "roles": 2}
    profile = body["profile"]
    assert profile["fsp"]["fsp_id"] == DEMO_ID
    assert profile["fsp"]["region"] == "Республика Татарстан"
    assert profile["fsp"]["linked_at"]
    assert len(profile["facts"]) == 11
    assert {fact["source"] for fact in profile["facts"]} == {"fsp"}
    assert {fact["verification"] for fact in profile["facts"]} == {"verified"}
    ranks = [fact for fact in profile["facts"] if fact["kind"] == "rank"]
    assert ranks[0]["value"]["rank"] == "kms"
    assert {fact["key"] for fact in profile["facts"] if fact["kind"] == "skill"} == {
        "algorithms",
        "product-development",
    }
    assert any(fact["key"] == "fsp_captain" for fact in profile["facts"])
    assert all(
        fact["evidence"].startswith("https://fsp.example/protocols/")
        for fact in profile["facts"]
        if fact["kind"] == "achievement"
    )

    category = profile["category"]
    assert category["stack"] == "backend"
    assert category["grade"] == "junior"
    assert category["grade_note"] == JUNIOR_NOTE
    assert category["label"].startswith("Backend · Junior")
    assert category["stack_confirmed"] is True
    assert category["grade_confirmed"] is True
    assert category["confidence_index"] == 50

    db.expire_all()
    stored = db.get(Candidate, candidate.id)
    assert stored.fsp_id == DEMO_ID
    assert stored.fsp_region == "Республика Татарстан"
    assert stored.fsp_linked_at is not None
    assert stored.category["grade"] == "junior"
    assert len(stored.embedding) == 384
    assert attempts(db, candidate.user.id) == 1


def test_the_answer_never_exposes_the_registry_internals(client, demo):
    _, headers = demo

    athlete = link(client, headers).json()["athlete"]

    assert set(athlete) == {"fsp_id", "short_name", "region"}


def test_get_profile_after_link_matches_the_link_answer(client, demo):
    _, headers = demo

    profile = link(client, headers).json()["profile"]

    assert client.get(f"{API}/candidate/profile", headers=headers).json() == profile


def test_fsp_id_may_be_typed_loosely(client, db, demo):
    candidate, headers = demo

    response = link(client, headers, "  fsp‑2024–00117 ")

    assert response.status_code == 200, response.text
    assert response.json()["athlete"]["fsp_id"] == DEMO_ID
    db.expire_all()
    assert db.get(Candidate, candidate.id).fsp_id == DEMO_ID


def test_name_matching_ignores_case_yo_and_extra_spaces(client, make_candidate, headers_for):
    candidate = make_candidate(
        full_name="  ЖУРАВЛЕВА   марина  дмитриевна ", birth_date=date(2000, 8, 21)
    )

    response = link(client, headers_for(candidate.user), "FSP-2022-00058")

    assert response.status_code == 200, response.text
    assert response.json()["athlete"]["short_name"] == "Журавлёва М. Д."


def test_the_registry_name_with_yo_matches_a_name_with_ye_the_other_way_round(
    client, make_candidate, headers_for
):
    candidate = make_candidate(
        full_name="журавлёва Марина Дмитриевна", birth_date=date(2000, 8, 21)
    )

    assert link(client, headers_for(candidate.user), "FSP-2022-00058").status_code == 200


@pytest.mark.parametrize(
    ("fsp_id", "registry_name", "birth"),
    [
        ("FSP-2022-00058", "Журавлёва Марина Дмитриевна", date(2000, 8, 21)),  # "ё"
        (DEMO_ID, DEMO_NAME, DEMO_BIRTH),  # "й"
    ],
)
def test_a_decomposed_name_matches_the_registry(
    client, make_candidate, headers_for, fsp_id, registry_name, birth
):
    # "е" + U+0308 and "и" + U+0306 instead of the single code points "ё" and "й".
    decomposed = unicodedata.normalize("NFD", registry_name)
    assert decomposed != registry_name
    candidate = make_candidate(full_name=decomposed, birth_date=birth)

    response = link(client, headers_for(candidate.user), fsp_id)

    assert response.status_code == 200, response.text


def test_a_decomposed_name_links_on_the_first_attempt(client, db, make_candidate, headers_for):
    candidate = make_candidate(
        full_name=unicodedata.normalize("NFD", DEMO_NAME), birth_date=DEMO_BIRTH
    )

    assert link(client, headers_for(candidate.user)).status_code == 200
    assert attempts(db, candidate.user.id) == 1


def test_normalize_name_gives_one_form_for_every_spelling():
    spelled = [
        "Журавлёва Марина Дмитриевна",
        "ЖУРАВЛЁВА  МАРИНА ДМИТРИЕВНА",
        "журавлева марина дмитриевна",
        unicodedata.normalize("NFD", "Журавлёва Марина Дмитриевна"),
    ]

    assert len({candidate_fsp.normalize_name(name) for name in spelled}) == 1
    assert candidate_fsp.normalize_name(None) == ""


# --- the five refusals, in the order of SPEC 6.1 ---------------------------------------------


def test_incomplete_profile(client, make_candidate, headers_for, assert_error):
    candidate = make_candidate(full_name=DEMO_NAME, birth_date=None)

    response = link(client, headers_for(candidate.user))

    assert_error(response, 409, "PROFILE_INCOMPLETE")


def test_unknown_id(client, db, demo, assert_error):
    candidate, headers = demo

    response = link(client, headers, "FSP-0000-00000")

    assert_error(response, 404, "FSP_ATHLETE_NOT_FOUND")
    assert attempts(db, candidate.user.id) == 1
    db.expire_all()
    assert db.get(Candidate, candidate.id).fsp_id is None


def test_id_linked_to_another_user(client, make_candidate, demo, assert_error):
    make_candidate(email="owner@example.test", fsp_id=DEMO_ID, fsp_linked_at=utcnow())
    _, headers = demo

    response = link(client, headers)

    body = assert_error(response, 409, "FSP_ALREADY_LINKED")
    assert body["details"] == {"linked_to_you": False}


def test_id_already_linked_to_you(client, demo, assert_error):
    _, headers = demo
    assert link(client, headers).status_code == 200

    response = link(client, headers)

    body = assert_error(response, 409, "FSP_ALREADY_LINKED")
    assert body["details"] == {"linked_to_you": True}


def test_another_id_while_one_is_linked(client, db, demo, assert_error):
    candidate, headers = demo
    assert link(client, headers).status_code == 200

    response = link(client, headers, "FSP-2022-00058")

    body = assert_error(response, 409, "FSP_ALREADY_LINKED")
    assert body["details"] == {"linked_to_you": True}
    db.expire_all()
    assert db.get(Candidate, candidate.id).fsp_id == DEMO_ID


@pytest.mark.parametrize(
    ("full_name", "birth_date"),
    [
        ("Смирнов Алексей Петрович", DEMO_BIRTH),
        (DEMO_NAME, date(2003, 5, 15)),
        ("Другой Человек", date(1990, 1, 1)),
    ],
)
def test_identity_mismatch(
    client, db, make_candidate, headers_for, assert_error, full_name, birth_date
):
    candidate = make_candidate(full_name=full_name, birth_date=birth_date)

    response = link(client, headers_for(candidate.user))

    assert_error(response, 409, "FSP_IDENTITY_MISMATCH")
    db.expire_all()
    stored = db.get(Candidate, candidate.id)
    assert stored.fsp_id is None
    assert fsp_facts(db, candidate.id) == []


def test_mismatch_does_not_say_which_field_is_wrong(client, make_candidate, headers_for):
    wrong_name = make_candidate(full_name="Смирнов Алексей Петрович", birth_date=DEMO_BIRTH)
    wrong_date = make_candidate(full_name=DEMO_NAME, birth_date=date(2003, 5, 15))

    first = link(client, headers_for(wrong_name.user)).json()
    second = link(client, headers_for(wrong_date.user)).json()

    assert first["message"] == second["message"]
    assert first["details"] == second["details"] == {}


def test_checks_run_in_the_documented_order(
    client, db, make_candidate, headers_for, assert_error
):
    # 1 comes before 2: an incomplete profile is told so even when the limit is used up.
    incomplete = make_candidate(full_name=DEMO_NAME, birth_date=None)
    db.add_all([LinkAttempt(user_id=incomplete.user.id, created_at=utcnow()) for _ in range(5)])
    db.commit()
    assert_error(link(client, headers_for(incomplete.user)), 409, "PROFILE_INCOMPLETE")

    # 2 comes before 3: past the limit even an unknown id gets 429.
    limited = make_candidate(full_name=DEMO_NAME, birth_date=DEMO_BIRTH)
    db.add_all([LinkAttempt(user_id=limited.user.id, created_at=utcnow()) for _ in range(5)])
    db.commit()
    assert_error(link(client, headers_for(limited.user), "FSP-0000-00000"), 429, "RATE_LIMITED")

    # 4 comes before 5: a taken id is reported before the identity is compared.
    make_candidate(email="owner@example.test", fsp_id=DEMO_ID, fsp_linked_at=utcnow())
    stranger = make_candidate(full_name="Другой Человек", birth_date=date(1990, 1, 1))
    body = assert_error(link(client, headers_for(stranger.user)), 409, "FSP_ALREADY_LINKED")
    assert body["details"] == {"linked_to_you": False}


# --- the attempt limit -----------------------------------------------------------------------


def test_sixth_attempt_within_an_hour_is_limited(client, db, demo, assert_error):
    candidate, headers = demo
    for _ in range(5):
        assert_error(link(client, headers, "FSP-0000-00000"), 404, "FSP_ATHLETE_NOT_FOUND")

    response = link(client, headers)

    body = assert_error(response, 429, "RATE_LIMITED")
    assert body["details"]["limit"] == 5
    assert body["details"]["available_at"]
    # A refused attempt is not counted, so the limit lifts once the old attempts age out.
    assert attempts(db, candidate.user.id) == 5
    db.expire_all()
    assert db.get(Candidate, candidate.id).fsp_id is None


def test_attempts_older_than_an_hour_do_not_count(client, db, demo):
    candidate, headers = demo
    old = utcnow() - timedelta(hours=1, minutes=1)
    db.add_all([LinkAttempt(user_id=candidate.user.id, created_at=old) for _ in range(9)])
    db.commit()

    assert link(client, headers).status_code == 200


def test_four_recent_attempts_still_allow_the_fifth(client, db, demo):
    candidate, headers = demo
    db.add_all([LinkAttempt(user_id=candidate.user.id, created_at=utcnow()) for _ in range(4)])
    db.commit()

    assert link(client, headers).status_code == 200


def test_the_limit_is_per_user(client, db, demo, make_candidate, headers_for):
    candidate, headers = demo
    db.add_all([LinkAttempt(user_id=candidate.user.id, created_at=utcnow()) for _ in range(5)])
    db.commit()
    other = make_candidate(full_name="Журавлёва Марина Дмитриевна", birth_date=date(2000, 8, 21))

    assert link(client, headers).status_code == 429
    assert link(client, headers_for(other.user), "FSP-2022-00058").status_code == 200


def test_every_attempt_is_recorded_even_when_it_fails(client, db, demo):
    candidate, headers = demo

    link(client, headers, "FSP-0000-00000")
    link(client, headers, "FSP-0000-00001")
    link(client, headers)

    assert attempts(db, candidate.user.id) == 3


# --- a lost race never becomes a 500 ---------------------------------------------------------


def test_losing_the_race_for_an_id_is_fsp_already_linked(
    client, db, demo, make_candidate, monkeypatch, assert_error
):
    candidate, headers = demo
    make_candidate(email="owner@example.test", fsp_id=DEMO_ID, fsp_linked_at=utcnow())
    real_find_owner = candidate_fsp._find_owner
    calls = []

    def blind_first_time(session, fsp_id):
        calls.append(fsp_id)
        return None if len(calls) == 1 else real_find_owner(session, fsp_id)

    # The id looks free at the check and is taken by the time of the commit.
    monkeypatch.setattr(candidate_fsp, "_find_owner", blind_first_time)

    response = link(client, headers)

    body = assert_error(response, 409, "FSP_ALREADY_LINKED")
    assert body["details"] == {"linked_to_you": False}
    assert len(calls) == 2
    db.expire_all()
    assert db.get(Candidate, candidate.id).fsp_id is None
    assert fsp_facts(db, candidate.id) == []


# --- unlinking -------------------------------------------------------------------------------


def test_unlink_removes_fsp_facts_and_keeps_the_others(client, db, demo):
    candidate, headers = demo
    link(client, headers)
    client.post(
        f"{API}/candidate/achievements",
        json={"title": "Хакатон Весна", "year": 2024, "level": "regional", "result": "prize"},
        headers=headers,
    )

    response = client.delete(LINK, headers=headers)

    assert response.status_code == 200, response.text
    profile = response.json()
    assert profile["fsp"] is None
    assert [fact["source"] for fact in profile["facts"]] == ["self"]
    assert profile["category"]["achievement_points"] == 0
    assert profile["category"]["confidence_index"] == 0
    assert fsp_facts(db, candidate.id) == []
    stored = db.get(Candidate, candidate.id)
    assert stored.fsp_id is None
    assert stored.fsp_linked_at is None
    assert stored.fsp_region is None
    assert stored.category == profile["category"]


def test_unlink_unlocks_the_name_and_frees_the_id(client, make_candidate, demo, headers_for):
    _, headers = demo
    link(client, headers)
    patch = f"{API}/candidate/profile"
    assert client.patch(patch, json={"full_name": "Новое Имя"}, headers=headers).status_code == 409

    assert client.delete(LINK, headers=headers).status_code == 200

    assert client.patch(patch, json={"full_name": "Новое Имя"}, headers=headers).status_code == 200
    # The id is free again: its rightful owner (by name and birth date) can take it.
    owner = make_candidate(
        email="rightful@example.test", full_name=DEMO_NAME, birth_date=DEMO_BIRTH
    )
    assert link(client, headers_for(owner.user)).status_code == 200


def test_the_same_id_can_be_linked_again_after_unlinking(client, demo):
    _, headers = demo
    link(client, headers)
    client.delete(LINK, headers=headers)

    response = link(client, headers)

    assert response.status_code == 200, response.text
    assert response.json()["profile"]["category"]["grade"] == "junior"


def test_unlink_without_a_link_changes_nothing(client, make_candidate, headers_for):
    candidate = make_candidate(facts=[skill_fact("python", 2, "resume")], city="Казань")

    response = client.delete(LINK, headers=headers_for(candidate.user))

    assert response.status_code == 200
    assert response.json()["city"] == "Казань"
    assert len(response.json()["facts"]) == 1


def test_unlink_keeps_manual_achievements(client, db, make_candidate, headers_for):
    fact = manual_achievement_fact("u1", "Олимпиада", 2023, "national", "prize", None, None)
    candidate = make_candidate(
        facts=[fact],
        full_name=DEMO_NAME,
        birth_date=DEMO_BIRTH,
    )

    headers = headers_for(candidate.user)
    link(client, headers)
    client.delete(LINK, headers=headers)

    db.expire_all()
    kept = list(db.scalars(select(ProfileFact).where(ProfileFact.candidate_id == candidate.id)))
    assert [(f.source, f.key) for f in kept] == [("self", "manual:u1")]


# --- access and input ------------------------------------------------------------------------


def test_link_requires_a_candidate(client, employer_headers, assert_error):
    assert_error(link(client, employer_headers), 403, "FORBIDDEN")
    assert_error(client.delete(LINK, headers=employer_headers), 403, "FORBIDDEN")


def test_link_requires_a_token(client):
    assert client.post(LINK, json={"fsp_id": DEMO_ID}).status_code == 401
    assert client.delete(LINK).status_code == 401


@pytest.mark.parametrize("payload", [{}, {"fsp_id": ""}, {"fsp_id": "x" * 65}, {"fsp_id": 5}])
def test_bad_body_is_a_validation_error(client, demo, assert_error, payload):
    _, headers = demo

    assert_error(client.post(LINK, json=payload, headers=headers), 422, "VALIDATION_ERROR")
