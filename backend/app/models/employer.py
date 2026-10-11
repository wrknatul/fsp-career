from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.user import User


class Employer(Base):
    __tablename__ = "employers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    company_name: Mapped[str] = mapped_column(String(200))
    about: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(300))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(254))
    contact_telegram: Mapped[str | None] = mapped_column(String(64))
    # Set by the platform, never by the employer; true for the demo companies.
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="employer")
    vacancies: Mapped[list[Vacancy]] = relationship(
        back_populates="employer",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Vacancy.id",
    )


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_id: Mapped[int] = mapped_column(
        ForeignKey("employers.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    stack: Mapped[str] = mapped_column(String(16))
    grade: Mapped[str] = mapped_column(String(16))
    team_role: Mapped[str | None] = mapped_column(String(16))
    skills_required: Mapped[list[str]] = mapped_column(JSON, default=list)
    skills_optional: Mapped[list[str]] = mapped_column(JSON, default=list)
    work_formats: Mapped[list[str]] = mapped_column(JSON, default=list)
    city: Mapped[str | None] = mapped_column(String(100))
    salary_from: Mapped[int | None] = mapped_column(Integer)
    salary_to: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    employer: Mapped[Employer] = relationship(back_populates="vacancies")
