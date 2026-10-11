"""Hiding contacts and shortening names (SPEC sections 7.8 and 8)."""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.redaction import HIDDEN, display_name, redact_contacts, scrub_personal


@pytest.mark.parametrize(
    "contact",
    [
        "ivan.petrov+work@mail.ru",
        "ivan@sub.example.co.uk",
        "+7 (900) 123-45-67",
        "+7 900 000-00-17",
        "8 900 123 45 67",
        "89001234567",
        "8-800-555-35-35",
        "900-123-45-67",
        "+79001234567",
        "7 495 123 45 67",
        "+375 29 123-45-67",
        "1234567890",
        "@alexey_smirnov_demo",
        "t.me/alexey_smirnov",
        "https://t.me/alexey_smirnov",
        "http://example.com/resume?id=5",
        "https://vk.com/id12345",
        "vk.com/alexey",
        "www.example.org/me",
        "github.com/alexey",
    ],
)
def test_each_kind_of_contact_is_hidden(contact: str) -> None:
    assert redact_contacts(f"Контакты: {contact} — пишите") == f"Контакты: {HIDDEN} — пишите"


def test_several_contacts_in_one_text() -> None:
    text = "Почта a@b.ru, телефон +7 900 111-22-33, ник @dev_guy, сайт https://me.dev/cv."
    assert redact_contacts(text) == (
        f"Почта {HIDDEN}, телефон {HIDDEN}, ник {HIDDEN}, сайт {HIDDEN}."
    )


@pytest.mark.parametrize(
    "text",
    [
        "В 2021 году я начал карьеру",
        "Зарплата 120 000 рублей",
        "Ожидания: от 120 000 до 150 000",
        "Ожидания: 120 000 - 150 000 руб.",
        "03.2020 - 09.2021",
        "03.2020-09.2021",
        "2019 - 2022",
        "2019-2022",
        "2019 2020 2021 2022",
        "Python 3.12, FastAPI 0.115",
        "15.03.2021",
        "10 лет опыта, 25 человек в команде",
        # a range written without spaces around the hyphen is still a range of two sums
        "Ожидания: 120000-150000",
        "Ожидания: 100 000-150 000 руб.",
        "Зарплата 90 000-120 000",
        "Зарплата 50000-80000",
    ],
)
def test_years_salaries_and_periods_are_not_phones(text: str) -> None:
    assert redact_contacts(text) == text


@pytest.mark.parametrize(
    "phone",
    [
        "8 495 123-4567",
        "8 (495) 123-4567",
        "495 123-45-67",
        "8-900-123-45-67",
        "+7 900 123-4567",
    ],
)
def test_the_salary_range_rule_does_not_let_phones_through(phone: str) -> None:
    assert redact_contacts(f"тел. {phone}") == f"тел. {HIDDEN}"


def test_none_and_empty() -> None:
    assert redact_contacts(None) is None
    assert redact_contacts("") == ""


def test_text_without_contacts_is_untouched() -> None:
    text = "Разрабатывал сервисы на Python, FastAPI и PostgreSQL.\nУдалённо или гибрид."
    assert redact_contacts(text) == text


PERSON = {
    "full_name": "Смирнов Алексей Игоревич",
    "birth_date": date(2003, 5, 14),
    "telegram": "@alexey_smirnov_demo",
    "phone": "+7 900 000-00-17",
    "email": "alexey.smirnov@example.test",
}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Смирнов Алексей Игоревич — Python-разработчик", f"{HIDDEN} — Python-разработчик"),
        ("Меня зовут Алексей Смирнов.", f"Меня зовут {HIDDEN}."),
        ("смирнов АЛЕКСЕЙ игоревич", HIDDEN),
        ("Фамилия: Смирнова, отчество Игоревичу", f"Фамилия: {HIDDEN}, отчество {HIDDEN}"),
        ("С Алексеем всё хорошо", f"С {HIDDEN} всё хорошо"),
        ("Игоревич", HIDDEN),
        ("Смирнов", HIDDEN),
    ],
)
def test_the_full_name_and_its_parts_are_scrubbed(text: str, expected: str) -> None:
    assert scrub_personal(text, **PERSON) == expected


def test_e_and_yo_are_the_same_letter_in_a_name() -> None:
    assert scrub_personal("Королёва Анна", full_name="Королева Анна Игоревна") == HIDDEN
    assert scrub_personal("Королева Анна", full_name="Королёва Анна Игоревна") == HIDDEN


@pytest.mark.parametrize(
    "written",
    [
        "2003-05-14",
        "14.05.2003",
        "14/05/2003",
        "14-05-2003",
        "14.5.2003",
        "2003.05.14",
        "14 мая 2003",
        "14 Мая 2003",
        "14.05.03",
    ],
)
def test_the_birth_date_is_scrubbed_in_every_notation(written: str) -> None:
    assert scrub_personal(f"родился {written} в Казани", **PERSON) == f"родился {HIDDEN} в Казани"


@pytest.mark.parametrize(
    "written",
    [
        "+7 900 000-00-17",
        "8 (900) 000-00-17",
        "89000000017",
        "+79000000017",
        "900 000 00 17",
        "8-900-000-00-17",
    ],
)
def test_the_phone_is_scrubbed_in_every_notation(written: str) -> None:
    assert scrub_personal(f"звонить {written} вечером", **PERSON) == f"звонить {HIDDEN} вечером"


def test_the_nickname_with_and_without_at_and_the_email_are_scrubbed() -> None:
    text = (
        "ник alexey_smirnov_demo, телеграм @alexey_smirnov_demo, почта ALEXEY.SMIRNOV@example.test"
    )
    assert scrub_personal(text, **PERSON) == f"ник {HIDDEN}, телеграм {HIDDEN}, почта {HIDDEN}"


@pytest.mark.parametrize(
    "text",
    [
        "Python 3.12, FastAPI 0.115, зарплата 120 000 - 150 000",
        "03.2020 – 09.2021, 2003 год, 14.05.2004, 15.05.2003",
        "Смирновский район, Алексейка, Игоревка",
        "Разрабатываю сервисы на Python",
    ],
)
def test_texts_about_somebody_else_are_left_alone(text: str) -> None:
    assert scrub_personal(text, **PERSON) == text


def test_scrub_personal_without_data_changes_nothing() -> None:
    assert scrub_personal("Смирнов 14.05.2003") == "Смирнов 14.05.2003"
    assert scrub_personal(None, **PERSON) is None
    assert scrub_personal("", **PERSON) == ""
    assert scrub_personal("a b", full_name=" ", telegram="@", phone="12") == "a b"


def test_display_name() -> None:
    assert display_name("Смирнов Алексей Игоревич") == "Алексей С."
    assert display_name("Смирнов Алексей") == "Алексей С."
    assert display_name("Алексей") == "Алексей"
    assert display_name("  Ёлкина   Анна  Петровна ") == "Анна Ё."
    assert display_name("смирнов алексей") == "алексей С."
    assert display_name("") == ""
