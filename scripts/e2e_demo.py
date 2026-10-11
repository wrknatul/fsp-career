#!/usr/bin/env python3
"""End-to-end walk through the demo scenario (docs/SPEC.md, section 3) over HTTP.

Runs against a freshly seeded stand and fails loudly on the first broken step.
Uses only the standard library, so it works without the backend virtualenv:

    python3 scripts/e2e_demo.py                       # http://localhost:8100/api/v1
    python3 scripts/e2e_demo.py http://host/api/v1

The scenario is one-shot: reset the demo data before running it again
(`docker compose exec backend python -m app.seed --reset`).
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8100/api/v1").rstrip("/")
QUESTIONS_PATH = Path(__file__).resolve().parents[1] / "backend/app/domain/data/questions.json"

DEMO_PASSWORD = "demo12345"
CANDIDATE_EMAIL = "demo.candidate@fsp-career.test"
EMPLOYER_EMAIL = "demo.employer@fsp-career.test"
DEMO_FSP_ID = "FSP-2024-00117"
# Private data of the demo candidate that an employer must not see before an accepted offer.
PRIVATE_MARKERS = ["Смирнов", "@alexey_smirnov_demo", "+7 900 000-00-17", "2003-05-14", CANDIDATE_EMAIL]


class StepFailed(Exception):
    pass


def call(
    method: str,
    path: str,
    token: str | None = None,
    body: Any = None,
    form: dict[str, str] | None = None,
    expect: int | tuple[int, ...] = 200,
) -> tuple[Any, str]:
    """Perform a request and return (parsed JSON, raw text)."""
    headers = {"Accept": "application/json"}
    data: bytes | None = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form is not None:
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in form.items():
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
            )
        parts.append(f"--{boundary}--\r\n")
        data = "".join(parts).encode("utf-8")
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(BASE_URL + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status, raw = response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read().decode("utf-8")
    except urllib.error.URLError as error:
        raise StepFailed(f"{method} {path}: стенд недоступен ({error.reason})") from error

    expected = (expect,) if isinstance(expect, int) else expect
    if status not in expected:
        raise StepFailed(f"{method} {path}: ожидался HTTP {expected}, пришёл {status}: {raw[:400]}")
    return (json.loads(raw) if raw else None), raw


def check(condition: bool, message: str) -> None:
    if not condition:
        raise StepFailed(message)


def login(email: str) -> str:
    payload, _ = call("POST", "/auth/login", body={"email": email, "password": DEMO_PASSWORD})
    return payload["access_token"]


def facts_of(profile: dict[str, Any], **criteria: str) -> list[dict[str, Any]]:
    return [f for f in profile["facts"] if all(f.get(k) == v for k, v in criteria.items())]


def correct_answers(session: dict[str, Any]) -> dict[str, int]:
    """Map every question of a session to the index of its correct option.

    The API never returns the key, so it is taken from the question bank in the
    repository and located among the shuffled options by text.
    """
    bank = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    by_id: dict[str, dict[str, Any]] = {}

    def collect(node: Any) -> None:
        if isinstance(node, dict):
            if "id" in node and "options" in node and "correct" in node:
                by_id[node["id"]] = node
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)

    collect(bank)
    answers: dict[str, int] = {}
    for question in session["questions"]:
        source = by_id.get(question["id"])
        check(source is not None, f"вопроса {question['id']} нет в банке")
        right_text = source["options"][source["correct"]]
        check(right_text in question["options"], f"верный вариант вопроса {question['id']} не найден")
        answers[question["id"]] = question["options"].index(right_text)
    return answers


def main() -> int:
    step = "подготовка"
    try:
        health, _ = call("GET", "/health")
        check(health["status"] == "ok" and health["database"] == "ok", f"health: {health}")

        step = "1. Вход соискателем, пустой профиль"
        candidate_token = login(CANDIDATE_EMAIL)
        profile, _ = call("GET", "/candidate/profile", candidate_token)
        candidate_id = profile["id"]
        check(profile["category"]["stack"] is None, "категория должна быть не определена")
        check(profile["fsp"] is None and profile["resume"] is None, "ФСП и резюме должны быть пусты")
        offers, _ = call("GET", "/candidate/offers", candidate_token)
        check(len(offers) == 1, f"ожидался ровно один входящий оффер, пришло {len(offers)}")
        check(offers[0]["company"]["name"] == "Орбита Софт", f"оффер не от «Орбиты Софт»: {offers[0]['company']}")
        print(f"✓ {step}: категория «{profile['category']['label']}», входящих офферов 1")

        step = "2. Привязка ФСП ID"
        link, _ = call("POST", "/candidate/fsp/link", candidate_token, body={"fsp_id": DEMO_FSP_ID})
        profile = link["profile"]
        category = profile["category"]
        check(link["imported"]["achievements"] == 6, f"ожидалось 6 результатов: {link['imported']}")
        check(category["stack"] == "backend", f"стек после ФСП: {category['stack']}")
        check(category["grade"] == "junior", f"грейд после ФСП: {category['grade']}")
        check(bool(category["grade_note"]), "нет пояснения про гейт опыта")
        ranks = facts_of(profile, kind="rank")
        check(len(ranks) == 1 and ranks[0]["value"]["rank"] == "kms", f"разряд: {ranks}")
        check(all(f["verification"] == "verified" for f in facts_of(profile, source="fsp")), "факты ФСП не verified")
        points_after_fsp = category["grade_points"]
        print(f"✓ {step}: «{category['label']}», {points_after_fsp} баллов; {category['grade_note']}")

        step = "3. Резюме"
        demo, _ = call("GET", "/candidate/resume/demo", candidate_token)
        parsed, _ = call("POST", "/candidate/resume", candidate_token, form={"text": demo["text"]})
        profile = parsed["profile"]
        category = profile["category"]
        years = parsed["extracted"]["experience_years"]
        check(1.3 <= years <= 1.7, f"опыт из демо-резюме: {years}")
        check(category["grade"] == "middle", f"грейд после резюме: {category['grade']}")
        check(any(s["skill"] == "python" for s in parsed["extracted"]["skills"]), "python не извлечён")
        points_after_resume = category["grade_points"]
        check(points_after_resume > points_after_fsp, "баллы после резюме не выросли")
        print(f"✓ {step}: опыт {years} г., «{category['label']}», {points_after_resume} баллов")

        step = "4. Экспресс-тест по Python"
        tests, _ = call("GET", "/candidate/tests", candidate_token)
        check(any(t["skill"] == "python" for t in tests), "теста python нет в списке")
        session, raw_session = call("POST", "/candidate/tests/python/start", candidate_token, expect=(200, 201))
        check(len(session["questions"]) == 6, f"вопросов в сессии: {len(session['questions'])}")
        check('"correct"' not in raw_session, "в ответе start утёк ключ ответов")
        result, _ = call(
            "POST",
            f"/candidate/tests/sessions/{session['session_id']}/submit",
            candidate_token,
            body={"answers": correct_answers(session)},
        )
        profile = result["profile"]
        check(result["level"] == 3 and result["passed"], f"результат теста: {result['level']}")
        check(bool(facts_of(profile, kind="skill", key="python", source="test")), "нет факта python/test")
        points_after_test = profile["category"]["grade_points"]
        check(points_after_test > points_after_resume, "баллы после теста не выросли")
        print(f"✓ {step}: «{result['level_title']}», {points_after_test} баллов; {profile['category']['grade_note']}")

        step = "5. Олимпиада вручную"
        profile, _ = call(
            "POST",
            "/candidate/achievements",
            candidate_token,
            body={
                "title": "Всероссийская олимпиада школьников по информатике",
                "year": 2021,
                "level": "national",
                "result": "prize",
                "discipline": None,
                "document_url": None,
            },
            expect=201,
        )
        manual = facts_of(profile, kind="achievement", source="self")
        check(len(manual) == 1 and manual[0]["verification"] == "declared", f"достижение вручную: {manual}")
        print(f"✓ {step}: «{manual[0]['title']}», {profile['category']['grade_points']} баллов")

        step = "6. Вход работодателем, матрица категорий"
        employer_token = login(EMPLOYER_EMAIL)
        matrix, raw_matrix = call("GET", "/employer/categories", employer_token)
        check(matrix["total_candidates"] >= 20, f"кандидатов в матрице: {matrix['total_candidates']}")
        check(sum(c["count"] for c in matrix["cells"]) == matrix["total_candidates"], "сумма ячеек не равна итогу")
        print(f"✓ {step}: {matrix['total_candidates']} кандидатов, {matrix['fsp_verified_total']} с результатами ФСП")

        step = "7. Поиск"
        query = {"text": "python fastapi разработчик серверной части", "fsp_verified_only": True, "limit": 50}
        search, raw_search = call("POST", "/employer/search", employer_token, body=query)
        check(search["total"] >= 5, f"с результатами ФСП найдено {search['total']}, нужно не меньше 5")
        mine = [m for m in search["items"] if m["candidate"]["id"] == candidate_id]
        check(len(mine) == 1, "демо-соискателя нет в выдаче")
        check(mine[0]["score"] is not None and bool(mine[0]["reasons"]), "нет оценки или объяснения")
        check(search["parsed_query"] and "python" in search["parsed_query"]["skills"], "python не распознан в тексте")
        position = search["items"].index(mine[0]) + 1
        print(f"✓ {step}: найдено {search['total']}, демо-соискатель на месте {position}, оценка {mine[0]['score']}")

        step = "8. Карточка без контактов и оффер"
        card, raw_card = call("GET", f"/employer/candidates/{candidate_id}", employer_token)
        check(card["display_name"] == "Алексей С.", f"имя в карточке: {card['display_name']}")
        check(card["contacts"] is None, "контакты видны до оффера")
        for raw, where in ((raw_card, "карточке"), (raw_search, "выдаче"), (raw_matrix, "матрице")):
            for marker in PRIVATE_MARKERS:
                check(marker not in raw, f"в {where} до оффера видно «{marker}»")
        vacancies, _ = call("GET", "/employer/vacancies", employer_token)
        vacancy = next((v for v in vacancies if v["title"] == "Python-разработчик" and v["is_active"]), None)
        check(vacancy is not None, "нет активной вакансии «Python-разработчик»")
        offer, raw_offer = call(
            "POST",
            "/employer/offers",
            employer_token,
            body={
                "candidate_id": candidate_id,
                "vacancy_id": vacancy["id"],
                "salary": 150000,
                "message": "Алексей, нам подходит ваш профиль. Готовы обсудить задачи и старт.",
            },
            expect=201,
        )
        check(offer["status"] == "sent" and offer["contacts"] is None, "оффер создан неверно")
        for marker in PRIVATE_MARKERS:
            check(marker not in raw_offer, f"в ответе на оффер видно «{marker}»")
        print(f"✓ {step}: «{card['display_name']}», оффер на {offer['salary']} ₽ отправлен")

        step = "9. Соискатель принимает оффер"
        offers, _ = call("GET", "/candidate/offers", candidate_token)
        incoming = next((o for o in offers if o["id"] == offer["id"]), None)
        check(incoming is not None and incoming["company"]["name"] == "Северный код", "оффера нет во входящих")
        check(incoming["employer_contacts"] is None, "контакты работодателя видны до принятия")
        accepted, _ = call(
            "POST", f"/candidate/offers/{offer['id']}/respond", candidate_token, body={"decision": "accept"}
        )
        check(accepted["status"] == "accepted" and accepted["employer_contacts"], "контакты работодателя не открылись")
        card, _ = call("GET", f"/employer/candidates/{candidate_id}", employer_token)
        check(card["contacts"] and card["contacts"]["email"] == CANDIDATE_EMAIL, "контакты соискателя не открылись")
        check(card["display_name"] == "Смирнов Алексей Игоревич", f"полное ФИО не открылось: {card['display_name']}")
        call("POST", f"/candidate/offers/{offer['id']}/respond", candidate_token, body={"decision": "decline"}, expect=409)
        print(f"✓ {step}: стороны видят контакты друг друга, повторный ответ отклонён")

    except StepFailed as failure:
        print(f"✗ {step}: {failure}", file=sys.stderr)
        return 1

    print("\nДемо-сценарий пройден целиком.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
