from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.user import User


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    city: Mapped[str | None] = mapped_column(String(100))
    work_formats: Mapped[list[str]] = mapped_column(JSON, default=list)
    relocation: Mapped[bool] = mapped_column(Boolean, default=False)
    salary_expectation: Mapped[int | None] = mapped_column(Integer)
    about: Mapped[str | None] = mapped_column(Text)
    telegram: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(32))
    # False until the candidate explicitly allows employers to see the profile.
    visible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    fsp_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    fsp_linked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    fsp_region: Mapped[str | None] = mapped_column(String(200))
    resume_text: Mapped[str | None] = mapped_column(Text)
    resume_filename: Mapped[str | None] = mapped_column(String(255))
    resume_parsed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Serialized `Category` (domain `Categorization`). SQL NULL means "not computed yet" and
    # is treated as `categorize([], prefs)`. `none_as_null` keeps Python None a real SQL NULL.
    category: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    embedding: Mapped[list[float] | None] = mapped_column(JSON(none_as_null=True))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="candidate")
    facts: Mapped[list[ProfileFact]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProfileFact.id",
    )


class ProfileFact(Base):
    __tablename__ = "profile_facts"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "kind",
            "key",
            "source",
            name="uq_profile_facts_candidate_kind_key_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    # skill | experience | achievement | rank | role
    kind: Mapped[str] = mapped_column(String(16))
    key: Mapped[str] = mapped_column(String(255))
    # Ready-made Russian caption, set by the domain.
    title: Mapped[str] = mapped_column(Text)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # fsp | test | resume | self
    source: Mapped[str] = mapped_column(String(16))
    # verified | tested | parsed | declared
    verification: Mapped[str] = mapped_column(String(16))
    evidence: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    candidate: Mapped[Candidate] = relationship(back_populates="facts")


class QuizSession(Base):
    """One attempt at an express test (table `test_sessions`)."""

    __tablename__ = "test_sessions"
    __table_args__ = (Index("ix_test_sessions_candidate_id_skill", "candidate_id", "skill"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    skill: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Share of the total weight answered correctly, 0..1.
    score: Mapped[float | None] = mapped_column(Float)
    level: Mapped[int | None] = mapped_column(Integer)
    answers: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))


class LinkAttempt(Base):
    """One attempt to link an FSP id; used for the "5 per hour" limit."""

    __tablename__ = "link_attempts"
    __table_args__ = (Index("ix_link_attempts_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
