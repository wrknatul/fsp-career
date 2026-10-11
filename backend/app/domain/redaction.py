"""Hiding contacts in free text and shortening a name for the employer's eyes.

Two layers: `redact_contacts` knows the *shape* of contacts (an e-mail, a phone, a link) and
needs no context; `scrub_personal` knows *whose* text it is and removes that person's own
full name, birth date, nickname, phone and e-mail wherever they were typed.
"""

from __future__ import annotations

import re
from datetime import date
from functools import lru_cache

HIDDEN = "[скрыто]"

_END_PUNCT = r".,;:!?"
_URL_BODY = rf"[^\s<>\"'«»)\]]*[^\s<>\"'«»)\]{_END_PUNCT}]"

_EMAIL = re.compile(r"[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,8}")
_URL = re.compile(rf"(?:https?://|www\.){_URL_BODY}", re.IGNORECASE)
_SOCIAL = re.compile(
    r"(?<![\w@.])(?:[\w-]{1,63}\.)?"
    r"(?:vk\.com|vk\.ru|t\.me|telegram\.me|telegram\.dog|wa\.me|instagram\.com|facebook\.com"
    r"|linkedin\.com|github\.com|gitlab\.com|ok\.ru|hh\.ru|behance\.net|habr\.com)"
    rf"(?:/{_URL_BODY})?",
    re.IGNORECASE,
)
_NICK = re.compile(r"(?<![\w.@/])@[A-Za-z0-9_]{3,32}\b")

# Digit groups joined by separators that phone numbers use: space, dot, hyphen, brackets.
# A hyphen with spaces around it ("120 000 - 150 000") is a range, not part of a number.
_SPACE = r"[ \t  ]"
_SEPARATOR = rf"(?:{_SPACE}?[()]{_SPACE}?|{_SPACE}|-|\.)"
_PHONE_RUN = re.compile(rf"(?<!\w)\+?\(?\d+(?:{_SEPARATOR}\d+)*")
_YEAR_GROUP = re.compile(r"(?:19|20)\d{2}")
# A sum of money as people write it: "120 000" (groups of three) or "120000" (five to seven digits).
_AMOUNT = re.compile(rf"\d{{1,3}}(?:{_SPACE}\d{{3}})+|\d{{5,7}}")
_MIN_PHONE_DIGITS = 10


def _hide_phone(match: re.Match[str]) -> str:
    raw = match.group(0)
    if sum(ch.isdigit() for ch in raw) < _MIN_PHONE_DIGITS:
        return raw
    groups = re.findall(r"\d+", raw)
    # "03.2020-09.2021" and "2019 2020 2021" are periods, not phones.
    if sum(1 for g in groups if _YEAR_GROUP.fullmatch(g)) >= 2:
        return raw
    # "120000-150000" and "100 000-150 000" are salary ranges: two sums joined by one hyphen.
    halves = raw.split("-")
    if len(halves) == 2 and all(_AMOUNT.fullmatch(half) for half in halves):
        return raw
    return HIDDEN


def redact_contacts(text: str | None) -> str | None:
    """Replace e-mails, phones, @nicknames and links with `[скрыто]`."""
    if text is None:
        return None
    result = _EMAIL.sub(HIDDEN, text)
    result = _URL.sub(HIDDEN, result)
    result = _SOCIAL.sub(HIDDEN, result)
    result = _PHONE_RUN.sub(_hide_phone, result)
    return _NICK.sub(HIDDEN, result)


# --- the person's own data ---------------------------------------------------------------------

_MONTHS_GENITIVE = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)  # fmt: skip
_DATE_SEP = r"[\s./\-]{1,3}"
_PHONE_SEP = r"[\s().\-]*"
_NAME_VOWEL_ENDINGS = "аеиоуыэюяйь"
_NAME_ENDING_MAX = 2  # "Смирнов" -> "Смирновым", "Алексей" -> "Алексеем"
_NAME_INFLECT_MIN = 4  # a shorter word ("Ян", "Лев") is matched as it is, not by its stem
_MIN_HANDLE = 3
_MIN_PHONE_DIGITS_OWN = 6


def _name_word_pattern(word: str) -> str:
    """One word of a name as a pattern: any case, "ё" = "е", and the usual Russian endings."""
    lowered = word.lower()
    inflected = len(lowered) >= _NAME_INFLECT_MIN
    stem = lowered[:-1] if inflected and lowered[-1] in _NAME_VOWEL_ENDINGS else lowered
    body = "".join("[её]" if ch in "её" else re.escape(ch) for ch in stem)
    if inflected:
        body += rf"\w{{0,{_NAME_ENDING_MAX}}}"
    return body


def _name_pattern(full_name: str) -> re.Pattern[str] | None:
    words = [w for w in re.split(r"[\s.,]+", full_name) if len(w) >= 2]
    if not words:
        return None
    unit = rf"(?<!\w)(?:{'|'.join(dict.fromkeys(_name_word_pattern(w) for w in words))})(?!\w)"
    # A whole run of name words ("Смирнов Алексей Игоревич") becomes one mark.
    return re.compile(rf"{unit}(?:[ \t.,]{{1,3}}{unit})*", re.IGNORECASE)


def _birth_date_pattern(born: date) -> re.Pattern[str]:
    day, month, year = rf"0?{born.day}", rf"0?{born.month}", born.year
    forms = [
        rf"{year}{_DATE_SEP}{month}{_DATE_SEP}{day}",
        rf"{day}{_DATE_SEP}{month}{_DATE_SEP}{year}",
        rf"{day}[ \t]+{_MONTHS_GENITIVE[born.month - 1]}[ \t]+{year}",
        rf"{day}{_DATE_SEP}{month}{_DATE_SEP}{year % 100:02d}",
    ]
    return re.compile(rf"(?<!\d)(?:{'|'.join(forms)})(?!\d)", re.IGNORECASE)


def _phone_pattern(phone: str) -> re.Pattern[str] | None:
    digits = re.sub(r"\D", "", phone)
    if len(digits) < _MIN_PHONE_DIGITS_OWN:
        return None
    core = digits[-10:]  # without the country code: "+7", "8" or none
    prefix = rf"(?:\+?[78]{_PHONE_SEP})?" if len(digits) >= 10 else ""
    return re.compile(rf"(?<!\d){prefix}{_PHONE_SEP.join(core)}(?!\d)")


@lru_cache(maxsize=1024)
def _personal_patterns(
    full_name: str | None,
    birth_date: date | None,
    telegram: str | None,
    phone: str | None,
    email: str | None,
) -> tuple[re.Pattern[str], ...]:
    found: list[re.Pattern[str] | None] = []
    if birth_date is not None:
        found.append(_birth_date_pattern(birth_date))
    if phone:
        found.append(_phone_pattern(phone))
    if email and email.strip():
        found.append(re.compile(re.escape(email.strip()), re.IGNORECASE))
    handle = (telegram or "").strip().lstrip("@")
    if len(handle) >= _MIN_HANDLE:
        found.append(re.compile(rf"(?<![\w])@?{re.escape(handle)}(?!\w)", re.IGNORECASE))
    if full_name:
        found.append(_name_pattern(full_name))
    return tuple(pattern for pattern in found if pattern is not None)


def scrub_personal(
    text: str | None,
    *,
    full_name: str | None = None,
    birth_date: date | None = None,
    telegram: str | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> str | None:
    """Replace the person's own data in a free text with `[скрыто]`.

    * the full name, and each of its words alone (surname, name, patronymic) in any case,
      with "ё" = "е" and the usual endings ("Смирнова", "Алексеем");
    * the birth date as ISO, "14.05.2003", "14/05/03" or "14 мая 2003";
    * the telegram nickname with or without "@", the phone in any notation, the e-mail.

    Use it for texts the person typed or that were cut out of their documents, in addition to
    `redact_contacts`, which does not know whose text it is.
    """
    if text is None:
        return None
    for pattern in _personal_patterns(full_name, birth_date, telegram, phone, email):
        text = pattern.sub(HIDDEN, text)
    return text


def display_name(full_name: str) -> str:
    """"Смирнов Алексей Игоревич" -> "Алексей С."; one word stays as it is."""
    words = full_name.split()
    if not words:
        return ""
    if len(words) == 1:
        return words[0]
    surname, first_name = words[0], words[1]
    return f"{first_name} {surname[0].upper()}."
