"""Engine, session factory and the `get_db` dependency."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings, normalize_database_url


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_engine(url: str) -> Engine:
    """Create an engine; SQLite gets thread-safe settings and enforced foreign keys."""
    url = normalize_database_url(url)
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return create_engine(url, pool_pre_ping=True)

    kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
    if parsed.database in (None, "", ":memory:"):
        # One shared connection, otherwise every checkout would see its own empty database.
        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


engine = make_engine(get_settings().DATABASE_URL)

# expire_on_commit=False: objects stay readable after commit() without another query.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """One session per request. Routes call `db.commit()` themselves; on close, any
    uncommitted work is rolled back."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
