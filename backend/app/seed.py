"""Demo data (SPEC section 10): `python -m app.seed [--reset]` and seeding of an empty database.

* `seed_if_empty(db=None)` fills the database when there are no users yet (the application
  calls it on start when `SEED_DEMO_DATA` is on).
* `python -m app.seed` does the same from the command line; `--reset` first deletes the rows
  of every application table and then seeds again.

Profiles are built by the very services the API uses: facts from the FSP registry come from
`fsp_mapping.facts_from_fsp`, resume facts from `resume_parser.parse_resume`, test facts from
`quiz.grade_session` (with answers chosen to reach the planned level), and every category and
text vector is computed by `recompute_candidate`. No category is written by hand.

The generation is deterministic: one `random.Random(42)` decides everything the plan in
`app/seed_data/plan.py` leaves open (names of the invented people, dates, contacts, the choice
of "about me" texts). Two runs differ only in the wall-clock columns (`created_at`,
`updated_at`, the dates derived from "now") and in `password_hash` (bcrypt salts every hash).
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, delete, func, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes.candidate_tests import session_seed
from app.core.config import get_settings
from app.core.security import hash_password
from app.core.timeutil import utcnow
from app.db.base import Base
from app.db.session import SessionLocal
from app.db.session import engine as default_engine
from app.domain import facts as domain_facts
from app.domain import fsp_mapping, ontology, quiz, resume_parser
from app.domain.scoring_config import QUIZ_TIME_LIMIT_SECONDS
from app.domain.types import Categorization
from app.fsp_registry.mock import MockFspRegistry
from app.models import Candidate, Employer, Offer, ProfileFact, QuizSession, User, Vacancy
from app.seed_data import plan
from app.services.profile import recompute_candidate, replace_facts, upsert_fact

logger = logging.getLogger(__name__)

SEED = 42
DEMO_PASSWORD = "demo12345"
EMAIL_DOMAIN = "fsp-career.test"

BACKEND_DIR = Path(__file__).resolve().parents[1]
RESUMES_DIR = Path(__file__).resolve().parent / "seed_data" / "resumes"

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}  # fmt: skip

# Words of the header line of a resume ("Москва · удалённо или гибрид") -> work format.
_HEADER_FORMATS = (("удалённ", "remote"), ("офис", "office"), ("гибрид", "hybrid"))


# --- result ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SeedSummary:
    """What the database holds after seeding (also printed by the command line)."""

    candidates: int
    with_fsp: int
    with_resume: int
    with_tests: int
    with_manual: int
    employers: int
    vacancies: int
    offers: dict[str, int]
    # (stack, grade) -> (all candidates, of them linked to the FSP registry)
    matrix: dict[tuple[str, str], tuple[int, int]]
    undefined: int


@dataclass
class _Context:
    db: Session
    now: datetime
    registry: MockFspRegistry
    password_hash: str
    jwt_secret: str
    used_contacts: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class _Person:
    full_name: str
    birth_date: date
    city: str
    email: str
    telegram: str
    phone: str


# --- small helpers --------------------------------------------------------------------------------


def _translit(text: str) -> str:
    return "".join(_TRANSLIT.get(char, char) for char in text.lower())


def _read_template(name: str) -> str:
    return (RESUMES_DIR / f"{name}.txt").read_text(encoding="utf-8")


def _header_work_formats(text: str) -> list[str]:
    """Work formats named on the header line of a resume (the line with the city and a dot).

    The rule parser reads such a header too ("Москва · удалённо"); this is the fallback that
    keeps the questionnaire of the seeded candidate in agreement with the text of the resume
    whatever the parser rules become.
    """
    for line in text.splitlines()[1:8]:
        if "·" in line:
            lowered = line.lower()
            return [name for word, name in _HEADER_FORMATS if word in lowered]
    return []


def _make_phone(rng: random.Random, used: set[str]) -> str:
    """An invented phone in the range `+7 900 000-NN-NN`, like the demo candidate's.

    The code "000" is never assigned to a subscriber, so no seeded number can belong to a real
    person (SPEC section 10: every person is invented). The four draws of the old random
    number are kept, so the rest of the generated data does not change.
    """
    while True:
        rng.randint(10, 99)  # the old region and subscriber digits: drawn and dropped
        rng.randint(100, 999)
        phone = f"+7 900 000-{rng.randint(10, 99)}-{rng.randint(10, 99)}"
        if phone not in used and phone != plan.DEMO_CANDIDATE_PHONE:
            used.add(phone)
            return phone


def _unique_slug(base: str, used: set[str]) -> str:
    slug, number = base, 2
    while slug in used:
        slug, number = f"{base}{number}", number + 1
    used.add(slug)
    return slug


def _random_birth(rng: random.Random, years: tuple[int, int]) -> date:
    return date(rng.randint(*years), rng.randint(1, 12), rng.randint(1, 28))


def _invent_names(master: random.Random) -> dict[str, str]:
    """Full names of the invented people by candidate key, in plan order, without repeats."""
    invented = [spec for spec in plan.CANDIDATES if spec.fsp_id is None]
    surnames = master.sample(plan.SURNAMES, len(invented))
    names: dict[str, str] = {}
    for spec, (male_surname, female_surname) in zip(invented, surnames, strict=True):
        male_patronymic, female_patronymic = master.choice(plan.PATRONYMICS)
        if spec.gender == "f":
            names[spec.key] = (
                f"{female_surname} {master.choice(plan.FEMALE_FIRST_NAMES)} {female_patronymic}"
            )
        else:
            names[spec.key] = (
                f"{male_surname} {master.choice(plan.MALE_FIRST_NAMES)} {male_patronymic}"
            )
    return names


def _person_for(
    ctx: _Context, spec: plan.CandidateSpec, rng: random.Random, invented: dict[str, str]
) -> _Person:
    if spec.fsp_id is not None:
        athlete = ctx.registry.get_athlete(spec.fsp_id)
        if athlete is None:
            raise LookupError(f"{spec.fsp_id} is not in the registry")
        full_name = athlete["full_name"]
        birth_date = date.fromisoformat(athlete["birth_date"])
        city = athlete["city"]
    else:
        full_name = invented[spec.key]
        birth_date = _random_birth(rng, spec.born)
        city = rng.choice(plan.CITIES)
    surname, first_name = full_name.split()[:2]
    local = _unique_slug(f"{_translit(first_name)}.{_translit(surname)}", ctx.used_contacts)
    # The "_demo" suffix (like the demo candidate's) keeps the nickname off any real account.
    handle = f"@{local.replace('.', '_')}_demo"
    return _Person(
        full_name=full_name,
        birth_date=birth_date,
        city=city,
        email=f"{local}@{EMAIL_DOMAIN}",
        telegram=handle,
        phone=_make_phone(rng, ctx.used_contacts),
    )


# --- building blocks ------------------------------------------------------------------------------


def _new_user(ctx: _Context, *, email: str, role: str, full_name: str) -> User:
    created = ctx.now - timedelta(days=45)
    user = User(
        email=email,
        password_hash=ctx.password_hash,
        role=role,
        full_name=full_name,
        consent_at=created,
        created_at=created,
    )
    ctx.db.add(user)
    return user


def _new_candidate(ctx: _Context, person: _Person, *, relocation: bool) -> Candidate:
    user = _new_user(ctx, email=person.email, role="candidate", full_name=person.full_name)
    candidate = Candidate(
        user=user,
        birth_date=person.birth_date,
        city=person.city,
        work_formats=[],
        relocation=relocation,
        salary_expectation=None,
        about=None,
        telegram=person.telegram,
        phone=person.phone,
        visible=True,
    )
    ctx.db.add(candidate)
    ctx.db.flush()
    return candidate


def _link_fsp(ctx: _Context, candidate: Candidate, fsp_id: str, rng: random.Random) -> None:
    """Link the candidate to a registry record the way `POST /candidate/fsp/link` does."""
    athlete = ctx.registry.get_athlete(fsp_id)
    if athlete is None:
        raise LookupError(f"{fsp_id} is not in the registry")
    candidate.fsp_id = athlete["fsp_id"]
    candidate.fsp_linked_at = ctx.now - timedelta(days=rng.randint(5, 40))
    candidate.fsp_region = athlete.get("region")
    ctx.db.flush()
    replace_facts(ctx.db, candidate, "fsp", fsp_mapping.facts_from_fsp(athlete))


def _add_resume(
    ctx: _Context, candidate: Candidate, person: _Person, template: str, rng: random.Random
) -> None:
    """Parse the resume text like `POST /candidate/resume` and fill the empty questionnaire."""
    text = _read_template(template).format(
        full_name=person.full_name,
        city=person.city,
        email=person.email,
        phone=person.phone,
        telegram=person.telegram,
    )
    parsed = resume_parser.parse_resume(text, ctx.now.date(), full_name=person.full_name)
    replace_facts(ctx.db, candidate, "resume", parsed.facts)
    candidate.resume_text = text
    candidate.resume_filename = "resume.txt" if rng.random() < 0.5 else None
    candidate.resume_parsed_at = ctx.now - timedelta(days=rng.randint(3, 30))
    if not candidate.city and parsed.city:
        candidate.city = parsed.city
    if not candidate.work_formats:
        candidate.work_formats = list(parsed.work_formats) or _header_work_formats(text)
    if candidate.salary_expectation is None and parsed.salary_expectation is not None:
        candidate.salary_expectation = parsed.salary_expectation
    if "переезд" in text.lower():
        candidate.relocation = True


@cache
def _correct_options() -> dict[str, str]:
    """The text of the correct option by question id, from the bank the domain itself uses."""
    return {
        question["id"]: question["options"][question["correct"]]
        for test in ontology.read_json("questions.json")["tests"]
        for question in test["questions"]
    }


def _answers_for_level(skill: str, session_seed_value: int, level: int) -> dict[str, int]:
    """Answers (index among the shuffled options) that grade to exactly `level`.

    Level 3 is all correct (weight 12). Level 2 misses one question of weight 2 (weight 10),
    level 1 misses one question of weight 3 (weight 9).
    """
    correct = _correct_options()
    wrong_difficulty = {3: None, 2: 2, 1: 3}[level]
    answers: dict[str, int] = {}
    spent = False
    for question in quiz.build_session(skill, session_seed_value):
        right = question.options.index(correct[question.id])
        if question.difficulty == wrong_difficulty and not spent:
            answers[question.id] = (right + 1) % len(question.options)
            spent = True
        else:
            answers[question.id] = right
    return answers


def _pass_test(
    ctx: _Context, candidate: Candidate, skill: str, level: int, rng: random.Random
) -> None:
    """Store a finished test session and the fact it gives, like `POST .../submit` does."""
    started = ctx.now - timedelta(days=rng.randint(3, 40), minutes=rng.randint(0, 600))
    session = QuizSession(
        candidate_id=candidate.id,
        skill=skill,
        started_at=started,
        expires_at=started + timedelta(seconds=QUIZ_TIME_LIMIT_SECONDS),
    )
    ctx.db.add(session)
    ctx.db.flush()
    seed = session_seed(ctx.jwt_secret, session.id)
    answers = _answers_for_level(skill, seed, level)
    outcome = quiz.grade_session(skill, seed, answers)
    if outcome.level != level or outcome.fact is None:
        raise RuntimeError(f"test {skill}: planned level {level}, graded {outcome.level}")
    session.submitted_at = started + timedelta(minutes=rng.randint(4, 7))
    session.score = outcome.score
    session.level = outcome.level
    session.answers = answers
    upsert_fact(ctx.db, candidate, outcome.fact, keep_higher_level=True)


def _add_manual_achievement(
    ctx: _Context, candidate: Candidate, key: str, rng: random.Random
) -> None:
    title, year, level, result, discipline, document_url = plan.MANUAL_ACHIEVEMENTS[key]
    uid = str(uuid.UUID(int=rng.getrandbits(128), version=4))
    fact = domain_facts.manual_achievement_fact(
        uid, title, year, level, result, discipline, document_url
    )
    upsert_fact(ctx.db, candidate, fact)


def _finish_profile(ctx: _Context, candidate: Candidate, rng: random.Random) -> None:
    """Fill what the facts did not, then recompute the category and the text vector."""
    category = recompute_candidate(ctx.db, candidate)
    if not candidate.work_formats:
        candidate.work_formats = list(rng.choice(plan.WORK_FORMAT_CHOICES))
    if candidate.salary_expectation is None:
        low, high = plan.SALARY_BY_GRADE[category.grade or "junior"]
        candidate.salary_expectation = rng.randrange(low, high + 1, 5) * 1000
    if rng.random() < 0.65:
        candidate.about = rng.choice(plan.ABOUTS[category.stack or "general"])
    recompute_candidate(ctx.db, candidate)


def _build_candidate(
    ctx: _Context, spec: plan.CandidateSpec, rng: random.Random, invented: dict[str, str]
) -> Candidate:
    person = _person_for(ctx, spec, rng, invented)
    candidate = _new_candidate(ctx, person, relocation=rng.random() < 0.25)
    if spec.fsp_id is not None:
        _link_fsp(ctx, candidate, spec.fsp_id, rng)
    if spec.template is not None:
        _add_resume(ctx, candidate, person, spec.template, rng)
    for skill, level in spec.tests:
        _pass_test(ctx, candidate, skill, level, rng)
    for key in spec.manual:
        _add_manual_achievement(ctx, candidate, key, rng)
    _finish_profile(ctx, candidate, rng)
    return candidate


def _build_demo_candidate(ctx: _Context) -> Candidate:
    """The demo candidate: no FSP link, no resume, no tests (their absence is the scenario)."""
    person = _Person(
        full_name=plan.DEMO_CANDIDATE_NAME,
        birth_date=date(*plan.DEMO_CANDIDATE_BIRTH),
        city=plan.DEMO_CANDIDATE_CITY,
        email=plan.DEMO_CANDIDATE_EMAIL,
        telegram=plan.DEMO_CANDIDATE_TELEGRAM,
        phone=plan.DEMO_CANDIDATE_PHONE,
    )
    candidate = _new_candidate(ctx, person, relocation=False)
    candidate.about = plan.DEMO_CANDIDATE_ABOUT
    recompute_candidate(ctx.db, candidate)
    return candidate


def _build_employers(ctx: _Context) -> dict[str, Employer]:
    employers: dict[str, Employer] = {}
    for spec in plan.EMPLOYERS:
        user = _new_user(ctx, email=spec.email, role="employer", full_name=spec.contact_name)
        employer = Employer(
            user=user,
            company_name=spec.company_name,
            about=spec.about,
            website=spec.website,
            contact_name=spec.contact_name,
            contact_email=spec.contact_email,
            contact_telegram=spec.contact_telegram,
            verified=True,
        )
        ctx.db.add(employer)
        employers[spec.key] = employer
    ctx.db.flush()
    return employers


def _build_vacancies(ctx: _Context, employers: dict[str, Employer]) -> dict[str, Vacancy]:
    vacancies: dict[str, Vacancy] = {}
    for spec in plan.VACANCIES:
        vacancy = Vacancy(
            employer_id=employers[spec.employer].id,
            title=spec.title,
            description=spec.description,
            stack=spec.stack,
            grade=spec.grade,
            team_role=spec.team_role,
            skills_required=list(spec.skills_required),
            skills_optional=list(spec.skills_optional),
            work_formats=list(spec.work_formats),
            city=spec.city,
            salary_from=spec.salary_from,
            salary_to=spec.salary_to,
            is_active=spec.is_active,
            created_at=ctx.now - timedelta(days=spec.days_ago),
        )
        ctx.db.add(vacancy)
        vacancies[spec.key] = vacancy
    ctx.db.flush()
    return vacancies


def _build_offers(
    ctx: _Context,
    employers: dict[str, Employer],
    vacancies: dict[str, Vacancy],
    candidates: dict[str, Candidate],
) -> None:
    for spec in plan.OFFERS:
        sent = ctx.now - timedelta(days=spec.sent_days_ago)
        answered = (
            ctx.now - timedelta(days=spec.answered_days_ago)
            if spec.answered_days_ago is not None
            else None
        )
        ctx.db.add(
            Offer(
                employer_id=employers[spec.employer].id,
                candidate_id=candidates[spec.candidate].id,
                vacancy_id=vacancies[spec.vacancy].id,
                salary=spec.salary,
                message=spec.message,
                status=spec.status,
                candidate_comment=spec.candidate_comment,
                created_at=sent,
                responded_at=answered,
            )
        )
    ctx.db.flush()


# --- public functions -----------------------------------------------------------------------------


def reset_all(db: Session) -> None:
    """Delete every row of every application table (children first); the caller commits."""
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(delete(table))
    db.flush()
    # The rows are gone: forget the objects loaded from them, or new rows with the same ids
    # would collide with them in the session's identity map.
    db.expunge_all()


def seed_all(db: Session, now: datetime | None = None) -> SeedSummary:
    """Write the demo data into an empty database and commit. Any failure rolls it all back."""
    settings = get_settings()
    master = random.Random(SEED)
    ctx = _Context(
        db=db,
        now=now or utcnow(),
        registry=MockFspRegistry(),
        password_hash=hash_password(DEMO_PASSWORD, rounds=settings.BCRYPT_ROUNDS),
        jwt_secret=settings.JWT_SECRET,
    )
    try:
        invented = _invent_names(master)
        # One generator per person, taken in plan order: what is drawn for one candidate does
        # not depend on how the data of the previous one came out.
        generators = {spec.key: random.Random(master.getrandbits(64)) for spec in plan.CANDIDATES}

        candidates: dict[str, Candidate] = {"demo": _build_demo_candidate(ctx)}
        employers = _build_employers(ctx)
        for spec in plan.CANDIDATES:
            candidates[spec.key] = _build_candidate(ctx, spec, generators[spec.key], invented)
        vacancies = _build_vacancies(ctx, employers)
        _build_offers(ctx, employers, vacancies, candidates)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return summarize(db)


def seed_if_empty(db: Session | None = None) -> bool:
    """Seed the demo data if there are no users yet; True when something was written."""
    if db is None:
        with SessionLocal() as session:
            return seed_if_empty(session)
    if db.scalar(select(func.count(User.id))):
        return False
    summary = seed_all(db)
    logger.info(
        "Demo data seeded: %s candidates, %s employers", summary.candidates, summary.employers
    )
    return True


def summarize(db: Session) -> SeedSummary:
    """Counts of what the database holds, with the "stack x grade" matrix."""

    def count_candidates_with(*conditions: Any) -> int:
        statement = select(func.count(func.distinct(ProfileFact.candidate_id))).where(*conditions)
        return db.scalar(statement) or 0

    candidates = list(db.scalars(select(Candidate).order_by(Candidate.id)))
    matrix: dict[tuple[str, str], list[int]] = {}
    undefined = 0
    for candidate in candidates:
        category = Categorization.model_validate(candidate.category or {})
        if category.stack is None or category.grade is None:
            undefined += 1
            continue
        cell = matrix.setdefault((category.stack, category.grade), [0, 0])
        cell[0] += 1
        cell[1] += int(candidate.fsp_id is not None)
    offers = Counter(db.scalars(select(Offer.status)))
    return SeedSummary(
        candidates=len(candidates),
        with_fsp=sum(candidate.fsp_id is not None for candidate in candidates),
        with_resume=sum(candidate.resume_text is not None for candidate in candidates),
        with_tests=count_candidates_with(ProfileFact.kind == "skill", ProfileFact.source == "test"),
        with_manual=count_candidates_with(
            ProfileFact.kind == "achievement", ProfileFact.source == "self"
        ),
        employers=db.scalar(select(func.count(Employer.id))) or 0,
        vacancies=db.scalar(select(func.count(Vacancy.id))) or 0,
        offers=dict(offers),
        matrix={cell: (counts[0], counts[1]) for cell, counts in matrix.items()},
        undefined=undefined,
    )


def format_summary(summary: SeedSummary) -> str:
    """The summary as text: totals and the "stack x grade" table (all candidates / with FSP)."""
    grades = list(ontology.GRADE_TITLES)
    lines = [
        f"Соискателей: {summary.candidates} (с ФСП: {summary.with_fsp}, с резюме: "
        f"{summary.with_resume}, с тестами: {summary.with_tests}, с достижениями вручную: "
        f"{summary.with_manual}, без категории: {summary.undefined})",
        f"Работодателей: {summary.employers}, вакансий: {summary.vacancies}, офферов: "
        + ", ".join(f"{status} {count}" for status, count in sorted(summary.offers.items())),
        "",
        "Стек × грейд: всего (из них с ФСП)",
        "".join(["стек".ljust(30), *(ontology.GRADE_TITLES[grade].ljust(10) for grade in grades)]),
    ]
    for stack, title in ontology.STACK_TITLES.items():
        cells = []
        for grade in grades:
            total, linked = summary.matrix.get((stack, grade), (0, 0))
            cells.append((f"{total} ({linked})" if total else "-").ljust(10))
        lines.append(title.ljust(30) + "".join(cells))
    return "\n".join(lines)


# --- command line ---------------------------------------------------------------------------------


def ensure_schema(engine: Engine) -> None:
    """Create the tables with Alembic when the database has none (a fresh SQLite file).

    In the container `entrypoint.sh` has migrated the database already; this makes
    `python -m app.seed` usable on an empty database as well, without a second way of creating
    tables that Alembic would later trip over.
    """
    if inspect(engine).has_table(User.__tablename__):
        return
    if engine.url.get_backend_name() == "sqlite" and engine.url.database in (None, "", ":memory:"):
        # An in-memory database dies with its connection: Alembic's own engine could not see it.
        Base.metadata.create_all(engine)
        return
    from alembic.config import Config

    from alembic import command

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    url = engine.url.render_as_string(hide_password=False)
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")


def main(argv: Sequence[str] | None = None, *, engine: Engine | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.seed",
        description="Fill an empty database with the demo data (SPEC section 10).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete ALL rows of the application tables first, then seed again",
    )
    args = parser.parse_args(argv)

    engine = engine or default_engine
    ensure_schema(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        if args.reset:
            # One transaction: if seeding fails, the old data is still there.
            reset_all(db)
            summary = seed_all(db)
        elif seed_if_empty(db):
            summary = summarize(db)
        else:
            print("В базе уже есть пользователи: демо-данные не добавлены (для замены — --reset).")
            return 0
    print("Демо-данные созданы.\n")
    print(format_summary(summary))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    sys.exit(main())
