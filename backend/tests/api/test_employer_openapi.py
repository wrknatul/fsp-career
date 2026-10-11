"""Every employer and reference route is documented in Russian with its errors (SPEC 12.3)."""

from __future__ import annotations

import json
import re

import pytest

from .test_employer_kit import API

CYRILLIC = re.compile("[А-Яа-яЁё]")

ROUTES = [
    ("get", "/reference/dictionaries", {"200"}),
    ("get", "/employer/vacancies", {"200", "401", "403"}),
    ("post", "/employer/vacancies", {"201", "401", "403", "422"}),
    ("patch", "/employer/vacancies/{vacancy_id}", {"200", "401", "403", "404", "422"}),
    ("get", "/employer/categories", {"200", "401", "403", "422"}),
    ("post", "/employer/search", {"200", "401", "403", "404", "422"}),
    ("get", "/employer/candidates/{candidate_id}", {"200", "401", "403", "404", "422"}),
    ("post", "/employer/offers", {"201", "401", "403", "404", "409", "422"}),
    ("get", "/employer/offers", {"200", "401", "403"}),
]


@pytest.fixture()
def spec(client):
    return client.get("/api/openapi.json").json()


@pytest.mark.parametrize(("method", "path", "codes"), ROUTES)
def test_route_is_documented(spec, method, path, codes):
    operation = spec["paths"][f"{API}{path}"][method]

    assert CYRILLIC.search(operation["summary"]), operation["summary"]
    assert CYRILLIC.search(operation["description"]), operation["description"]
    assert set(operation["responses"]) == codes
    for code, response in operation["responses"].items():
        assert response["description"].strip(), code
        # The default FastAPI 422 schema must not leak in: errors have one format.
        assert "HTTPValidationError" not in json.dumps(response), code
        if code.startswith(("4", "5")):
            assert response["content"]["application/json"]["schema"]["$ref"].endswith("/ApiError")


@pytest.mark.parametrize(("method", "path", "codes"), ROUTES)
def test_route_declares_a_response_model(spec, method, path, codes):
    operation = spec["paths"][f"{API}{path}"][method]
    success = operation["responses"][min(code for code in codes if code.startswith("2"))]

    schema = success["content"]["application/json"]["schema"]
    assert "$ref" in schema or "items" in schema


def test_employer_routes_are_in_the_employer_group(spec):
    for method, path, _ in ROUTES:
        tags = spec["paths"][f"{API}{path}"][method]["tags"]
        expected = "Справочники" if path.startswith("/reference") else "Работодатель"
        assert tags == [expected], path
