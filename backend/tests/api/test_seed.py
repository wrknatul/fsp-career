"""The demo data (SPEC section 10): the numbers, the demo accounts, determinism, the command line.

`seeded` fills the in-memory database of the test with `seed_all`; the API tests then talk to
it through the same `client` fixture the other API tests use.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import DateTime, func, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes.candidate_tests import session_seed
from app.core.config import get_settings
from app.core.security import verify_password
from app.db.base import Base
from app.db.session import make_engine
from app.domain import categorizer, embedding, fsp_mapping, quiz, resume_parser
from app.domain.types import Categorization
from app.fsp_registry.mock import MockFspRegistry
from app.models import (
    Candidate,
    Employer,
    Offer,
    ProfileFact,
    QuizSession,
    User,
    Vacancy,
)
from app.services.profile import candidate_prefs, load_fact_rows, to_fact_data

API = "/api/v1"
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
DEMO_PASSWORD = "demo12345"
DEMO_CANDIDATE = "demo.candidate@fsp-career.test"
DEMO_EMPLOYER = "demo.employer@fsp-career.test"


@pytest.fixture()
def seeded(db: Session) -> Session:
    from app.seed import seed_all

    seed_all(db, now=NOW)
    return db


def login(client: Any, email: str) -> dict[str, str]:
    response = client.post(f"{API}/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def count(db: Session, model: Any) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def candidates_with_facts(db: Session, **criteria: Any) -> set[int]:
    statement = select(ProfileFact.candidate_id).distinct()
    for name, value in criteria.items():
        statement = statement.where(getattr(ProfileFact, name) == value)
    return set(db.scalars(statement))


# --- numbers of SPEC section 10 -------------------------------------------------------------------


def test_an_empty_database_gets_the_numbers_of_the_spec(db: Session):
    from app.seed import seed_if_empty

    assert count(db, User) == 0
    assert seed_if_empty(db) is True

    assert count(db, Candidate) == 30
    assert all(c.visible for c in db.scalars(select(Candidate)))
    linked = select(func.count(Candidate.id)).where(Candidate.fsp_id.is_not(None))
    with_resume = select(func.count(Candidate.id)).where(Candidate.resume_text.is_not(None))
    assert db.scalar(linked) == 20
    assert db.scalar(with_resume) == 26
    assert len(candidates_with_facts(db, kind="skill", source="test")) == 16
    assert len(candidates_with_facts(db, kind="achievement", source="self")) == 6

    assert count(db, Employer) == 3
    assert all(e.verified for e in db.scalars(select(Employer)))
    assert count(db, Vacancy) == 6
    assert count(db, User) == 33

    statuses = set(db.scalars(select(Offer.status)))
    assert count(db, Offer) == 6
    assert statuses == {"sent", "accepted", "declined"}


def test_the_demo_accounts_share_one_password(seeded: Session):
    users = list(seeded.scalars(select(User)))

    assert len(users) == 33
    assert all(verify_password(DEMO_PASSWORD, user.password_hash) for user in users)
    assert {u.email for u in users} >= {
        DEMO_CANDIDATE,
        DEMO_EMPLOYER,
        "hr@orbita-soft.test",
        "hr@neurolab.test",
    }
    assert len({u.email for u in users}) == 33


def test_a_second_call_adds_nothing(seeded: Session):
    from app.seed import seed_if_empty

    before = {model: count(seeded, model) for model in (User, Candidate, ProfileFact, Offer)}

    assert seed_if_empty(seeded) is False

    assert {model: count(seeded, model) for model in before} == before


def test_seeding_without_a_session_uses_the_application_database(session_factory, monkeypatch):
    from app import seed

    monkeypatch.setattr(seed, "SessionLocal", session_factory)

    assert seed.seed_if_empty() is True
    assert seed.seed_if_empty() is False

    with session_factory() as db:
        assert count(db, Candidate) == 30


def test_the_application_seeds_an_empty_database_on_start(session_factory, monkeypatch):
    from fastapi.testclient import TestClient

    from app import seed
    from app.core.config import Settings
    from app.db.session import get_db
    from app.main import create_app

    monkeypatch.setattr(seed, "SessionLocal", session_factory)
    application = create_app(Settings(SEED_DEMO_DATA=True))

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as client:  # the context manager runs the lifespan
        response = client.post(
            f"{API}/auth/login", json={"email": DEMO_CANDIDATE, "password": DEMO_PASSWORD}
        )

    assert response.status_code == 200, response.text
    with session_factory() as db:
        assert count(db, Candidate) == 30


# --- the demo candidate and the demo employer ---------------------------------------------------


def test_the_demo_candidate_is_as_the_spec_describes_him(client: Any, seeded: Session):
    user = seeded.scalar(select(User).where(User.email == DEMO_CANDIDATE))
    candidate = user.candidate

    assert user.full_name == "Смирнов Алексей Игоревич"
    assert candidate.birth_date == date(2003, 5, 14)
    assert candidate.city == "Казань"
    assert candidate.telegram == "@alexey_smirnov_demo"
    assert candidate.phone == "+7 900 000-00-17"
    assert candidate.visible is True
    # No FSP link, no resume, no tests, no facts at all: the scenario builds the profile.
    assert candidate.fsp_id is None and candidate.fsp_linked_at is None
    assert candidate.resume_text is None and candidate.resume_parsed_at is None
    assert load_fact_rows(seeded, candidate) == []
    sessions = select(QuizSession).where(QuizSession.candidate_id == candidate.id)
    assert seeded.scalars(sessions).all() == []

    headers = login(client, DEMO_CANDIDATE)
    profile = client.get(f"{API}/candidate/profile", headers=headers).json()
    assert profile["category"]["stack"] is None
    assert profile["category"]["label"] == "Категория не определена"
    assert profile["fsp"] is None and profile["resume"] is None and profile["facts"] == []

    offers = client.get(f"{API}/candidate/offers", headers=headers).json()
    assert len(offers) == 1
    assert offers[0]["company"]["name"] == "Орбита Софт"
    assert offers[0]["company"]["verified"] is True
    assert offers[0]["status"] == "sent"
    assert offers[0]["employer_contacts"] is None
    assert count_offers_of(seeded, candidate.id) == 1


def count_offers_of(db: Session, candidate_id: int) -> int:
    return db.scalar(select(func.count(Offer.id)).where(Offer.candidate_id == candidate_id)) or 0


def test_the_demo_employer_has_an_open_python_vacancy_without_an_offer_to_the_demo_candidate(
    client: Any, seeded: Session
):
    employer = seeded.scalar(select(User).where(User.email == DEMO_EMPLOYER)).employer
    demo = seeded.scalar(select(User).where(User.email == DEMO_CANDIDATE)).candidate

    assert employer.company_name == "Северный код"
    assert employer.verified is True
    python = [v for v in employer.vacancies if v.title == "Python-разработчик"]
    assert len(python) == 1
    vacancy = python[0]
    assert vacancy.is_active is True
    assert vacancy.stack == "backend" and vacancy.grade in {"junior", "middle"}
    offers_to_demo = seeded.scalars(
        select(Offer).where(Offer.candidate_id == demo.id, Offer.employer_id == employer.id)
    ).all()
    assert offers_to_demo == []

    headers = login(client, DEMO_EMPLOYER)
    vacancies = client.get(f"{API}/employer/vacancies", headers=headers).json()
    assert any(v["title"] == "Python-разработчик" and v["is_active"] for v in vacancies)


def test_every_vacancy_and_offer_is_consistent(seeded: Session):
    from app.domain import ontology

    for vacancy in seeded.scalars(select(Vacancy)):
        for skill in [*vacancy.skills_required, *vacancy.skills_optional]:
            assert ontology.is_known_skill(skill), (vacancy.title, skill)
        assert vacancy.salary_from <= vacancy.salary_to
    for offer in seeded.scalars(select(Offer)):
        assert offer.vacancy.employer_id == offer.employer_id
        assert offer.vacancy.salary_from <= offer.salary <= offer.vacancy.salary_to
        assert offer.candidate.visible
        assert (offer.status == "sent") == (offer.responded_at is None)
        assert offer.responded_at is None or offer.responded_at > offer.created_at


# --- the employer sees a matrix and can search --------------------------------------------------


def test_the_matrix_covers_the_stacks_and_every_grade(client: Any, seeded: Session):
    headers = login(client, DEMO_EMPLOYER)

    matrix = client.get(f"{API}/employer/categories", headers=headers).json()

    # 30 candidates, the demo one has no category yet.
    assert matrix["total_candidates"] == 29
    assert sum(cell["count"] for cell in matrix["cells"]) == matrix["total_candidates"]
    stacks = {cell["stack"] for cell in matrix["cells"]}
    grades = {cell["grade"] for cell in matrix["cells"]}
    assert len(stacks) >= 8  # SPEC: all stacks, perhaps except one or two
    assert grades == {"intern", "junior", "middle", "senior"}
    assert matrix["fsp_verified_total"] == 20
    assert max(cell["count"] for cell in matrix["cells"]) <= 5, "one cell must not hold the pool"


@pytest.mark.parametrize(
    "query",
    [
        {"fsp_verified_only": True, "limit": 50},
        {
            "text": "python fastapi разработчик серверной части",
            "fsp_verified_only": True,
            "limit": 50,
        },
    ],
)
def test_the_fsp_switch_leaves_at_least_five_candidates(client: Any, seeded: Session, query):
    headers = login(client, DEMO_EMPLOYER)

    response = client.post(f"{API}/employer/search", json=query, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 5
    assert all(item["candidate"]["fsp_linked"] for item in body["items"])
    if "text" in query:
        assert body["items"][0]["score"] is not None and body["items"][0]["reasons"]


# --- profiles come from the services of the API -------------------------------------------------


def test_stored_categories_are_what_the_domain_computes(seeded: Session):
    for candidate in seeded.scalars(select(Candidate)):
        facts = [to_fact_data(row) for row in load_fact_rows(seeded, candidate)]
        expected = categorizer.categorize(facts, candidate_prefs(candidate))
        assert Categorization.model_validate(candidate.category) == expected, candidate.user.email
        text = embedding.profile_text(facts, expected, candidate.about, candidate.resume_text)
        assert candidate.embedding == embedding.embed(text), candidate.user.email
        assert len(candidate.embedding) == 384


def test_linked_candidates_match_the_registry_the_way_the_link_checks_it(
    client: Any, seeded: Session
):
    registry = MockFspRegistry()
    linked = list(seeded.scalars(select(Candidate).where(Candidate.fsp_id.is_not(None))))
    assert len(linked) == 20
    assert "FSP-2024-00117" not in {c.fsp_id for c in linked}  # the demo record stays free

    for candidate in linked:
        athlete = registry.get_athlete(candidate.fsp_id)
        assert candidate.user.full_name == athlete["full_name"]
        assert candidate.birth_date == date.fromisoformat(athlete["birth_date"])
        rows = load_fact_rows(seeded, candidate)
        stored = [(r.kind, r.key, r.value) for r in rows if r.source == "fsp"]
        expected = [(f.kind, f.key, f.value) for f in fsp_mapping.facts_from_fsp(athlete)]
        assert sorted(stored, key=repr) == sorted(expected, key=repr), candidate.fsp_id
        assert all(r.verification == "verified" for r in candidate.facts if r.source == "fsp")

    # The API agrees: linking the same id again is refused as "already linked to you".
    candidate = linked[0]
    headers = login(client, candidate.user.email)
    response = client.post(
        f"{API}/candidate/fsp/link", json={"fsp_id": candidate.fsp_id}, headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "FSP_ALREADY_LINKED"
    assert response.json()["details"] == {"linked_to_you": True}


def test_resume_facts_are_what_the_parser_returns_for_the_stored_text(seeded: Session):
    with_resume = list(seeded.scalars(select(Candidate).where(Candidate.resume_text.is_not(None))))
    assert len(with_resume) == 26

    for candidate in with_resume:
        parsed = resume_parser.parse_resume(
            candidate.resume_text, NOW.date(), full_name=candidate.user.full_name
        )
        stored = [
            (r.kind, r.key, r.title, r.value, r.evidence)
            for r in load_fact_rows(seeded, candidate)
            if r.source == "resume"
        ]
        expected = [(f.kind, f.key, f.title, f.value, f.evidence) for f in parsed.facts]
        assert sorted(stored, key=repr) == sorted(expected, key=repr), candidate.user.email
        assert candidate.user.full_name in candidate.resume_text
        # The parser keeps contacts out of the facts.
        own_contacts = [candidate.user.email, candidate.telegram, candidate.phone]
        for _, _, title, value, evidence in stored:
            blob = f"{title} {value} {evidence}"
            assert not [c for c in own_contacts if c and c in blob], candidate.user.email


def test_planned_tests_are_real_sessions_that_grade_to_the_stored_result(seeded: Session):
    secret = get_settings().JWT_SECRET
    sessions = list(seeded.scalars(select(QuizSession)))
    assert sessions

    best: dict[tuple[int, str], int] = {}
    for session in sessions:
        outcome = quiz.grade_session(
            session.skill, session_seed(secret, session.id), session.answers
        )
        assert outcome.level == session.level >= 1
        assert outcome.score == session.score
        assert session.submitted_at is not None and session.submitted_at < NOW
        key = (session.candidate_id, session.skill)
        best[key] = max(best.get(key, 0), outcome.level)

    facts = {
        (f.candidate_id, f.key): f.value["level"]
        for f in seeded.scalars(
            select(ProfileFact).where(ProfileFact.kind == "skill", ProfileFact.source == "test")
        )
    }
    assert facts == best


def test_manual_achievements_are_declared_and_deterministic(seeded: Session):
    manual = select(ProfileFact).where(
        ProfileFact.kind == "achievement", ProfileFact.source == "self"
    )
    facts = list(seeded.scalars(manual))

    assert len(facts) == 6
    assert all(f.verification == "declared" and f.key.startswith("manual:") for f in facts)
    assert len({f.key for f in facts}) == 6


def test_contacts_are_unique_and_none_contains_another(seeded: Session):
    """The privacy tests search raw text for these strings: a prefix would be a false alarm."""
    people = list(seeded.scalars(select(Candidate)))
    for kind, values in {
        "email": [c.user.email for c in people],
        "telegram": [c.telegram for c in people],
        "phone": [c.phone for c in people],
        "name": [c.user.full_name for c in people],
    }.items():
        assert len(set(values)) == len(values), kind
        for one in values:
            assert [other for other in values if other != one and one in other] == [], (kind, one)
    # Invented people never share a surname with anybody (some registry families do).
    registry_surnames = [c.user.full_name.split()[0] for c in people if c.fsp_id]
    invented = [c.user.full_name.split()[0] for c in people if not c.fsp_id]
    assert len(set(invented)) == len(invented)
    assert not set(invented) & set(registry_surnames)
    assert invented.count("Смирнов") == 1 and "Смирнов" not in registry_surnames


def test_every_address_is_in_the_reserved_test_zone(seeded: Session):
    for user in seeded.scalars(select(User)):
        assert user.email.endswith(".test"), user.email


def test_every_resume_template_is_used_and_agrees_with_the_questionnaire(seeded: Session):
    from app.seed import RESUMES_DIR, _header_work_formats
    from app.seed_data import plan

    used = {spec.template for spec in plan.CANDIDATES if spec.template}
    assert used == {path.stem for path in RESUMES_DIR.glob("*.txt")}

    with_resume = list(seeded.scalars(select(Candidate).where(Candidate.resume_text.is_not(None))))
    for candidate in with_resume:
        # The header line of the resume ("Москва · удалённо") and the settings must agree.
        assert set(candidate.work_formats) == set(_header_work_formats(candidate.resume_text))


def test_everybody_but_the_demo_candidate_has_a_filled_questionnaire(seeded: Session):
    for candidate in seeded.scalars(select(Candidate)):
        if candidate.user.email == DEMO_CANDIDATE:
            assert not candidate.work_formats and candidate.salary_expectation is None
        else:
            assert candidate.work_formats, candidate.user.email
            assert candidate.salary_expectation and candidate.city, candidate.user.email
            assert candidate.category["stack"] is not None, candidate.user.email


def test_the_schema_is_created_in_memory_without_alembic():
    from app import seed

    engine = make_engine("sqlite://")
    try:
        assert not inspect(engine).has_table("users")
        seed.ensure_schema(engine)
        tables = set(inspect(engine).get_table_names())
        assert "users" in tables and "alembic_version" not in tables
    finally:
        engine.dispose()


# --- determinism and reset ----------------------------------------------------------------------


def snapshot(db: Session, *, datetimes: bool, volatile: bool = False) -> dict[str, list[tuple]]:
    """Every row of every table; `password_hash` is always left out (bcrypt salts it).

    `datetimes=False` leaves out every time column. `volatile=False` keeps the two time columns
    that the services stamp with the wall clock (`profile_facts.created_at`,
    `candidates.updated_at`) out of a comparison that otherwise includes the times.
    """
    db.expire_all()
    result: dict[str, list[tuple]] = {}
    for table in Base.metadata.sorted_tables:
        columns = []
        for column in table.columns:
            is_time = isinstance(getattr(column.type, "impl", column.type), DateTime)
            if column.name == "password_hash" or (is_time and not datetimes):
                continue
            if (table.name, column.name) in {
                ("profile_facts", "created_at"),
                ("candidates", "updated_at"),
            } and not volatile:
                continue
            columns.append(column)
        rows = db.execute(select(*columns).order_by(*table.primary_key.columns)).all()
        result[table.name] = [tuple(row) for row in rows]
    return result


@pytest.mark.filterwarnings("error::sqlalchemy.exc.SAWarning")
def test_two_resets_give_identical_data(db: Session):
    from app.seed import reset_all, seed_all

    seed_all(db, now=NOW)
    first = snapshot(db, datetimes=True)
    assert len(first["candidates"]) == 30

    reset_all(db)
    db.commit()
    assert count(db, User) == 0
    seed_all(db, now=NOW)
    second = snapshot(db, datetimes=True)

    assert first == second
    # The ids restart too, so the demo candidate is always candidate 1 on SQLite.
    assert [row[0] for row in first["candidates"]][:3] == [1, 2, 3]


@pytest.mark.filterwarnings("error::sqlalchemy.exc.SAWarning")
def test_reset_removes_whatever_else_the_database_held(db: Session, candidate_user, employer_user):
    from app.seed import reset_all, seed_all

    assert count(db, User) == 2
    reset_all(db)
    seed_all(db, now=NOW)

    assert count(db, User) == 33
    assert db.scalar(select(User).where(User.email == "candidate@example.test")) is None


def test_a_failed_reset_keeps_the_old_data(seeded: Session, monkeypatch):
    from app import seed

    before = snapshot(seeded, datetimes=True, volatile=True)

    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(seed, "_build_offers", boom)
    seed.reset_all(seeded)
    with pytest.raises(RuntimeError):
        seed.seed_all(seeded, now=NOW)

    assert snapshot(seeded, datetimes=True, volatile=True) == before


def test_the_summary_lists_every_cell_and_the_totals(seeded: Session):
    from app.seed import format_summary, summarize

    summary = summarize(seeded)
    text = format_summary(summary)

    assert (summary.candidates, summary.with_fsp, summary.with_resume) == (30, 20, 26)
    assert (summary.with_tests, summary.with_manual, summary.undefined) == (16, 6, 1)
    assert sum(total for total, _ in summary.matrix.values()) == 29
    assert sum(linked for _, linked in summary.matrix.values()) == 20
    assert "Стек × грейд" in text and "Backend" in text and "с ФСП: 20" in text


# --- the command line ---------------------------------------------------------------------------


def test_the_command_line_builds_the_schema_and_repeats_itself(tmp_path: Path, capsys):
    from app import seed

    engine = make_engine(f"sqlite:///{tmp_path / 'cli.sqlite3'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        assert seed.main(["--reset"], engine=engine) == 0
        out = capsys.readouterr().out
        assert "Демо-данные созданы" in out and "Стек × грейд" in out

        with factory() as db:
            first = snapshot(db, datetimes=False)
            assert count(db, Candidate) == 30
        assert inspect(engine).has_table("alembic_version")  # created by Alembic, not create_all

        assert seed.main(["--reset"], engine=engine) == 0
        capsys.readouterr()
        with factory() as db:
            assert snapshot(db, datetimes=False) == first

        # Without --reset a filled database is left alone.
        assert seed.main([], engine=engine) == 0
        assert "уже есть" in capsys.readouterr().out
        with factory() as db:
            assert snapshot(db, datetimes=False) == first
    finally:
        engine.dispose()


def test_the_command_line_seeds_a_migrated_database_without_touching_the_schema(
    tmp_path: Path, capsys
):
    from app import seed

    engine = make_engine(f"sqlite:///{tmp_path / 'cli.sqlite3'}")
    try:
        seed.ensure_schema(engine)
        tables = set(inspect(engine).get_table_names())
        assert "alembic_version" in tables and "users" in tables

        seed.ensure_schema(engine)  # a second call finds the tables and does nothing
        assert set(inspect(engine).get_table_names()) == tables
        assert seed.main([], engine=engine) == 0
        assert "Демо-данные созданы" in capsys.readouterr().out
    finally:
        engine.dispose()
