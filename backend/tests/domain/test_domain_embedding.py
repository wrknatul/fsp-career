"""The local text vector (SPEC section 7.6)."""

from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

import pytest
from domain_testkit import experience, fsp_achievement, skill

from app.domain.categorizer import categorize
from app.domain.embedding import cosine, embed, profile_text
from app.domain.types import CandidatePrefs

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PREFS = CandidatePrefs()


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


def _profile(facts, about=None, resume_text=None) -> str:
    return profile_text(facts, categorize(facts, PREFS), about, resume_text)


BACKEND_FACTS = [
    skill("python", "test", 3),
    skill("fastapi", "resume", 2),
    skill("postgresql", "resume", 2),
    skill("docker", "resume", 2),
    experience(4),
]
FRONTEND_FACTS = [
    skill("react", "test", 3),
    skill("typescript", "resume", 2),
    skill("html-css", "resume", 2),
    skill("figma", "resume", 2),
    experience(4),
]


def test_vector_has_384_dimensions_and_unit_length() -> None:
    vector = embed("Backend-разработчик: Python, FastAPI, PostgreSQL")
    assert len(vector) == 384
    assert _norm(vector) == pytest.approx(1.0, abs=1e-4)
    assert all(isinstance(x, float) for x in vector)


def test_vector_is_deterministic() -> None:
    text = "Ищем разработчика на Python и FastAPI"
    assert embed(text) == embed(text)


def test_vector_does_not_depend_on_the_interpreter_hash_seed() -> None:
    code = (
        "from app.domain.embedding import embed; "
        "v = embed('Python backend FastAPI разработчик'); "
        "print(sum(i * x for i, x in enumerate(v)))"
    )
    outputs = set()
    for seed in ("1", "2", "random"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        done = subprocess.run(
            [sys.executable, "-c", code],
            cwd=BACKEND_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.add(done.stdout.strip())
    assert len(outputs) == 1


def test_empty_text_gives_the_zero_vector() -> None:
    for text in ("", "   ", "и в на the of 2021"):
        vector = embed(text)
        assert len(vector) == 384
        assert not any(vector)


def test_cosine() -> None:
    a = embed("python backend fastapi")
    assert cosine(a, a) == pytest.approx(1.0, abs=1e-4)
    assert cosine(a, embed("")) == 0.0
    assert cosine([], a) == 0.0
    assert cosine(a, []) == 0.0
    assert -1.0 <= cosine(a, embed("react frontend typescript")) <= 1.0
    with pytest.raises(ValueError):
        cosine([1.0, 2.0], [1.0, 2.0, 3.0])


def test_skill_names_are_normalised_to_one_feature() -> None:
    assert embed("Python") == embed("питоном")
    assert embed("Kubernetes") == embed("k8s")


def test_negated_skill_is_not_a_feature() -> None:
    assert cosine(embed("не знаю Docker"), embed("Docker")) < 0.3


def test_similar_texts_are_closer_than_different_ones() -> None:
    query = embed("python backend fastapi")
    near = embed("backend-разработчик на Python и FastAPI")
    far = embed("дизайнер интерфейсов Figma и React")
    assert cosine(query, near) > cosine(query, far) + 0.2


def test_query_is_closer_to_a_backend_profile_than_to_a_frontend_one() -> None:
    query = embed("python backend fastapi")
    backend = embed(_profile(BACKEND_FACTS, about="Люблю чистый код"))
    frontend = embed(_profile(FRONTEND_FACTS, about="Люблю аккуратный интерфейс"))
    assert cosine(query, backend) > cosine(query, frontend)
    assert cosine(query, backend) > 0.3
    frontend_query = embed("react typescript frontend")
    assert cosine(frontend_query, frontend) > cosine(frontend_query, backend)


def test_stronger_evidence_pulls_harder() -> None:
    strong = _profile([skill("python", "test", 3)])
    weak = _profile([skill("python", "resume", 1)])
    assert strong.count("skill:python") > weak.count("skill:python") >= 1


# --- profile_text ----------------------------------------------------------------------------
def test_profile_text_has_skills_stack_grade_and_role() -> None:
    text = _profile(BACKEND_FACTS)
    assert "skill:python" in text
    assert "skill:fastapi" in text
    assert "Backend" in text
    assert "Middle" in text or "Junior" in text
    assert "Разработчик" in text


def test_profile_text_hides_contacts_everywhere() -> None:
    text = _profile(
        BACKEND_FACTS,
        about="Пишите ivan@mail.ru или +7 900 123-45-67, @ivan_dev",
        resume_text="Резюме. Мой сайт https://ivan.dev, телеграм t.me/ivan, vk.com/ivan",
    )
    for secret in ("ivan@mail.ru", "123-45-67", "@ivan_dev", "https://ivan.dev", "t.me/ivan"):
        assert secret not in text
    assert "[скрыто]" in text
    assert "Резюме" in text


def test_profile_text_takes_the_first_4000_characters_of_the_resume() -> None:
    resume = "а" * 4000 + "ЗАПРЕДЕЛОМ"
    text = _profile([skill("python", "test", 1)], resume_text=resume)
    assert "ЗАПРЕДЕЛОМ" not in text
    assert "а" * 4000 in text
    assert "а" * 4001 not in text


def test_a_contact_cut_by_the_limit_does_not_leak() -> None:
    resume = "x " * 1998 + "ivan.petrov@mail.ru"  # the address starts before the 4000th character
    text = _profile([skill("python", "test", 1)], resume_text=resume)
    assert "ivan.petrov" not in text


def test_profile_text_includes_achievements_and_disciplines() -> None:
    facts = [
        skill("algorithms", "fsp", 3),
        fsp_achievement("R1", "national", 1, title="Кубок Волги"),
    ]
    text = _profile(facts)
    assert "Кубок Волги" in text
    assert "Алгоритмическое программирование" in text


def test_profile_text_of_an_empty_profile() -> None:
    assert _profile([]) == ""
    assert not any(embed(_profile([])))
