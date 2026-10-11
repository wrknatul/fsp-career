"""The unified error format (SPEC section 8) and the request-body limits of the contract."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import DataError, IntegrityError

import app.schemas as schemas
from app.core.errors import AppError
from app.domain.types import Categorization
from app.schemas.health import HealthResponse

ALLOWED_ORIGIN = "http://localhost:5173"


class ProbeBody(BaseModel):
    name: str = Field(min_length=3)
    age: int


@pytest.fixture()
def probe(api_app, client):
    """The client plus routes that fail in every interesting way."""
    router = APIRouter()

    @router.get("/probe/ok")
    def ok() -> dict[str, bool]:
        return {"ok": True}

    @router.get("/probe/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    @router.get("/probe/app-error")
    def app_error() -> None:
        raise AppError(
            "TEST_COOLDOWN",
            "Подождите немного",
            409,
            {"available_at": datetime(2026, 10, 10, 12, 0, tzinfo=UTC), "attempt": 2},
        )

    @router.get("/probe/forbidden")
    def forbidden() -> None:
        raise HTTPException(status_code=403, detail="not for you")

    @router.get("/probe/unavailable")
    def unavailable() -> None:
        raise HTTPException(status_code=503, detail="database exploded")

    @router.get("/probe/integrity")
    def integrity() -> None:
        raise IntegrityError("INSERT ...", {}, Exception("UNIQUE constraint failed"))

    @router.get("/probe/data-error")
    def data_error() -> None:
        raise DataError("INSERT ...", {}, Exception("value too long"))

    @router.get("/probe/query")
    def query(limit: int = Query(ge=1, le=5)) -> dict[str, int]:
        return {"limit": limit}

    @router.post("/probe/body")
    def body(payload: ProbeBody) -> dict[str, str]:
        return {"name": payload.name}

    @router.post("/probe/body-list")
    def body_list(payload: list[ProbeBody]) -> dict[str, int]:
        return {"count": len(payload)}

    @router.get("/probe/bad-response", response_model=HealthResponse)
    def bad_response() -> dict[str, int]:
        return {"nope": 1}

    api_app.include_router(router)
    return client


# --- 500 -------------------------------------------------------------------------------------


def test_unhandled_exception_is_a_unified_500_without_internals(probe, assert_error, caplog):
    with caplog.at_level(logging.ERROR):
        response = probe.get("/probe/boom")

    body = assert_error(response, 500, "INTERNAL_ERROR")
    assert "secret internal detail" not in response.text
    assert "RuntimeError" not in response.text
    assert body["details"] == {}
    # ...but it is in the log, together with the same trace id.
    record = next(r for r in caplog.records if body["trace_id"] in r.getMessage())
    assert record.exc_info is not None
    assert "secret internal detail" in str(record.exc_info[1])


def test_500_carries_cors_headers_for_an_allowed_origin(probe, assert_error):
    response = probe.get("/probe/boom", headers={"Origin": ALLOWED_ORIGIN})

    assert_error(response, 500, "INTERNAL_ERROR")
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "x-trace-id" in response.headers["access-control-expose-headers"].lower()


def test_500_has_no_cors_headers_for_a_foreign_origin(probe):
    response = probe.get("/probe/boom", headers={"Origin": "http://evil.example"})

    assert response.status_code == 500
    assert "access-control-allow-origin" not in response.headers


def test_invalid_response_model_is_a_unified_500(probe, assert_error):
    response = probe.get("/probe/bad-response", headers={"Origin": ALLOWED_ORIGIN})

    assert_error(response, 500, "INTERNAL_ERROR")
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_http_exception_5xx_is_hidden_behind_internal_error(probe, assert_error):
    response = probe.get("/probe/unavailable")

    assert_error(response, 503, "INTERNAL_ERROR")
    assert "exploded" not in response.text


# --- 4xx -------------------------------------------------------------------------------------


def test_validation_error_format(probe, assert_error):
    response = probe.post("/probe/body", json={"name": "ab", "age": "old"})

    body = assert_error(response, 422, "VALIDATION_ERROR")
    errors = body["details"]["errors"]
    assert [item["field"] for item in errors] == ["name", "age"]
    assert errors[0]["loc"] == ["body", "name"]
    assert errors[0]["message"] == "Минимальная длина — 3 симв."
    assert errors[1]["message"] == "Ожидается целое число"
    assert all(set(item) == {"loc", "field", "message", "type"} for item in errors)
    assert "name — Минимальная длина" in body["message"]


def test_validation_error_does_not_echo_the_input(probe):
    response = probe.post("/probe/body", json={"name": "hunter2-super-secret", "age": "x"})

    assert response.status_code == 422
    assert "hunter2-super-secret" not in response.text


def test_validation_error_for_query_parameters(probe, assert_error):
    response = probe.get("/probe/query", params={"limit": 99})

    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert body["details"]["errors"][0]["loc"] == ["query", "limit"]
    assert body["details"]["errors"][0]["message"] == "Значение должно быть не больше 5"


def test_missing_required_field(probe, assert_error):
    response = probe.post("/probe/body", json={"age": 3})

    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert body["details"]["errors"][0]["message"] == "Обязательное поле"


def test_malformed_json_body(probe, assert_error):
    response = probe.post(
        "/probe/body", content=b"{not json", headers={"Content-Type": "application/json"}
    )

    body = assert_error(response, 422, "VALIDATION_ERROR")
    # The parser's character offset must not leak into `loc`/`field`/`message` as a "field".
    (item,) = body["details"]["errors"]
    assert item["loc"] == ["body"]
    assert item["field"] == ""
    assert item["type"] == "json_invalid"
    assert body["message"] == (
        "Некорректные данные запроса: Тело запроса не является корректным JSON"
    )


def test_malformed_json_keeps_numeric_loc_parts_of_other_errors(probe, assert_error):
    # Only `json_invalid` loses its offset: a list index in a normal error is meaningful.
    response = probe.post("/probe/body-list", json=[{"name": "abc", "age": 1}, {"name": "x"}])

    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert body["details"]["errors"][0]["loc"] == ["body", 1, "name"]
    assert body["details"]["errors"][0]["field"] == "1.name"


def test_unknown_path_is_a_unified_404(probe, assert_error):
    assert_error(probe.get("/api/v1/definitely/not/here"), 404, "NOT_FOUND")


def test_wrong_method_is_a_unified_405(probe, assert_error):
    assert_error(probe.post("/probe/ok"), 405, "METHOD_NOT_ALLOWED")


def test_http_exception_4xx_is_mapped_to_a_code(probe, assert_error):
    response = probe.get("/probe/forbidden")

    assert_error(response, 403, "FORBIDDEN")
    assert "not for you" not in response.text


def test_app_error_keeps_status_code_and_details(probe, assert_error):
    response = probe.get("/probe/app-error")

    body = assert_error(response, 409, "TEST_COOLDOWN")
    assert body["message"] == "Подождите немного"
    assert body["details"] == {"available_at": "2026-10-10T12:00:00Z", "attempt": 2}


def test_integrity_error_never_becomes_a_500(probe, assert_error):
    response = probe.get("/probe/integrity", headers={"Origin": ALLOWED_ORIGIN})

    assert_error(response, 409, "CONFLICT")
    assert "UNIQUE" not in response.text
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_data_error_is_a_validation_error(probe, assert_error):
    response = probe.get("/probe/data-error")

    assert_error(response, 422, "VALIDATION_ERROR")
    assert "too long" not in response.text


# --- trace id --------------------------------------------------------------------------------


def test_trace_id_is_set_on_success_and_differs_between_requests(probe):
    first = probe.get("/probe/ok")
    second = probe.get("/probe/ok")

    assert first.status_code == second.status_code == 200
    assert uuid.UUID(first.headers["x-trace-id"])
    assert first.headers["x-trace-id"] != second.headers["x-trace-id"]


def test_client_supplied_trace_id_is_not_trusted(probe):
    response = probe.get("/probe/ok", headers={"X-Trace-Id": "evil\nvalue"})

    assert uuid.UUID(response.headers["x-trace-id"])


# --- contract limits (request bodies) ----------------------------------------------------------

CONTRACT_NAMES = [
    "User",
    "Fact",
    "CandidateProfile",
    "FspLinkResult",
    "ResumeParseResult",
    "TestInfo",
    "TestSession",
    "TestResult",
    "CandidateOffer",
    "EmployerProfile",
    "CategoryMatrix",
    "MatchQuery",
    "CandidateBrief",
    "CandidateMatch",
    "SearchResponse",
    "CandidateCard",
    "Vacancy",
    "VacancyInput",
    "EmployerOffer",
    "Dictionaries",
    "FspAthletePublic",
    "Category",
    "SkillEvidence",
    "Explanation",
]


@pytest.mark.parametrize("name", CONTRACT_NAMES)
def test_every_contract_type_has_a_schema(name):
    assert hasattr(schemas, name)


def test_category_is_the_domain_categorization():
    assert schemas.Category is Categorization


def test_test_schemas_are_not_collected_by_pytest():
    for name in ("TestInfo", "TestSession", "TestResult"):
        assert getattr(schemas, name).__test__ is False


@pytest.mark.parametrize(
    "data",
    [
        {"offset": 501},
        {"offset": -1},
        {"limit": 0},
        {"limit": 51},
        {"text": "я" * 2001},
        {"salary_max": 0},
        {"salary_max": 2**40},
        {"vacancy_id": 0},
        {"stacks": ["cobol"]},
        {"disciplines": ["chess"]},
        {"work_formats": ["moon"]},
    ],
)
def test_match_query_rejects(data):
    with pytest.raises(ValidationError):
        schemas.MatchQuery(**data)


def test_match_query_boundaries_and_defaults():
    query = schemas.MatchQuery()
    assert (query.limit, query.offset) == (20, 0)
    assert query.strict_skills is False
    assert query.fsp_verified_only is False
    assert query.confirmed_only is False
    edge = schemas.MatchQuery(limit=50, offset=500, text="я" * 2000, salary_max=1)
    assert (edge.limit, edge.offset) == (50, 500)


def test_match_query_normalizes_skills_and_converts_to_domain():
    query = schemas.MatchQuery(
        skills_required=[" Python ", "python", "SQL"], stacks=["backend", "backend"], limit=5
    )

    assert query.skills_required == ["python", "sql"]
    domain = query.to_domain()
    assert type(domain).__module__ == "app.domain.types"
    assert domain.skills_required == ["python", "sql"]
    assert domain.stacks == ["backend"]
    assert not hasattr(domain, "limit")


def vacancy(**overrides: Any) -> dict[str, Any]:
    data = {
        "title": "Python-разработчик",
        "description": "Делаем API",
        "stack": "backend",
        "grade": "junior",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "data",
    [
        {"salary_from": 0},
        {"salary_to": -5},
        {"salary_from": 200_000, "salary_to": 100_000},
        {"title": "x"},
        {"title": "  "},
        {"stack": "cobol"},
        {"grade": "guru"},
        {"team_role": "ceo"},
        {"description": "x" * 5001},
        {"skills_required": ["python"] * 40 + [f"s{i}" for i in range(40)]},
    ],
)
def test_vacancy_input_rejects(data):
    with pytest.raises(ValidationError):
        schemas.VacancyInput(**vacancy(**data))


def test_vacancy_input_defaults():
    parsed = schemas.VacancyInput(**vacancy())

    assert parsed.is_active is True
    assert parsed.team_role is None
    assert parsed.skills_required == []
    assert parsed.work_formats == []
    assert parsed.salary_from is None


def test_vacancy_patch_is_partial_and_rejects_null_for_required_fields():
    patch = schemas.VacancyPatch(salary_from=100_000, city=None)

    assert patch.model_fields_set == {"salary_from", "city"}
    for field in ("title", "stack", "grade", "is_active", "skills_required"):
        with pytest.raises(ValidationError):
            schemas.VacancyPatch(**{field: None})


@pytest.mark.parametrize(
    "data",
    [
        {"salary": 0},
        {"salary": -1},
        {"salary": 10**12},
        {"candidate_id": 0},
        {"vacancy_id": 2**40},
        {"message": "я" * 1001},
    ],
)
def test_offer_create_rejects(data):
    with pytest.raises(ValidationError):
        schemas.OfferCreate(**{"candidate_id": 1, "vacancy_id": 1, "salary": 100_000, **data})


def test_offer_create_message_limit_is_inclusive():
    offer = schemas.OfferCreate(candidate_id=1, vacancy_id=1, salary=1, message="я" * 1000)

    assert len(offer.message) == 1000


def test_offer_respond_request():
    assert schemas.OfferRespondRequest(decision="accept", comment="я" * 500).decision == "accept"
    for data in ({"decision": "maybe"}, {"decision": "accept", "comment": "я" * 501}, {}):
        with pytest.raises(ValidationError):
            schemas.OfferRespondRequest(**data)


@pytest.mark.parametrize(
    "data",
    [
        {"title": "ab"},
        {"title": "x" * 201},
        {"year": 1989},
        {"year": datetime.now(UTC).year + 1},
        {"level": "galactic"},
        {"result": "lost"},
        {"discipline": "chess"},
        {"document_url": "javascript:alert(1)"},
        {"document_url": "ftp://files.example/x"},
        {"document_url": "https://"},
    ],
)
def test_achievement_create_rejects(data):
    base = {"title": "ICPC", "year": 2024, "level": "national", "result": "prize"}
    with pytest.raises(ValidationError):
        schemas.AchievementCreate(**{**base, **data})


def test_achievement_create_accepts_the_boundaries():
    base = {"level": "national", "result": "prize"}
    assert schemas.AchievementCreate(title="abc", year=1990, **base).year == 1990
    assert schemas.AchievementCreate(title="я" * 200, year=datetime.now(UTC).year, **base)
    parsed = schemas.AchievementCreate(
        title=" ICPC ", year=2024, document_url=" https://example.test/doc ", **base
    )
    assert parsed.title == "ICPC"
    assert parsed.document_url == "https://example.test/doc"
    assert parsed.discipline is None


@pytest.mark.parametrize(
    "data",
    [
        {"salary_expectation": 0},
        {"full_name": None},
        {"visible": None},
        {"work_formats": None},
        {"work_formats": ["remote", "office", "hybrid", "remote2"]},
        {"phone": "9" * 33},
        {"about": "я" * 2001},
        {"birth_date": "2999-01-01"},
        {"birth_date": "1800-01-01"},
        {"about": "bad\x00text"},
    ],
)
def test_candidate_profile_update_rejects(data):
    with pytest.raises(ValidationError):
        schemas.CandidateProfileUpdate(**data)


def test_candidate_profile_update_allows_clearing_nullable_fields():
    patch = schemas.CandidateProfileUpdate(city=None, about="  ", salary_expectation=None)

    assert patch.model_fields_set == {"city", "about", "salary_expectation"}
    assert patch.about is None


def test_test_submit_request_limits():
    assert schemas.TestSubmitRequest(answers={"q1": 0, "q2": 3}).answers == {"q1": 0, "q2": 3}
    for answers in ({"q1": -1}, {"q1": "a"}, {"": 1}, {f"q{i}": 0 for i in range(51)}):
        with pytest.raises(ValidationError):
            schemas.TestSubmitRequest(answers=answers)
