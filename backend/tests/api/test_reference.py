from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain import ontology
from app.main import create_app

from .test_employer_kit import API

URL = f"{API}/reference/dictionaries"

SECTIONS = {
    "stacks",
    "grades",
    "team_roles",
    "work_formats",
    "sources",
    "verifications",
    "disciplines",
    "competition_levels",
    "sport_ranks",
    "skills",
    "cities",
    "fsp_registry_mode",
}


def test_dictionaries_need_no_authorization(client):
    response = client.get(URL)

    assert response.status_code == 200, response.text
    assert set(response.json()) == SECTIONS


def test_dictionaries_ignore_a_broken_token(client):
    response = client.get(URL, headers={"Authorization": "Bearer not-a-token"})

    assert response.status_code == 200


def test_dictionaries_hold_the_official_ids_in_the_official_order(client):
    body = client.get(URL).json()

    assert [item["id"] for item in body["stacks"]] == [
        "backend",
        "frontend",
        "fullstack",
        "mobile",
        "ml",
        "devops",
        "security",
        "embedded",
        "qa",
        "analyst",
    ]
    assert [item["id"] for item in body["grades"]] == ["intern", "junior", "middle", "senior"]
    assert [item["id"] for item in body["team_roles"]] == [
        "lead",
        "developer",
        "researcher",
        "devops",
        "qa",
        "analyst",
    ]
    assert [item["id"] for item in body["work_formats"]] == ["remote", "office", "hybrid"]
    assert [item["id"] for item in body["sources"]] == ["fsp", "test", "resume", "self"]
    assert [item["id"] for item in body["disciplines"]] == [
        "algorithmic",
        "product",
        "security",
        "robotics",
        "uav",
    ]
    assert [item["id"] for item in body["competition_levels"]] == [
        "municipal",
        "regional",
        "district",
        "national",
        "international",
    ]
    assert [item["id"] for item in body["sport_ranks"]] == [
        "third",
        "second",
        "first",
        "kms",
        "ms",
    ]


def test_every_dictionary_entry_has_a_russian_title(client):
    body = client.get(URL).json()

    for section in SECTIONS - {"skills", "cities", "fsp_registry_mode"}:
        for item in body[section]:
            assert set(item) >= {"id", "title"}, (section, item)
            assert item["title"].strip(), (section, item)


def test_verifications_carry_their_weights(client):
    body = client.get(URL).json()

    weights = {item["id"]: item["weight"] for item in body["verifications"]}
    assert weights == {"verified": 1.0, "tested": 0.85, "parsed": 0.55, "declared": 0.35}
    titles = {item["id"]: item["title"] for item in body["verifications"]}
    assert titles["verified"] == "Подтверждено ФСП"
    assert titles["tested"] == "Подтверждено тестом"


def test_the_ontology_has_66_skills(client):
    body = client.get(URL).json()

    skills = body["skills"]
    assert len(skills) == 66
    assert len({item["id"] for item in skills}) == 66
    for item in skills:
        assert set(item) == {"id", "title", "stacks"}
        assert item["title"].strip()
        assert isinstance(item["stacks"], list)
    by_id = {item["id"]: item for item in skills}
    assert by_id["python"]["stacks"][:2] == ["backend", "ml"]
    assert by_id["git"]["stacks"] == []
    stack_ids = {item["id"] for item in body["stacks"]}
    assert all(set(item["stacks"]) <= stack_ids for item in skills)


def test_cities_are_a_list_of_names(client):
    body = client.get(URL).json()

    assert len(body["cities"]) >= 50
    assert all(isinstance(city, str) and city for city in body["cities"])
    assert "Москва" in body["cities"]


def test_dictionaries_match_the_domain(client):
    body = client.get(URL).json()

    expected = ontology.dictionaries()
    assert {key: body[key] for key in expected} == expected


def test_registry_mode_is_mock_by_default(client):
    assert client.get(URL).json()["fsp_registry_mode"] == "mock"


def test_registry_mode_follows_the_settings():
    application = create_app(Settings(FSP_REGISTRY_MODE="live"))

    response = TestClient(application).get(URL)

    assert response.status_code == 200
    assert response.json()["fsp_registry_mode"] == "live"


def test_dictionaries_are_documented_in_russian(client):
    operation = client.get("/api/openapi.json").json()["paths"][URL]["get"]

    assert operation["summary"]
    assert operation["description"]
    assert any("а" <= char <= "я" for char in operation["summary"].lower())
