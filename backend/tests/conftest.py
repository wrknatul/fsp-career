"""Shared fixtures for the API tests.

Database: SQLite in memory behind a `StaticPool` (one shared connection) with
`PRAGMA foreign_keys=ON`; the schema comes from `Base.metadata.create_all`.

How the pieces fit together:

* `db` is the test's own session. The app gets a *separate* session per request (like in
  production); both talk to the same connection. Data a test creates must be committed
  before it calls the API; the factories below commit for you.
* After every request the `client` expires everything loaded in `db`, so objects held by the
  test show what the request wrote.
* The password of every user made by the fixtures is `TEST_PASSWORD`.

Application modules are imported inside fixtures, not at import time, so the domain tests
that share this conftest do not depend on the API layer being importable.
"""

from __future__ import annotations

import itertools
import os
from collections.abc import Callable, Iterator
from functools import cache
from typing import Any

import pytest

# Must be set before any `app.*` import: the module-level settings and engine read them.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ["JWT_SECRET"] = "test-only-secret-that-is-long-enough-for-hs256"
os.environ["CORS_ORIGINS"] = "http://localhost:5173,http://localhost:8088"
os.environ["FSP_REGISTRY_MODE"] = "mock"
os.environ["FSP_MOCK_ROUTES_ENABLED"] = "true"

TEST_PASSWORD = "password123"


@cache
def _password_hash() -> str:
    from app.core.security import hash_password

    return hash_password(TEST_PASSWORD, rounds=4)


@pytest.fixture()
def test_password() -> str:
    return TEST_PASSWORD


@pytest.fixture()
def settings() -> Any:
    from app.core.config import Settings

    return Settings()


@pytest.fixture()
def engine() -> Iterator[Any]:
    from sqlalchemy import create_engine, event
    from sqlalchemy.pool import StaticPool

    import app.models  # noqa: F401  (registers the tables)
    from app.db.base import Base

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture()
def session_factory(engine: Any) -> Any:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def db(session_factory: Any) -> Iterator[Any]:
    session = session_factory()
    yield session
    session.close()


@pytest.fixture()
def api_app(session_factory: Any, settings: Any) -> Any:
    """A fresh application whose `get_db` is bound to the test database."""
    from app.db.session import get_db
    from app.main import create_app

    application = create_app(settings)

    def override_get_db() -> Iterator[Any]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = override_get_db
    return application


def make_client(application: Any, db: Any) -> Any:
    from fastapi.testclient import TestClient

    class ExpiringClient(TestClient):
        """Expires the test session after each request so it re-reads what the API wrote."""

        def request(self, *args: Any, **kwargs: Any) -> Any:
            try:
                return super().request(*args, **kwargs)
            finally:
                db.expire_all()

    return ExpiringClient(application)


@pytest.fixture()
def client(api_app: Any, db: Any) -> Any:
    return make_client(api_app, db)


@pytest.fixture()
def make_candidate(db: Any) -> Callable[..., Any]:
    """Factory: user + candidate + facts in the database.

    ``make_candidate(email=..., full_name=..., facts=[FactData, ...], visible=True,
    category=None, **prefs)``. ``prefs`` are `Candidate` columns (city, work_formats,
    relocation, salary_expectation, about, telegram, phone, birth_date, fsp_id, ...).
    The category is *not* recomputed: ``category`` (a dict or None) is stored as given.
    """
    from app.core.timeutil import utcnow
    from app.models import Candidate, ProfileFact, User

    counter = itertools.count(1)
    allowed = {column.key for column in Candidate.__table__.columns} - {"id", "user_id"}

    def factory(
        email: str | None = None,
        full_name: str = "Иванов Иван Иванович",
        facts: list[Any] | None = None,
        visible: bool = True,
        category: dict[str, Any] | None = None,
        **prefs: Any,
    ) -> Candidate:
        unknown = set(prefs) - allowed
        if unknown:
            raise TypeError(f"unknown Candidate fields: {sorted(unknown)}")
        number = next(counter)
        now = utcnow()
        user = User(
            email=email or f"candidate{number}@example.test",
            password_hash=_password_hash(),
            role="candidate",
            full_name=full_name,
            consent_at=now,
        )
        candidate = Candidate(
            visible=visible,
            category=category,
            **{"work_formats": [], "relocation": False, **prefs},
        )
        user.candidate = candidate
        for fact in facts or []:
            candidate.facts.append(
                ProfileFact(
                    kind=fact.kind,
                    key=fact.key,
                    title=fact.title,
                    value=fact.value,
                    source=fact.source,
                    verification=fact.verification,
                    evidence=fact.evidence,
                )
            )
        db.add(user)
        db.commit()
        return candidate

    return factory


@pytest.fixture()
def make_employer(db: Any) -> Callable[..., Any]:
    """Factory: user + employer in the database.

    ``make_employer(email=..., company_name=..., full_name=..., verified=True, **fields)``;
    ``fields`` are `Employer` columns (about, website, contact_name, ...).
    """
    from app.core.timeutil import utcnow
    from app.models import Employer, User

    counter = itertools.count(1)
    allowed = {column.key for column in Employer.__table__.columns} - {"id", "user_id"}

    def factory(
        email: str | None = None,
        company_name: str = "Тестовая компания",
        full_name: str = "Петров Пётр Петрович",
        verified: bool = True,
        **fields: Any,
    ) -> Employer:
        unknown = set(fields) - allowed
        if unknown:
            raise TypeError(f"unknown Employer fields: {sorted(unknown)}")
        number = next(counter)
        address = email or f"employer{number}@example.test"
        user = User(
            email=address,
            password_hash=_password_hash(),
            role="employer",
            full_name=full_name,
            consent_at=utcnow(),
        )
        employer = Employer(
            company_name=company_name,
            verified=verified,
            **{"contact_name": full_name, "contact_email": address, **fields},
        )
        user.employer = employer
        db.add(user)
        db.commit()
        return employer

    return factory


@pytest.fixture()
def headers_for(settings: Any) -> Callable[[Any], dict[str, str]]:
    """``headers_for(user)`` -> ``{"Authorization": "Bearer <token>"}``."""
    from app.core.security import create_access_token

    def build(user: Any) -> dict[str, str]:
        token = create_access_token(user.id, user.role, settings)
        return {"Authorization": f"Bearer {token}"}

    return build


@pytest.fixture()
def assert_error() -> Callable[..., dict[str, Any]]:
    """``assert_error(response, 404, "NOT_FOUND")``: checks the unified error format.

    Verifies status, `error_code`, the exact set of keys, a Russian `message`, a UUID
    `trace_id` equal to the `X-Trace-Id` header, and returns the parsed body.
    """
    import re
    import uuid

    def check(response: Any, status: int, error_code: str) -> dict[str, Any]:
        assert response.status_code == status, response.text
        body = response.json()
        assert set(body) == {"success", "error_code", "message", "trace_id", "details"}
        assert body["success"] is False
        assert body["error_code"] == error_code
        assert re.search("[А-Яа-яЁё]", body["message"]), body["message"]
        uuid.UUID(body["trace_id"])
        assert response.headers["X-Trace-Id"] == body["trace_id"]
        assert isinstance(body["details"], dict)
        return body

    return check


@pytest.fixture()
def candidate_user(make_candidate: Callable[..., Any]) -> Any:
    """A candidate's `User`; the `Candidate` row is ``candidate_user.candidate``."""
    return make_candidate(email="candidate@example.test").user


@pytest.fixture()
def employer_user(make_employer: Callable[..., Any]) -> Any:
    """An employer's `User`; the `Employer` row is ``employer_user.employer``."""
    return make_employer(email="employer@example.test").user


@pytest.fixture()
def candidate_headers(candidate_user: Any, headers_for: Callable[[Any], dict[str, str]]) -> Any:
    return headers_for(candidate_user)


@pytest.fixture()
def employer_headers(employer_user: Any, headers_for: Callable[[Any], dict[str, str]]) -> Any:
    return headers_for(employer_user)
