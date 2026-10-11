"""Skill ontology: integrity of skills.json and the alias matching rules (SPEC section 4)."""

from __future__ import annotations

import time

import pytest

from app.domain import ontology
from app.domain.ontology import (
    Mention,
    dictionaries,
    find_skills,
    is_known_skill,
    load_cities,
    load_ontology,
    norm_key,
    normalize_skill,
    resolve_overlaps,
    skill_title,
)

# The table of SPEC section 4, transcribed: skill -> (core stacks, secondary stacks).
SPEC_TABLE: dict[str, tuple[set[str], set[str]]] = {
    "python": ({"backend", "ml"}, {"analyst", "qa", "devops"}),
    "java": ({"backend"}, {"mobile"}),
    "kotlin": ({"mobile"}, {"backend"}),
    "swift": ({"mobile"}, set()),
    "go": ({"backend"}, {"devops"}),
    "cpp": ({"embedded"}, {"backend"}),
    "csharp": ({"backend"}, set()),
    "javascript": ({"frontend"}, {"backend"}),
    "typescript": ({"frontend"}, {"backend"}),
    "rust": (set(), {"backend", "embedded"}),
    "php": ({"backend"}, set()),
    "sql": ({"analyst"}, {"backend"}),
    "html-css": ({"frontend"}, set()),
    "fastapi": ({"backend"}, set()),
    "django": ({"backend"}, set()),
    "spring": ({"backend"}, set()),
    "flask": (set(), {"backend"}),
    "react": ({"frontend"}, set()),
    "vue": ({"frontend"}, set()),
    "angular": ({"frontend"}, set()),
    "nodejs": ({"backend"}, {"frontend"}),
    "flutter": ({"mobile"}, set()),
    "android": ({"mobile"}, set()),
    "ios": ({"mobile"}, set()),
    "react-native": ({"mobile"}, {"frontend"}),
    "pytorch": ({"ml"}, set()),
    "tensorflow": ({"ml"}, set()),
    "sklearn": ({"ml"}, set()),
    "pandas": ({"analyst"}, {"ml"}),
    "docker": ({"devops"}, {"backend"}),
    "kubernetes": ({"devops"}, set()),
    "terraform": ({"devops"}, set()),
    "ansible": ({"devops"}, set()),
    "linux": ({"devops"}, {"security", "embedded"}),
    "ci-cd": ({"devops"}, {"qa"}),
    "nginx": (set(), {"devops"}),
    "git": (set(), set()),
    "postgresql": ({"backend"}, {"analyst"}),
    "mongodb": (set(), {"backend"}),
    "redis": (set(), {"backend"}),
    "kafka": (set(), {"backend"}),
    "rabbitmq": (set(), {"backend"}),
    "algorithms": ({"backend"}, {"ml"}),
    "product-development": (set(), {"backend", "frontend"}),
    "system-design": (set(), {"backend"}),
    "infosec": ({"security"}, set()),
    "pentest": ({"security"}, set()),
    "cryptography": ({"security"}, set()),
    "reverse-engineering": ({"security"}, set()),
    "robotics": ({"embedded"}, set()),
    "ros": ({"embedded"}, set()),
    "uav": ({"embedded"}, set()),
    "microcontrollers": ({"embedded"}, set()),
    "machine-learning": ({"ml"}, set()),
    "nlp": ({"ml"}, set()),
    "llm": ({"ml"}, set()),
    "computer-vision": ({"ml"}, {"embedded"}),
    "data-analysis": ({"analyst"}, set()),
    "business-analysis": ({"analyst"}, set()),
    "bi-tools": ({"analyst"}, set()),
    "testing": ({"qa"}, set()),
    "test-automation": ({"qa"}, set()),
    "selenium": ({"qa"}, set()),
    "jira": (set(), {"analyst", "qa"}),
    "figma": (set(), {"frontend"}),
    "ui-ux": (set(), {"frontend"}),
}


# --- integrity -----------------------------------------------------------------------------------
def test_there_are_exactly_66_skills_with_unique_ids() -> None:
    skills = load_ontology().skills
    ids = [s.id for s in skills]
    assert len(SPEC_TABLE) == 66
    assert len(skills) == 66
    assert len(set(ids)) == 66


def test_stacks_match_the_spec_table_exactly() -> None:
    skills = {s.id: s for s in load_ontology().skills}
    assert set(skills) == set(SPEC_TABLE)
    for skill_id, (core, secondary) in SPEC_TABLE.items():
        actual_core = {k for k, v in skills[skill_id].stacks.items() if v == "core"}
        actual_secondary = {k for k, v in skills[skill_id].stacks.items() if v == "secondary"}
        assert actual_core == core, skill_id
        assert actual_secondary == secondary, skill_id


def test_every_stack_but_fullstack_has_two_core_skills() -> None:
    ont = load_ontology()
    for stack in ontology.STACK_TITLES:
        if stack == "fullstack":
            assert ont.core_skills(stack) == ()
        else:
            assert len(ont.core_skills(stack)) >= 2, stack


def test_aliases_do_not_overlap_between_skills() -> None:
    owner: dict[str, str] = {}
    for skill in load_ontology().skills:
        for alias in skill.aliases:
            key = norm_key(alias)
            assert owner.setdefault(key, skill.id) == skill.id, f"{alias!r} is shared"


def test_aliases_contain_latin_and_russian_spellings() -> None:
    skills = load_ontology().skills
    assert all(any(a.isascii() for a in s.aliases) or s.id == "algorithms" for s in skills)
    without_russian = [
        s.id for s in skills if not any(not a.isascii() and "+" not in a for a in s.aliases)
    ]
    assert without_russian == ["ros"]  # ROS has no common Russian spelling


def test_forbidden_short_aliases_are_absent() -> None:
    all_aliases = {norm_key(a) for s in load_ontology().skills for a in s.aliases}
    assert not all_aliases & {"go", "c", "r", "с"}


def test_discipline_skills_exist() -> None:
    for skill_id in ontology.DISCIPLINE_SKILL.values():
        assert is_known_skill(skill_id)


def test_cities_list_has_60_unique_names() -> None:
    cities = load_cities()
    assert len(cities) == 60
    assert len(set(cities)) == 60


# --- alias rules ---------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Пишу на C++ и C#", ["cpp", "csharp"]),
        ("С++ (кириллическая С) и С#", ["cpp", "csharp"]),
        ("три года работаю с питоном", ["python"]),
        ("администрирую постгреса", ["postgresql"]),
        ("React Native", ["react-native"]),
        ("React и React Native", ["react", "react-native"]),
        ("пишу на реакт и реакт нейтив", ["react", "react-native"]),
        ("go to market strategy", []),
        ("golang, язык Go", ["go"]),
        ("не знаю Python", []),
        ("изучаю Kubernetes", []),
        ("хочу освоить Rust", []),
        ("планирую выучить Docker", []),
        ("прошёл курс по SQL", []),
        ("курсы Python и Django", []),
        ("без опыта работы с Kafka", []),
        ("Python, не знаю Java", ["python"]),
        ("JavaScript, Java", ["javascript", "java"]),
        ("PostgreSQL и MySQL", ["postgresql", "sql"]),
        ("Vue.js, Node.js, Next.js", ["vue", "nodejs", "react"]),
        ("Docker. Не пользуюсь Redis", ["docker"]),
        ("ml и nlp", ["machine-learning", "nlp"]),
    ],
)
def test_find_skills_follows_alias_rules(text: str, expected: list[str]) -> None:
    assert find_skills(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # every word of a Russian multi-word alias takes case endings, not only the last one
        ("машинное обучение", ["machine-learning"]),
        ("опыт машинного обучения", ["machine-learning"]),
        ("занимаюсь машинным обучением", ["machine-learning"]),
        ("интересуюсь машинному обучению", ["machine-learning"]),
        ("анализа данных", ["data-analysis"]),
        ("занимался анализом данных", ["data-analysis"]),
        ("компьютерным зрением", ["computer-vision"]),
        ("задачи компьютерного зрения", ["computer-vision"]),
        ("ручным тестированием", ["testing"]),
        ("автоматизации тестирования", ["test-automation"]),
        ("автоматизацией тестирования", ["test-automation"]),
        ("большими языковыми моделями", ["llm"]),
        ("системным дизайном", ["system-design"]),
        # a soft sign counts as a vowel of the stem
        ("кибербезопасность", ["infosec"]),
        ("Эксперт по кибербезопасности", ["infosec"]),
        ("занимаюсь кибербезопасностью", ["infosec"]),
        ("информационной безопасностью", ["infosec"]),
        ("специалист по информационной безопасности", ["infosec"]),
        # the same stems must not catch other words
        ("машинное отделение корабля", []),
        ("компьютерный зал", []),
        ("анализ крови", []),
    ],
)
def test_multi_word_aliases_take_case_endings(text: str, expected: list[str]) -> None:
    assert find_skills(text) == expected


def test_multi_word_alias_endings_do_not_break_negation_or_overlap() -> None:
    assert find_skills("не знаю машинного обучения") == []
    assert find_skills("Python и анализом данных") == ["python", "data-analysis"]
    # the longer alias still wins over the one inside it
    assert find_skills("автоматизации тестирования") == ["test-automation"]


def test_a_text_with_tens_of_thousands_of_mentions_is_handled_quickly() -> None:
    started = time.perf_counter()
    assert find_skills("c++ " * 25_000) == ["cpp"]
    assert find_skills("питонах " * 12_500) == ["python"]
    assert find_skills("не не не не не python " * 4_500) == []
    assert time.perf_counter() - started < 4.0


def test_resolve_overlaps_keeps_the_longest_and_the_earliest() -> None:
    mentions = [
        Mention("react", 0, 5),
        Mention("react-native", 0, 12),
        Mention("native", 6, 12),
        Mention("go", 20, 22),
        Mention("go-long", 20, 30),
        Mention("tail", 30, 33),
        Mention("inside", 21, 25),
    ]
    assert [(m.key, m.start) for m in resolve_overlaps(mentions)] == [
        ("react-native", 0),
        ("go-long", 20),
        ("tail", 30),
    ]


def test_negation_looks_back_only_a_bounded_distance() -> None:
    # the reach (256 characters) cuts "стене" into "сте" + "не": the tail is not a negation
    text = "стене " + "a" * 252 + " Python"
    assert text.index("Python") - 256 == text.index("не")
    assert find_skills(text) == ["python"]
    # a line with a negation inside the reach is still negated
    assert find_skills("x " * 200 + "не знаю Python") == []


def test_negation_window_is_four_words() -> None:
    assert find_skills("не очень хорошо знаю Python") == []
    assert find_skills("не очень хорошо и давно знаю Python") == ["python"]


def test_negation_does_not_cross_lines() -> None:
    assert find_skills("Не курю\nPython") == ["python"]


def test_negated_first_mention_does_not_hide_a_later_real_one() -> None:
    assert find_skills("не знаю Python. Потом выучил Python и Django") == ["python", "django"]


def test_stem_rule_catches_case_endings() -> None:
    assert find_skills("опыт с джанго и докером") == ["django", "docker"]
    assert find_skills("работал с кафкой и редисом") == ["kafka", "redis"]


def test_stem_rule_does_not_match_unrelated_longer_words() -> None:
    assert find_skills("джаваскрипт") == ["javascript"]
    assert find_skills("питонисса") == []


def test_javascript_does_not_hide_inside_other_words() -> None:
    assert find_skills("Vue.js") == ["vue"]
    assert find_skills("JavaScript") == ["javascript"]


# --- normalize_skill and the rest of the interface -------------------------------------------
def test_normalize_skill() -> None:
    assert normalize_skill("Питоном") == "python"
    assert normalize_skill("  PostgreSQL ") == "postgresql"
    assert normalize_skill("Node.js") == "nodejs"
    assert normalize_skill("go") == "go"
    assert normalize_skill("React Native") == "react-native"
    assert normalize_skill("c") is None
    assert normalize_skill("с") is None
    assert normalize_skill("") is None
    assert normalize_skill("квантовая гастрономия") is None


def test_skill_title_and_known_skill() -> None:
    assert skill_title("python") == "Python"
    assert skill_title("cpp") == "C++"
    assert is_known_skill("fastapi")
    assert not is_known_skill("cobol")
    with pytest.raises(KeyError):
        skill_title("cobol")


def test_dictionaries_shape() -> None:
    data = dictionaries()
    assert "fsp_registry_mode" not in data
    assert [s["id"] for s in data["stacks"]] == list(ontology.STACK_TITLES)
    assert len(data["stacks"]) == 10
    assert [g["id"] for g in data["grades"]] == ["intern", "junior", "middle", "senior"]
    assert len(data["team_roles"]) == 6
    assert [f["id"] for f in data["work_formats"]] == ["remote", "office", "hybrid"]
    assert [s["id"] for s in data["sources"]] == ["fsp", "test", "resume", "self"]
    weights = {v["id"]: v["weight"] for v in data["verifications"]}
    assert weights == {"verified": 1.0, "tested": 0.85, "parsed": 0.55, "declared": 0.35}
    assert len(data["disciplines"]) == 5
    assert len(data["competition_levels"]) == 5
    assert [r["id"] for r in data["sport_ranks"]] == ["third", "second", "first", "kms", "ms"]
    assert len(data["skills"]) == 66
    assert len(data["cities"]) == 60
    python = next(s for s in data["skills"] if s["id"] == "python")
    assert python["stacks"][:2] == ["backend", "ml"]  # core stacks come first
