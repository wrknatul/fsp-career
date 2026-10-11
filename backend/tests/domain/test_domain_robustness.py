"""Guards of the package itself: purity of imports and cheap handling of hostile input."""

from __future__ import annotations

import ast
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from app.domain.embedding import embed
from app.domain.matcher import parse_query_text
from app.domain.ontology import find_skills, normalize_skill
from app.domain.redaction import redact_contacts
from app.domain.resume_parser import parse_resume

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "app" / "domain"
FORBIDDEN_MODULES = (
    "app.api",
    "app.models",
    "app.db",
    "app.core",
    "app.services",
    "app.schemas",
    "sqlalchemy",
    "fastapi",
    "starlette",
    "requests",
    "httpx",
    "urllib",
    "socket",
    "http",
    "subprocess",
    "os",
)


def _modules() -> list[Path]:
    files = sorted(DOMAIN_DIR.glob("*.py"))
    assert len(files) >= 11
    return files


def _imported_modules(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


@pytest.mark.parametrize("path", _modules(), ids=lambda p: p.name)
def test_package_stays_pure(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for name in _imported_modules(tree):
        for forbidden in FORBIDDEN_MODULES:
            assert name != forbidden and not name.startswith(forbidden + "."), (
                f"{path.name} imports {name}"
            )


@pytest.mark.parametrize("path", _modules(), ids=lambda p: p.name)
def test_no_environment_and_no_builtin_hash(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "hash", f"{path.name} uses the built-in hash()"
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"environ", "getenv"}, f"{path.name} reads the environment"


def test_frozen_types_module_is_not_touched() -> None:
    source = (DOMAIN_DIR / "types.py").read_text(encoding="utf-8")
    assert "Frozen domain types shared by every backend zone." in source
    assert "class MatchResult(BaseModel):" in source


HOSTILE_INPUTS = {
    "one endless digit line": "1 " * 50_000,
    "ranges on one line": "2019 - " * 14_000,
    "ranges on many lines": "2019 - 2020\n" * 8_000,
    "dashes": "-" * 100_000,
    "one long word": "a" * 100_000,
    "dotted word": "a." * 50_000 + "@",
    "cyrillic stem": "питон" * 20_000,
    "salary line": "зарплата " + "1 000 " * 15_000,
    "months": "март " * 20_000,
    "headings": "Опыт работы\n" * 8_000,
    "ats": "@" * 100_000,
    # many mentions of skills on one line (overlap resolution, negation windows)
    "dense cpp": "c++ " * 25_000,
    "dense cyrillic stem": "питонах " * 12_500,
    "dense negations": "не не не не не python " * 4_545,
    "dense dated python": "03.2020 – 04.2021 Python " * 4_166,
    "dense formats": "удалённо " * 11_000,
    "dense cities": "москва " * 14_000,
    # runs of whitespace (patterns that begin with \s* or \s+)
    "spaces": " " * 100_000 + "1",
    "spaces between ranges": ("03.2020 – 04.2021" + " " * 400 + "\n") * 240,
    # contacts around a skill on a very long line (the quote is cut after clearing)
    "contacts and skills": "python a@b.cc " * 7_000,
    "phones and skills": "Python +7 900 000-00-17 " * 4_000,
    "labels": "город\n" * 20_000,
}
FUNCTIONS: dict[str, Callable[[str], object]] = {
    "parse_resume": parse_resume,
    "redact_contacts": redact_contacts,
    "find_skills": find_skills,
    "parse_query_text": parse_query_text,
    "embed": embed,
    "normalize_skill": normalize_skill,
}


@pytest.mark.parametrize("name", HOSTILE_INPUTS)
def test_hostile_input_is_handled_quickly(name: str) -> None:
    text = HOSTILE_INPUTS[name]
    for function_name, function in FUNCTIONS.items():
        started = time.perf_counter()
        function(text)
        elapsed = time.perf_counter() - started
        assert elapsed < 4.0, f"{function_name} took {elapsed:.1f}s on {name!r}"
