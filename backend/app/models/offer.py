from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime
from app.models.candidate import Candidate
from app.models.employer import Employer, Vacancy


class Offer(Base):
    """An employer's offer to a candidate for one vacancy.

    Statuses: `sent` -> `accepted` | `declined` (both terminal). Contacts are never copied
    here: they are computed on read from the status. There is no expiry in the MVP.
    """

    __tablename__ = "offers"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "candidate_id", name="uq_offers_vacancy_candidate"),
        CheckConstraint("status IN ('sent', 'accepted', 'declined')", name="status"),
        CheckConstraint("salary > 0", name="salary_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_id: Mapped[int] = mapped_column(
        ForeignKey("employers.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"))
    salary: Mapped[int] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="sent")
    candidate_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    employer: Mapped[Employer] = relationship()
    candidate: Mapped[Candidate] = relationship()
    vacancy: Mapped[Vacancy] = relationship()
