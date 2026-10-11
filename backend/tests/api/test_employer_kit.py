"""Builders shared by the employer API tests. This module has no tests of its own.

Candidates are made with the `make_candidate` factory from `conftest.py`; their category and
text vector are computed by the domain functions (`categorize`, `profile_text`, `embed`),
exactly like the real profile service stores them.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.domain.categorizer import categorize
from app.domain.embedding import embed, profile_text
from app.domain.facts import experience_fact, skill_fact
from app.domain.types import VERIFICATION_BY_SOURCE, CandidatePrefs, FactData
from app.models import Candidate, Employer, Offer, Vacancy

API = "/api/v1"

MakeCandidate = Callable[..., Candidate]


# --- facts ---------------------------------------------------------------------------------------


def skills(*skill_ids: str, source: str = "resume", level: int = 2) -> list[FactData]:
    return [skill_fact(skill_id, level, source) for skill_id in skill_ids]  # type: ignore[arg-type]


def experience(years: float) -> FactData:
    return experience_fact(years, [])


def fsp_result(
    result_id: str,
    level: str,
    place: int,
    discipline: str = "algorithmic",
    *,
    title: str | None = None,
    year: int = 2025,
) -> FactData:
    name = title or f"Соревнование {result_id}"
    result = "winner" if place == 1 else "prize" if place <= 3 else "participant"
    return FactData(
        kind="achievement",
        key=f"fsp:{result_id}",
        title=f"{name} — {place} место",
        value={
            "title": name,
            "discipline": discipline,
            "level": level,
            "place": place,
            "result": result,
            "date": f"{year}-04-10",
            "year": year,
            "team_name": None,
            "team_role": None,
            "participants_total": 100,
            "document_url": f"https://fsp.example/protocols/{result_id}",
        },
        source="fsp",
        verification=VERIFICATION_BY_SOURCE["fsp"],
        evidence=f"https://fsp.example/protocols/{result_id}",
    )


def fsp_rank(rank: str = "kms", discipline: str = "algorithmic") -> FactData:
    return FactData(
        kind="rank",
        key="sport_rank",
        title="КМС · Алгоритмическое программирование",
        value={"rank": rank, "discipline": discipline, "assigned_at": None, "order_no": "№ 118"},
        source="fsp",
        verification=VERIFICATION_BY_SOURCE["fsp"],
        evidence="№ 118",
    )


# --- candidates ----------------------------------------------------------------------------------


def build_candidate(
    make_candidate: MakeCandidate,
    facts: list[FactData],
    *,
    about: str | None = None,
    resume_text: str | None = None,
    **columns: Any,
) -> Candidate:
    """A candidate whose stored category and vector are computed by the domain."""
    prefs = CandidatePrefs(
        city=columns.get("city"),
        work_formats=columns.get("work_formats", []),
        relocation=columns.get("relocation", False),
        salary_expectation=columns.get("salary_expectation"),
    )
    category = categorize(facts, prefs)
    vector = embed(profile_text(facts, category, about, resume_text))
    return make_candidate(
        facts=facts,
        category=category.model_dump(mode="json"),
        embedding=vector,
        about=about,
        resume_text=resume_text,
        **columns,
    )


# The roster below, as the domain categorizes it: (stack, grade).
ROSTER_CATEGORIES: dict[str, tuple[str, str]] = {
    "alexey": ("backend", "middle"),
    "backend_junior": ("backend", "junior"),
    "backend_mid": ("backend", "middle"),
    "frontend_junior": ("frontend", "junior"),
    "ml_senior": ("ml", "senior"),
    "fullstack_mid": ("fullstack", "middle"),
    "devops_junior": ("devops", "junior"),
    "qa_intern": ("qa", "intern"),
    "security_fsp": ("security", "junior"),
    "analyst_junior": ("analyst", "junior"),
}


def build_roster(make_candidate: MakeCandidate) -> dict[str, Candidate]:
    """Ten findable candidates (every row of `ROSTER_CATEGORIES`) and two who must not be found.

    * `alexey`, `ml_senior`, `security_fsp` have results in the FSP registry;
    * `devops_junior` has a passed test (confirmed, but no FSP result);
    * `hidden_backend` is not visible, `no_stack` has no defined stack.
    """
    roster: dict[str, Candidate] = {}

    roster["alexey"] = build_candidate(
        make_candidate,
        [
            *skills("python", "fastapi", "postgresql", "docker"),
            *skills("algorithms", source="fsp", level=3),
            experience(1.5),
            fsp_result("a1", "national", 3, "algorithmic", title="Всероссийская олимпиада"),
            fsp_result("a2", "regional", 1, "product", title="Региональный хакатон"),
            fsp_rank("kms"),
        ],
        full_name="Смирнов Алексей Игоревич",
        city="Казань",
        work_formats=["remote", "hybrid"],
        salary_expectation=120_000,
        fsp_id="FSP-2024-00117",
        about="Люблю алгоритмы и backend",
    )
    roster["backend_junior"] = build_candidate(
        make_candidate,
        [*skills("python", "fastapi", "postgresql", "docker"), experience(1.5)],
        full_name="Орлов Павел Андреевич",
        city="Москва",
        work_formats=["remote"],
    )
    roster["backend_mid"] = build_candidate(
        make_candidate,
        [*skills("python", "django", "postgresql", "redis"), experience(6)],
        full_name="Кузнецов Дмитрий Сергеевич",
        city="Москва",
        work_formats=["office"],
        salary_expectation=200_000,
    )
    roster["frontend_junior"] = build_candidate(
        make_candidate,
        [*skills("javascript", "typescript", "react", "vue"), experience(1.5)],
        full_name="Попова Мария Ильинична",
        city="Санкт-Петербург",
        work_formats=["remote"],
        salary_expectation=90_000,
    )
    roster["ml_senior"] = build_candidate(
        make_candidate,
        [
            *skills("python", "pytorch", "machine-learning", "sklearn"),
            *skills("python", "algorithms", source="test", level=3),
            experience(8),
            fsp_result("m1", "national", 1, "algorithmic", title="Всероссийский чемпионат"),
        ],
        full_name="Волков Егор Максимович",
        city="Новосибирск",
        work_formats=["hybrid"],
    )
    roster["fullstack_mid"] = build_candidate(
        make_candidate,
        [
            *skills("python", "fastapi", "postgresql", "react", "typescript", "javascript"),
            experience(6),
        ],
        full_name="Соколова Анна Викторовна",
        city="Москва",
    )
    roster["devops_junior"] = build_candidate(
        make_candidate,
        [
            *skills("docker", "kubernetes", "terraform", "ansible", "linux"),
            *skills("docker", source="test", level=2),
            experience(1.5),
        ],
        full_name="Лебедев Игорь Олегович",
        city="Екатеринбург",
        work_formats=["remote"],
    )
    roster["qa_intern"] = build_candidate(
        make_candidate,
        skills("testing", "test-automation", "selenium"),
        full_name="Морозова Ольга Петровна",
        city="Тула",
    )
    roster["security_fsp"] = build_candidate(
        make_candidate,
        [
            *skills("pentest", "cryptography", "linux"),
            *skills("infosec", source="fsp", level=3),
            experience(0.5),
            fsp_result("s1", "national", 1, "security", title="Всероссийский CTF"),
            fsp_result("s2", "regional", 2, "security", title="Региональный CTF"),
        ],
        full_name="Новиков Артём Романович",
        city="Нижний Новгород",
        work_formats=["office", "hybrid"],
    )
    roster["analyst_junior"] = build_candidate(
        make_candidate,
        [*skills("sql", "pandas", "data-analysis", "bi-tools"), experience(3)],
        full_name="Федорова Елена Дмитриевна",
        city="Самара",
        work_formats=["hybrid"],
        relocation=True,
    )

    roster["hidden_backend"] = build_candidate(
        make_candidate,
        [*skills("python", "fastapi", "postgresql", "docker"), experience(1.5)],
        full_name="Скрытов Борис Борисович",
        visible=False,
    )
    roster["no_stack"] = build_candidate(
        make_candidate,
        skills("git"),
        full_name="Безстеков Глеб Глебович",
    )
    return roster


# --- employer side -------------------------------------------------------------------------------


def add_vacancy(db: Any, employer: Employer, **fields: Any) -> Vacancy:
    data: dict[str, Any] = {
        "title": "Python-разработчик",
        "description": "Пишем backend на FastAPI",
        "stack": "backend",
        "grade": "middle",
        "team_role": None,
        "skills_required": ["python"],
        "skills_optional": [],
        "work_formats": [],
        "city": None,
        "salary_from": None,
        "salary_to": None,
        "is_active": True,
    }
    data.update(fields)
    vacancy = Vacancy(employer_id=employer.id, **data)
    db.add(vacancy)
    db.commit()
    return vacancy


def add_offer(
    db: Any,
    employer: Employer,
    candidate: Candidate,
    vacancy: Vacancy,
    *,
    status: str = "sent",
    salary: int = 150_000,
    candidate_comment: str | None = None,
) -> Offer:
    offer = Offer(
        employer_id=employer.id,
        candidate_id=candidate.id,
        vacancy_id=vacancy.id,
        salary=salary,
        status=status,
        candidate_comment=candidate_comment,
    )
    db.add(offer)
    db.commit()
    return offer


def set_offer_status(db: Any, offer: Offer, status: str, comment: str | None = None) -> None:
    """What the candidate's "respond" route does, done directly in the database."""
    offer.status = status
    if comment is not None:
        offer.candidate_comment = comment
    db.commit()
