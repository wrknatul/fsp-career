"""Health check, OpenAPI, application start-up and the small core helpers."""

from __future__ import annotations

import logging
import re
import sys
import types
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

import app.main as main_module
from app.core.config import APP_VERSION, DEFAULT_JWT_SECRET, Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.core.timeutil import as_utc, utcnow
from app.db.session import get_db, make_engine
from app.main import create_app
from app.models import Candidate, ProfileFact, User

API = "/api/v1"


# --- /health ---------------------------------------------------------------------------------


def test_health(client):
    response = client.get(f"{API}/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": APP_VERSION, "database": "ok"}


def test_health_reports_a_broken_database_without_failing(api_app, client, caplog):
    class BrokenSession:
        def execute(self, *_args: Any, **_kwargs: Any) -> None:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        def close(self) -> None:
            pass

    api_app.dependency_overrides[get_db] = lambda: BrokenSession()

    with caplog.at_level(logging.ERROR):
        response = client.get(f"{API}/health")

    assert response.status_code == 200
    assert response.json()["database"] == "error"
    assert "connection refused" not in response.text


# --- OpenAPI ---------------------------------------------------------------------------------


def test_openapi_and_docs_are_served_under_api(client):
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/redoc").status_code == 200
    assert client.get("/openapi.json").status_code == 404


def test_core_routes_are_documented_in_russian(client):
    spec = client.get("/api/openapi.json").json()
    expected = {
        ("get", "/api/v1/health"),
        ("post", "/api/v1/auth/register"),
        ("post", "/api/v1/auth/login"),
        ("get", "/api/v1/auth/me"),
        ("get", "/api/v1/employer/profile"),
        ("get", "/api/v1/fsp-mock/athletes/{fsp_id}"),
    }
    documented = {(m, p) for p, ops in spec["paths"].items() for m in ops}
    assert expected <= documented
    for method, path in expected:
        operation = spec["paths"][path][method]
        assert re.search("[А-Яа-яЁё]", operation["summary"]), (method, path)
        assert re.search("[А-Яа-яЁё]", operation["description"]), (method, path)
        assert operation["tags"], (method, path)
        assert "200" in operation["responses"] or "201" in operation["responses"]
        for status, response in operation["responses"].items():
            if status.startswith("4"):
                assert response["content"]["application/json"]["schema"] == {
                    "$ref": "#/components/schemas/ApiError"
                }, (method, path, status)


def test_response_schemas_list_every_key_as_required(client):
    # Bodies always carry every key (nullable ones as `null`); the schema must say so, or a
    # client generated from OpenAPI types them as optional.
    from app.schemas.base import ApiModel

    schemas = client.get("/api/openapi.json").json()["components"]["schemas"]
    response_models = {cls.__name__ for cls in ApiModel.__subclasses__()}
    checked = {name: schema for name, schema in schemas.items() if name in response_models}

    # Guard against the check passing vacuously.
    assert {"EmployerProfile", "FspAthletePublic", "FspResultPublic", "HealthResponse"} <= set(
        checked
    )
    assert "AuthResponse" in checked
    for name, schema in checked.items():
        assert set(schema.get("required", [])) == set(schema["properties"]), name


def test_register_consent_is_documented_as_a_boolean(client):
    schema = client.get("/api/openapi.json").json()["components"]["schemas"]["RegisterRequest"]

    assert schema["properties"]["consent"]["type"] == "boolean"
    assert "consent" not in schema["required"]


def test_all_routes_live_under_api_v1(client):
    spec = client.get("/api/openapi.json").json()

    assert all(path.startswith("/api/v1/") for path in spec["paths"])
    tag_names = {tag["name"] for tag in spec["tags"]}
    assert {"Служебные", "Авторизация", "Соискатель", "Работодатель", "Справочники"} <= tag_names


# --- CORS ------------------------------------------------------------------------------------


def test_cors_preflight_for_an_allowed_origin(client):
    response = client.options(
        f"{API}/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    # A literal "*" would not cover Authorization in browsers: the header must be named.
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_cors_preflight_for_a_foreign_origin_is_refused(client):
    response = client.options(
        f"{API}/auth/login",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert "access-control-allow-origin" not in response.headers


# --- start-up --------------------------------------------------------------------------------


def start(settings: Settings) -> None:
    with TestClient(create_app(settings)):
        pass


def test_startup_warns_about_the_default_jwt_secret(caplog):
    with caplog.at_level(logging.WARNING, logger="app.main"):
        start(Settings(JWT_SECRET=DEFAULT_JWT_SECRET, SEED_DEMO_DATA=False))

    assert any("JWT_SECRET" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize(
    "secret",
    [
        "change-me-generate-with-openssl-rand-hex-32",  # the line from .env.example
        "Change-Me-Please-Make-This-A-Long-String-1",
        "dev-only-something-that-is-long-enough-to-pass",
        "too-short-secret",  # 16 bytes: below the HS256 minimum
        "я" * 15,  # 15 characters but 30 bytes
    ],
)
def test_startup_warns_about_a_placeholder_or_short_jwt_secret(caplog, secret):
    with caplog.at_level(logging.WARNING, logger="app.main"):
        start(Settings(JWT_SECRET=secret, SEED_DEMO_DATA=False))

    assert any("JWT_SECRET" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("secret", ["", " ", "   \t\n"])
def test_blank_jwt_secret_is_refused_at_start(secret):
    # An empty key would make every sign-in fail with a 500 after the user row is saved.
    with pytest.raises(ValidationError, match="JWT_SECRET must not be empty"):
        Settings(JWT_SECRET=secret)


def test_blank_jwt_secret_from_the_environment_is_refused(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "")

    with pytest.raises(ValidationError, match="JWT_SECRET must not be empty"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("secret", "weak"),
    [
        (DEFAULT_JWT_SECRET, True),
        ("change-me-generate-with-openssl-rand-hex-32", True),
        ("x" * 31, True),
        ("x" * 32, False),
        ("я" * 16, False),  # 16 characters, 32 bytes
        ("0123456789abcdef" * 4, False),
    ],
)
def test_uses_default_jwt_secret(secret, weak):
    assert Settings(JWT_SECRET=secret).uses_default_jwt_secret is weak


def test_startup_is_quiet_with_a_real_jwt_secret(caplog):
    with caplog.at_level(logging.WARNING, logger="app.main"):
        start(Settings(JWT_SECRET="x" * 40, SEED_DEMO_DATA=False))

    assert not [r for r in caplog.records if r.name == "app.main"]


def test_startup_survives_a_missing_seed_module(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "app.seed", None)  # makes `import app.seed` fail

    with caplog.at_level(logging.WARNING, logger="app.main"):
        start(Settings(JWT_SECRET="x" * 40, SEED_DEMO_DATA=True))

    assert any("app.seed" in record.getMessage() for record in caplog.records)


def test_startup_logs_a_broken_seed_import_with_traceback(monkeypatch, caplog):
    def broken_import(_name: str) -> None:
        raise ModuleNotFoundError("No module named 'app.services.x'", name="app.services.x")

    # Replace `importlib` inside app.main only: patching the real one would break other imports.
    fake_importlib = types.SimpleNamespace(import_module=broken_import)
    monkeypatch.setattr(main_module, "importlib", fake_importlib)

    with caplog.at_level(logging.WARNING, logger="app.main"):
        start(Settings(JWT_SECRET="x" * 40, SEED_DEMO_DATA=True))

    record = next(r for r in caplog.records if "importing app.seed failed" in r.getMessage())
    assert record.exc_info is not None


def test_startup_runs_seed_if_empty_when_enabled(monkeypatch):
    calls: list[str] = []
    fake = types.ModuleType("app.seed")
    fake.seed_if_empty = lambda: calls.append("seed")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.seed", fake)

    start(Settings(JWT_SECRET="x" * 40, SEED_DEMO_DATA=True))
    start(Settings(JWT_SECRET="x" * 40, SEED_DEMO_DATA=False))

    assert calls == ["seed"]


def test_startup_does_not_hide_a_failing_seed(monkeypatch):
    fake = types.ModuleType("app.seed")

    def broken() -> None:
        raise RuntimeError("seed broke")

    fake.seed_if_empty = broken  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.seed", fake)

    with pytest.raises(RuntimeError, match="seed broke"):
        start(Settings(JWT_SECRET="x" * 40, SEED_DEMO_DATA=True))


# --- settings --------------------------------------------------------------------------------


def test_settings_defaults_without_environment(monkeypatch):
    # conftest sets a few variables for the whole suite: start from a clean slate.
    for name in Settings.model_fields:
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.DATABASE_URL == "sqlite:///./dev.sqlite3"
    assert settings.uses_default_jwt_secret
    assert "http://localhost:5173" in settings.CORS_ORIGINS
    assert settings.JWT_TTL_MINUTES == 720
    assert settings.TEST_COOLDOWN_MINUTES == 1440
    assert settings.MAX_UPLOAD_BYTES == 2_097_152
    assert settings.FSP_REGISTRY_MODE == "mock"
    assert settings.SEED_DEMO_DATA is True
    assert settings.FSP_MOCK_ROUTES_ENABLED is True
    assert settings.BCRYPT_ROUNDS == 12


@pytest.mark.parametrize(
    "raw",
    ["http://a.test, http://b.test", '["http://a.test", "http://b.test"]'],
)
def test_cors_origins_accept_a_comma_list_and_json(monkeypatch, raw):
    monkeypatch.setenv("CORS_ORIGINS", raw)

    assert Settings(_env_file=None).CORS_ORIGINS == ["http://a.test", "http://b.test"]


def test_plain_postgres_url_uses_the_psycopg_driver():
    assert (
        Settings(DATABASE_URL="postgresql://u:p@db:5432/app").DATABASE_URL
        == "postgresql+psycopg://u:p@db:5432/app"
    )
    assert Settings(DATABASE_URL="postgresql+psycopg://u:p@db/app").DATABASE_URL.startswith(
        "postgresql+psycopg://"
    )


# --- engine ----------------------------------------------------------------------------------


def test_sqlite_engine_enforces_foreign_keys_and_shares_memory_connection():
    engine = make_engine("sqlite://")

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        connection.exec_driver_sql("CREATE TABLE t (id INTEGER)")
        connection.commit()
    with engine.connect() as connection:  # a different checkout still sees the table
        assert connection.exec_driver_sql("SELECT count(*) FROM t").scalar() == 0
    engine.dispose()


# --- time ------------------------------------------------------------------------------------


def test_utcnow_is_aware_utc():
    now = utcnow()

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_as_utc():
    naive = datetime(2026, 10, 10, 12, 0)
    moscow = datetime(2026, 10, 10, 15, 0, tzinfo=timezone(timedelta(hours=3)))

    assert as_utc(naive) == datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    assert as_utc(naive).tzinfo is not None
    assert as_utc(moscow) == datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    assert as_utc(moscow).utcoffset() == timedelta(0)
    assert as_utc(None) is None


def test_datetime_columns_come_back_aware_utc(db):
    moscow = timezone(timedelta(hours=3))
    user = User(
        email="time@example.test",
        password_hash="x",
        role="candidate",
        full_name="Время",
        consent_at=datetime(2026, 10, 10, 15, 0, tzinfo=moscow),
    )
    user.candidate = Candidate(work_formats=[], relocation=False, visible=False)
    user.candidate.facts.append(
        ProfileFact(
            kind="skill",
            key="python",
            title="Python",
            value={},
            source="self",
            verification="declared",
        )
    )
    db.add(user)
    db.commit()
    db.expire_all()

    stored = db.get(User, user.id)
    # SQLite hands back naive values; the column type turns them into aware UTC.
    assert stored.consent_at == datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    assert stored.consent_at.utcoffset() == timedelta(0)
    assert stored.created_at.tzinfo is not None
    assert stored.candidate.updated_at.tzinfo is not None
    assert stored.candidate.facts[0].created_at.tzinfo is not None


# --- security --------------------------------------------------------------------------------


def test_password_hash_roundtrip():
    hashed = hash_password("пароль-12345", rounds=4)

    assert hashed.startswith("$2")
    assert verify_password("пароль-12345", hashed)
    assert not verify_password("пароль-12346", hashed)


def test_verify_password_never_raises_on_hostile_input():
    hashed = hash_password("password123", rounds=4)

    assert not verify_password("a" * 100, hashed)
    assert not verify_password("password123", "not-a-hash")
    assert not verify_password("bad\ud800", hashed)


def test_hash_password_refuses_more_than_72_bytes():
    with pytest.raises(ValueError):
        hash_password("a" * 73, rounds=4)


def test_access_token_roundtrip(settings):
    token = create_access_token(42, "employer", settings)

    payload = decode_access_token(token, settings)

    assert payload["sub"] == "42"
    assert payload["role"] == "employer"
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "HS256"
    ttl = datetime.fromtimestamp(payload["exp"], UTC) - datetime.fromtimestamp(payload["iat"], UTC)
    assert ttl == timedelta(minutes=settings.JWT_TTL_MINUTES)


def test_access_token_with_another_secret_is_rejected(settings):
    token = create_access_token(1, "candidate", settings)
    other = Settings(JWT_SECRET="another-secret-that-is-long-enough-for-hs256")

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token, other)
