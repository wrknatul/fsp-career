"""`POST /candidate/achievements` and `DELETE /candidate/achievements/{id}` (SPEC section 6.4)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.timeutil import utcnow
from app.domain.facts import manual_achievement_fact, skill_fact
from app.models import Candidate, ProfileFact

API = "/api/v1"
URL = f"{API}/candidate/achievements"

PAYLOAD = {
    "title": "Заключительный этап ВсОШ по информатике",
    "year": 2023,
    "level": "national",
    "result": "prize",
    "discipline": "algorithmic",
    "document_url": "https://example.test/diploma/123",
}


def stored_facts(db, candidate_id: int) -> list[ProfileFact]:
    db.expire_all()
    return list(
        db.scalars(
            select(ProfileFact)
            .where(ProfileFact.candidate_id == candidate_id)
            .order_by(ProfileFact.id)
        )
    )


@pytest.fixture()
def me(candidate_user, candidate_headers):
    return candidate_user.candidate, candidate_headers


# --- adding ----------------------------------------------------------------------------------


def test_add_an_achievement(client, db, me):
    candidate, headers = me

    response = client.post(URL, json=PAYLOAD, headers=headers)

    assert response.status_code == 201, response.text
    profile = response.json()
    assert len(profile["facts"]) == 1
    fact = profile["facts"][0]
    assert fact["kind"] == "achievement"
    assert fact["source"] == "self"
    assert fact["verification"] == "declared"
    assert fact["key"].startswith("manual:")
    assert fact["title"] == "Заключительный этап ВсОШ по информатике, 2023 — призёр"
    assert fact["evidence"] == "https://example.test/diploma/123"
    assert fact["value"] == {
        "title": "Заключительный этап ВсОШ по информатике",
        "discipline": "algorithmic",
        "level": "national",
        "place": None,
        "result": "prize",
        "date": None,
        "year": 2023,
        "team_name": None,
        "team_role": None,
        "participants_total": None,
        "document_url": "https://example.test/diploma/123",
    }
    # 35% of a national prize: 14 * 0.8 * 0.35.
    category = profile["category"]
    assert category["grade_points"] == 3.9
    explanation = category["grade_explanations"][0]
    assert (explanation["source"], explanation["verification"]) == ("self", "declared")
    assert explanation["points"] == pytest.approx(3.92)
    db.expire_all()
    stored = stored_facts(db, candidate.id)
    assert [(f.source, f.verification) for f in stored] == [("self", "declared")]
    assert db.get(Candidate, candidate.id).category == category
    assert len(db.get(Candidate, candidate.id).embedding) == 384


def test_optional_fields_may_be_left_out(client, me):
    _, headers = me

    response = client.post(
        URL,
        json={
            "title": "Хакатон «Весна»",
            "year": 2024,
            "level": "regional",
            "result": "participant",
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text
    fact = response.json()["facts"][0]
    assert fact["value"]["discipline"] is None
    assert fact["value"]["document_url"] is None
    assert fact["evidence"] is None


def test_the_same_achievement_can_be_added_twice(client, db, me):
    candidate, headers = me

    first = client.post(URL, json=PAYLOAD, headers=headers).json()
    second = client.post(URL, json=PAYLOAD, headers=headers).json()

    assert len(second["facts"]) == 2
    assert len({fact["key"] for fact in second["facts"]}) == 2
    assert second["category"]["grade_points"] > first["category"]["grade_points"]


def test_an_achievement_lifts_the_grade_with_a_discount(client, make_candidate, headers_for):
    candidate = make_candidate(
        facts=[skill_fact("python", 2, "test"), skill_fact("fastapi", 2, "test")]
    )
    headers = headers_for(candidate.user)
    # The factory does not compute the category: ask the API to, with a harmless change.
    before = client.patch(
        f"{API}/candidate/profile", json={"relocation": True}, headers=headers
    ).json()["category"]

    after = client.post(URL, json=PAYLOAD, headers=headers).json()["category"]

    assert after["stack"] == "backend"
    # A national prize is worth 14 * 0.8 = 11.2 points to the FSP, a declared one 35% of that.
    assert after["grade_points"] - before["grade_points"] == pytest.approx(3.92, abs=0.1)
    assert after["achievement_points"] == before["achievement_points"] == 0
    assert after["confidence_index"] == before["confidence_index"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "ab"},
        {"title": "  "},
        {"title": "я" * 201},
        {"year": 1989},
        {"year": 3000},
        {"year": "прошлый"},
        {"level": "galactic"},
        {"result": "winner-ish"},
        {"discipline": "chess"},
        {"document_url": "javascript:alert(1)"},
        {"document_url": "ftp://example.test/x"},
        {"document_url": "http://" + "a" * 500},
    ],
)
def test_bad_values_are_refused(client, db, me, assert_error, overrides):
    candidate, headers = me

    response = client.post(URL, json={**PAYLOAD, **overrides}, headers=headers)

    assert_error(response, 422, "VALIDATION_ERROR")
    assert stored_facts(db, candidate.id) == []


@pytest.mark.parametrize("missing", ["title", "year", "level", "result"])
def test_required_fields(client, me, assert_error, missing):
    _, headers = me
    payload = {key: value for key, value in PAYLOAD.items() if key != missing}

    assert_error(client.post(URL, json=payload, headers=headers), 422, "VALIDATION_ERROR")


def test_this_year_is_allowed(client, me):
    _, headers = me

    response = client.post(URL, json={**PAYLOAD, "year": utcnow().year}, headers=headers)

    assert response.status_code == 201


# --- deleting --------------------------------------------------------------------------------


def test_delete_your_own_achievement(client, db, me):
    candidate, headers = me
    profile = client.post(URL, json=PAYLOAD, headers=headers).json()
    fact_id = profile["facts"][0]["id"]

    response = client.delete(f"{URL}/{fact_id}", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["facts"] == []
    assert body["category"]["grade_points"] == 0
    assert stored_facts(db, candidate.id) == []
    assert db.get(Candidate, candidate.id).category == body["category"]


def test_delete_keeps_the_other_facts(client, db, make_candidate, headers_for):
    keep = manual_achievement_fact("keep", "Хакатон", 2022, "regional", "winner", None, None)
    candidate = make_candidate(facts=[skill_fact("python", 2, "resume"), keep])
    headers = headers_for(candidate.user)
    profile = client.post(URL, json=PAYLOAD, headers=headers).json()
    new_id = next(
        f["id"]
        for f in profile["facts"]
        if f["key"].startswith("manual:") and f["key"] != "manual:keep"
    )

    body = client.delete(f"{URL}/{new_id}", headers=headers).json()

    assert sorted(f["key"] for f in body["facts"]) == ["manual:keep", "python"]


def test_cannot_delete_somebody_elses_achievement(
    client, db, make_candidate, headers_for, me, assert_error
):
    owner, owner_headers = me
    fact_id = client.post(URL, json=PAYLOAD, headers=owner_headers).json()["facts"][0]["id"]
    thief = make_candidate(email="thief@example.test")

    response = client.delete(f"{URL}/{fact_id}", headers=headers_for(thief.user))

    assert_error(response, 404, "NOT_FOUND")
    assert len(stored_facts(db, owner.id)) == 1


@pytest.mark.parametrize(
    "fact",
    [
        skill_fact("python", 2, "resume"),
        skill_fact("python", 2, "test"),
        skill_fact("algorithms", 3, "fsp"),
    ],
    ids=["resume", "test", "fsp"],
)
def test_cannot_delete_facts_that_are_not_self_declared(
    client, db, make_candidate, headers_for, assert_error, fact
):
    candidate = make_candidate(facts=[fact])
    fact_id = stored_facts(db, candidate.id)[0].id

    response = client.delete(f"{URL}/{fact_id}", headers=headers_for(candidate.user))

    assert_error(response, 404, "NOT_FOUND")
    assert len(stored_facts(db, candidate.id)) == 1


@pytest.mark.parametrize("fact_id", [0, 999999, 10**15])
def test_no_such_achievement(client, me, assert_error, fact_id):
    _, headers = me

    assert_error(client.delete(f"{URL}/{fact_id}", headers=headers), 404, "NOT_FOUND")


def test_delete_twice(client, me, assert_error):
    _, headers = me
    fact_id = client.post(URL, json=PAYLOAD, headers=headers).json()["facts"][0]["id"]
    assert client.delete(f"{URL}/{fact_id}", headers=headers).status_code == 200

    assert_error(client.delete(f"{URL}/{fact_id}", headers=headers), 404, "NOT_FOUND")


# --- access ----------------------------------------------------------------------------------


def test_achievements_are_for_candidates(client, employer_headers, assert_error):
    assert_error(client.post(URL, json=PAYLOAD, headers=employer_headers), 403, "FORBIDDEN")
    assert_error(client.delete(f"{URL}/1", headers=employer_headers), 403, "FORBIDDEN")


def test_achievements_need_a_token(client):
    assert client.post(URL, json=PAYLOAD).status_code == 401
    assert client.delete(f"{URL}/1").status_code == 401
