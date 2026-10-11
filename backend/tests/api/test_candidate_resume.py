"""`POST` and `DELETE /candidate/resume`, `GET /candidate/resume/demo` (SPEC section 6.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.api.routes import candidate_resume
from app.domain.facts import skill_fact
from app.models import Candidate, ProfileFact

API = "/api/v1"
URL = f"{API}/candidate/resume"
DEMO_URL = f"{URL}/demo"

# Periods are in the past and closed, so the experience (1.5 years) never changes.
RESUME = """Иванов Иван Иванович
Backend-разработчик (Python)

Казань · готов работать удалённо или в гибридном формате
Телефон: +7 900 000-00-17
Почта: ivan.ivanov@example.test
Telegram: @ivan_dev_demo

Зарплатные ожидания: от 120 000 рублей на руки

Опыт работы

04.2023 – 09.2024
Разработчик Python, ООО «Ромашка»
Разрабатывал REST API на FastAPI, PostgreSQL, Docker. Работал с Git.

Навыки
Python, FastAPI, PostgreSQL, Docker, Git
"""

OTHER_RESUME = """Петров Пётр
Разработчик баз данных

Опыт работы

01.2022 – 12.2022
Разработчик, ООО «Лист»
Писал запросы на SQL и отчёты.

Навыки
SQL
"""


def make_pdf(lines: list[str]) -> bytes:
    """A one-page PDF with plain Latin text (enough for the extractor)."""
    stream = "BT /F1 12 Tf 14 TL 50 750 Td " + " ".join(f"({line}) Tj T*" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out + trailer.encode()


def post_text(client, headers, text: str):
    return client.post(URL, files={"text": (None, text)}, headers=headers)


def post_file(client, headers, name: str, content: bytes):
    files = {"file": (name, content, "application/octet-stream")}
    return client.post(URL, files=files, headers=headers)


def resume_facts(db, candidate_id: int) -> list[ProfileFact]:
    db.expire_all()
    return list(
        db.scalars(
            select(ProfileFact)
            .where(ProfileFact.candidate_id == candidate_id, ProfileFact.source == "resume")
            .order_by(ProfileFact.id)
        )
    )


@pytest.fixture()
def me(make_candidate, headers_for):
    candidate = make_candidate()
    return candidate, headers_for(candidate.user)


# --- text and files --------------------------------------------------------------------------


def test_resume_text_is_parsed(client, db, me):
    candidate, headers = me

    response = post_text(client, headers, RESUME)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parser"] == "rules"
    extracted = body["extracted"]
    assert [skill["skill"] for skill in extracted["skills"]] == [
        "python",
        "fastapi",
        "postgresql",
        "docker",
        "git",
    ]
    assert {skill["level"] for skill in extracted["skills"]} == {2}
    assert extracted["experience_years"] == 1.5
    assert extracted["positions"][0]["is_it"] is True
    assert extracted["work_formats"] == ["remote", "hybrid"]
    assert extracted["city"] == "Казань"
    assert extracted["salary_expectation"] == 120000
    assert extracted["is_lead"] is False

    profile = body["profile"]
    assert profile["resume"] == {
        "filename": None,
        "parsed_at": profile["resume"]["parsed_at"],
        "parser": "rules",
        "chars": len(RESUME.strip()),
    }
    facts = {(fact["kind"], fact["key"]): fact for fact in profile["facts"]}
    assert set(facts) == {
        ("skill", "python"),
        ("skill", "fastapi"),
        ("skill", "postgresql"),
        ("skill", "docker"),
        ("skill", "git"),
        ("experience", "total"),
    }
    assert {fact["source"] for fact in facts.values()} == {"resume"}
    assert {fact["verification"] for fact in facts.values()} == {"parsed"}
    assert facts[("experience", "total")]["value"]["years"] == 1.5
    assert profile["category"]["stack"] == "backend"

    db.expire_all()
    stored = db.get(Candidate, candidate.id)
    assert stored.resume_text == RESUME.strip()
    assert stored.resume_filename is None
    assert stored.resume_parsed_at is not None
    assert len(stored.embedding) == 384


def test_txt_file_is_parsed(client, db, me):
    candidate, headers = me

    response = post_file(client, headers, "my resume.txt", RESUME.encode("utf-8"))

    assert response.status_code == 200, response.text
    profile = response.json()["profile"]
    assert profile["resume"]["filename"] == "my resume.txt"
    assert response.json()["extracted"]["experience_years"] == 1.5
    assert len(resume_facts(db, candidate.id)) == 6


def test_txt_file_in_windows_1251(client, me):
    _, headers = me

    response = post_file(client, headers, "cv.TXT", RESUME.encode("cp1251"))

    assert response.status_code == 200, response.text
    assert response.json()["extracted"]["experience_years"] == 1.5


def test_a_path_in_the_file_name_is_dropped(client, me):
    _, headers = me

    response = post_file(client, headers, "C:\\Users\\ivan\\docs\\cv.txt", RESUME.encode("utf-8"))

    assert response.json()["profile"]["resume"]["filename"] == "cv.txt"


def test_pdf_file_is_parsed(client, me):
    _, headers = me
    pdf = make_pdf(["Backend developer", "Skills: Python, Docker, PostgreSQL"])

    response = post_file(client, headers, "cv.pdf", pdf)

    assert response.status_code == 200, response.text
    skills = [skill["skill"] for skill in response.json()["extracted"]["skills"]]
    assert skills == ["python", "docker", "postgresql"]
    assert response.json()["profile"]["resume"]["filename"] == "cv.pdf"


def test_form_encoded_text_works_too(client, me):
    _, headers = me

    response = client.post(URL, data={"text": RESUME}, headers=headers)

    assert response.status_code == 200, response.text


def test_the_file_wins_when_both_are_sent(client, me):
    _, headers = me

    response = client.post(
        URL,
        files={"file": ("cv.txt", OTHER_RESUME.encode("utf-8"), "text/plain")},
        data={"text": RESUME},
        headers=headers,
    )

    assert [s["skill"] for s in response.json()["extracted"]["skills"]] == ["sql"]


# --- refusals --------------------------------------------------------------------------------


def test_nothing_sent(client, me, assert_error):
    _, headers = me

    assert_error(client.post(URL, headers=headers), 422, "RESUME_EMPTY")
    assert_error(client.post(URL, data={}, headers=headers), 422, "RESUME_EMPTY")


@pytest.mark.parametrize("text", ["", "   \n\t  ", "\x00\x00"])
def test_blank_text(client, me, assert_error, text):
    _, headers = me

    assert_error(post_text(client, headers, text), 422, "RESUME_EMPTY")


def test_empty_file(client, me, assert_error):
    _, headers = me

    assert_error(post_file(client, headers, "cv.txt", b""), 422, "RESUME_EMPTY")
    assert_error(post_file(client, headers, "cv.txt", b" \n "), 422, "RESUME_EMPTY")


@pytest.mark.parametrize("name", ["cv.docx", "cv.exe", "cv", "cv.txt.exe", "cv.pdf.zip", "cv.rtf"])
def test_other_extensions_are_refused(client, me, assert_error, name):
    _, headers = me

    assert_error(post_file(client, headers, name, RESUME.encode("utf-8")), 415, "UNSUPPORTED_FILE")


def test_unreadable_pdf(client, me, assert_error):
    _, headers = me

    response = post_file(client, headers, "cv.pdf", b"%PDF-1.4 not a pdf")

    assert_error(response, 415, "UNSUPPORTED_FILE")


def test_file_over_the_limit(client, db, me, assert_error):
    candidate, headers = me
    too_big = b"a" * (2 * 1024 * 1024 + 1)

    body = assert_error(post_file(client, headers, "cv.txt", too_big), 413, "FILE_TOO_LARGE")

    assert body["details"] == {"max_bytes": 2097152}
    assert resume_facts(db, candidate.id) == []
    db.expire_all()
    assert db.get(Candidate, candidate.id).resume_text is None


def test_the_limit_comes_from_the_settings(client, api_app, settings, me, assert_error):
    _, headers = me
    api_app.state.settings = settings.model_copy(update={"MAX_UPLOAD_BYTES": 1000})
    at_limit = ("Python " * 200).encode("utf-8")[:1000]

    assert post_file(client, headers, "cv.txt", at_limit).status_code == 200
    assert_error(post_file(client, headers, "cv.txt", at_limit + b"a"), 413, "FILE_TOO_LARGE")


def test_wrong_extension_is_reported_before_the_size(client, me, assert_error):
    _, headers = me

    response = post_file(client, headers, "cv.exe", b"a" * (2 * 1024 * 1024 + 1))

    assert_error(response, 415, "UNSUPPORTED_FILE")


def test_text_over_the_limit(client, me, assert_error):
    _, headers = me

    body = assert_error(post_text(client, headers, "я" * 100_001), 422, "VALIDATION_ERROR")

    assert body["details"]["errors"][0]["field"] == "text"


def test_text_at_the_limit_is_accepted(client, me):
    _, headers = me

    assert post_text(client, headers, "я" * 100_000).status_code == 200


def test_file_with_too_much_text(client, me, assert_error):
    _, headers = me

    body = assert_error(
        post_file(client, headers, "cv.txt", b"a" * 100_001), 413, "FILE_TOO_LARGE"
    )

    assert body["details"] == {"max_chars": 100_000}


def test_a_refused_upload_changes_nothing(client, db, make_candidate, headers_for):
    candidate = make_candidate(facts=[skill_fact("python", 2, "resume")], city="Казань")
    headers = headers_for(candidate.user)

    assert post_file(client, headers, "cv.docx", b"x").status_code == 415
    assert post_text(client, headers, "  ").status_code == 422

    assert len(resume_facts(db, candidate.id)) == 1


# --- replacing and filling -------------------------------------------------------------------


def test_a_new_upload_replaces_the_resume_facts_only(client, db, make_candidate, headers_for):
    candidate = make_candidate(
        facts=[skill_fact("algorithms", 3, "fsp"), skill_fact("python", 1, "test")]
    )
    headers = headers_for(candidate.user)
    post_text(client, headers, RESUME)
    assert {f.key for f in resume_facts(db, candidate.id)} == {
        "python",
        "fastapi",
        "postgresql",
        "docker",
        "git",
        "total",
    }

    response = post_text(client, headers, OTHER_RESUME)

    assert response.status_code == 200, response.text
    assert {f.key for f in resume_facts(db, candidate.id)} == {"sql", "total"}
    all_facts = {(f["source"], f["key"]) for f in response.json()["profile"]["facts"]}
    assert ("fsp", "algorithms") in all_facts
    assert ("test", "python") in all_facts
    assert ("resume", "python") not in all_facts
    assert response.json()["profile"]["resume"]["chars"] == len(OTHER_RESUME.strip())


def test_the_same_resume_twice_does_not_duplicate_facts(client, db, me):
    candidate, headers = me

    post_text(client, headers, RESUME)
    post_text(client, headers, RESUME)

    assert len(resume_facts(db, candidate.id)) == 6


def test_empty_fields_are_filled_from_the_resume(client, db, me):
    candidate, headers = me

    body = post_text(client, headers, RESUME).json()

    assert body["applied_prefs"] == ["city", "work_formats", "salary_expectation"]
    profile = body["profile"]
    assert profile["city"] == "Казань"
    assert profile["work_formats"] == ["remote", "hybrid"]
    assert profile["salary_expectation"] == 120000
    assert profile["category"]["work_formats"] == ["remote", "hybrid"]
    db.expire_all()
    assert db.get(Candidate, candidate.id).city == "Казань"


def test_filled_fields_are_kept(client, make_candidate, headers_for):
    candidate = make_candidate(city="Москва", work_formats=["office"], salary_expectation=90000)

    body = post_text(client, headers_for(candidate.user), RESUME).json()

    assert body["applied_prefs"] == []
    profile = body["profile"]
    assert profile["city"] == "Москва"
    assert profile["work_formats"] == ["office"]
    assert profile["salary_expectation"] == 90000
    # The parse result still shows what the resume said.
    assert body["extracted"]["city"] == "Казань"


def test_only_empty_fields_are_filled(client, make_candidate, headers_for):
    candidate = make_candidate(city="Москва")

    body = post_text(client, headers_for(candidate.user), RESUME).json()

    assert body["applied_prefs"] == ["work_formats", "salary_expectation"]
    assert body["profile"]["city"] == "Москва"


def test_a_resume_without_those_fields_applies_nothing(client, me):
    _, headers = me

    body = post_text(client, headers, "Опыт работы\n\nPython, Docker").json()

    assert body["applied_prefs"] == []


def test_contacts_never_reach_the_facts(client, me):
    _, headers = me

    profile = post_text(client, headers, RESUME).json()["profile"]

    facts_dump = json.dumps(profile["facts"], ensure_ascii=False)
    for secret in ("ivan.ivanov", "example.test", "ivan_dev_demo", "900 000", "+7"):
        assert secret not in facts_dump
    assert profile["phone"] is None
    assert profile["telegram"] is None
    assert "resume_text" not in profile


# --- deleting --------------------------------------------------------------------------------


def test_delete_clears_the_resume_and_its_facts(client, db, make_candidate, headers_for):
    candidate = make_candidate(facts=[skill_fact("algorithms", 3, "fsp")])
    headers = headers_for(candidate.user)
    post_text(client, headers, RESUME)

    response = client.delete(URL, headers=headers)

    assert response.status_code == 200, response.text
    profile = response.json()
    assert profile["resume"] is None
    assert [(f["source"], f["key"]) for f in profile["facts"]] == [("fsp", "algorithms")]
    assert profile["category"]["experience_years"] == 0
    db.expire_all()
    stored = db.get(Candidate, candidate.id)
    assert stored.resume_text is None
    assert stored.resume_filename is None
    assert stored.resume_parsed_at is None
    assert resume_facts(db, candidate.id) == []
    assert stored.category == profile["category"]


def test_delete_keeps_the_fields_already_copied_to_the_questionnaire(client, me):
    _, headers = me
    post_text(client, headers, RESUME)

    profile = client.delete(URL, headers=headers).json()

    assert profile["city"] == "Казань"
    assert profile["salary_expectation"] == 120000


def test_delete_without_a_resume_is_fine(client, me):
    _, headers = me

    response = client.delete(URL, headers=headers)

    assert response.status_code == 200
    assert response.json()["resume"] is None


def test_the_resume_can_be_uploaded_again_after_deleting(client, me):
    _, headers = me
    post_text(client, headers, RESUME)
    client.delete(URL, headers=headers)

    response = post_text(client, headers, RESUME)

    assert response.status_code == 200
    assert response.json()["profile"]["resume"] is not None


# --- the demo text ---------------------------------------------------------------------------


def test_demo_resume_text(client, me):
    _, headers = me
    expected = Path(candidate_resume.DEMO_RESUME_PATH).read_text(encoding="utf-8")

    response = client.get(DEMO_URL, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"text": expected}
    assert "Python" in expected


def test_demo_resume_can_be_sent_back_as_the_resume(client, me):
    _, headers = me
    text = client.get(DEMO_URL, headers=headers).json()["text"]

    response = post_text(client, headers, text)

    assert response.status_code == 200, response.text
    extracted = response.json()["extracted"]
    skills = {skill["skill"] for skill in extracted["skills"]}
    assert {"python", "fastapi", "postgresql", "docker", "git"} <= skills
    assert extracted["experience_years"] >= 1.0
    assert extracted["city"] == "Казань"


def test_missing_demo_file_is_not_found(client, me, monkeypatch, tmp_path, assert_error):
    _, headers = me
    monkeypatch.setattr(candidate_resume, "DEMO_RESUME_PATH", tmp_path / "absent.txt")

    assert_error(client.get(DEMO_URL, headers=headers), 404, "NOT_FOUND")


# --- access ----------------------------------------------------------------------------------


def test_resume_routes_are_for_candidates(client, employer_headers, assert_error):
    assert_error(post_text(client, employer_headers, RESUME), 403, "FORBIDDEN")
    assert_error(client.delete(URL, headers=employer_headers), 403, "FORBIDDEN")
    assert_error(client.get(DEMO_URL, headers=employer_headers), 403, "FORBIDDEN")


def test_resume_routes_need_a_token(client):
    assert client.post(URL, files={"text": (None, RESUME)}).status_code == 401
    assert client.delete(URL).status_code == 401
    assert client.get(DEMO_URL).status_code == 401
