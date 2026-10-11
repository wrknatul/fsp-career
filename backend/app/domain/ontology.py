"""Skill ontology, reference dictionaries and the alias matching engine (SPEC section 4).

The alias engine is shared by the resume parser (skills, work formats, cities) and by the
matcher (text of a search query), so every text in the system is recognised the same way.
"""

from __future__ import annotations

import json
import re
from bisect import bisect_left
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.domain.scoring_config import (
    NEGATION_WINDOW,
    NEGATION_WORDS,
    STEM_MIN_LENGTH,
    STEM_SUFFIX_MAX,
    VERIFICATION_WEIGHT,
)

DATA_DIR = Path(__file__).resolve().parent / "data"

# --- Reference dictionaries (SPEC section 4); the order of the keys is the official order ------
STACK_TITLES: dict[str, str] = {
    "backend": "Backend",
    "frontend": "Frontend",
    "fullstack": "Fullstack",
    "mobile": "Мобильная разработка",
    "ml": "ML / Data Science",
    "devops": "DevOps / SRE",
    "security": "Информационная безопасность",
    "embedded": "Embedded / робототехника",
    "qa": "Тестирование",
    "analyst": "Аналитика",
}
# Stacks that can be computed from skills (everything except the synthetic fullstack).
CONCRETE_STACKS: tuple[str, ...] = tuple(s for s in STACK_TITLES if s != "fullstack")

GRADE_TITLES: dict[str, str] = {
    "intern": "Стажёр",
    "junior": "Junior",
    "middle": "Middle",
    "senior": "Senior",
}
TEAM_ROLE_TITLES: dict[str, str] = {
    "lead": "Тимлид",
    "developer": "Разработчик",
    "researcher": "Исследователь / алгоритмист",
    "devops": "Инженер инфраструктуры",
    "qa": "Тестировщик",
    "analyst": "Аналитик",
}
WORK_FORMAT_TITLES: dict[str, str] = {"remote": "Удалённо", "office": "Офис", "hybrid": "Гибрид"}
SOURCE_TITLES: dict[str, str] = {
    "fsp": "Реестр ФСП",
    "test": "Тест платформы",
    "resume": "Резюме",
    "self": "Указано соискателем",
}
VERIFICATION_TITLES: dict[str, str] = {
    "verified": "Подтверждено ФСП",
    "tested": "Подтверждено тестом",
    "parsed": "Из резюме",
    "declared": "Заявлено соискателем",
}
DISCIPLINE_TITLES: dict[str, str] = {
    "algorithmic": "Алгоритмическое программирование",
    "product": "Продуктовое программирование (хакатон)",
    "security": "Программирование систем информационной безопасности",
    "robotics": "Программирование робототехники",
    "uav": "Программирование БАС",
}
# Skill that a competition discipline proves (SPEC section 4).
DISCIPLINE_SKILL: dict[str, str] = {
    "algorithmic": "algorithms",
    "product": "product-development",
    "security": "infosec",
    "robotics": "robotics",
    "uav": "uav",
}
LEVEL_TITLES: dict[str, str] = {
    "municipal": "Муниципальный",
    "regional": "Региональный",
    "district": "Федеральный округ",
    "national": "Всероссийский",
    "international": "Международный",
}
SPORT_RANK_TITLES: dict[str, str] = {
    "third": "III разряд",
    "second": "II разряд",
    "first": "I разряд",
    "kms": "КМС",
    "ms": "Мастер спорта России",
}

_TIERS = ("core", "secondary")


# --- Alias matching engine ----------------------------------------------------------------------
_LEFT = r"(?<![\w+#.])"
_RIGHT = r"(?![\w+#])"
_VOWELS = frozenset("аеиоуыэюя")
# A word that ends with one of these loses it before the case endings are added; the soft
# sign counts like a vowel ("безопасность" -> "безопасности", "безопасностью").
_STEM_TAIL = _VOWELS | {"ь"}
# Endings of an adjective in the base form: the whole ending is replaced by case endings
# ("машинное" -> "машинного", "машинным", "машинному").
_ADJECTIVE_ENDINGS = ("ая", "яя", "ое", "ее", "ый", "ий", "ой", "ые", "ие")
# How far back a negation word is looked for. Four words fit in this many characters unless
# the words are absurdly long, so a long line is never read from its start.
_NEGATION_REACH_CHARS = 256
_CYRILLIC = re.compile(r"[а-я][а-я\s\-]*")
_WORD = re.compile(r"\w+")
_SENTENCE_END = re.compile(r"[.!?;]+(?=\s|$)")
_INLINE_SPACE = r"[ \t ]+"


def norm_key(value: str) -> str:
    """Lower-case, `ё` -> `е`, collapsed whitespace: the form used for comparisons."""
    return " ".join(value.lower().replace("ё", "е").split())


@dataclass(frozen=True)
class Mention:
    """One recognised occurrence of an alias of `key` at text[start:end]."""

    key: str
    start: int
    end: int


@dataclass(frozen=True)
class AliasPattern:
    scan: re.Pattern[str]  # finds aliases inside a text (with word-boundary guards)
    full: re.Pattern[str]  # for `fullmatch` of a whole short string


def _literal(word: str) -> str:
    """Regex of a word that must match as written (`е` also matches `ё`)."""
    return "".join("[её]" if char == "е" else re.escape(char) for char in word)


def _case_stem(word: str, *, last: bool) -> str:
    """The word without the part that changes with the case.

    The last word of an alias loses its last vowel or soft sign (SPEC section 4). A word in
    front of it is usually an adjective ("машинное обучение"), so it loses the whole
    adjective ending: "машинным обучением" must be found too.
    """
    if not last and word.endswith(_ADJECTIVE_ENDINGS):
        return word[:-2]
    if word[-1] in _STEM_TAIL:
        return word[:-1]
    return word


def _alias_regex(alias: str) -> str:
    """Regex body of one alias.

    A Cyrillic alias of five or more characters is matched by stems (the word without its
    last vowel) plus up to three more letters, which catches the case endings. Every word
    of a multi-word alias takes endings, as long as the word itself has five characters;
    the last word takes them whatever its length.
    """
    norm = norm_key(alias)
    stemmed = len(norm) >= STEM_MIN_LENGTH and _CYRILLIC.fullmatch(norm) is not None
    endings = rf"\w{{0,{STEM_SUFFIX_MAX}}}"
    words = norm.split(" ")
    parts: list[str] = []
    for index, word in enumerate(words):
        last = index == len(words) - 1
        if stemmed and (last or len(word) >= STEM_MIN_LENGTH):
            parts.append(_literal(_case_stem(word, last=last)) + endings)
        else:
            parts.append(_literal(word))
    return _INLINE_SPACE.join(parts)


def compile_aliases(aliases: Iterable[str]) -> AliasPattern | None:
    """Compile a set of aliases into one pattern; None when there is nothing to match."""
    bodies = sorted({norm_key(a) for a in aliases if a and a.strip()}, key=len, reverse=True)
    if not bodies:
        return None
    alternatives = "|".join(_alias_regex(alias) for alias in bodies)
    return AliasPattern(
        scan=re.compile(f"{_LEFT}(?:{alternatives}){_RIGHT}", re.IGNORECASE),
        full=re.compile(f"(?:{alternatives})", re.IGNORECASE),
    )


def resolve_overlaps(mentions: Iterable[Mention]) -> list[Mention]:
    """When occurrences overlap the longer one wins (`react native` does not give `react`).

    Accepted occurrences never overlap each other, so a new one can only collide with its two
    neighbours in the order of the starts: the check is logarithmic, not linear, and a text of
    a hundred thousand characters with tens of thousands of mentions stays cheap.
    """
    starts: list[int] = []
    accepted: list[Mention] = []
    for mention in sorted(mentions, key=lambda m: (-(m.end - m.start), m.start)):
        position = bisect_left(starts, mention.start)
        if position > 0 and accepted[position - 1].end > mention.start:
            continue
        if position < len(accepted) and accepted[position].start < mention.end:
            continue
        starts.insert(position, mention.start)
        accepted.insert(position, mention)
    return accepted


def is_negated(text: str, start: int) -> bool:
    """True when one of the negation words stands in the four words before `start`.

    The window never crosses a line break or the end of a sentence.
    """
    reach_start = max(0, start - _NEGATION_REACH_CHARS)
    line_break = text.rfind("\n", reach_start, start)
    if line_break >= 0:
        begin = line_break + 1
    else:
        begin = reach_start
        if begin > 0 and text[begin - 1].isalnum():
            # The reach cut a word in two: its tail must not pass for a word of its own.
            while begin < start and text[begin].isalnum():
                begin += 1
    prefix = text[begin:start]
    last_end = 0
    for match in _SENTENCE_END.finditer(prefix):
        last_end = match.end()
    words = _WORD.findall(norm_key(prefix[last_end:]))
    return any(word in NEGATION_WORDS for word in words[-NEGATION_WINDOW:])


def scan_mentions(
    text: str,
    patterns: Mapping[str, AliasPattern],
    *,
    respect_negation: bool = True,
) -> list[Mention]:
    """All occurrences of every pattern, overlaps resolved, negated ones dropped."""
    found: list[Mention] = []
    for key, pattern in patterns.items():
        for match in pattern.scan.finditer(text):
            found.append(Mention(key, match.start(), match.end()))
    resolved = resolve_overlaps(found)
    if respect_negation:
        resolved = [m for m in resolved if not is_negated(text, m.start)]
    return resolved


# --- Ontology ---------------------------------------------------------------------------------
@dataclass(frozen=True, eq=False)
class Skill:
    id: str
    title: str
    aliases: tuple[str, ...]
    stacks: dict[str, str]  # stack id -> "core" | "secondary"

    def stack_ids(self) -> list[str]:
        """Core stacks first, then secondary ones, each group in the official order."""
        ordered = [s for s in STACK_TITLES if self.stacks.get(s) == "core"]
        ordered += [s for s in STACK_TITLES if self.stacks.get(s) == "secondary"]
        return ordered


@dataclass(frozen=True, eq=False)
class Ontology:
    skills: tuple[Skill, ...]
    by_id: dict[str, Skill]
    exact: dict[str, str]  # normalised id / title / alias -> skill id
    patterns: dict[str, AliasPattern]

    def core_skills(self, stack: str) -> tuple[str, ...]:
        return tuple(s.id for s in self.skills if s.stacks.get(stack) == "core")


def read_json(name: str) -> Any:
    """Read one of the bundled data files."""
    with (DATA_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def _build_skill(raw: dict[str, Any]) -> Skill:
    stacks = dict(raw["stacks"])
    for stack, tier in stacks.items():
        if stack not in CONCRETE_STACKS:
            raise ValueError(f"skills.json: unknown stack {stack!r} in skill {raw['id']!r}")
        if tier not in _TIERS:
            raise ValueError(f"skills.json: unknown tier {tier!r} in skill {raw['id']!r}")
    return Skill(
        id=raw["id"],
        title=raw["title"],
        aliases=tuple(raw["aliases"]),
        stacks=stacks,
    )


@lru_cache(maxsize=1)
def load_ontology() -> Ontology:
    skills = tuple(_build_skill(raw) for raw in read_json("skills.json"))
    by_id: dict[str, Skill] = {}
    exact: dict[str, str] = {}
    patterns: dict[str, AliasPattern] = {}
    for skill in skills:
        if skill.id in by_id:
            raise ValueError(f"skills.json: duplicate skill id {skill.id!r}")
        by_id[skill.id] = skill
        for form in (skill.id, skill.title, *skill.aliases):
            key = norm_key(form)
            owner = exact.setdefault(key, skill.id)
            if owner != skill.id:
                raise ValueError(
                    f"skills.json: {form!r} belongs to both {owner!r} and {skill.id!r}"
                )
        pattern = compile_aliases(skill.aliases)
        if pattern is not None:
            patterns[skill.id] = pattern
    return Ontology(skills=skills, by_id=by_id, exact=exact, patterns=patterns)


@lru_cache(maxsize=1)
def load_cities() -> tuple[str, ...]:
    return tuple(read_json("cities.json"))


@lru_cache(maxsize=1)
def load_stopwords() -> frozenset[str]:
    data = read_json("stopwords.json")
    return frozenset(norm_key(word) for lang in data.values() for word in lang)


# --- Public interface (SPEC section 7.8) ----------------------------------------------------
def is_known_skill(skill_id: str) -> bool:
    return skill_id in load_ontology().by_id


def skill_title(skill_id: str) -> str:
    skill = load_ontology().by_id.get(skill_id)
    if skill is None:
        raise KeyError(f"unknown skill id: {skill_id!r}")
    return skill.title


def normalize_skill(raw: str) -> str | None:
    """Map a free-form skill name ("Питоном", "Node.js", "postgres") to a skill id."""
    if not raw or not raw.strip():
        return None
    ontology = load_ontology()
    key = norm_key(raw)
    hit = ontology.exact.get(key)
    if hit is not None:
        return hit
    for skill_id, pattern in ontology.patterns.items():
        if pattern.full.fullmatch(key):
            return skill_id
    return None


def find_skill_mentions(text: str, *, respect_negation: bool = True) -> list[Mention]:
    """Occurrences of ontology skills in `text`, in the order they appear."""
    if not text:
        return []
    return scan_mentions(text, load_ontology().patterns, respect_negation=respect_negation)


def find_skills(text: str) -> list[str]:
    """Skill ids found in `text`, in the order of the first occurrence."""
    seen: dict[str, None] = {}
    for mention in find_skill_mentions(text):
        seen.setdefault(mention.key, None)
    return list(seen)


def dictionaries() -> dict[str, Any]:
    """The contract type `Dictionaries` without `fsp_registry_mode`."""
    ontology = load_ontology()
    return {
        "stacks": [{"id": k, "title": v} for k, v in STACK_TITLES.items()],
        "grades": [{"id": k, "title": v} for k, v in GRADE_TITLES.items()],
        "team_roles": [{"id": k, "title": v} for k, v in TEAM_ROLE_TITLES.items()],
        "work_formats": [{"id": k, "title": v} for k, v in WORK_FORMAT_TITLES.items()],
        "sources": [{"id": k, "title": v} for k, v in SOURCE_TITLES.items()],
        "verifications": [
            {"id": k, "title": v, "weight": VERIFICATION_WEIGHT[k]}
            for k, v in VERIFICATION_TITLES.items()
        ],
        "disciplines": [{"id": k, "title": v} for k, v in DISCIPLINE_TITLES.items()],
        "competition_levels": [{"id": k, "title": v} for k, v in LEVEL_TITLES.items()],
        "sport_ranks": [{"id": k, "title": v} for k, v in SPORT_RANK_TITLES.items()],
        "skills": [
            {"id": s.id, "title": s.title, "stacks": s.stack_ids()} for s in ontology.skills
        ],
        "cities": list(load_cities()),
    }
