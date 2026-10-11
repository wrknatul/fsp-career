from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.timeutil import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.employer import Employer


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('candidate', 'employer')", name="role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Always stored as `lower().strip()` (enforced by the validator below).
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))
    full_name: Mapped[str] = mapped_column(String(200))
    consent_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    candidate: Mapped[Candidate | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )
    employer: Mapped[Employer | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )

    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        return value.lower().strip()
