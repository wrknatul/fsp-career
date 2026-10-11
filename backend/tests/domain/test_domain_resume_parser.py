"""Resume parsing by rules: text extraction and fields (SPEC section 6.2)."""

from __future__ import annotations

import io
import re
from datetime import date

import pytest
from domain_testkit import TODAY
from pypdf import PdfWriter

from app.domain.redaction import HIDDEN, redact_contacts
from app.domain.resume_parser import ResumeError, extract_text, parse_resume

INTERN = """Петров Игорь Сергеевич
Желаемая должность: Стажёр-разработчик (Python)
Город: Казань
Формат работы: удалённо, гибрид
Зарплатные ожидания: от 40 000 руб.
Телефон: +7 900 111-22-33, почта igor.petrov@mail.ru, telegram @igor_p

Опыт работы
Стажёр-программист
ООО «Вектор»
06.2026 — н.в.
- Писал скрипты на Python, учился работать с Git.

Образование
Казанский федеральный университет, 2022 — 2026
Курсы по SQL, 2025

Навыки
Python, Git, SQL, не знаю Docker, изучаю Kubernetes
"""

DEVELOPER = """Иванова Мария Андреевна
Python-разработчик
Москва
Формат работы: удалённо или гибрид. Не готова работать в офисе.
Желаемая зарплата: от 250 000 ₽ на руки

Опыт работы

Python-разработчик, Яндекс
03.2021 — 12.2023
Разрабатывала сервисы на FastAPI и PostgreSQL, использовала Docker и Redis.

Senior Python developer — Тинькофф
07.2023 — н.в.
Проектировала микросервисы, писала на питоне, работала с Kafka.

Продавец-консультант, Магнит
2018 — 2019

Python-разработчик, ООО Будущее
01.2030 — 12.2030

Образование
МГТУ им. Баумана, 2013 — 2019
"""

TEAM_LEAD = """Сидоров Павел Николаевич
Тимлид, Java
Желаемая зарплата: 300 000 - 350 000 руб.
г. Санкт-Петербург, рассматриваю гибрид

Опыт работы
Руководитель группы разработки — ООО «Банк-Тех»
05.2022 — настоящее время
Руководил командой из 6 человек: Java, Spring Boot, Kafka, PostgreSQL.

Senior Java-разработчик, Сбер
10.2018 – 04.2022
Kubernetes, Docker, CI/CD.

Образование
СПбГУ 2008 — 2013
"""


def _skills(result) -> dict[str, int]:
    return {s.skill: s.level for s in result.skills}


# --- the three Russian resumes -----------------------------------------------------------------
def test_intern_resume() -> None:
    result = parse_resume(INTERN, TODAY)
    assert result.parser == "rules"
    assert _skills(result) == {"python": 1, "git": 1, "sql": 1}  # level 1: under a year
    assert result.experience_years == pytest.approx(0.36, abs=0.02)
    assert result.is_lead is False
    assert result.work_formats == ["remote", "hybrid"]
    assert result.city == "Казань"
    assert result.salary_expectation == 40000
    assert len(result.positions) == 1
    position = result.positions[0]
    assert position.title == "Стажёр-программист"
    assert position.company == "ООО «Вектор»"
    assert position.period == "06.2026 — н.в."
    assert position.is_it is True


def test_developer_resume() -> None:
    result = parse_resume(DEVELOPER, TODAY)
    assert _skills(result) == {
        "python": 2,
        "fastapi": 2,
        "postgresql": 2,
        "docker": 2,
        "redis": 2,
        "system-design": 2,
        "kafka": 2,
    }
    # 03.2021 - 12.2023 and 07.2023 - today overlap and are glued together: 5.6 years
    assert result.experience_years == pytest.approx(5.6, abs=0.05)
    assert result.is_lead is False
    assert result.work_formats == ["remote", "hybrid"]  # "не готова работать в офисе" is ignored
    assert result.city == "Москва"
    assert result.salary_expectation == 250000


def test_team_lead_resume() -> None:
    result = parse_resume(TEAM_LEAD, TODAY)
    assert result.is_lead is True
    assert result.experience_years == pytest.approx(8.0, abs=0.05)
    assert result.city == "Санкт-Петербург"
    assert result.work_formats == ["hybrid"]
    assert result.salary_expectation is None  # a range without "от" is ambiguous
    assert {"java", "spring", "kafka", "postgresql", "kubernetes", "docker", "ci-cd"} <= set(
        _skills(result)
    )
    assert all(level == 2 for level in _skills(result).values())


def test_facts_of_a_resume() -> None:
    result = parse_resume(TEAM_LEAD, TODAY)
    for fact in result.facts:
        assert fact.source == "resume"
        assert fact.verification == "parsed"
    kinds = {f.kind for f in result.facts}
    assert kinds == {"skill", "experience", "role"}
    experience = next(f for f in result.facts if f.kind == "experience")
    assert experience.key == "total"
    assert experience.title == "Опыт в ИТ: 8 лет"
    assert experience.value["years"] == result.experience_years
    assert len(experience.value["positions"]) == 2
    assert set(experience.value["positions"][0]) == {"title", "company", "period", "years"}
    lead = next(f for f in result.facts if f.kind == "role")
    assert (lead.key, lead.title) == ("resume_lead", "Тимлид (по резюме)")
    java = next(f for f in result.facts if f.key == "java")
    assert java.title == "Java"
    assert java.value == {"level": 2}
    assert java.evidence and "Java" in java.evidence


def test_a_resume_without_a_lead_has_no_lead_fact() -> None:
    result = parse_resume(DEVELOPER, TODAY)
    assert not [f for f in result.facts if f.kind == "role"]


def test_contacts_never_reach_the_facts() -> None:
    result = parse_resume(INTERN + "\nПишите на igor.petrov@mail.ru или +7 900 111-22-33", TODAY)
    blob = " ".join(
        [f.title for f in result.facts]
        + [f.evidence or "" for f in result.facts]
        + [p.title + (p.company or "") + p.period for p in result.positions]
    )
    assert "igor.petrov" not in blob
    assert "111-22-33" not in blob
    assert "@igor_p" not in blob


def _leaked_contact(blob: str) -> bool:
    """A fragment of the test e-mail, phone or link survived in `blob`."""
    return (
        "@" in blob
        or "alexey" in blob
        or "smirnov" in blob
        or "https:" in blob
        or "example" in blob
        or re.search(r"\d{3}", blob) is not None
    )


def test_a_contact_on_the_edge_of_the_evidence_window_is_not_left_in_pieces() -> None:
    """The window is cut after the contacts are cleared, wherever the contact stands."""
    contacts = (
        " почта alexey.smirnov@example.test телефон +7 900 000-00-17 end",
        " сайт https://example.test/alexey.smirnov телефон 8 (900) 000-00-17 end",
    )
    for contact in contacts:
        for filler in range(0, 175):
            text = "Python " + "x" * filler + contact
            facts = parse_resume(text, TODAY).facts
            evidence = next(f.evidence for f in facts if f.key == "python")
            assert evidence is not None
            assert not _leaked_contact(evidence), (filler, evidence)
            assert len(evidence) <= 140


def test_a_contact_before_the_skill_does_not_push_the_skill_out_of_the_evidence() -> None:
    text = "почта alexey.smirnov@example.test " * 6 + "и " + "x" * 120 + " Python"
    evidence = next(f.evidence for f in parse_resume(text, TODAY).facts if f.key == "python")
    assert evidence is not None
    assert "Python" in evidence
    assert not _leaked_contact(evidence)


def test_a_contact_on_the_edge_of_the_title_window_is_not_left_in_pieces() -> None:
    for filler in range(0, 200):
        text = (
            "тел +7 900 000-00-17 "
            + "x" * filler
            + " Python-разработчик 03.2020 – н.в. Backend, https://example.test/alexey.smirnov"
        )
        result = parse_resume(text, TODAY)
        blob = " ".join(f"{p.title} {p.company or ''} {p.period}" for p in result.positions)
        blob += " ".join(f.evidence or "" for f in result.facts if f.kind != "skill")
        blob = blob.replace("03.2020", "")  # the period itself is three digits and a dot
        assert not _leaked_contact(blob), (filler, blob)


def test_the_owners_name_is_hidden_in_every_quote_and_title() -> None:
    name = "Смирнов Алексей Игоревич"
    text = f"{name} — Python-разработчик\n{name}, Python-разработчик 03.2021 – н.в.\nFastAPI\n"

    plain = parse_resume(text, TODAY)
    hidden = parse_resume(text, TODAY, full_name=name)

    assert "Смирнов" in " ".join(f.evidence or "" for f in plain.facts)  # the leak without a name
    blob = " ".join(
        [f.evidence or "" for f in hidden.facts]
        + [f"{p.title} {p.company or ''} {p.period}" for p in hidden.positions]
    )
    assert not re.search(r"Смирнов|Алексей|Игоревич", blob), blob
    python = next(f for f in hidden.facts if f.key == "python")
    assert python.evidence == f"{HIDDEN} — Python-разработчик"
    assert [(s.skill, s.level) for s in hidden.skills] == [(s.skill, s.level) for s in plain.skills]


def test_a_long_quote_is_cut_between_words_with_an_ellipsis() -> None:
    words = [f"слово{n}" for n in range(60)]
    line = " ".join([*words[:30], "Проектирую схемы в PostgreSQL", *words[30:]])
    text = f"Опыт работы\n{line}\n"

    evidence = next(f.evidence for f in parse_resume(text, TODAY).facts if f.key == "postgresql")

    assert evidence is not None and len(evidence) <= 140
    assert evidence.startswith("…") and evidence.endswith("…")
    assert "PostgreSQL" in evidence
    pieces = evidence.strip("…").split()
    assert set(pieces) <= set(line.split()), pieces  # no word is cut in the middle


def test_a_short_quote_has_no_ellipsis() -> None:
    evidence = next(
        f.evidence for f in parse_resume("Пишу на Python и Go", TODAY).facts if f.key == "python"
    )
    assert evidence == "Пишу на Python и Go"


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Москва · удалённо", ["remote"]),
        ("Казань · гибрид", ["hybrid"]),
        ("Санкт-Петербург | офис", ["office"]),
        ("Екатеринбург, удалённо, гибрид", ["remote", "hybrid"]),
        # not a header: other words stand next to the format word
        ("Мы ищем людей в офис", []),
        ("Разрабатывал сервис для офис-менеджеров", []),
    ],
)
def test_a_work_format_after_a_city_in_the_header_is_found(
    header: str, expected: list[str]
) -> None:
    text = f"Петров Игорь Сергеевич\nPython-разработчик\n\n{header}\nПочта: igor@example.test\n"
    assert parse_resume(text, TODAY).work_formats == expected


def test_evidence_passes_redaction() -> None:
    text = "Python — пишите igor@mail.ru, +7 900 111-22-33, @igor_p"
    result = parse_resume(text, TODAY)
    evidence = next(f.evidence for f in result.facts if f.key == "python")
    assert evidence == redact_contacts(evidence)
    assert "igor@mail.ru" not in evidence
    assert "[скрыто]" in evidence


# --- experience rules ----------------------------------------------------------------------------
def test_study_is_not_experience() -> None:
    text = """Опыт работы
Python-разработчик, Яндекс
01.2025 — 12.2025

Образование
Университет, Прикладная информатика
2019 — 2023
Курсы
Школа программистов, курс Python
2023 — 2024
"""
    result = parse_resume(text, TODAY)
    assert result.experience_years == pytest.approx(1.0, abs=0.02)
    assert len(result.positions) == 1


def test_study_with_an_it_flavour_is_not_experience() -> None:
    text = "Курсы Python и Django, 2021 — 2022\nИТ-колледж, программирование, 2018 — 2022\n"
    result = parse_resume(text, TODAY)
    assert result.experience_years == 0.0
    assert result.positions == []


def test_non_it_position_is_listed_but_not_counted() -> None:
    text = """Опыт работы
Менеджер по продажам, ООО Ромашка
2015 — 2019
"""
    result = parse_resume(text, TODAY)
    assert result.experience_years == 0.0
    assert len(result.positions) == 1
    assert result.positions[0].is_it is False
    assert not [f for f in result.facts if f.kind == "experience"]


def test_now_markers() -> None:
    for marker in ("н.в.", "по настоящее время", "по н.в.", "наст. время", "настоящее время"):
        result = parse_resume(f"Python-разработчик, Яндекс\n03.2024 — {marker}", TODAY)
        assert result.experience_years == pytest.approx(2.6, abs=0.05), marker


def test_future_period_is_dropped_and_end_is_clipped_to_today() -> None:
    future = parse_resume("Python-разработчик, Яндекс\n01.2030 — 12.2030", TODAY)
    assert future.experience_years == 0.0
    assert future.positions == []
    clipped = parse_resume("Python-разработчик, Яндекс\n01.2026 — 12.2030", TODAY)
    assert clipped.experience_years == pytest.approx(0.78, abs=0.02)  # Jan 2026 - Oct 10 2026


@pytest.mark.parametrize(
    ("period", "years"),
    [
        ("2019 — 2022", 3.0),
        ("2019-2022", 3.0),
        ("с 2019 по 2022", 3.0),
        ("2019 г. — 2022 г.", 3.0),
        ("2019г.-2022г.", 3.0),
        ("с 2019 года по 2022 год", 3.0),
        ("03.2020 – 06.2022", 28 / 12),
        ("март 2021 — июнь 2023", 28 / 12),
        ("Март 2021 – Июнь 2023", 28 / 12),
        ("01.03.2021 — 30.06.2023", 28 / 12),
        ("мар. 2021 — июн. 2023", 28 / 12),
        ("March 2021 - June 2023", 28 / 12),
    ],
)
def test_date_range_formats(period: str, years: float) -> None:
    result = parse_resume(f"Python-разработчик, Яндекс\n{period}", TODAY)
    assert result.experience_years == pytest.approx(years, abs=0.06), period


def test_overlapping_positions_are_glued_not_added() -> None:
    text = """Python-разработчик, A
01.2020 — 12.2021
Backend-разработчик, B
01.2021 — 12.2022
"""
    result = parse_resume(text, TODAY)
    assert result.experience_years == pytest.approx(3.0, abs=0.02)
    assert len(result.positions) == 2


def test_phrases_without_dates_are_not_experience() -> None:
    result = parse_resume("Опыт: 5 лет в Python, 3 года в Django. Работал в IT.", TODAY)
    assert result.experience_years == 0.0
    assert result.positions == []


def test_skill_level_depends_on_experience() -> None:
    low = parse_resume("Python-разработчик, Яндекс\n01.2026 — н.в.\nPython", TODAY)
    high = parse_resume("Python-разработчик, Яндекс\n01.2024 — н.в.\nPython", TODAY)
    assert _skills(low) == {"python": 1}
    assert _skills(high) == {"python": 2}


def test_positions_with_the_header_below_the_dates() -> None:
    text = """Опыт работы
03.2022 — 03.2024
Python-разработчик
Яндекс
Делал сервисы.

06.2020 — 03.2022
Стажёр-программист
Сбер
"""
    result = parse_resume(text, TODAY)
    assert [p.title for p in result.positions] == ["Python-разработчик", "Стажёр-программист"]
    assert [p.company for p in result.positions] == ["Яндекс", "Сбер"]
    # 06.2020 - 03.2022 and 03.2022 - 03.2024 are 22 + 25 months of 12: 3.9 years
    assert result.experience_years == pytest.approx(46 / 12, abs=0.05)


HH_LAYOUT = """Август 2021 — настоящее время
5 лет 2 месяца
ООО «Ромашка»
Москва, romashka.ru
Python-разработчик
Разрабатывал сервисы на Django...

Июнь 2019 — Июль 2021
2 года 2 месяца
ЗАО «Лютик»
Junior Python Developer
"""


def test_hh_ru_layout_date_company_place_title() -> None:
    result = parse_resume(HH_LAYOUT, TODAY)
    assert [p.title for p in result.positions] == ["Python-разработчик", "Junior Python Developer"]
    assert [p.company for p in result.positions] == ["ООО «Ромашка»", "ЗАО «Лютик»"]
    assert all(p.is_it for p in result.positions)
    # 06.2019 - 10.2026 on the test date: both positions count, nothing is lost
    assert result.experience_years == pytest.approx(7.36, abs=0.05)


def test_hh_ru_layout_with_two_place_lines() -> None:
    text = "Август 2021 — настоящее время\nООО «Ромашка»\nМосква\nromashka.ru\nPython-разработчик\n"
    result = parse_resume(text, TODAY)
    assert [p.title for p in result.positions] == ["Python-разработчик"]


def test_a_sentence_below_an_ordinary_header_is_not_a_job_title() -> None:
    sales = "Менеджер по продажам\nРазработка планов продаж\n"
    for text in (
        "Июнь 2019 — Июль 2021\nООО «Лютик»\nМосква\n" + sales,
        "Июнь 2019 — Июль 2021\n2 года 2 месяца\nООО «Лютик»\n" + sales,
    ):
        result = parse_resume(text, TODAY)
        assert result.experience_years == 0.0, text
        assert not any(p.is_it for p in result.positions), text


@pytest.mark.parametrize(
    "title",
    [
        # security
        "Security Engineer",
        "Application Security Engineer",
        "SOC-аналитик",
        "Инженер по безопасности приложений",
        "Инженер по информационной безопасности",
        "Исследователь безопасности",
        "Эксперт по кибербезопасности",
        "Специалист по защите информации",
        "Reverse engineer",
        "Пентестер",
        # analysts and data
        "Аналитик",
        "Системный аналитик",
        "Бизнес-аналитик",
        "Аналитик данных",
        "Data Analyst",
        "Инженер данных",
        "Data Engineer",
        # embedded and the rest
        "Embedded engineer",
        "Инженер-программист",
        "Системный инженер",
        "Инженер ПО",
        "Инженер по качеству ПО",
        "Инженер по автоматизации тестирования",
    ],
)
def test_it_roles_of_every_stack_count_as_experience(title: str) -> None:
    result = parse_resume(f"{title}, ООО «Тест»\n01.2020 — 12.2022\n", TODAY)
    assert [p.is_it for p in result.positions] == [True], title
    assert result.experience_years == pytest.approx(3.0, abs=0.02), title


@pytest.mark.parametrize(
    "title",
    [
        "Финансовый аналитик",
        "Маркетинговый аналитик",
        "Аналитик рынка",
        "Аналитик по продажам",
        "Менеджер по продажам",
        "Инженер по охране труда",
        "Инженер по технике безопасности",
        "Инженер по качеству продукции",
        "Бухгалтер",
        "Водитель",
    ],
)
def test_jobs_outside_it_do_not_count_as_experience(title: str) -> None:
    result = parse_resume(f"{title}, ООО «Тест»\n01.2020 — 12.2022\n", TODAY)
    assert [p.is_it for p in result.positions] == [False], title
    assert result.experience_years == 0.0, title


def test_lead_is_taken_from_a_dated_position_title_only() -> None:
    wish = parse_resume("Хочу стать тимлидом.\nPython-разработчик, Яндекс\n01.2020 — н.в.", TODAY)
    assert wish.is_lead is False
    for title in (
        "Тимлид",
        "Team Lead",
        "Руководитель команды разработки",
        "Руководитель группы разработки",
        "Руководитель группы, Python",
    ):
        result = parse_resume(f"{title}, Яндекс\n01.2020 — н.в.", TODAY)
        assert result.is_lead is True, title
    # a head of a non-IT group is not a lead of a development team
    sales = parse_resume("Руководитель группы продаж, Магнит\n01.2020 — н.в.", TODAY)
    assert sales.is_lead is False


# --- other fields --------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("line", "formats"),
    [
        ("Формат работы: удалённо", ["remote"]),
        ("Формат работы: офис или гибрид", ["office", "hybrid"]),
        ("Готов работать удалённо, в офисе, гибрид", ["remote", "office", "hybrid"]),
        ("Не готов работать в офисе", []),
        ("Работа без офиса. Удаленка", ["remote"]),
        ("Работа без офиса, только удаленка", []),  # "без" is within four words of both
        ("Предпочитаю remote", ["remote"]),
        ("Удалённо, гибрид", ["remote", "hybrid"]),
        ("Офис-менеджер, 2019", []),
    ],
)
def test_work_formats_with_negation(line: str, formats: list[str]) -> None:
    assert parse_resume(line, TODAY).work_formats == formats


@pytest.mark.parametrize(
    ("text", "city"),
    [
        ("Город: Казань", "Казань"),
        ("Проживаю в Нижнем Новгороде", "Нижний Новгород"),
        ("Локация: Санкт-Петербург", "Санкт-Петербург"),
        ("Алексей\nг. Екатеринбург", "Екатеринбург"),
        ("Алексей\nМосква, Россия", "Москва"),
        ("Алексей\nПроживание: Ростове-на-Дону", "Ростов-на-Дону"),
        ("Иванова Мария Андреевна\nPython-разработчик", None),
        ("Python-разработчик, Яндекс", None),
    ],
)
def test_city(text: str, city: str | None) -> None:
    assert parse_resume(text, TODAY).city == city


@pytest.mark.parametrize(
    ("line", "salary"),
    [
        ("Желаемая зарплата: от 120 000", 120000),
        ("Зарплатные ожидания: 150000 руб.", 150000),
        ("ЗП от 200 тыс.", 200000),
        ("Ожидания по зарплате — 180к", 180000),
        ("Зарплата: от 120 000 до 150 000 ₽", 120000),
        ("Зарплата: 120 000 - 150 000 ₽", None),
        ("Зарплата: до 150 000", None),
        ("Зарплата: от 3000 $", None),
        ("Зарплата: 2 000 EUR", None),
        ("Зарплата: 200 000 до вычета налогов", None),
        ("Зарплата: договорная", None),
        ("Зарплата: от 500", None),
    ],
)
def test_salary_expectation(line: str, salary: int | None) -> None:
    assert parse_resume(line, TODAY).salary_expectation == salary


def test_salary_on_the_next_line() -> None:
    assert parse_resume("Желаемая зарплата\nот 120 000 руб.", TODAY).salary_expectation == 120000


def test_empty_text_gives_an_empty_result() -> None:
    result = parse_resume("", TODAY)
    assert result.skills == []
    assert result.experience_years == 0.0
    assert result.facts == []
    assert result.city is None


def test_today_defaults_to_the_current_date() -> None:
    year = date.today().year
    result = parse_resume(f"Python-разработчик, Яндекс\n01.{year - 1} — н.в.")
    assert result.experience_years > 1.0


# --- extract_text --------------------------------------------------------------------------------
def test_extract_text_from_txt() -> None:
    assert extract_text("cv.txt", "Привет, мир".encode()) == "Привет, мир"
    assert extract_text("CV.TXT", "﻿Привет".encode()) == "Привет"


def test_extract_text_falls_back_to_cp1251() -> None:
    assert extract_text("cv.txt", "Резюме: Python".encode("cp1251")) == "Резюме: Python"


def test_empty_txt_is_rejected() -> None:
    for content in (b"", b"   \n\n  ", b"\x00\x00"):
        with pytest.raises(ResumeError) as caught:
            extract_text("cv.txt", content)
        assert caught.value.code == "RESUME_EMPTY"


@pytest.mark.parametrize("name", ["cv.docx", "cv.doc", "cv", "cv.txt.exe", "cv.rtf", ""])
def test_unsupported_extension(name: str) -> None:
    with pytest.raises(ResumeError) as caught:
        extract_text(name, b"text")
    assert caught.value.code == "UNSUPPORTED_FILE"
    assert caught.value.message


def _pdf_with_text(text: str) -> bytes:
    """A minimal one-page PDF whose page shows `text` in Helvetica."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref_at = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1))
    out.write(b"startxref\n%d\n%%%%EOF\n" % xref_at)
    return out.getvalue()


def _blank_pdf(pages: int, password: str | None = None) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    if password:
        writer.encrypt(password, algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_extract_text_from_pdf() -> None:
    text = extract_text("cv.pdf", _pdf_with_text("Python developer"))
    assert "Python developer" in text


def test_pdf_without_text_is_empty() -> None:
    with pytest.raises(ResumeError) as caught:
        extract_text("cv.pdf", _blank_pdf(1))
    assert caught.value.code == "RESUME_EMPTY"


def test_pdf_up_to_20_pages_is_read_and_longer_is_refused() -> None:
    with pytest.raises(ResumeError) as caught:
        extract_text("cv.pdf", _blank_pdf(21))
    assert caught.value.code == "UNSUPPORTED_FILE"
    with pytest.raises(ResumeError) as empty:  # 20 pages are read; there is just no text
        extract_text("cv.pdf", _blank_pdf(20))
    assert empty.value.code == "RESUME_EMPTY"


def test_encrypted_pdf_is_refused() -> None:
    with pytest.raises(ResumeError) as caught:
        extract_text("cv.pdf", _blank_pdf(1, password="secret"))
    assert caught.value.code == "UNSUPPORTED_FILE"


def test_unreadable_pdf_is_refused() -> None:
    for content in (b"this is not a pdf", b"", b"%PDF-1.4\ngarbage"):
        with pytest.raises(ResumeError) as caught:
            extract_text("cv.pdf", content)
        assert caught.value.code == "UNSUPPORTED_FILE"


def test_resume_error_carries_code_and_message() -> None:
    error = ResumeError("RESUME_EMPTY", "пусто")
    assert error.code == "RESUME_EMPTY"
    assert error.message == "пусто"
    assert str(error) == "пусто"
    assert isinstance(error, Exception)
