"""The mock FSP registry: data, generator and the public route."""

from __future__ import annotations

import json
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.fsp_registry.client import get_registry, short_name
from app.fsp_registry.generate import (
    ATHLETES_TOTAL,
    DEMO_FSP_ID,
    OUTPUT_PATH,
    build_registry,
    render,
)
from app.fsp_registry.mock import MockFspRegistry, normalize_fsp_id
from app.main import create_app

API = "/api/v1"
DISCIPLINES = {"algorithmic", "product", "security", "robotics", "uav"}
LEVELS = {"municipal", "regional", "district", "national", "international"}
RANKS = {"third", "second", "first", "kms", "ms"}


@pytest.fixture(scope="module")
def registry() -> MockFspRegistry:
    return MockFspRegistry()


# --- the data file ---------------------------------------------------------------------------


def test_registry_file_matches_the_generator():
    assert OUTPUT_PATH.read_text(encoding="utf-8") == render(build_registry())


def test_generator_is_deterministic():
    assert render(build_registry()) == render(build_registry())


def test_registry_shape(registry):
    athletes = registry.athletes()
    results = [r for a in athletes for r in a["results"]]
    competitions = {r["competition"]["competition_id"]: r["competition"] for r in results}

    assert len(athletes) == ATHLETES_TOTAL == 24
    assert 14 <= len(competitions) <= 18
    assert {c["discipline"] for c in competitions.values()} == DISCIPLINES
    assert {c["level"] for c in competitions.values()} == LEVELS
    assert {rank["rank"] for a in athletes for rank in a["ranks"]} == RANKS
    assert all(a["results"] for a in athletes)
    assert len({a["fsp_id"] for a in athletes}) == 24
    assert len({a["full_name"] for a in athletes}) == 24
    assert len({r["result_id"] for r in results}) == len(results)


def test_registry_records_follow_the_spec(registry):
    for athlete in registry.athletes():
        assert set(athlete) == {
            "fsp_id", "full_name", "birth_date", "region", "city", "ranks", "results"
        }  # fmt: skip
        for rank in athlete["ranks"]:
            assert set(rank) == {"rank", "discipline", "assigned_at", "order_no"}
        for result in athlete["results"]:
            assert set(result) == {
                "result_id", "competition", "place", "team_name", "team_role", "protocol_url"
            }  # fmt: skip
            competition = result["competition"]
            assert set(competition) == {
                "competition_id", "title", "discipline", "level", "kind", "date_start",
                "date_end", "city", "format", "participants_total",
            }  # fmt: skip
            assert competition["date_start"] <= competition["date_end"]
            assert 1 <= result["place"] <= competition["participants_total"]
            assert result["protocol_url"].startswith("https://fsp.example/protocols/")
            if competition["format"] == "individual":
                assert result["team_name"] is None
                assert result["team_role"] is None
            else:
                assert result["team_name"]


def test_demo_athlete_is_in_the_registry(registry):
    athlete = registry.get_athlete("FSP-2024-00117")

    assert athlete is not None
    assert athlete["fsp_id"] == DEMO_FSP_ID
    assert athlete["full_name"] == "Смирнов Алексей Игоревич"
    assert athlete["birth_date"] == "2003-05-14"
    assert athlete["region"] == "Республика Татарстан"
    assert athlete["city"] == "Казань"
    assert [(r["rank"], r["discipline"]) for r in athlete["ranks"]] == [("kms", "algorithmic")]

    results = athlete["results"]
    assert len(results) == 6
    assert Counter(r["competition"]["level"] for r in results) == {
        "national": 2,
        "district": 2,
        "regional": 2,
    }
    national = {
        r["competition"]["discipline"]: r
        for r in results
        if r["competition"]["level"] == "national"
    }
    assert national["algorithmic"]["place"] == 3
    assert national["product"]["place"] == 2
    assert national["product"]["team_role"] == "captain"
    assert any(r["team_role"] == "backend" for r in results)


def test_get_athlete_ignores_case_spaces_and_typographic_dashes(registry):
    for variant in ("fsp-2024-00117", "  FSP-2024-00117 ", "FSP‑2024‑00117"):
        assert registry.get_athlete(variant)["fsp_id"] == "FSP-2024-00117"
    assert normalize_fsp_id(" fsp–2024-00117") == "FSP-2024-00117"


def test_get_athlete_unknown_is_none(registry):
    assert registry.get_athlete("FSP-0000-00000") is None
    assert registry.get_athlete("") is None


def test_get_athlete_returns_independent_copies(registry):
    first = registry.get_athlete(DEMO_FSP_ID)
    first["results"].clear()

    assert len(registry.get_athlete(DEMO_FSP_ID)["results"]) == 6


def test_missing_registry_file_has_a_helpful_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="generate"):
        MockFspRegistry(tmp_path / "nope.json")


def test_get_registry_in_mock_mode_returns_the_mock():
    assert isinstance(get_registry(), MockFspRegistry)


@pytest.mark.parametrize(
    ("full_name", "expected"),
    [
        ("Смирнов Алексей Игоревич", "Смирнов А. И."),
        ("Иванова анна петровна", "Иванова А. П."),
        ("Смирнов Алексей", "Смирнов А."),
        ("Смирнов", "Смирнов"),
        ("  Смирнов   Алексей   Игоревич  ", "Смирнов А. И."),
        ("", ""),
    ],
)
def test_short_name(full_name, expected):
    assert short_name(full_name) == expected


# --- the route -------------------------------------------------------------------------------


def test_route_returns_the_demo_athlete(client):
    response = client.get(f"{API}/fsp-mock/athletes/FSP-2024-00117")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fsp_id"] == "FSP-2024-00117"
    assert body["short_name"] == "Смирнов А. И."
    assert body["region"] == "Республика Татарстан"
    assert body["ranks"] == [
        {
            "rank": "kms",
            "discipline": "algorithmic",
            "assigned_at": "2024-06-15",
            "order_no": "ORD-2024-0381",
        }
    ]
    assert len(body["results"]) == 6
    first = body["results"][0]
    assert set(first) == {
        "result_id", "competition", "place", "team_name", "team_role", "protocol_url"
    }  # fmt: skip
    assert first["competition"]["city"]  # the competition's own city is part of the contract


def test_route_never_exposes_birth_date_city_or_full_name(client, registry):
    for athlete in registry.athletes():
        response = client.get(f"{API}/fsp-mock/athletes/{athlete['fsp_id']}")

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"fsp_id", "short_name", "region", "ranks", "results"}
        assert "birth_date" not in response.text
        assert athlete["birth_date"] not in response.text
        assert athlete["full_name"] not in response.text


def test_route_unknown_id_is_404(client, assert_error):
    response = client.get(f"{API}/fsp-mock/athletes/FSP-0000-00000")

    assert_error(response, 404, "FSP_ATHLETE_NOT_FOUND")


def test_route_needs_no_authorization(client):
    assert client.get(f"{API}/fsp-mock/athletes/FSP-2024-00117").status_code == 200


def test_route_response_validates_for_every_athlete(client, registry):
    for athlete in registry.athletes():
        assert client.get(f"{API}/fsp-mock/athletes/{athlete['fsp_id']}").status_code == 200


def test_routes_are_off_when_the_flag_is_off(assert_error):
    application = create_app(Settings(FSP_MOCK_ROUTES_ENABLED=False, SEED_DEMO_DATA=False))
    disabled = TestClient(application)

    response = disabled.get(f"{API}/fsp-mock/athletes/FSP-2024-00117")

    assert_error(response, 404, "NOT_FOUND")
    paths = disabled.get("/api/openapi.json").json()["paths"]
    assert "/api/v1/fsp-mock/athletes/{fsp_id}" not in paths


def test_registry_json_is_valid_utf8_json():
    payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))

    assert payload["meta"]["fictional"] is True
    assert "Смирнов" in OUTPUT_PATH.read_text(encoding="utf-8")  # not \u-escaped
