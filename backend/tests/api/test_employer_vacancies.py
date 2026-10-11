from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from app.models import Vacancy

from .test_employer_kit import API, add_offer, add_vacancy, build_candidate, skills

URL = f"{API}/employer/vacancies"


def vacancy_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Python-разработчик",
        "description": "Пишем сервисы на FastAPI",
        "stack": "backend",
        "grade": "junior",
        "skills_required": ["python", "fastapi"],
        "skills_optional": ["docker"],
        "work_formats": ["remote", "hybrid"],
        "city": "Казань",
        "salary_from": 100_000,
        "salary_to": 150_000,
    }
    payload.update(overrides)
    return payload


# --- create --------------------------------------------------------------------------------------


def test_create_vacancy(client, db, employer_user, employer_headers):
    payload = vacancy_payload(team_role="developer")

    response = client.post(URL, json=payload, headers=employer_headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {
        "id",
        "title",
        "description",
        "stack",
        "grade",
        "team_role",
        "skills_required",
        "skills_optional",
        "work_formats",
        "city",
        "salary_from",
        "salary_to",
        "is_active",
        "created_at",
        "offers_count",
    }
    assert body["title"] == "Python-разработчик"
    assert body["stack"] == "backend"
    assert body["grade"] == "junior"
    assert body["team_role"] == "developer"
    assert body["skills_required"] == ["python", "fastapi"]
    assert body["skills_optional"] == ["docker"]
    assert body["work_formats"] == ["remote", "hybrid"]
    assert body["city"] == "Казань"
    assert (body["salary_from"], body["salary_to"]) == (100_000, 150_000)
    assert body["is_active"] is True
    assert body["offers_count"] == 0
    assert body["created_at"].endswith("Z") or "+" in body["created_at"]

    row = db.get(Vacancy, body["id"])
    assert row.employer_id == employer_user.employer.id
    assert row.skills_required == ["python", "fastapi"]
    assert row.is_active is True


def test_create_vacancy_applies_defaults(client, employer_headers):
    response = client.post(
        URL,
        json={
            "title": "Тестировщик",
            "description": "Ручное и автоматическое тестирование",
            "stack": "qa",
            "grade": "middle",
        },
        headers=employer_headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["team_role"] is None
    assert body["skills_required"] == []
    assert body["skills_optional"] == []
    assert body["work_formats"] == []
    assert body["city"] is None
    assert body["salary_from"] is None
    assert body["salary_to"] is None
    assert body["is_active"] is True


def test_create_vacancy_normalizes_skill_ids(client, employer_headers):
    response = client.post(
        URL,
        json=vacancy_payload(skills_required=[" Python ", "python", "FastAPI"], skills_optional=[]),
        headers=employer_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["skills_required"] == ["python", "fastapi"]


def test_create_vacancy_can_be_closed_from_the_start(client, employer_headers):
    response = client.post(URL, json=vacancy_payload(is_active=False), headers=employer_headers)

    assert response.status_code == 201
    assert response.json()["is_active"] is False


@pytest.mark.parametrize("field", ["skills_required", "skills_optional"])
def test_create_vacancy_rejects_an_unknown_skill(client, db, employer_headers, assert_error, field):
    response = client.post(
        URL, json=vacancy_payload(**{field: ["python", "cobol"]}), headers=employer_headers
    )

    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert [item["field"] for item in body["details"]["errors"]] == [field]
    assert "cobol" in body["message"] or "cobol" in body["details"]["errors"][0]["message"]
    assert db.scalar(select(Vacancy)) is None


def test_create_vacancy_reports_both_skill_fields_at_once(client, employer_headers, assert_error):
    response = client.post(
        URL,
        json=vacancy_payload(skills_required=["cobol"], skills_optional=["fortran"]),
        headers=employer_headers,
    )

    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert sorted(item["field"] for item in body["details"]["errors"]) == [
        "skills_optional",
        "skills_required",
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": ""},
        {"title": "x"},
        {"stack": "cobol"},
        {"grade": "guru"},
        {"team_role": "ceo"},
        {"work_formats": ["moon"]},
        {"salary_from": 0},
        {"salary_from": 200_000, "salary_to": 100_000},
        {"is_active": "maybe"},
    ],
)
def test_create_vacancy_validates_the_body(client, employer_headers, assert_error, overrides):
    response = client.post(URL, json=vacancy_payload(**overrides), headers=employer_headers)

    assert_error(response, 422, "VALIDATION_ERROR")


def test_create_vacancy_requires_the_required_fields(client, employer_headers, assert_error):
    response = client.post(URL, json={"title": "Только название"}, headers=employer_headers)

    body = assert_error(response, 422, "VALIDATION_ERROR")
    fields = {item["field"] for item in body["details"]["errors"]}
    assert fields >= {"description", "stack", "grade"}


# --- list ----------------------------------------------------------------------------------------


def test_list_is_empty_for_a_new_employer(client, employer_headers):
    response = client.get(URL, headers=employer_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_list_shows_only_own_vacancies_newest_first(
    client, db, employer_user, employer_headers, make_employer
):
    mine = employer_user.employer
    other = make_employer(email="other.company@example.test", company_name="Чужая компания")
    first = add_vacancy(db, mine, title="Первая")
    foreign = add_vacancy(db, other, title="Чужая")
    second = add_vacancy(db, mine, title="Вторая")
    third = add_vacancy(db, mine, title="Третья")

    response = client.get(URL, headers=employer_headers)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [third.id, second.id, first.id]
    assert foreign.id not in [item["id"] for item in response.json()]


def test_list_counts_offers_per_vacancy(
    client, db, employer_user, employer_headers, make_candidate
):
    employer = employer_user.employer
    busy = add_vacancy(db, employer, title="С офферами")
    quiet = add_vacancy(db, employer, title="Без офферов")
    for index, status in enumerate(["sent", "accepted", "declined"]):
        candidate = build_candidate(
            make_candidate,
            skills("python", "fastapi", "postgresql"),
            email=f"offer.target{index}@example.test",
        )
        add_offer(db, employer, candidate, busy, status=status)

    response = client.get(URL, headers=employer_headers)

    counts = {item["id"]: item["offers_count"] for item in response.json()}
    assert counts == {busy.id: 3, quiet.id: 0}


def test_offers_of_another_employer_are_not_counted(
    client, db, employer_user, employer_headers, make_employer, make_candidate
):
    mine = add_vacancy(db, employer_user.employer)
    other = make_employer(email="other.company@example.test")
    their_vacancy = add_vacancy(db, other)
    candidate = build_candidate(make_candidate, skills("python", "fastapi", "postgresql"))
    add_offer(db, other, candidate, their_vacancy)

    response = client.get(URL, headers=employer_headers)

    assert [(item["id"], item["offers_count"]) for item in response.json()] == [(mine.id, 0)]


# --- update --------------------------------------------------------------------------------------


def test_patch_changes_only_the_given_fields(client, db, employer_user, employer_headers):
    vacancy = add_vacancy(
        db,
        employer_user.employer,
        title="Старое название",
        grade="junior",
        skills_required=["python"],
        city="Москва",
        salary_from=100_000,
        salary_to=150_000,
    )

    response = client.patch(
        f"{URL}/{vacancy.id}",
        json={"title": "Новое название", "skills_optional": ["docker", "git"]},
        headers=employer_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == vacancy.id
    assert body["title"] == "Новое название"
    assert body["skills_optional"] == ["docker", "git"]
    assert body["grade"] == "junior"
    assert body["skills_required"] == ["python"]
    assert body["city"] == "Москва"
    assert (body["salary_from"], body["salary_to"]) == (100_000, 150_000)
    db.refresh(vacancy)
    assert vacancy.title == "Новое название"
    assert vacancy.skills_optional == ["docker", "git"]


def test_patch_with_an_empty_body_changes_nothing(client, db, employer_user, employer_headers):
    vacancy = add_vacancy(db, employer_user.employer, title="Без изменений")

    response = client.patch(f"{URL}/{vacancy.id}", json={}, headers=employer_headers)

    assert response.status_code == 200
    assert response.json()["title"] == "Без изменений"


def test_patch_can_close_and_reopen_a_vacancy(client, db, employer_user, employer_headers):
    vacancy = add_vacancy(db, employer_user.employer)

    path = f"{URL}/{vacancy.id}"

    closed = client.patch(path, json={"is_active": False}, headers=employer_headers)
    reopened = client.patch(path, json={"is_active": True}, headers=employer_headers)

    assert closed.json()["is_active"] is False
    assert reopened.json()["is_active"] is True


def test_patch_can_clear_nullable_fields(client, db, employer_user, employer_headers):
    vacancy = add_vacancy(
        db,
        employer_user.employer,
        team_role="lead",
        city="Казань",
        salary_from=100_000,
        salary_to=150_000,
    )

    response = client.patch(
        f"{URL}/{vacancy.id}",
        json={"team_role": None, "city": None, "salary_from": None, "salary_to": None},
        headers=employer_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["team_role"], body["city"], body["salary_from"], body["salary_to"]) == (
        None,
        None,
        None,
        None,
    )


def test_patch_reports_the_offers_count(
    client, db, employer_user, employer_headers, make_candidate
):
    employer = employer_user.employer
    vacancy = add_vacancy(db, employer)
    candidate = build_candidate(make_candidate, skills("python", "fastapi", "postgresql"))
    add_offer(db, employer, candidate, vacancy)

    path = f"{URL}/{vacancy.id}"

    response = client.patch(path, json={"title": "Новое"}, headers=employer_headers)

    assert response.json()["offers_count"] == 1


def test_patch_of_a_foreign_vacancy_is_not_found(
    client, db, employer_headers, make_employer, assert_error
):
    other = make_employer(email="other.company@example.test")
    foreign = add_vacancy(db, other, title="Чужая")

    path = f"{URL}/{foreign.id}"

    response = client.patch(path, json={"title": "Взлом"}, headers=employer_headers)

    assert_error(response, 404, "NOT_FOUND")
    db.refresh(foreign)
    assert foreign.title == "Чужая"


@pytest.mark.parametrize("vacancy_id", [987_654, 0, -1, 2**40])
def test_patch_of_a_missing_vacancy_is_not_found(
    client, employer_headers, assert_error, vacancy_id
):
    path = f"{URL}/{vacancy_id}"

    response = client.patch(path, json={"title": "Нет"}, headers=employer_headers)

    assert_error(response, 404, "NOT_FOUND")


def test_foreign_and_missing_vacancies_look_the_same(
    client, db, employer_headers, make_employer, assert_error
):
    foreign = add_vacancy(db, make_employer(email="other.company@example.test"))

    one = assert_error(
        client.patch(f"{URL}/{foreign.id}", json={}, headers=employer_headers), 404, "NOT_FOUND"
    )
    two = assert_error(
        client.patch(f"{URL}/987654", json={}, headers=employer_headers), 404, "NOT_FOUND"
    )

    assert (one["message"], one["details"]) == (two["message"], two["details"])


def test_patch_rejects_an_unknown_skill(client, db, employer_user, employer_headers, assert_error):
    vacancy = add_vacancy(db, employer_user.employer, skills_required=["python"])

    response = client.patch(
        f"{URL}/{vacancy.id}", json={"skills_required": ["cobol"]}, headers=employer_headers
    )

    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert [item["field"] for item in body["details"]["errors"]] == ["skills_required"]
    db.refresh(vacancy)
    assert vacancy.skills_required == ["python"]


@pytest.mark.parametrize(
    "field", ["title", "description", "stack", "grade", "skills_required", "is_active"]
)
def test_patch_rejects_null_for_required_fields(
    client, db, employer_user, employer_headers, assert_error, field
):
    vacancy = add_vacancy(db, employer_user.employer)

    response = client.patch(f"{URL}/{vacancy.id}", json={field: None}, headers=employer_headers)

    assert_error(response, 422, "VALIDATION_ERROR")


def test_patch_checks_the_salary_range_against_the_stored_value(
    client, db, employer_user, employer_headers, assert_error
):
    vacancy = add_vacancy(db, employer_user.employer, salary_from=100_000, salary_to=150_000)

    path = f"{URL}/{vacancy.id}"

    too_low = client.patch(path, json={"salary_to": 50_000}, headers=employer_headers)
    too_high = client.patch(path, json={"salary_from": 200_000}, headers=employer_headers)

    assert_error(too_low, 422, "VALIDATION_ERROR")
    assert_error(too_high, 422, "VALIDATION_ERROR")
    db.refresh(vacancy)
    assert (vacancy.salary_from, vacancy.salary_to) == (100_000, 150_000)


def test_patch_accepts_a_range_that_is_valid_after_merging(
    client, db, employer_user, employer_headers
):
    vacancy = add_vacancy(db, employer_user.employer, salary_from=100_000, salary_to=150_000)

    response = client.patch(
        f"{URL}/{vacancy.id}", json={"salary_from": 120_000}, headers=employer_headers
    )

    assert response.status_code == 200
    assert (response.json()["salary_from"], response.json()["salary_to"]) == (120_000, 150_000)


def test_patch_rejects_a_crossed_range_inside_the_body(
    client, db, employer_user, employer_headers, assert_error
):
    vacancy = add_vacancy(db, employer_user.employer)

    response = client.patch(
        f"{URL}/{vacancy.id}",
        json={"salary_from": 300_000, "salary_to": 100_000},
        headers=employer_headers,
    )

    assert_error(response, 422, "VALIDATION_ERROR")


# --- access --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", URL, None),
        ("post", URL, vacancy_payload()),
        ("patch", f"{URL}/1", {"title": "Новое"}),
    ],
)
def test_vacancy_routes_need_a_token(client, assert_error, method, path, body):
    response = client.request(method, path, json=body)

    assert_error(response, 401, "UNAUTHORIZED")


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", URL, None),
        ("post", URL, vacancy_payload()),
        ("patch", f"{URL}/1", {"title": "Новое"}),
    ],
)
def test_vacancy_routes_are_closed_to_candidates(
    client, candidate_headers, assert_error, method, path, body
):
    response = client.request(method, path, json=body, headers=candidate_headers)

    assert_error(response, 403, "FORBIDDEN")
