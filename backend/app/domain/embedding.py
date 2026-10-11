"""Local lexical vector of a text (SPEC section 7.6).

This is lexical similarity, not semantics: words, character 3-grams and normalised
ontology skills are hashed (signed, via `hashlib.md5`) into 384 dimensions. No external
model is called and the built-in `hash()` is never used: it is salted per process.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

from app.domain import scoring_config as cfg
from app.domain.categorizer import skill_evidence
from app.domain.ontology import (
    DISCIPLINE_TITLES,
    GRADE_TITLES,
    STACK_TITLES,
    TEAM_ROLE_TITLES,
    find_skill_mentions,
    is_known_skill,
    is_negated,
    load_stopwords,
    norm_key,
)
from app.domain.redaction import redact_contacts
from app.domain.types import Categorization, FactData

_SKILL_MARKER = re.compile(r"skill:([a-z0-9][a-z0-9-]*)")
_TOKEN = re.compile(r"[^\W_]+")
_SKILL_PREFIX = "s:"


def profile_text(
    facts: list[FactData],
    categorization: Categorization,
    about: str | None,
    resume_text: str | None,
) -> str:
    """The text a candidate is compared by; every part is passed through `redact_contacts`.

    Skills are written as `skill:<id>` markers, repeated in proportion to their evidence
    (a stronger proof pulls the vector harder).
    """
    parts: list[str] = []
    for item in sorted(skill_evidence(facts).values(), key=lambda e: (-e.evidence, e.skill)):
        repeat = max(1, round(item.evidence * cfg.PROFILE_SKILL_REPEAT_MAX))
        parts.extend([f"skill:{item.skill}"] * repeat)

    if categorization.stack:
        parts.append(f"{categorization.stack} {STACK_TITLES[categorization.stack]}")
    if categorization.grade:
        parts.append(f"{categorization.grade} {GRADE_TITLES[categorization.grade]}")
    if categorization.team_role:
        parts.append(f"{categorization.team_role} {TEAM_ROLE_TITLES[categorization.team_role]}")

    for fact in facts:
        if fact.kind != "achievement":
            continue
        parts.append(str(fact.value.get("title") or fact.title))
        discipline = fact.value.get("discipline")
        if isinstance(discipline, str) and discipline in DISCIPLINE_TITLES:
            parts.append(DISCIPLINE_TITLES[discipline])

    parts = [redact_contacts(part) or "" for part in parts]
    if about:
        parts.append(redact_contacts(about) or "")
    if resume_text:
        parts.append((redact_contacts(resume_text) or "")[: cfg.PROFILE_RESUME_CHARS])
    return "\n".join(part for part in parts if part)


def _hash_feature(feature: str) -> tuple[int, float]:
    digest = hashlib.md5(feature.encode("utf-8"), usedforsecurity=False).digest()
    index = int.from_bytes(digest[:4], "big") % cfg.EMBEDDING_DIM
    sign = 1.0 if digest[4] & 1 else -1.0
    return index, sign


def _features(text: str) -> Counter[str]:
    """Counts of the features of a text: `s:<skill id>`, `w:<word>` and `c:<3-gram>`."""
    counts: Counter[str] = Counter()

    # Skills written by `profile_text`.
    for match in _SKILL_MARKER.finditer(text):
        if is_known_skill(match.group(1)):
            counts[_SKILL_PREFIX + match.group(1)] += 1
    text = _SKILL_MARKER.sub(" ", text)

    # Skills found by their aliases: they become one feature, their words are not repeated.
    characters = list(text)
    for mention in find_skill_mentions(text, respect_negation=False):
        if not is_negated(text, mention.start):
            counts[_SKILL_PREFIX + mention.key] += 1
        for position in range(mention.start, mention.end):
            characters[position] = " "
    rest = norm_key("".join(characters))

    stopwords = load_stopwords()
    for word in _TOKEN.findall(rest):
        if len(word) < 2 or word.isdigit() or word in stopwords:
            continue
        counts["w:" + word] += 1
        padded = f"<{word}>"
        for i in range(len(padded) - cfg.NGRAM_SIZE + 1):
            counts["c:" + padded[i : i + cfg.NGRAM_SIZE]] += 1
    return counts


def embed(text: str) -> list[float]:
    """384-dimensional L2-normalised vector; the zero vector for a text without features."""
    vector = [0.0] * cfg.EMBEDDING_DIM
    for feature, count in _features(text or "").items():
        index, sign = _hash_feature(feature)
        weight = cfg.SKILL_FEATURE_WEIGHT if feature.startswith(_SKILL_PREFIX) else 1.0
        vector[index] += sign * weight * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [round(value / norm, cfg.EMBEDDING_DECIMALS) for value in vector]


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity; 0.0 when either vector is empty or has no length."""
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        raise ValueError(f"vectors of different length: {len(a)} and {len(b)}")
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / (norm_a * norm_b)
