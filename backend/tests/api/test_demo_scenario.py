"""The demo scenario of SPEC section 3, step by step, on the seeded database.

Every step checks the state it leaves behind. The scenario must pass right after `seed` and
again after `--reset`, so a second test runs it, resets the data and runs it once more.

Dates in the demo resume are fixed ("10.2025 – н.в."), so the experience it gives grows with
the calendar: about 1.5 years now. The checks use a range for it, not the exact number.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.domain import categorizer, fsp_mapping
from app.domain.ontology import read_json
from app.domain.types import CandidatePrefs, FactData
from app.fsp_registry.mock import MockFspRegistry

API = "/api/v1"
PASSWORD = "demo12345"
CANDIDATE_EMAIL = "demo.candidate@fsp-career.test"
EMPLOYER_EMAIL = "demo.employer@fsp-career.test"
FSP_ID = "FSP-2024-00117"
SENIOR_GATE_NOTE = "Для Senior нужен опыт от 3 лет и подтверждение тестом или ФСП"
JUNIOR_GATE_NOTE = "без опыта работы грейд не выше Junior"

# What the demo candidate keeps private until an offer is accepted.
PRIVATE_MARKERS = [
    "Смирнов",
    "alexey_smirnov_demo",
    "+7 900 000-00-17",
    "900 000-00-17",
    "2003-05-14",
    "14.05.2003",
    CANDIDATE_EMAIL,
    "alexey.smirnov@example.test",
]

QUESTION_BANK = {
    question["id"]: question
    for test in read_json("questions.json")["tests"]
    for question in test["questions"]
}


@pytest.fixture()
def seeded(db: Session) -> Session:
    from app.seed import seed_all

    seed_all(db)
    return db


def login(client: Any, email: str) -> dict[str, str]:
    response = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def right_answers(session: dict[str, Any]) -> dict[str, int]:
    """The index of the correct option of every question, from the bank (the API hides it)."""
    answers = {}
    for question in session["questions"]:
        bank = QUESTION_BANK[question["id"]]
        answers[question["id"]] = question["options"].index(bank["options"][bank["correct"]])
    return answers


def domain_category(profile: dict[str, Any]):
    """The category the domain computes from the facts and settings the API shows."""
    facts = [
        FactData(**{key: fact[key] for key in FactData.model_fields}) for fact in profile["facts"]
    ]
    prefs = CandidatePrefs(
        city=profile["city"],
        work_formats=profile["work_formats"],
        relocation=profile["relocation"],
        salary_expectation=profile["salary_expectation"],
    )
    return categorizer.categorize(facts, prefs)


def assert_hidden(raw: str, where: str) -> None:
    for marker in PRIVATE_MARKERS:
        assert marker not in raw, f"в {where} до принятого оффера виден «{marker}»"


def facts_of(profile: dict[str, Any], **criteria: str) -> list[dict[str, Any]]:
    return [f for f in profile["facts"] if all(f[k] == v for k, v in criteria.items())]


def walk_the_scenario(client: Any) -> None:
    candidate = login(client, CANDIDATE_EMAIL)
    employer = login(client, EMPLOYER_EMAIL)
    orbita = login(client, "hr@orbita-soft.test")

    # -- 1. The candidate signs in: no category, one incoming offer from "Орбита Софт".
    profile = client.get(f"{API}/candidate/profile", headers=candidate).json()
    candidate_id = profile["id"]
    assert profile["category"]["stack"] is None
    assert profile["category"]["label"] == "Категория не определена"
    assert profile["category"]["grade"] is None and profile["category"]["team_role"] is None
    assert profile["fsp"] is None and profile["resume"] is None and profile["facts"] == []
    assert profile["visible"] is True and profile["city"] == "Казань"

    offers = client.get(f"{API}/candidate/offers", headers=candidate).json()
    assert len(offers) == 1
    assert offers[0]["company"]["name"] == "Орбита Софт"
    assert offers[0]["status"] == "sent" and offers[0]["employer_contacts"] is None
    orbita_offer_id = offers[0]["id"]

    matrix_before = client.get(f"{API}/employer/categories", headers=employer).json()
    assert matrix_before["total_candidates"] == 29, "the demo candidate has no stack yet"

    # -- 2. The FSP link: six results and the KMS rank, "Backend · Junior" with the gate note.
    link = client.post(f"{API}/candidate/fsp/link", json={"fsp_id": FSP_ID}, headers=candidate)
    assert link.status_code == 200, link.text
    linked = link.json()
    expected_imports = {"achievement": 6, "rank": 1, "skill": 2, "role": 2}
    from collections import Counter

    athlete = MockFspRegistry().get_athlete(FSP_ID)
    by_kind = Counter(f.kind for f in fsp_mapping.facts_from_fsp(athlete))
    assert dict(by_kind) == expected_imports
    assert linked["imported"] == {"achievements": 6, "ranks": 1, "skills": 2, "roles": 2}
    assert linked["athlete"]["short_name"] == "Смирнов А. И."

    profile = linked["profile"]
    category = profile["category"]
    assert profile["fsp"]["fsp_id"] == FSP_ID
    assert len(facts_of(profile, kind="achievement", source="fsp")) == 6
    [rank] = facts_of(profile, kind="rank")
    assert rank["value"]["rank"] == "kms" and rank["verification"] == "verified"
    assert facts_of(profile, source="fsp") and all(
        f["verification"] == "verified" for f in facts_of(profile, source="fsp")
    )
    assert category["stack"] == "backend" and category["grade"] == "junior"
    assert category["label"].startswith("Backend · Junior")
    assert JUNIOR_GATE_NOTE in category["grade_note"]
    assert category["experience_years"] == 0
    assert category["grade_confirmed"] is True and category["confidence_index"] == 50
    assert category["achievement_points"] > 0
    # The role is whatever the domain computes: 20+ points in algorithmic programming with no
    # experience make a researcher; it is not hardcoded here.
    assert category["team_role"] == domain_category(profile).team_role
    assert domain_category(profile).model_dump() == category
    points_after_fsp = category["grade_points"]

    locked = client.patch(
        f"{API}/candidate/profile", json={"full_name": "Другое Имя"}, headers=candidate
    )
    assert locked.status_code == 409 and locked.json()["error_code"] == "FSP_LINKED_LOCKED"

    # -- 3. The demo resume: skills, ~1.5 years, work formats, the grade becomes Middle.
    demo_text = client.get(f"{API}/candidate/resume/demo", headers=candidate).json()["text"]
    parsed = client.post(
        f"{API}/candidate/resume", files={"text": (None, demo_text)}, headers=candidate
    )
    assert parsed.status_code == 200, parsed.text
    body = parsed.json()
    extracted = body["extracted"]
    assert 1.2 <= extracted["experience_years"] <= 1.9
    assert {s["skill"] for s in extracted["skills"]} >= {
        "python",
        "fastapi",
        "postgresql",
        "docker",
        "git",
    }
    assert set(extracted["work_formats"]) == {"remote", "hybrid"}
    assert extracted["salary_expectation"] == 120_000
    assert extracted["is_lead"] is False
    assert set(body["applied_prefs"]) == {"work_formats", "salary_expectation"}  # city was set

    profile = body["profile"]
    category = profile["category"]
    assert profile["resume"]["parser"] == "rules"
    assert profile["salary_expectation"] == 120_000
    assert set(profile["work_formats"]) == {"remote", "hybrid"}
    from_resume = facts_of(profile, source="resume")
    assert from_resume and all(f["verification"] == "parsed" for f in from_resume)
    [experience] = [f for f in from_resume if f["kind"] == "experience"]
    assert experience["value"]["years"] == pytest.approx(extracted["experience_years"])
    contacts_in_facts = " ".join(f"{f['title']} {f['value']} {f['evidence']}" for f in from_resume)
    for secret in ("alexey.smirnov@example.test", "alexey_smirnov_demo", "900 000-00-17"):
        assert secret not in contacts_in_facts, "the resume contacts must not become facts"
    assert category["stack"] == "backend" and category["grade"] == "middle"
    assert category["label"].startswith("Backend · Middle · Разработчик")
    assert category["team_role"] == "developer"
    assert category["experience_years"] == pytest.approx(extracted["experience_years"])
    assert category["grade_note"] is None
    assert category["grade_points"] > points_after_fsp
    assert category["confidence_index"] == 50
    assert domain_category(profile).model_dump() == category
    points_after_resume = category["grade_points"]
    experience_after_resume = category["experience_points"]

    # -- 4. The Python express test: "tested" skill, the experience is trusted more.
    tests = client.get(f"{API}/candidate/tests", headers=candidate).json()
    assert {t["skill"] for t in tests} >= {"python", "javascript", "sql", "algorithms"}
    assert all(t["best_result"] is None for t in tests)
    started = client.post(f"{API}/candidate/tests/python/start", headers=candidate)
    assert started.status_code == 201, started.text
    assert '"correct"' not in started.text
    session = started.json()
    assert [q["difficulty"] for q in session["questions"]] == [1, 1, 2, 2, 3, 3]
    submitted = client.post(
        f"{API}/candidate/tests/sessions/{session['session_id']}/submit",
        json={"answers": right_answers(session)},
        headers=candidate,
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert (result["level"], result["level_title"], result["passed"]) == (3, "Продвинутый", True)
    assert (result["correct"], result["total"], result["score"]) == (6, 6, 1.0)

    profile = result["profile"]
    category = profile["category"]
    [python_fact] = facts_of(profile, kind="skill", key="python", source="test")
    assert python_fact["verification"] == "tested" and python_fact["value"]["level"] == 3
    top = next(s for s in category["top_skills"] if s["skill"] == "python")
    assert (top["best_source"], top["verification"]) == ("test", "tested")
    assert category["grade_points"] > points_after_resume
    # One passed test lifts the trust in the resume experience from 0.6 to 0.8.
    assert category["experience_points"] == pytest.approx(
        experience_after_resume * 0.8 / 0.6, rel=0.02
    )
    assert category["confidence_index"] == 75
    # More than 70 points, but under three years of experience Senior is held back.
    assert category["grade"] == "middle"
    assert category["grade_note"] == SENIOR_GATE_NOTE
    assert domain_category(profile).model_dump() == category
    points_after_test = category["grade_points"]
    tests_now = client.get(f"{API}/candidate/tests", headers=candidate).json()
    [python_test] = [t for t in tests_now if t["skill"] == "python"]
    assert python_test["best_result"]["level"] == 3

    # -- 5. An olympiad by hand: "declared", it counts for 35%.
    added = client.post(
        f"{API}/candidate/achievements",
        json={
            "title": "Всероссийская олимпиада школьников по информатике",
            "year": 2021,
            "level": "national",
            "result": "prize",
            "discipline": None,
            "document_url": None,
        },
        headers=candidate,
    )
    assert added.status_code == 201, added.text
    profile = added.json()
    category = profile["category"]
    [manual] = facts_of(profile, kind="achievement", source="self")
    assert manual["verification"] == "declared" and manual["key"].startswith("manual:")
    assert "олимпиада школьников" in manual["title"]
    # national base 14 x prize 0.8 x 0.35 = 3.92
    assert category["grade_points"] - points_after_test == pytest.approx(3.92, abs=0.11)
    declared = [e for e in category["grade_explanations"] if e["source"] == "self"]
    assert len(declared) == 1 and declared[0]["points"] == pytest.approx(3.92, abs=0.01)
    assert category["confidence_index"] == 75
    assert domain_category(profile).model_dump() == category
    final_label = category["label"]

    # -- 6. The employer signs in and sees the matrix, now with the demo candidate in it.
    employer_profile = client.get(f"{API}/employer/profile", headers=employer).json()
    assert employer_profile["company_name"] == "Северный код" and employer_profile["verified"]
    matrix_response = client.get(f"{API}/employer/categories", headers=employer)
    matrix = matrix_response.json()
    assert matrix["total_candidates"] >= 20
    assert matrix["total_candidates"] == matrix_before["total_candidates"] + 1
    assert sum(cell["count"] for cell in matrix["cells"]) == matrix["total_candidates"]
    cell = {(c["stack"], c["grade"]): c for c in matrix["cells"]}[("backend", "middle")]
    cells_before = {(c["stack"], c["grade"]): c for c in matrix_before["cells"]}
    cell_before = cells_before[("backend", "middle")]
    assert cell["count"] == cell_before["count"] + 1
    assert cell["fsp_verified"] == cell_before["fsp_verified"] + 1
    assert_hidden(matrix_response.text, "матрице")

    # -- 7. The search: filters plus a text, a score with an explanation, five or more with FSP.
    query = {
        "text": "python fastapi разработчик серверной части",
        "fsp_verified_only": True,
        "limit": 50,
    }
    search_response = client.post(f"{API}/employer/search", json=query, headers=employer)
    assert search_response.status_code == 200, search_response.text
    search = search_response.json()
    assert search["total"] >= 5
    assert {"python", "fastapi"} <= set(search["parsed_query"]["skills"])
    [mine] = [m for m in search["items"] if m["candidate"]["id"] == candidate_id]
    assert mine["score"] is not None and 0 <= mine["score"] <= 100
    assert 2 <= len(mine["reasons"]) <= 4
    assert {s["skill"] for s in mine["matched_skills"]} >= {"python", "fastapi"}
    assert mine["candidate"]["display_name"] == "Алексей С."
    assert mine["candidate"]["fsp_linked"] is True and mine["candidate"]["sport_rank"] == "kms"
    assert mine["candidate"]["category"]["label"] == final_label
    scores = [m["score"] for m in search["items"]]
    assert scores == sorted(scores, reverse=True)
    assert_hidden(search_response.text, "выдаче")

    filtered = client.post(
        f"{API}/employer/search",
        json={"stacks": ["backend"], "grades": ["middle"], "fsp_verified_only": True, "limit": 50},
        headers=employer,
    ).json()
    assert candidate_id in [m["candidate"]["id"] for m in filtered["items"]]
    everyone = client.post(
        f"{API}/employer/search", json={"text": query["text"], "limit": 50}, headers=employer
    ).json()
    assert everyone["total"] >= search["total"]

    # -- 8. The card has no contacts and shows "Алексей С."; the offer goes out.
    card_response = client.get(f"{API}/employer/candidates/{candidate_id}", headers=employer)
    assert card_response.status_code == 200, card_response.text
    card = card_response.json()
    assert card["display_name"] == "Алексей С."
    assert card["contacts"] is None and card["offers"] == []
    assert card["category"]["label"] == final_label
    assert len(facts_of(card, kind="achievement")) == 7  # six FSP results and the olympiad
    assert_hidden(card_response.text, "карточке")

    vacancies = client.get(f"{API}/employer/vacancies", headers=employer).json()
    [vacancy] = [v for v in vacancies if v["title"] == "Python-разработчик" and v["is_active"]]
    created = client.post(
        f"{API}/employer/offers",
        json={
            "candidate_id": candidate_id,
            "vacancy_id": vacancy["id"],
            "salary": 150_000,
            "message": "Алексей, нам подходит ваш профиль. Готовы обсудить задачи и старт.",
        },
        headers=employer,
    )
    assert created.status_code == 201, created.text
    offer = created.json()
    assert offer["status"] == "sent" and offer["salary"] == 150_000 and offer["contacts"] is None
    assert offer["candidate"]["display_name"] == "Алексей С."
    assert_hidden(created.text, "ответе на оффер")
    again = client.post(
        f"{API}/employer/offers",
        json={"candidate_id": candidate_id, "vacancy_id": vacancy["id"], "salary": 150_000},
        headers=employer,
    )
    assert again.status_code == 409 and again.json()["error_code"] == "OFFER_ALREADY_SENT"
    listed = client.get(f"{API}/employer/offers", headers=employer)
    assert_hidden(listed.text, "списке офферов")

    # -- 9. The candidate accepts: both sides see each other's contacts.
    inbox = client.get(f"{API}/candidate/offers", headers=candidate).json()
    assert [o["company"]["name"] for o in inbox] == ["Северный код", "Орбита Софт"]
    incoming = inbox[0]
    assert incoming["id"] == offer["id"] and incoming["salary"] == 150_000
    assert incoming["status"] == "sent" and incoming["employer_contacts"] is None
    assert incoming["vacancy"]["title"] == "Python-разработчик"

    accepted = client.post(
        f"{API}/candidate/offers/{offer['id']}/respond",
        json={"decision": "accept"},
        headers=candidate,
    )
    assert accepted.status_code == 200, accepted.text
    answer = accepted.json()
    assert answer["status"] == "accepted" and answer["responded_at"] is not None
    assert answer["employer_contacts"]["contact_email"] == "hr@severny-kod.test"
    assert answer["employer_contacts"]["contact_name"]

    card = client.get(f"{API}/employer/candidates/{candidate_id}", headers=employer).json()
    assert card["display_name"] == "Смирнов Алексей Игоревич"
    assert card["contacts"] == {
        "email": CANDIDATE_EMAIL,
        "telegram": "@alexey_smirnov_demo",
        "phone": "+7 900 000-00-17",
    }
    assert [(o["vacancy_title"], o["status"]) for o in card["offers"]] == [
        ("Python-разработчик", "accepted")
    ]
    employer_offers = client.get(f"{API}/employer/offers", headers=employer).json()
    [mine_offer] = [o for o in employer_offers if o["id"] == offer["id"]]
    assert mine_offer["contacts"]["email"] == CANDIDATE_EMAIL
    assert mine_offer["candidate"]["display_name"] == "Смирнов Алексей Игоревич"
    # The birth date and the resume stay private even now.
    raw_card = client.get(f"{API}/employer/candidates/{candidate_id}", headers=employer).text
    assert "2003-05-14" not in raw_card and "Технический университет" not in raw_card

    again = client.post(
        f"{API}/candidate/offers/{offer['id']}/respond",
        json={"decision": "decline"},
        headers=candidate,
    )
    assert again.status_code == 409 and again.json()["error_code"] == "OFFER_ALREADY_RESPONDED"

    # Another employer still sees nothing: the unlock belongs to the pair.
    other = client.get(f"{API}/employer/candidates/{candidate_id}", headers=orbita)
    assert other.status_code == 200
    assert other.json()["display_name"] == "Алексей С." and other.json()["contacts"] is None
    assert_hidden(other.text, "карточке другого работодателя")
    inbox = client.get(f"{API}/candidate/offers", headers=candidate).json()
    [still] = [o for o in inbox if o["id"] == orbita_offer_id]
    assert still["status"] == "sent" and still["employer_contacts"] is None


def test_the_demo_scenario_passes_on_the_seeded_database(client: Any, seeded: Session):
    walk_the_scenario(client)


def test_the_demo_scenario_passes_again_after_a_reset(client: Any, seeded: Session):
    from app.seed import reset_all, seed_all

    walk_the_scenario(client)

    reset_all(seeded)
    seed_all(seeded)

    walk_the_scenario(client)
