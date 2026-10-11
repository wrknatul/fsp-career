from __future__ import annotations

import pytest

from .test_employer_kit import API, add_offer, add_vacancy, build_roster


@pytest.fixture()
def roster(make_candidate):
    return build_roster(make_candidate)


def card_url(candidate_id: int) -> str:
    return f"{API}/employer/candidates/{candidate_id}"


def test_the_card_of_a_candidate(client, employer_headers, roster):
    alexey = roster["alexey"]

    response = client.get(card_url(alexey.id), headers=employer_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "id",
        "display_name",
        "city",
        "category",
        "salary_expectation",
        "relocation",
        "fsp_linked",
        "sport_rank",
        "about",
        "facts",
        "work_formats",
        "contacts",
        "offers",
    }
    assert body["id"] == alexey.id
    assert body["display_name"] == "Алексей С."
    assert body["city"] == "Казань"
    assert body["salary_expectation"] == 120_000
    assert body["relocation"] is False
    assert body["fsp_linked"] is True
    assert body["sport_rank"] == "kms"
    assert body["about"] == "Люблю алгоритмы и backend"
    assert body["work_formats"] == ["remote", "hybrid"]
    assert body["contacts"] is None
    assert body["offers"] == []
    assert body["category"]["stack"] == "backend"
    assert body["category"]["grade"] == "middle"
    assert body["category"]["grade_explanations"]
    assert body["category"]["top_skills"]


def test_the_card_lists_all_facts_with_their_sources(client, employer_headers, roster):
    body = client.get(card_url(roster["alexey"].id), headers=employer_headers).json()

    expected = {(f.kind, f.key, f.source, f.verification) for f in roster["alexey"].facts}
    shown = {(f["kind"], f["key"], f["source"], f["verification"]) for f in body["facts"]}
    assert shown == expected
    assert len(body["facts"]) == len(roster["alexey"].facts)
    for fact in body["facts"]:
        assert set(fact) == {
            "id",
            "kind",
            "key",
            "title",
            "value",
            "source",
            "verification",
            "evidence",
            "created_at",
        }


def test_facts_come_in_the_order_they_were_stored(client, employer_headers, roster):
    facts = client.get(card_url(roster["alexey"].id), headers=employer_headers).json()["facts"]

    ids = [fact["id"] for fact in facts]
    assert ids == sorted(ids)


def test_the_card_of_a_candidate_with_a_resume_only(client, employer_headers, roster):
    body = client.get(card_url(roster["backend_junior"].id), headers=employer_headers).json()

    assert body["fsp_linked"] is False
    assert body["sport_rank"] is None
    assert body["about"] is None
    assert {f["verification"] for f in body["facts"]} == {"parsed"}


def test_a_visible_candidate_without_a_stack_has_a_card(client, employer_headers, roster):
    response = client.get(card_url(roster["no_stack"].id), headers=employer_headers)

    assert response.status_code == 200
    assert response.json()["category"]["stack"] is None
    assert response.json()["category"]["label"] == "Категория не определена"


def test_the_card_of_a_candidate_whose_category_was_not_computed(
    client, employer_headers, make_candidate
):
    fresh = make_candidate(category=None, city="Тула")

    body = client.get(card_url(fresh.id), headers=employer_headers).json()

    assert body["category"]["stack"] is None
    assert body["category"]["label"] == "Категория не определена"
    assert body["facts"] == []


def test_the_card_shows_only_offers_of_this_employer(
    client, db, employer_user, employer_headers, make_employer, roster
):
    mine = employer_user.employer
    other = make_employer(email="other.company@example.test")
    alexey = roster["alexey"]
    first = add_vacancy(db, mine, title="Первая")
    second = add_vacancy(db, mine, title="Вторая")
    foreign = add_vacancy(db, other, title="Чужая")
    add_offer(db, mine, alexey, first, status="declined", salary=100_000)
    add_offer(db, mine, alexey, second, status="sent", salary=120_000)
    add_offer(db, other, alexey, foreign, status="sent", salary=300_000)

    offers = client.get(card_url(alexey.id), headers=employer_headers).json()["offers"]

    assert [(o["vacancy_title"], o["status"], o["salary"]) for o in offers] == [
        ("Вторая", "sent", 120_000),
        ("Первая", "declined", 100_000),
    ]
    assert set(offers[0]) == {"id", "vacancy_id", "vacancy_title", "status", "salary", "created_at"}
    assert offers[0]["vacancy_id"] == second.id


def test_the_card_of_another_candidate_does_not_show_the_offer(
    client, db, employer_user, employer_headers, roster
):
    vacancy = add_vacancy(db, employer_user.employer)
    add_offer(db, employer_user.employer, roster["alexey"], vacancy)

    body = client.get(card_url(roster["backend_mid"].id), headers=employer_headers).json()

    assert body["offers"] == []


# --- hidden and missing --------------------------------------------------------------------------


def test_a_hidden_candidate_is_not_found(client, employer_headers, roster, assert_error):
    response = client.get(card_url(roster["hidden_backend"].id), headers=employer_headers)

    assert_error(response, 404, "NOT_FOUND")


def test_a_missing_candidate_is_not_found(client, employer_headers, roster, assert_error):
    response = client.get(card_url(987_654), headers=employer_headers)

    assert_error(response, 404, "NOT_FOUND")


def test_hidden_and_missing_candidates_are_indistinguishable(
    client, employer_headers, roster, assert_error
):
    hidden = client.get(card_url(roster["hidden_backend"].id), headers=employer_headers)
    missing = client.get(card_url(987_654), headers=employer_headers)

    one = assert_error(hidden, 404, "NOT_FOUND")
    two = assert_error(missing, 404, "NOT_FOUND")

    assert (one["error_code"], one["message"], one["details"]) == (
        two["error_code"],
        two["message"],
        two["details"],
    )
    assert set(one) == set(two)
    assert hidden.headers["content-type"] == missing.headers["content-type"]


@pytest.mark.parametrize("candidate_id", [0, -1, 2**31, 2**40])
def test_ids_outside_the_database_range_are_not_found(
    client, employer_headers, assert_error, candidate_id
):
    response = client.get(card_url(candidate_id), headers=employer_headers)

    assert_error(response, 404, "NOT_FOUND")


def test_a_non_numeric_id_is_a_validation_error(client, employer_headers, assert_error):
    response = client.get(f"{API}/employer/candidates/abc", headers=employer_headers)

    assert_error(response, 422, "VALIDATION_ERROR")


def test_a_candidate_who_shows_the_profile_again_is_found(
    client, db, employer_headers, roster
):
    hidden = roster["hidden_backend"]
    hidden.visible = True
    db.commit()

    assert client.get(card_url(hidden.id), headers=employer_headers).status_code == 200


# --- access --------------------------------------------------------------------------------------


def test_the_card_needs_a_token(client, roster, assert_error):
    assert_error(client.get(card_url(roster["alexey"].id)), 401, "UNAUTHORIZED")


def test_the_card_is_closed_to_candidates(client, candidate_headers, roster, assert_error):
    response = client.get(card_url(roster["alexey"].id), headers=candidate_headers)

    assert_error(response, 403, "FORBIDDEN")
