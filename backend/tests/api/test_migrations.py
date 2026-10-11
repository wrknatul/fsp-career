"""`alembic upgrade head` must produce exactly the schema the models describe."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.command import downgrade, upgrade
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, delete, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import make_engine
from app.models import Candidate, Employer, Offer, ProfileFact, User, Vacancy

BACKEND_DIR = Path(__file__).resolve().parents[2]


def alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture()
def migrated(tmp_path: Path):
    """A SQLite file migrated to head; yields (engine, config)."""
    url = f"sqlite:///{tmp_path / 'migrated.sqlite3'}"
    config = alembic_config(url)
    upgrade(config, "head")
    engine = make_engine(url)
    yield engine, config
    engine.dispose()


def table_names(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


# --- structure -------------------------------------------------------------------------------


def test_there_is_a_single_head():
    heads = ScriptDirectory.from_config(alembic_config("sqlite://")).get_heads()

    assert heads == ["0001"]


def test_upgrade_creates_the_tables_and_columns_of_the_models(migrated):
    engine, _ = migrated
    inspector = inspect(engine)

    assert table_names(engine) == set(Base.metadata.tables)
    for name, table in Base.metadata.tables.items():
        reflected = {column["name"]: column for column in inspector.get_columns(name)}
        assert set(reflected) == {column.name for column in table.columns}, name
        for column in table.columns:
            assert reflected[column.name]["nullable"] == column.nullable, (name, column.name)


def test_upgrade_creates_the_indexes_unique_constraints_and_foreign_keys(migrated):
    engine, _ = migrated
    inspector = inspect(engine)

    for name, table in Base.metadata.tables.items():
        expected_indexes = {
            (index.name, tuple(c.name for c in index.columns), bool(index.unique))
            for index in table.indexes
        }
        reflected_indexes = {
            (index["name"], tuple(index["column_names"]), bool(index["unique"]))
            for index in inspector.get_indexes(name)
        }
        assert reflected_indexes == expected_indexes, name

        expected_unique = {
            tuple(sorted(c.name for c in constraint.columns))
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        reflected_unique = {
            tuple(sorted(constraint["column_names"]))
            for constraint in inspector.get_unique_constraints(name)
        }
        assert reflected_unique == expected_unique, name

        expected_fks = {
            (tuple(fk.column_keys), fk.referred_table.name, fk.ondelete)
            for fk in table.foreign_key_constraints
        }
        reflected_fks = {
            (
                tuple(fk["constrained_columns"]),
                fk["referred_table"],
                fk["options"].get("ondelete"),
            )
            for fk in inspector.get_foreign_keys(name)
        }
        assert reflected_fks == expected_fks, name


def test_autogenerate_finds_no_difference(migrated):
    engine, _ = migrated

    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


def test_create_all_and_migration_agree(migrated, tmp_path):
    engine, _ = migrated
    created = make_engine(f"sqlite:///{tmp_path / 'created.sqlite3'}")
    Base.metadata.create_all(created)
    try:
        for name in Base.metadata.tables:
            assert [c["name"] for c in inspect(created).get_columns(name)] == [
                c["name"] for c in inspect(engine).get_columns(name)
            ], name
    finally:
        created.dispose()


def test_downgrade_removes_everything(migrated):
    engine, config = migrated

    downgrade(config, "base")

    assert table_names(engine) == set()


# --- the migrated database enforces the rules -------------------------------------------------


def make_user(email: str, role: str = "candidate") -> User:
    return User(
        email=email,
        password_hash="x",
        role=role,
        full_name="Тест",
        consent_at=datetime.now(UTC),
    )


@pytest.fixture()
def session(migrated):
    engine, _ = migrated
    with Session(engine, expire_on_commit=False) as db:
        yield db


def add_candidate(db: Session, email: str = "c@example.test") -> Candidate:
    user = make_user(email)
    user.candidate = Candidate(work_formats=[], relocation=False, visible=False)
    db.add(user)
    db.commit()
    return user.candidate


def add_employer_with_vacancy(db: Session) -> tuple[Employer, Vacancy]:
    user = make_user("e@example.test", "employer")
    user.employer = Employer(company_name="ООО", verified=False)
    user.employer.vacancies.append(
        Vacancy(title="Dev", description="", stack="backend", grade="junior")
    )
    db.add(user)
    db.commit()
    return user.employer, user.employer.vacancies[0]


def test_email_is_unique(session):
    session.add(make_user("same@example.test"))
    session.commit()
    session.add(make_user("same@example.test"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_email_is_normalized_on_write(session):
    user = make_user("  Mixed.Case@Example.TEST ")
    session.add(user)
    session.commit()

    assert session.scalar(select(User.email)) == "mixed.case@example.test"


def test_role_is_checked(session):
    session.add(make_user("x@example.test", role="admin"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_foreign_keys_are_enforced(session):
    session.add(Candidate(user_id=999, work_formats=[], relocation=False, visible=False))

    with pytest.raises(IntegrityError):
        session.commit()


def test_fact_uniqueness_is_per_candidate_kind_key_and_source(session):
    candidate = add_candidate(session)

    def fact(source: str, verification: str) -> ProfileFact:
        return ProfileFact(
            candidate_id=candidate.id,
            kind="skill",
            key="python",
            title="Python",
            value={"level": 1},
            source=source,
            verification=verification,
        )

    session.add_all([fact("resume", "parsed"), fact("test", "tested")])
    session.commit()  # same skill from different sources is fine
    session.add(fact("resume", "parsed"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_fsp_id_is_unique_but_may_be_missing_for_many(session):
    add_candidate(session, "a@example.test")
    add_candidate(session, "b@example.test")  # two NULL fsp_id values are fine
    session.query(Candidate).update({"fsp_id": None})
    first, second = session.scalars(select(Candidate)).all()
    first.fsp_id = "FSP-2024-00117"
    session.commit()
    second.fsp_id = "FSP-2024-00117"

    with pytest.raises(IntegrityError):
        session.commit()


def test_offer_pair_is_unique_and_salary_status_are_checked(session):
    employer, vacancy = add_employer_with_vacancy(session)
    candidate = add_candidate(session)

    def offer(**overrides: Any) -> Offer:
        values = {
            "employer_id": employer.id,
            "candidate_id": candidate.id,
            "vacancy_id": vacancy.id,
            "salary": 100_000,
            "status": "sent",
        }
        return Offer(**{**values, **overrides})

    session.add(offer())
    session.commit()

    for broken in (offer(), offer(salary=0), offer(status="maybe")):
        session.add(broken)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_deleting_a_user_cascades_in_the_database(session):
    candidate = add_candidate(session)
    session.add(
        ProfileFact(
            candidate_id=candidate.id,
            kind="skill",
            key="python",
            title="Python",
            value={},
            source="self",
            verification="declared",
        )
    )
    session.commit()

    session.execute(delete(User))
    session.commit()

    assert session.scalars(select(Candidate)).all() == []
    assert session.scalars(select(ProfileFact)).all() == []


def test_null_category_is_a_real_sql_null(session):
    candidate = add_candidate(session)
    candidate.category = None
    session.commit()

    raw = session.connection().exec_driver_sql("SELECT category FROM candidates").scalar()

    assert raw is None
