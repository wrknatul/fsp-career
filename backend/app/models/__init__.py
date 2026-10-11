"""All ORM models. Importing this package registers every table on `Base.metadata`."""

from app.models.candidate import Candidate, LinkAttempt, ProfileFact, QuizSession
from app.models.employer import Employer, Vacancy
from app.models.offer import Offer
from app.models.user import User

__all__ = [
    "Candidate",
    "Employer",
    "LinkAttempt",
    "Offer",
    "ProfileFact",
    "QuizSession",
    "User",
    "Vacancy",
]
