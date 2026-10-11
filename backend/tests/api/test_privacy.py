"""SPEC section 12, item 4: until an offer is accepted, an employer never sees a candidate's
e-mail, telegram, phone, birth date or full name, not even when the candidate typed them into
"about me", the resume text, an achievement title or an offer comment.

The seeded database is walked as an employer would: the matrix with every slice, the search
with many filters and on every page, every candidate card (existing, hidden and missing ids),
the offers and the vacancies. The raw text of every answer is searched for every private
string of every candidate; the only candidates exempt are those who accepted an offer of
*this* employer. A hidden candidate must be found nowhere.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.redaction import display_name
from app.fsp_registry.mock import MockFspRegistry
from app.models import Candidate, Offer, User

API = "/api/v1"
PASSWORD = "demo12345"
REDACTED = "[скрыто]"
EMPLOYERS = {
    "north": "demo.employer@fsp-career.test",
    "orbita": "hr@orbita-soft.test",
    "neuro": "hr@neurolab.test",
}
TEAM_ROLES = ["lead", "developer", "researcher", "devops", "qa", "analyst"]
STACKS = [
    "backend", "frontend", "fullstack", "mobile", "ml", "devops", "security", "embedded", "qa",
    "analyst",
]  # fmt: skip
GRADES = ["intern", "junior", "middle", "senior"]
FORMATS = ["remote", "office", "hybrid"]
DISCIPLINES = ["algorithmic", "product", "security", "robotics", "uav"]

# What one candidate writes into the free texts (all of it is invented).
LEAK_PHONE = "+7 913 555-44-33"
LEAK_PHONE_8 = "8 (913) 555-44-33"
LEAK_PHONE_PLAIN = "89135554433"
LEAK_EMAIL = "privacy.leak@example.test"
LEAK_HANDLE = "@leaky_nick_77"
MONTHS_GENITIVE = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)  # fmt: skip


@dataclass(frozen=True)
class Typed:
    """The free texts of one candidate who types private data into every field.

    Besides the extra contacts above, the candidate writes *their own* name, birth date,
    nickname without "@" and registered phone in several notations, in "about me", in the
    first line of the resume (next to a skill, so the quote of that skill is the line with the
    name), in an achievement title and in the comment to an offer.
    """

    about: str
    resume: str
    achievement_title: str
    comment: str
    secrets: list[str]


def typed_by(person: Candidate) -> Typed:
    full_name = person.user.full_name
    surname, first_name, patronymic = full_name.split()
    born = person.birth_date
    dotted = born.strftime("%d.%m.%Y")
    words = f"{born.day} {MONTHS_GENITIVE[born.month - 1]} {born.year}"
    slashed = born.strftime("%d/%m/%Y")
    nick = (person.telegram or "").lstrip("@")
    core = re.sub(r"\D", "", person.phone or "")[-10:]
    own_phone_8 = f"8 ({core[:3]}) {core[3:6]}-{core[6:8]}-{core[8:]}"
    own_phone_plain = f"8{core}"
    name_then_surname = f"{first_name} {surname}"

    about = (
        f"Звоните {LEAK_PHONE} или {LEAK_PHONE_8}, пишите на {LEAK_EMAIL} или в телеграм "
        f"{LEAK_HANDLE}. Меня зовут {name_then_surname}, родился {dotted} ({words}). "
        f"Мой ник {nick}, мой номер {own_phone_8}. Люблю Kubernetes и Terraform."
    )
    resume = f"""{full_name} — Python-разработчик
DevOps-инженер

Москва · удалённо
Дата рождения: {born.isoformat()} ({slashed})
Телефон: {LEAK_PHONE_PLAIN} или {own_phone_plain}
Почта: {LEAK_EMAIL}
Telegram: {LEAK_HANDLE}, ник без собаки: {nick}

Опыт работы

01.2021 – н.в.
DevOps-инженер, ООО «Тестовый Стенд»
Kubernetes и Terraform каждый день. Пишите {LEAK_EMAIL}, звоните {LEAK_PHONE} или {LEAK_HANDLE}.
Docker, Linux, Python, CI/CD, Ansible: связь {LEAK_HANDLE} и {LEAK_PHONE}.

Навыки
Kubernetes, Terraform, Docker, Linux, Python, Ansible, CI/CD
"""
    title = f"Хакатон, {full_name} {dotted}, связь: {LEAK_EMAIL}"
    comment = (
        f"Спасибо! Пишите мне на {LEAK_EMAIL} или звоните {LEAK_PHONE}, {LEAK_HANDLE}. "
        f"{name_then_surname}, родился {words}."
    )
    return Typed(
        about=about,
        resume=resume,
        achievement_title=title,
        comment=comment,
        secrets=[
            LEAK_EMAIL,
            LEAK_PHONE,
            "9135554433",
            LEAK_PHONE_8,
            LEAK_PHONE_PLAIN,
            LEAK_HANDLE,
            LEAK_HANDLE.lstrip("@"),
            nick,
            own_phone_8,
            own_phone_plain,
            core,
            name_then_surname,
            words,
            slashed,
        ],
    )


@dataclass(frozen=True)
class Secret:
    candidate_id: int
    kind: str
    value: str


@pytest.fixture()
def seeded(db: Session) -> Session:
    from app.seed import seed_all

    seed_all(db)
    return db


def login(client: Any, email: str) -> dict[str, str]:
    response = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def secrets_of(db: Session) -> list[Secret]:
    """Every private string of every candidate (what an employer must not get)."""
    found: list[Secret] = []
    for candidate in db.scalars(select(Candidate).order_by(Candidate.id)):
        user = candidate.user
        values = {
            "email": user.email,
            "telegram": candidate.telegram,
            "telegram without @": (candidate.telegram or "").lstrip("@"),
            "phone": candidate.phone,
            "phone digits": re.sub(r"\D", "", candidate.phone or ""),
            "phone without country code": re.sub(r"\D", "", candidate.phone or "")[-10:],
            "birth date": candidate.birth_date.isoformat() if candidate.birth_date else None,
            "birth date dotted": (
                candidate.birth_date.strftime("%d.%m.%Y") if candidate.birth_date else None
            ),
            "full name": user.full_name,
            "surname": user.full_name.split()[0],
        }
        found += [Secret(candidate.id, kind, value) for kind, value in values.items() if value]
    return found


def leak_secrets(candidate_id: int, typed: Typed) -> list[Secret]:
    """What the candidate typed into the free texts: each string must stay out of every answer."""
    return [Secret(candidate_id, "typed private string", value) for value in typed.secrets]


def strings_in(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in [*value.keys(), *value.values()] for s in strings_in(item)]
    if isinstance(value, list):
        return [s for item in value for s in strings_in(item)]
    return []


FORBIDDEN_KEYS = {"birth_date", "resume_text", "resume_filename", "password_hash", "consent_at"}
CONTACT_KEYS = {"email", "telegram", "phone"}


def forbidden_keys_in(value: Any, *, inside_contacts: bool = False) -> list[str]:
    """Keys that must not exist in an answer to an employer (contacts only under `contacts`)."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_KEYS or (key in CONTACT_KEYS and not inside_contacts):
                found.append(key)
            found += forbidden_keys_in(item, inside_contacts=key == "contacts")
    elif isinstance(value, list):
        for item in value:
            found += forbidden_keys_in(item, inside_contacts=inside_contacts)
    return found


class EmployerWalk:
    """Calls the routes of one employer and checks every answer for private data."""

    def __init__(
        self, client: Any, headers: dict[str, str], secrets: list[Secret], unlocked: set[int]
    ) -> None:
        self.client = client
        self.headers = headers
        self.secrets = secrets
        self.unlocked = unlocked
        self.requests = 0
        # Strings that are legitimately in an answer because they belong to an unlocked
        # candidate (a surname that two families share is the only way another one matches).
        self.exempt_text = "\n".join(s.value for s in secrets if s.candidate_id in unlocked)
        # Secrets of closed candidates that the exemption above would let through; with the
        # seeded data there must be none, otherwise the check is weaker than it looks.
        self.masked = [
            s for s in secrets if s.candidate_id not in unlocked and s.value in self.exempt_text
        ]
        self.seen_ids: set[int] = set()

    def check(self, label: str, response: Any, *, own_data: bool = False) -> Any:
        self.requests += 1
        text = response.text
        try:
            body = response.json()
        except ValueError:
            body = None
        haystacks = [text, "\n".join(strings_in(body))]
        for secret in self.secrets:
            if secret.candidate_id in self.unlocked or secret.value in self.exempt_text:
                continue
            for haystack in haystacks:
                assert secret.value not in haystack, (
                    f"{label}: «{secret.kind}» of candidate {secret.candidate_id} is in the answer"
                )
        if not own_data:
            assert forbidden_keys_in(body) == [], f"{label}: {forbidden_keys_in(body)}"
        return body

    def get(self, path: str, *, own_data: bool = False, expect: tuple[int, ...] = (200,)) -> Any:
        response = self.client.get(f"{API}{path}", headers=self.headers)
        assert response.status_code in expect, (path, response.status_code, response.text)
        return self.check(f"GET {path}", response, own_data=own_data)

    def search(self, body: dict[str, Any], *, page: int = 10) -> list[dict[str, Any]]:
        """Every page of a search; returns all items."""
        items: list[dict[str, Any]] = []
        offset = 0
        while True:
            query = {**body, "limit": page, "offset": offset}
            response = self.client.post(f"{API}/employer/search", json=query, headers=self.headers)
            assert response.status_code == 200, (query, response.text)
            answer = self.check(f"POST /employer/search {body}", response)
            items += answer["items"]
            offset += page
            if offset >= answer["total"] or offset > 500:
                break
        self.seen_ids.update(item["candidate"]["id"] for item in items)
        return items

    def walk(self, *, full: bool, max_id: int) -> None:
        self.get("/employer/profile", own_data=True)
        # The matrix and all its slices.
        self.get("/employer/categories")
        for role in TEAM_ROLES:
            self.get(f"/employer/categories?team_role={role}")
        for work_format in FORMATS:
            self.get(f"/employer/categories?work_format={work_format}")
        self.get("/employer/categories?team_role=developer&work_format=remote")

        vacancies = self.get("/employer/vacancies")
        self.get("/employer/offers")

        # The search: no filters, then every filter, every page.
        self.search({})
        self.search({"text": "python fastapi postgresql разработчик серверной части"})
        self.search({"fsp_verified_only": True})
        self.search({"confirmed_only": True})
        self.search({"stacks": ["backend", "fullstack"], "grades": ["middle", "senior"]})
        if full:
            for stack in STACKS:
                self.search({"stacks": [stack]})
            for grade in GRADES:
                self.search({"grades": [grade]})
            for role in TEAM_ROLES:
                self.search({"team_roles": [role]})
            for work_format in FORMATS:
                self.search({"work_formats": [work_format]})
            for discipline in DISCIPLINES:
                self.search({"disciplines": [discipline]})
            self.search({"city": "Москва"})
            self.search({"salary_max": 150000})
            self.search({"text": "kubernetes terraform ansible docker devops"})
            self.search(
                {
                    "skills_required": ["python"],
                    "skills_optional": ["docker"],
                    "strict_skills": True,
                }
            )
            self.search({"text": "Звоните privacy.leak"})
            for vacancy in vacancies:
                self.search({"vacancy_id": vacancy["id"]})

        # Every card: existing, hidden or missing ids alike.
        for candidate_id in [0, *range(1, max_id + 2), 999_999]:
            self.get(f"/employer/candidates/{candidate_id}", expect=(200, 404))


def employer_walk(
    client: Any, db: Session, employer_key: str, secrets: list[Secret]
) -> EmployerWalk:
    headers = login(client, EMPLOYERS[employer_key])
    employer = db.scalar(select(User).where(User.email == EMPLOYERS[employer_key])).employer
    unlocked = set(
        db.scalars(
            select(Offer.candidate_id).where(
                Offer.employer_id == employer.id, Offer.status == "accepted"
            )
        )
    )
    return EmployerWalk(client, headers, secrets, unlocked)


@pytest.fixture()
def leaky(client: Any, seeded: Session) -> dict[str, Any]:
    """The seeded database where one candidate typed private data into every free text.

    Candidate "P" (a DevOps engineer without FSP) writes contacts, their own full name, birth
    date and nickname (see `typed_by`) into "about me", the resume text and the title of an
    achievement; the demo employer sends them an offer and they decline it with the same kind
    of data in the comment.
    """
    person = next(
        c
        for c in seeded.scalars(select(Candidate).order_by(Candidate.id))
        if c.fsp_id is None and (c.category or {}).get("stack") == "devops"
    )
    typed = typed_by(person)
    headers = login(client, person.user.email)
    answers = [
        client.patch(f"{API}/candidate/profile", json={"about": typed.about}, headers=headers),
        client.post(
            f"{API}/candidate/resume", files={"text": (None, typed.resume)}, headers=headers
        ),
        client.post(
            f"{API}/candidate/achievements",
            json={
                "title": typed.achievement_title,
                "year": 2024,
                "level": "regional",
                "result": "winner",
            },
            headers=headers,
        ),
    ]
    assert [a.status_code for a in answers] == [200, 200, 201], [a.text for a in answers]

    secrets = [*secrets_of(seeded), *leak_secrets(person.id, typed)]
    walk = employer_walk(client, seeded, "north", secrets)
    vacancies = walk.get("/employer/vacancies")
    vacancy = next(v for v in vacancies if v["title"] == "Python-разработчик")
    offer = client.post(
        f"{API}/employer/offers",
        json={"candidate_id": person.id, "vacancy_id": vacancy["id"], "salary": 200_000},
        headers=walk.headers,
    )
    assert offer.status_code == 201, offer.text
    walk.check("POST /employer/offers", offer)  # the answer to the sender is private too
    declined = client.post(
        f"{API}/candidate/offers/{offer.json()['id']}/respond",
        json={"decision": "decline", "comment": typed.comment},
        headers=headers,
    )
    assert declined.status_code == 200, declined.text
    return {
        "id": person.id,
        "headers": headers,
        "email": person.user.email,
        "max_id": max(seeded.scalars(select(Candidate.id))),
        "secrets": secrets,
    }


# --- before an accepted offer -------------------------------------------------------------------


@pytest.mark.parametrize("employer_key", ["north", "orbita", "neuro"])
def test_nothing_private_reaches_an_employer_before_an_accepted_offer(
    client: Any, seeded: Session, leaky: dict[str, Any], employer_key: str
):
    walk = employer_walk(client, seeded, employer_key, leaky["secrets"])

    walk.walk(full=employer_key == "north", max_id=leaky["max_id"])

    assert walk.masked == []
    assert walk.requests > 40
    # The walk reached the leaky candidate (otherwise it would prove nothing about them).
    assert leaky["id"] in walk.seen_ids


def test_the_typed_contacts_are_replaced_by_a_mark_not_dropped_silently(
    client: Any, seeded: Session, leaky: dict[str, Any]
):
    """Positive control: the leaky texts do reach the employer, with the contacts hidden."""
    walk = employer_walk(client, seeded, "north", leaky["secrets"])

    card = walk.get(f"/employer/candidates/{leaky['id']}")
    assert REDACTED in card["about"] and "Kubernetes" in card["about"]
    achievements = [f for f in card["facts"] if f["kind"] == "achievement"]
    assert any(REDACTED in f["title"] and "Хакатон" in f["title"] for f in achievements)
    assert any(REDACTED in (f["evidence"] or "") for f in card["facts"] if f["source"] == "resume")
    assert {"kubernetes", "terraform"} <= {f["key"] for f in card["facts"] if f["kind"] == "skill"}
    # The quote of a skill on the first line of the resume keeps the skill, not the name.
    python = next(f for f in card["facts"] if f["key"] == "python" and f["source"] == "resume")
    assert python["evidence"].startswith(REDACTED) and "Python-разработчик" in python["evidence"]
    assert "Данилов" not in card["about"] and "Тимофей Данилов" not in card["about"]
    assert card["display_name"] == "Тимофей Д."
    assert card["contacts"] is None

    hit = next(
        item
        for item in walk.search({"text": "kubernetes terraform"})
        if item["candidate"]["id"] == leaky["id"]
    )
    assert hit["candidate"]["display_name"] == "Тимофей Д."
    assert REDACTED in hit["candidate"]["about"]

    offers = walk.get("/employer/offers")
    declined = next(o for o in offers if o["candidate"]["id"] == leaky["id"])
    assert declined["status"] == "declined" and declined["contacts"] is None
    assert REDACTED in declined["candidate_comment"]
    assert declined["candidate"]["display_name"] == "Тимофей Д."


def test_stored_texts_with_the_name_and_birth_date_are_hidden_when_read(
    client: Any, seeded: Session
):
    """The filter works on read too: old rows, or any path that stored a name unfiltered."""
    person = seeded.scalar(select(Candidate).where(Candidate.fsp_id == "FSP-2022-00053"))
    born = person.birth_date
    private = f"{person.user.full_name}, {born.isoformat()}, {born.strftime('%d.%m.%Y')}"
    skill = next(f for f in person.facts if f.source == "resume" and f.kind == "skill")
    achievement = next(f for f in person.facts if f.kind == "achievement")
    skill.evidence = f"{private} — Python"
    achievement.title = f"{achievement.title} {private}"
    achievement.value = {**achievement.value, "note": private}
    seeded.commit()

    walk = employer_walk(client, seeded, "north", secrets_of(seeded))
    card = walk.get(f"/employer/candidates/{person.id}")
    shown = {f["id"]: f for f in card["facts"]}

    hidden = ", ".join([REDACTED] * 3)  # the name, the ISO date, the dotted date
    assert shown[skill.id]["evidence"] == f"{hidden} — Python"
    assert shown[achievement.id]["title"].endswith(hidden)
    assert shown[achievement.id]["value"]["note"] == hidden
    walk.walk(full=False, max_id=person.id)
    assert person.id in walk.seen_ids


def test_other_employers_do_not_see_the_typed_contacts_either(
    client: Any, seeded: Session, leaky: dict[str, Any]
):
    for key in ("orbita", "neuro"):
        walk = employer_walk(client, seeded, key, leaky["secrets"])
        card = walk.get(f"/employer/candidates/{leaky['id']}")
        assert card["contacts"] is None and card["offers"] == []
        assert REDACTED in card["about"]


# --- an accepted offer opens the data of that pair only -----------------------------------------


def test_an_accepted_offer_opens_the_contacts_for_that_employer_only(client: Any, seeded: Session):
    accepted = list(seeded.scalars(select(Offer).where(Offer.status == "accepted")))
    assert len(accepted) == 2 and len({o.employer_id for o in accepted}) == 2
    secrets = secrets_of(seeded)

    for offer in accepted:
        candidate = offer.candidate
        owner_email = offer.employer.user.email
        for key, email in EMPLOYERS.items():
            walk = employer_walk(client, seeded, key, secrets)
            card = walk.get(f"/employer/candidates/{candidate.id}")
            if email == owner_email:
                assert card["display_name"] == candidate.user.full_name
                assert card["contacts"] == {
                    "email": candidate.user.email,
                    "telegram": candidate.telegram,
                    "phone": candidate.phone,
                }
                mine = next(o for o in walk.get("/employer/offers") if o["id"] == offer.id)
                assert mine["contacts"]["email"] == candidate.user.email
                # Not even now: the birth date, the resume and the registration data.
                assert candidate.birth_date.isoformat() not in json.dumps(card, ensure_ascii=False)
                assert forbidden_keys_in(card) == []
            else:
                assert card["display_name"] == display_name(candidate.user.full_name)
                assert card["contacts"] is None
                assert card["offers"] == []


def test_a_declined_offer_keeps_the_candidate_closed(client: Any, seeded: Session):
    declined = seeded.scalar(select(Offer).where(Offer.status == "declined"))
    candidate = declined.candidate
    email = declined.employer.user.email

    headers = login(client, email)
    card = client.get(f"{API}/employer/candidates/{candidate.id}", headers=headers).json()

    assert card["contacts"] is None
    assert card["display_name"] == display_name(candidate.user.full_name)
    assert candidate.user.full_name not in json.dumps(card, ensure_ascii=False)
    assert [o["status"] for o in card["offers"]] == ["declined"]


def test_a_candidate_cannot_use_the_employer_routes(client: Any, seeded: Session):
    headers = login(client, "demo.candidate@fsp-career.test")

    for method, path in (
        ("get", "/employer/categories"),
        ("get", "/employer/candidates/2"),
        ("get", "/employer/offers"),
        ("post", "/employer/search"),
    ):
        response = getattr(client, method)(f"{API}{path}", headers=headers)
        assert response.status_code in (403, 422), (path, response.status_code)
        if response.status_code == 403:
            assert response.json()["error_code"] == "FORBIDDEN"


# --- a hidden candidate -------------------------------------------------------------------------


def test_a_hidden_candidate_is_found_nowhere(client: Any, seeded: Session):
    hidden = seeded.scalar(select(Candidate).where(Candidate.fsp_id == "FSP-2022-00053"))
    hidden_id, short = hidden.id, display_name(hidden.user.full_name)
    secrets = [*secrets_of(seeded), Secret(hidden_id, "short name", short)]
    employer = login(client, EMPLOYERS["north"])

    def matrix_total() -> int:
        return client.get(f"{API}/employer/categories", headers=employer).json()["total_candidates"]

    visible_before = EmployerWalk(client, employer, [], set())
    assert hidden_id in {i["candidate"]["id"] for i in visible_before.search({})}
    total_before = matrix_total()
    assert client.get(f"{API}/employer/candidates/{hidden_id}", headers=employer).status_code == 200

    own = login(client, hidden.user.email)
    response = client.patch(f"{API}/candidate/profile", json={"visible": False}, headers=own)
    assert response.status_code == 200 and response.json()["visible"] is False

    walk = employer_walk(client, seeded, "north", secrets)
    walk.walk(full=True, max_id=max(seeded.scalars(select(Candidate.id))))
    assert hidden_id not in walk.seen_ids
    assert matrix_total() == total_before - 1

    missing = client.get(f"{API}/employer/candidates/999999", headers=employer)
    gone = client.get(f"{API}/employer/candidates/{hidden_id}", headers=employer)
    assert gone.status_code == missing.status_code == 404
    assert {**gone.json(), "trace_id": ""} == {**missing.json(), "trace_id": ""}

    offer = client.post(
        f"{API}/employer/offers",
        json={"candidate_id": hidden_id, "vacancy_id": 1, "salary": 100_000},
        headers=employer,
    )
    assert offer.status_code == 404 and offer.json()["error_code"] == "NOT_FOUND"


def test_a_candidate_who_hides_the_profile_after_an_offer_stays_as_a_name_only(
    client: Any, seeded: Session, leaky: dict[str, Any]
):
    response = client.patch(
        f"{API}/candidate/profile", json={"visible": False}, headers=leaky["headers"]
    )
    assert response.status_code == 200

    walk = employer_walk(client, seeded, "north", leaky["secrets"])
    walk.walk(full=False, max_id=leaky["max_id"])

    assert leaky["id"] not in walk.seen_ids
    entry = next(o for o in walk.get("/employer/offers") if o["candidate"]["id"] == leaky["id"])
    candidate = entry["candidate"]
    assert candidate["display_name"] == "Тимофей Д."
    assert candidate["city"] is None and candidate["about"] is None
    assert candidate["salary_expectation"] is None and candidate["category"]["stack"] is None
    assert entry["contacts"] is None
    gone = walk.get(f"/employer/candidates/{leaky['id']}", expect=(404,))
    assert gone["error_code"] == "NOT_FOUND"


# --- the public mock of the registry ------------------------------------------------------------


def test_the_registry_mock_never_returns_the_birth_date_the_city_or_the_full_name(client: Any):
    athletes = MockFspRegistry().athletes()
    assert len(athletes) == 24

    for athlete in athletes:
        response = client.get(f"{API}/fsp-mock/athletes/{athlete['fsp_id']}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == {"fsp_id", "short_name", "region", "ranks", "results"}
        assert "birth_date" not in response.text and "full_name" not in response.text
        assert athlete["birth_date"] not in response.text
        assert athlete["full_name"] not in response.text
        for result in body["results"]:
            assert set(result["competition"]) >= {"city", "title"}  # the competition's own city
            assert "birth_date" not in result

    unknown = client.get(f"{API}/fsp-mock/athletes/FSP-1999-00000")
    assert unknown.status_code == 404 and unknown.json()["error_code"] == "FSP_ATHLETE_NOT_FOUND"
