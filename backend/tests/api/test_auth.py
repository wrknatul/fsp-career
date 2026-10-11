from __future__ import annotations

from datetime import timedelta
from typing import Any

import jwt
import pytest
from fastapi import APIRouter
from sqlalchemy import func, select

from app.api import deps
from app.api.deps import CurrentCandidate, CurrentEmployer, DbSession
from app.api.routes import auth as auth_routes
from app.core.timeutil import utcnow
from app.domain.types import FactData
from app.models import Candidate, Employer, User

API = "/api/v1"


def register_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "email": "new.user@example.test",
        "password": "password123",
        "role": "candidate",
        "full_name": "Новый Пользователь",
        "consent": True,
    }
    payload.update(overrides)
    return payload


def count(db: Any, model: Any) -> int:
    return db.scalar(select(func.count()).select_from(model))


# --- registration ----------------------------------------------------------------------------


def test_register_candidate(client, db):
    response = client.post(f"{API}/auth/register", json=register_payload(show_profile=True))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"] == {
        "id": body["user"]["id"],
        "email": "new.user@example.test",
        "role": "candidate",
        "full_name": "Новый Пользователь",
    }
    candidate = db.scalar(select(Candidate))
    assert candidate.user_id == body["user"]["id"]
    assert candidate.visible is True
    assert candidate.category is None
    assert candidate.embedding is None
    assert candidate.work_formats == []
    assert candidate.relocation is False
    assert candidate.fsp_id is None
    user = db.get(User, body["user"]["id"])
    assert user.consent_at is not None
    assert user.consent_at.tzinfo is not None
    assert user.password_hash != "password123"


def test_register_candidate_is_hidden_by_default(client, db):
    assert client.post(f"{API}/auth/register", json=register_payload()).status_code == 201

    assert db.scalar(select(Candidate)).visible is False


def test_register_token_works_right_away(client):
    body = client.post(f"{API}/auth/register", json=register_payload()).json()

    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})

    assert me.status_code == 200
    assert me.json() == body["user"]


def test_register_employer(client, db):
    response = client.post(
        f"{API}/auth/register",
        json=register_payload(
            role="employer",
            email="hr@company.test",
            full_name="Анна Кадрова",
            company_name="  Северный код  ",
            show_profile=True,
        ),
    )

    assert response.status_code == 201, response.text
    assert response.json()["user"]["role"] == "employer"
    employer = db.scalar(select(Employer))
    assert employer.company_name == "Северный код"
    assert employer.verified is False
    assert employer.contact_name == "Анна Кадрова"
    assert employer.contact_email == "hr@company.test"
    assert count(db, Candidate) == 0


def test_register_employer_requires_company_name(client, db, assert_error):
    response = client.post(f"{API}/auth/register", json=register_payload(role="employer"))

    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert [item["field"] for item in body["details"]["errors"]] == ["company_name"]
    assert body["details"]["errors"][0]["loc"] == ["body", "company_name"]
    assert count(db, User) == 0


@pytest.mark.parametrize("company_name", ["", "   ", None])
def test_register_employer_blank_company_name(client, assert_error, company_name):
    response = client.post(
        f"{API}/auth/register",
        json=register_payload(role="employer", company_name=company_name),
    )

    assert_error(response, 422, "VALIDATION_ERROR")


@pytest.mark.parametrize(
    "extra",
    [
        {"consent": False},
        {},
        # The contract: anything that is not `true` is CONSENT_REQUIRED, not a type error.
        {"consent": None},
        {"consent": "true"},
        {"consent": "yes"},
        {"consent": 1},
        {"consent": 0},
        {"consent": []},
    ],
    ids=["false", "absent", "null", "string-true", "string-yes", "one", "zero", "list"],
)
def test_register_requires_consent(client, db, assert_error, extra):
    payload = register_payload()
    payload.pop("consent")
    payload.update(extra)

    response = client.post(f"{API}/auth/register", json=payload)

    assert_error(response, 422, "CONSENT_REQUIRED")
    assert count(db, User) == 0


def test_register_employer_requires_consent_too(client, assert_error):
    response = client.post(
        f"{API}/auth/register",
        json=register_payload(role="employer", company_name="ООО", consent=False),
    )

    assert_error(response, 422, "CONSENT_REQUIRED")


def test_register_normalizes_email(client, db):
    response = client.post(
        f"{API}/auth/register", json=register_payload(email="  New.User@Example.TEST ")
    )

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "new.user@example.test"
    assert db.scalar(select(User)).email == "new.user@example.test"


def test_register_email_taken_ignores_case(client, db, assert_error):
    assert client.post(f"{API}/auth/register", json=register_payload()).status_code == 201

    response = client.post(
        f"{API}/auth/register", json=register_payload(email="NEW.USER@example.test")
    )

    assert_error(response, 409, "EMAIL_TAKEN")
    assert count(db, User) == 1


def test_register_email_taken_across_roles(client, assert_error):
    client.post(f"{API}/auth/register", json=register_payload())

    response = client.post(
        f"{API}/auth/register",
        json=register_payload(role="employer", company_name="ООО Ромашка"),
    )

    assert_error(response, 409, "EMAIL_TAKEN")


def test_register_lost_race_is_email_taken_not_500(client, db, monkeypatch, assert_error):
    # The pre-check passes (as if a parallel request had not committed yet) and the unique
    # constraint fires on commit: this must not become a 500.
    client.post(f"{API}/auth/register", json=register_payload())
    monkeypatch.setattr(auth_routes, "_find_user_by_email", lambda _db, _email: None)

    response = client.post(f"{API}/auth/register", json=register_payload())

    assert_error(response, 409, "EMAIL_TAKEN")
    assert count(db, User) == 1
    assert count(db, Candidate) == 1


@pytest.mark.parametrize(
    ("password", "ok"),
    [
        ("1234567", False),
        ("12345678", True),
        ("a" * 72, True),
        ("a" * 73, False),
        ("я" * 36, True),  # 72 bytes
        ("я" * 37, False),  # 74 bytes although only 37 characters
        ("пароль", True),  # 6 characters but 12 bytes
        ("яяя", False),  # 6 bytes
    ],
)
def test_register_password_length_is_counted_in_bytes(client, password, ok):
    response = client.post(f"{API}/auth/register", json=register_payload(password=password))

    assert response.status_code == (201 if ok else 422), response.text


def test_register_long_cyrillic_password_can_log_in(client):
    password = "я" * 36
    client.post(f"{API}/auth/register", json=register_payload(password=password))

    response = client.post(
        f"{API}/auth/login", json={"email": "new.user@example.test", "password": password}
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "email",
    [
        "plainaddress",
        "a@b",
        "a@@b.test",
        "a b@c.test",
        "@c.test",
        "a@.test",
        "a@c..test",
        "x" * 250 + "@a.test",
    ],
)
def test_register_rejects_malformed_email(client, assert_error, email):
    response = client.post(f"{API}/auth/register", json=register_payload(email=email))

    assert_error(response, 422, "VALIDATION_ERROR")


def test_register_accepts_reserved_demo_domain(client):
    response = client.post(
        f"{API}/auth/register", json=register_payload(email="demo.candidate@fsp-career.test")
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "overrides",
    [
        {"role": "admin"},
        {"full_name": "   "},
        {"full_name": "x" * 201},
        {"full_name": "Bad\x00Name"},
        {"show_profile": "yes"},
    ],
)
def test_register_rejects_bad_fields(client, db, assert_error, overrides):
    response = client.post(f"{API}/auth/register", json=register_payload(**overrides))

    assert_error(response, 422, "VALIDATION_ERROR")
    assert count(db, User) == 0


def test_register_does_not_leak_password_in_errors(client):
    response = client.post(
        f"{API}/auth/register", json=register_payload(password="short", role="bogus")
    )

    assert response.status_code == 422
    assert "short" not in response.text


# --- login -----------------------------------------------------------------------------------


def test_login(client, candidate_user, test_password):
    response = client.post(
        f"{API}/auth/login", json={"email": "candidate@example.test", "password": test_password}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["id"] == candidate_user.id
    assert body["user"]["role"] == "candidate"
    payload = jwt.decode(body["access_token"], options={"verify_signature": False})
    assert payload["sub"] == str(candidate_user.id)


def test_login_ignores_email_case_and_spaces(client, candidate_user, test_password):
    response = client.post(
        f"{API}/auth/login", json={"email": " CANDIDATE@Example.test ", "password": test_password}
    )

    assert response.status_code == 200


def test_login_wrong_password(client, candidate_user, assert_error):
    response = client.post(
        f"{API}/auth/login", json={"email": "candidate@example.test", "password": "wrong-password"}
    )

    assert_error(response, 401, "INVALID_CREDENTIALS")


def test_login_unknown_email_looks_the_same(client, candidate_user, assert_error):
    wrong = client.post(
        f"{API}/auth/login", json={"email": "candidate@example.test", "password": "wrong-password"}
    )
    unknown = client.post(
        f"{API}/auth/login", json={"email": "nobody@example.test", "password": "wrong-password"}
    )

    first = assert_error(wrong, 401, "INVALID_CREDENTIALS")
    second = assert_error(unknown, 401, "INVALID_CREDENTIALS")
    assert first["message"] == second["message"]


def test_login_with_overlong_password_is_a_401_not_a_500(client, candidate_user, assert_error):
    for email in ("candidate@example.test", "nobody@example.test"):
        response = client.post(f"{API}/auth/login", json={"email": email, "password": "a" * 200})

        assert_error(response, 401, "INVALID_CREDENTIALS")


def test_login_missing_fields(client, assert_error):
    response = client.post(f"{API}/auth/login", json={"email": "a@b.test"})

    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert body["details"]["errors"][0]["field"] == "password"


# --- /auth/me and token checks -----------------------------------------------------------------


def test_me(client, candidate_user, candidate_headers):
    response = client.get(f"{API}/auth/me", headers=candidate_headers)

    assert response.status_code == 200
    assert response.json() == {
        "id": candidate_user.id,
        "email": "candidate@example.test",
        "role": "candidate",
        "full_name": "Иванов Иван Иванович",
    }


def test_me_without_token_is_401_in_unified_format(client, assert_error):
    response = client.get(f"{API}/auth/me")

    assert_error(response, 401, "UNAUTHORIZED")
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "header",
    ["Bearer", "Bearer garbage", "Bearer a.b.c", "Basic Zm9vOmJhcg==", "Token abc", ""],
)
def test_me_with_bad_authorization_header(client, assert_error, header):
    response = client.get(f"{API}/auth/me", headers={"Authorization": header})

    assert_error(response, 401, "UNAUTHORIZED")


def test_me_with_expired_token(client, candidate_user, settings, assert_error):
    now = utcnow()
    token = jwt.encode(
        {
            "sub": str(candidate_user.id),
            "role": "candidate",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        },
        settings.JWT_SECRET,
        algorithm="HS256",
    )

    response = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert_error(response, 401, "UNAUTHORIZED")


def test_me_with_token_signed_by_someone_else(client, candidate_user, assert_error):
    token = jwt.encode(
        {"sub": str(candidate_user.id), "exp": utcnow() + timedelta(hours=1)},
        "another-secret-that-is-long-enough-for-hs256",
        algorithm="HS256",
    )

    response = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert_error(response, 401, "UNAUTHORIZED")


def test_me_with_unsigned_token(client, candidate_user, assert_error):
    token = jwt.encode(
        {"sub": str(candidate_user.id), "exp": utcnow() + timedelta(hours=1)},
        None,
        algorithm="none",
    )

    response = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert_error(response, 401, "UNAUTHORIZED")


@pytest.mark.parametrize("claims", [{}, {"sub": "not-a-number"}, {"sub": "999999"}])
def test_me_with_token_that_points_nowhere(client, settings, assert_error, claims):
    token = jwt.encode(
        {**claims, "exp": utcnow() + timedelta(hours=1)}, settings.JWT_SECRET, algorithm="HS256"
    )

    response = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert_error(response, 401, "UNAUTHORIZED")


def test_token_of_deleted_user_stops_working(
    client, db, candidate_user, candidate_headers, assert_error
):
    db.delete(candidate_user)
    db.commit()

    response = client.get(f"{API}/auth/me", headers=candidate_headers)

    assert_error(response, 401, "UNAUTHORIZED")


# --- roles -----------------------------------------------------------------------------------


@pytest.fixture()
def role_client(api_app, client):
    """The client plus two probe routes guarded by `require_candidate` / `require_employer`."""
    router = APIRouter()

    @router.get("/probe/candidate")
    def candidate_probe(candidate: CurrentCandidate) -> dict[str, Any]:
        return {"candidate_id": candidate.id, "type": type(candidate).__name__}

    @router.get("/probe/employer")
    def employer_probe(employer: CurrentEmployer) -> dict[str, Any]:
        return {"employer_id": employer.id, "type": type(employer).__name__}

    api_app.include_router(router)
    return client


def test_require_candidate_returns_the_candidate_row(
    role_client, candidate_user, candidate_headers
):
    response = role_client.get("/probe/candidate", headers=candidate_headers)

    assert response.status_code == 200
    assert response.json() == {"candidate_id": candidate_user.candidate.id, "type": "Candidate"}


def test_require_employer_returns_the_employer_row(role_client, employer_user, employer_headers):
    response = role_client.get("/probe/employer", headers=employer_headers)

    assert response.status_code == 200
    assert response.json() == {"employer_id": employer_user.employer.id, "type": "Employer"}


def test_candidate_cannot_use_employer_routes(
    role_client, candidate_user, candidate_headers, assert_error
):
    assert_error(role_client.get("/probe/employer", headers=candidate_headers), 403, "FORBIDDEN")
    real_route = role_client.get(f"{API}/employer/profile", headers=candidate_headers)
    assert_error(real_route, 403, "FORBIDDEN")


def test_employer_cannot_use_candidate_routes(
    role_client, employer_user, employer_headers, assert_error
):
    assert_error(role_client.get("/probe/candidate", headers=employer_headers), 403, "FORBIDDEN")


def test_role_routes_without_token_are_401_not_403(role_client, assert_error):
    assert_error(role_client.get("/probe/candidate"), 401, "UNAUTHORIZED")
    assert_error(role_client.get("/probe/employer"), 401, "UNAUTHORIZED")


def test_missing_candidate_row_is_a_clean_404(
    role_client, db, candidate_user, candidate_headers, assert_error
):
    db.delete(candidate_user.candidate)
    db.commit()

    response = role_client.get("/probe/candidate", headers=candidate_headers)

    assert_error(response, 404, "NOT_FOUND")


# --- employer profile --------------------------------------------------------------------------


def test_employer_profile(client, employer_user, employer_headers):
    response = client.get(f"{API}/employer/profile", headers=employer_headers)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": employer_user.employer.id,
        "user": {
            "id": employer_user.id,
            "email": "employer@example.test",
            "role": "employer",
            "full_name": "Петров Пётр Петрович",
        },
        "company_name": "Тестовая компания",
        "about": None,
        "website": None,
        "contact_name": "Петров Пётр Петрович",
        "contact_email": "employer@example.test",
        "contact_telegram": None,
        "verified": True,
    }


def test_employer_profile_requires_auth(client, assert_error):
    assert_error(client.get(f"{API}/employer/profile"), 401, "UNAUTHORIZED")


def test_deps_module_exposes_the_documented_names():
    for name in ("get_current_user", "require_candidate", "require_employer", "get_app_settings"):
        assert callable(getattr(deps, name))


# --- the test fixtures themselves (other test modules rely on them) -------------------------------


def test_make_candidate_stores_facts_category_and_prefs(make_candidate, db):
    fact = FactData(
        kind="skill",
        key="python",
        title="Python",
        value={"level": 2},
        source="test",
        verification="tested",
        evidence="ok",
    )
    category = {"stack": "backend", "grade": "junior"}

    created = make_candidate(
        email="Fixture@Example.test",
        full_name="Пётр Первый",
        facts=[fact],
        visible=False,
        category=category,
        city="Казань",
        work_formats=["remote"],
        salary_expectation=150_000,
    )

    db.expire_all()
    stored = db.get(Candidate, created.id)
    assert stored.visible is False
    assert stored.category == category  # stored as given, never recomputed
    assert (stored.city, stored.work_formats, stored.salary_expectation) == (
        "Казань",
        ["remote"],
        150_000,
    )
    assert stored.user.email == "fixture@example.test"
    assert stored.user.full_name == "Пётр Первый"
    assert [(f.key, f.source, f.verification, f.value, f.evidence) for f in stored.facts] == [
        ("python", "test", "tested", {"level": 2}, "ok")
    ]


def test_make_candidate_defaults(make_candidate, db):
    first = make_candidate()
    second = make_candidate()

    assert first.visible is True
    assert first.category is None
    assert first.user.email != second.user.email
    query = "SELECT count(*) FROM candidates WHERE category IS NULL"
    assert db.connection().exec_driver_sql(query).scalar() == 2


def test_factories_reject_unknown_fields(make_candidate, make_employer):
    with pytest.raises(TypeError):
        make_candidate(cty="Казань")
    with pytest.raises(TypeError):
        make_employer(compan="x")


def test_make_employer(make_employer, db):
    employer = make_employer(email="boss@example.test", company_name="Ромашка", verified=False)

    db.expire_all()
    stored = db.get(Employer, employer.id)
    assert stored.company_name == "Ромашка"
    assert stored.verified is False
    assert stored.user.role == "employer"


def test_client_expires_objects_held_by_the_test(
    api_app, client, candidate_user, candidate_headers
):
    router = APIRouter()

    @router.post("/probe/city")
    def set_city(candidate: CurrentCandidate, db: DbSession) -> None:
        candidate.city = "Уфа"
        db.commit()

    api_app.include_router(router)
    held = candidate_user.candidate
    assert held.city is None

    assert client.post("/probe/city", headers=candidate_headers).status_code == 200

    assert held.city == "Уфа"  # no refresh needed in the test
