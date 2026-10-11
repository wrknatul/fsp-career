"""The candidate's whole path through the cabinet (SPEC section 3, steps 1-5)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

API = "/api/v1"
FULL_NAME = "Смирнов Алексей Игоревич"
JUNIOR_NOTE = "Спортивные результаты учтены, но без опыта работы грейд не выше Junior"

# Closed periods in the past: exactly 1.5 years of IT experience, whatever day the test runs.
RESUME = """Смирнов Алексей Игоревич
Backend-разработчик (Python)

Казань · готов работать удалённо или в гибридном формате
Зарплатные ожидания: от 120 000 рублей на руки

Опыт работы

04.2023 – 09.2024
Младший backend-разработчик, ООО «Кама Софт»
Разрабатывал REST API на FastAPI, PostgreSQL, Docker. Работал с Git.

Навыки
Python, FastAPI, PostgreSQL, Docker, Git
"""

QUESTIONS_JSON = Path(__file__).resolve().parents[2] / "app" / "domain" / "data" / "questions.json"
BANK = {
    question["id"]: question
    for test in json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))["tests"]
    for question in test["questions"]
}


def right_answers(session: dict) -> dict[str, int]:
    answers = {}
    for question in session["questions"]:
        bank = BANK[question["id"]]
        answers[question["id"]] = question["options"].index(bank["options"][bank["correct"]])
    return answers


@pytest.fixture()
def alexey(client):
    """A freshly registered candidate named like the demo athlete, with the birth date set."""
    response = client.post(
        f"{API}/auth/register",
        json={
            "email": "alexey.flow@example.test",
            "password": "password123",
            "role": "candidate",
            "full_name": FULL_NAME,
            "consent": True,
            "show_profile": True,
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    patch = client.patch(
        f"{API}/candidate/profile", json={"birth_date": "2003-05-14"}, headers=headers
    )
    assert patch.status_code == 200, patch.text
    return headers


def test_fsp_then_resume_then_test_grows_the_grade(client, alexey):
    headers = alexey

    def profile() -> dict:
        return client.get(f"{API}/candidate/profile", headers=headers).json()

    # A new account: nothing is known yet.
    start = profile()
    assert start["category"]["label"] == "Категория не определена"
    assert start["category"]["grade"] is None
    assert start["category"]["grade_points"] == 0

    # 1. The FSP link brings verified results, but without work experience the grade stays junior.
    linked = client.post(
        f"{API}/candidate/fsp/link", json={"fsp_id": "FSP-2024-00117"}, headers=headers
    )
    assert linked.status_code == 200, linked.text
    after_fsp = linked.json()["profile"]["category"]
    assert after_fsp["stack"] == "backend"
    assert after_fsp["grade"] == "junior"
    assert after_fsp["grade_note"] == JUNIOR_NOTE
    assert after_fsp["confidence_index"] == 50
    assert after_fsp["experience_years"] == 0
    assert profile()["category"] == after_fsp

    # 2. A resume with 1.5 years of experience lifts the gate: junior -> middle.
    parsed = client.post(f"{API}/candidate/resume", files={"text": (None, RESUME)}, headers=headers)
    assert parsed.status_code == 200, parsed.text
    after_resume = parsed.json()["profile"]["category"]
    assert parsed.json()["extracted"]["experience_years"] == 1.5
    assert after_resume["experience_years"] == 1.5
    assert after_resume["grade"] == "middle"
    assert after_resume["grade_note"] is None
    assert after_resume["label"].startswith("Backend · Middle")
    assert after_resume["grade_points"] == pytest.approx(after_fsp["grade_points"] + 10.8, abs=0.11)
    assert after_resume["confidence_index"] == 50
    assert parsed.json()["applied_prefs"] == ["city", "work_formats", "salary_expectation"]
    assert profile()["category"] == after_resume

    # 3. A passed test: the resume experience is trusted more (0.6 -> 0.8) and the test adds points.
    session = client.post(f"{API}/candidate/tests/python/start", headers=headers).json()
    result = client.post(
        f"{API}/candidate/tests/sessions/{session['session_id']}/submit",
        json={"answers": right_answers(session)},
        headers=headers,
    )
    assert result.status_code == 200, result.text
    assert result.json()["level"] == 3
    after_test = result.json()["profile"]["category"]
    assert after_test["grade"] == "middle"
    # 12 * 1.5 = 18 raw points: trust 0.6 -> 0.8 adds 3.6, the level-3 test adds 15.
    test_gain = after_test["grade_points"] - after_resume["grade_points"]
    assert test_gain == pytest.approx(18.6, abs=0.11)
    assert after_test["confidence_index"] == 75
    assert after_test["grade_confirmed"] is True
    assert after_test["stack_confirmed"] is True
    python = next(s for s in after_test["top_skills"] if s["skill"] == "python")
    assert (python["verification"], python["best_source"]) == ("tested", "test")
    assert profile()["category"] == after_test

    # 4. A declared achievement adds a little, at 35%, and does not touch the confirmation index.
    added = client.post(
        f"{API}/candidate/achievements",
        json={"title": "Хакатон «Весна»", "year": 2024, "level": "regional", "result": "winner"},
        headers=headers,
    )
    assert added.status_code == 201, added.text
    after_manual = added.json()["category"]
    manual_gain = after_manual["grade_points"] - after_test["grade_points"]
    assert manual_gain == pytest.approx(5 * 0.35, abs=0.11)
    assert after_manual["confidence_index"] == 75

    # The profile now shows the facts of all four sources.
    sources = {fact["source"] for fact in profile()["facts"]}
    assert sources == {"fsp", "resume", "test", "self"}


def test_unlinking_and_deleting_the_resume_walks_the_grade_back(client, alexey):
    headers = alexey
    client.post(f"{API}/candidate/fsp/link", json={"fsp_id": "FSP-2024-00117"}, headers=headers)
    client.post(f"{API}/candidate/resume", files={"text": (None, RESUME)}, headers=headers)

    no_fsp = client.delete(f"{API}/candidate/fsp/link", headers=headers).json()
    assert no_fsp["fsp"] is None
    assert {fact["source"] for fact in no_fsp["facts"]} == {"resume"}
    assert no_fsp["category"]["confidence_index"] == 0
    assert no_fsp["category"]["achievement_points"] == 0

    no_resume = client.delete(f"{API}/candidate/resume", headers=headers).json()
    assert no_resume["facts"] == []
    assert no_resume["category"]["label"] == "Категория не определена"
    assert no_resume["category"]["grade_points"] == 0


def test_the_demo_resume_text_goes_through_the_whole_path(client, alexey):
    headers = alexey
    client.post(f"{API}/candidate/fsp/link", json={"fsp_id": "FSP-2024-00117"}, headers=headers)

    text = client.get(f"{API}/candidate/resume/demo", headers=headers).json()["text"]
    parsed = client.post(f"{API}/candidate/resume", files={"text": (None, text)}, headers=headers)

    assert parsed.status_code == 200, parsed.text
    profile = parsed.json()["profile"]
    assert profile["category"]["experience_years"] >= 1.0
    assert profile["category"]["grade"] in {"middle", "senior"}
    assert profile["category"]["stack"] == "backend"
    assert {s["skill"] for s in parsed.json()["extracted"]["skills"]} >= {"python", "fastapi"}


# --- documentation ---------------------------------------------------------------------------

CANDIDATE_OPERATIONS = {
    ("get", "/candidate/profile"),
    ("patch", "/candidate/profile"),
    ("post", "/candidate/fsp/link"),
    ("delete", "/candidate/fsp/link"),
    ("post", "/candidate/resume"),
    ("delete", "/candidate/resume"),
    ("get", "/candidate/resume/demo"),
    ("get", "/candidate/tests"),
    ("post", "/candidate/tests/{skill}/start"),
    ("post", "/candidate/tests/sessions/{session_id}/submit"),
    ("post", "/candidate/achievements"),
    ("delete", "/candidate/achievements/{fact_id}"),
    ("get", "/candidate/offers"),
    ("post", "/candidate/offers/{offer_id}/respond"),
}


def test_every_candidate_route_is_documented(api_app):
    paths = api_app.openapi()["paths"]
    found = {
        (method, path.removeprefix(API))
        for path, operations in paths.items()
        if path.startswith(f"{API}/candidate/")
        for method in operations
    }
    assert found == CANDIDATE_OPERATIONS

    cyrillic = re.compile("[А-Яа-яЁё]")
    for method, path in sorted(CANDIDATE_OPERATIONS):
        operation = paths[f"{API}{path}"][method]
        assert cyrillic.search(operation["summary"]), (method, path)
        assert cyrillic.search(operation["description"]), (method, path)
        assert operation["tags"] == ["Соискатель"], (method, path)
        success = [code for code in operation["responses"] if code.startswith("2")]
        assert len(success) == 1, (method, path)
        schema = operation["responses"][success[0]]["content"]["application/json"]["schema"]
        assert "$ref" in schema or schema.get("type") == "array", (method, path)
        # Every error answer is described with the unified error model.
        assert {"401", "403"} <= set(operation["responses"]), (method, path)
        for code, response in operation["responses"].items():
            if not code.startswith("2"):
                ref = response["content"]["application/json"]["schema"]["$ref"]
                assert ref.endswith("/ApiError"), (method, path, code)
