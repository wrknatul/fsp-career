"""Reading a resume with rules only: no models, no network (SPEC section 6.2).

`extract_text` turns an uploaded `.txt` or `.pdf` into text; `parse_resume` finds skills,
IT experience, work formats, city, salary expectations and whether the person is a lead.
"""

from __future__ import annotations

import io
import re
from datetime import date
from functools import lru_cache
from typing import Any

from app.domain import scoring_config as cfg
from app.domain.facts import experience_fact, skill_fact
from app.domain.ontology import (
    AliasPattern,
    compile_aliases,
    find_skill_mentions,
    load_cities,
    norm_key,
    scan_mentions,
    skill_title,
)
from app.domain.redaction import HIDDEN, redact_contacts, scrub_personal
from app.domain.types import FactData, ParsedPosition, ParsedResume, ParsedSkill


class ResumeError(Exception):
    """A resume could not be read; `code` is the API error code, `message` is for people."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# --- text extraction -----------------------------------------------------------------------------
def _decode_txt(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return content.decode("cp1251")
    except UnicodeDecodeError as error:
        raise ResumeError("UNSUPPORTED_FILE", "Не удалось прочитать кодировку файла") from error


def _pdf_text(content: bytes) -> str:
    from pypdf import PdfReader  # imported here: only PDF uploads need it

    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise ResumeError("UNSUPPORTED_FILE", "PDF защищён паролем, загрузите другой файл")
        pages = reader.pages
        if len(pages) > cfg.MAX_PDF_PAGES:
            raise ResumeError(
                "UNSUPPORTED_FILE",
                f"В PDF больше {cfg.MAX_PDF_PAGES} страниц: загрузите краткую версию резюме",
            )
        return "\n".join(page.extract_text() or "" for page in pages)
    except ResumeError:
        raise
    except Exception as error:  # pypdf raises many unrelated types on damaged files
        raise ResumeError("UNSUPPORTED_FILE", "Не удалось прочитать PDF-файл") from error


def extract_text(filename: str, content: bytes) -> str:
    """Text of a `.txt` (UTF-8, then cp1251) or `.pdf` (pypdf, up to 20 pages) resume."""
    name = (filename or "").strip().lower()
    if name.endswith(".txt"):
        text = _decode_txt(content)
    elif name.endswith(".pdf"):
        text = _pdf_text(content)
    else:
        raise ResumeError("UNSUPPORTED_FILE", "Поддерживаются только файлы .txt и .pdf")
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ResumeError("RESUME_EMPTY", "В файле не нашлось текста резюме")
    return text


# --- dates ---------------------------------------------------------------------------------------
_MONTHS: dict[str, int] = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "май": 5, "мая": 5, "июн": 6,
    "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_MONTH_NAME = (
    r"(?:янв(?:арь|аря)?|фев(?:раль|раля)?|мар(?:т|та)?|апр(?:ель|еля)?|ма[йя]|июн[ья]?|июл[ья]?"
    r"|авг(?:уст|уста)?|сен(?:тябрь|тября|т)?|окт(?:ябрь|ября)?|ноя(?:брь|бря|б)?"
    r"|дек(?:абрь|абря)?|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?"
    r"|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_YEAR = r"(?:19|20)\d{2}"
_MONTH_NUM = r"(?:0?[1-9]|1[0-2])"
_ENDPOINT = (
    rf"(?:[0-3]?\d[./]{_MONTH_NUM}[./]{_YEAR}"  # 15.03.2021
    rf"|{_MONTH_NUM}[./]{_YEAR}"  # 03.2021
    rf"|{_MONTH_NAME}\.?[ \t ]*{_YEAR}"  # март 2021
    rf"|{_YEAR})"  # 2021
)
_NOW = (
    r"(?:н\.?[ \t]?в\.?|наст(?:оящее|оящ|\.)?[ \t]*(?:время|вр\.?)?"
    r"|сейчас|сегодня|now|present|current)"
)
_YEAR_WORD = r"(?:[ \t]*г(?:ода?|\.)?(?![а-яa-z]))?"  # "2019 г.", "2019г.", "2019 год(а)"
_RANGE = re.compile(
    rf"(?<![\d.\w])(?:с[ \t]+)?(?P<start>{_ENDPOINT}){_YEAR_WORD}[ \t]*"
    r"(?:[-–—−‑]+|\bпо\b|\bдо\b|\bto\b)[ \t]*(?:по[ \t]+)?"
    rf"(?:(?P<end>{_ENDPOINT}){_YEAR_WORD}(?!\d)|(?P<now>{_NOW})(?!\w))",
    re.IGNORECASE,
)
_ENDPOINT_PARTS = re.compile(
    rf"(?:[0-3]?\d[./])?(?P<num>{_MONTH_NUM})[./](?P<year1>{_YEAR})"
    rf"|(?P<name>[a-zа-я]+)\.?[ \t ]*(?P<year2>{_YEAR})"
    rf"|(?P<year3>{_YEAR})",
    re.IGNORECASE,
)


def _parse_endpoint(raw: str) -> tuple[int, int | None]:
    """(year, month); the month is None when only a year was written."""
    match = _ENDPOINT_PARTS.fullmatch(norm_key(raw).replace(" ", " "))
    if match is None:
        raise ValueError(f"not a date: {raw!r}")
    if match.group("num"):
        return int(match.group("year1")), int(match.group("num"))
    if match.group("name"):
        return int(match.group("year2")), _MONTHS[match.group("name")[:3]]
    return int(match.group("year3")), None


def _period_bounds(match: re.Match[str], today: date) -> tuple[date, date] | None:
    """Start and end (exclusive) of a period clipped to today, or None if it is unusable.

    A month counts whole, from its first day to the first day of the next one. A bare year
    is taken as the middle of that year, so "2019 — 2022" is three years and consecutive
    ranges ("2019 — 2022", "2022 — 2024") neither overlap nor leave a gap.
    """
    start_year, start_month = _parse_endpoint(match.group("start"))
    if match.group("now"):
        end_year, end_month = None, None
    else:
        end_year, end_month = _parse_endpoint(match.group("end"))

    if start_month is not None:
        start = date(start_year, start_month, 1)
    else:
        start = date(start_year, 7, 1)
        if start > today and start_year <= today.year:
            start = date(start_year, 1, 1)

    if end_year is None:
        end = today
    elif end_month is not None:
        end = date(end_year + 1, 1, 1) if end_month == 12 else date(end_year, end_month + 1, 1)
    else:
        end = date(end_year, 7, 1)
        if start_month is None and start_year == end_year:
            start = date(start_year, 1, 1)  # "2022 — 2022": half a year, the best guess

    end = min(end, today)
    if start >= end:
        return None
    return start, end


def _merged_days(periods: list[tuple[date, date]]) -> int:
    """Total days covered by the periods; overlapping ones are glued together."""
    total = 0
    current_start: date | None = None
    current_end: date | None = None
    for start, end in sorted(periods):
        if current_end is None or start > current_end:
            if current_start is not None and current_end is not None:
                total += (current_end - current_start).days
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_start is not None and current_end is not None:
        total += (current_end - current_start).days
    return total


# --- contacts: always cleared before a text is cut -----------------------------------------------
# Any fragment of a resume that leaves this module (a quote, a job title, a company) is cut
# from a line that has already passed `redact_contacts`. Cutting first would split an e-mail
# or a phone number in two, and the halves are no longer recognised as contacts.
@lru_cache(maxsize=4)
def _clear_line(line: str) -> str:
    return redact_contacts(line) or ""


def _trim_marker_edges(piece: str, *, cut_start: bool, cut_end: bool) -> str:
    """Remove half of a `[скрыто]` marker that a cut left at an edge of `piece`."""
    if cut_start:
        for size in range(len(HIDDEN) - 1, 0, -1):
            if piece.startswith(HIDDEN[-size:]):
                piece = piece[size:]
                break
    if cut_end:
        for size in range(len(HIDDEN) - 1, 0, -1):
            if piece.endswith(HIDDEN[:size]):
                piece = piece[:-size]
                break
    return piece


# --- sections and lines --------------------------------------------------------------------------
_EDU_HEADINGS = (
    r"образование|дополнительное\s+образование|обучение|курсы(?:\s+и\s+сертификаты)?|"
    r"повышение\s+квалификации|сертификаты|education|courses|training"
)
_EXP_HEADINGS = (
    r"опыт(?:\s+работы)?|места\s+работы|карьера|трудовая\s+деятельность|"
    r"work\s+experience|experience|employment"
)
_OTHER_HEADINGS = (
    r"навыки|ключевые\s+навыки|технологии|стек|о\s+себе|обо\s+мне|контакты|проекты|"
    r"личные\s+проекты|пет-проекты|достижения|языки|желаемая\s+должность|желаемая\s+зарплата|"
    r"интересы|хобби|рекомендации|дополнительная\s+информация|резюме|профиль|цель|"
    r"summary|skills|projects|about(?:\s+me)?|contacts|languages"
)
_DURATION_TAIL = r"(?:\s*[:\-—–]?\s*\d+\s*(?:год|года|лет|мес)\S*(?:\s+\d+\s*мес\S*)?)?"
_HEADING = re.compile(
    rf"^[\s#*\-•_]*(?:(?P<edu>{_EDU_HEADINGS})|(?P<exp>{_EXP_HEADINGS})|(?P<other>{_OTHER_HEADINGS}))"
    rf"\s*[:\-—–]?{_DURATION_TAIL}\s*$",
    re.IGNORECASE,
)
_INLINE_EDU = re.compile(rf"^[\s#*\-•_]*(?:{_EDU_HEADINGS})\s*[:\-—–]\s*\S", re.IGNORECASE)
_BULLET = re.compile(r"^\s*[-–—•*·▪●■◦►]\s+")
_DURATION = re.compile(r"\d+\s*(?:год|года|лет|мес\w*)(?:\s+\d+\s*мес\w*)?", re.IGNORECASE)


def _heading_kind(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return None
    match = _HEADING.match(stripped)
    if match is None:
        return None
    return "edu" if match.group("edu") else "exp" if match.group("exp") else "other"


def _is_candidate(line: str) -> bool:
    """Could this line be a job title or a company name?"""
    stripped = line.strip()
    if not stripped or len(stripped) > 90 or len(stripped.split()) > 12:
        return False
    if _BULLET.match(line) or _RANGE.search(stripped) or _heading_kind(stripped):
        return False
    return not (stripped.endswith(".") and len(stripped.split()) > 6)


def _plausible_company(line: str) -> bool:
    """Short, not a sentence, not a job title: could be the name of an employer."""
    stripped = line.strip()
    return (
        len(stripped) <= 60
        and len(stripped.split()) <= 6
        and not stripped.endswith((".", "!", "?", ":"))
        and _signal(stripped) < 2
    )


_HEADER_LOOKAHEAD = 2  # lines read past a two-line header that held no job title
_SITE_OR_COUNTRY = re.compile(r"\b[\w-]+\.(?:ru|su|com|org|net|io|dev)\b|россия|russia", re.I)


def _is_location_line(line: str) -> bool:
    """A city, a country or a site: the line that follows the employer in an hh.ru export."""
    return bool(_SITE_OR_COUNTRY.search(line)) or _first_city(line, strict=False) is not None


def _neighbour_lines(lines: list[str], index: int, step: int) -> list[str]:
    """The header of a position next to a bare date line, in document order.

    Walks from the date line above (step -1) or below (step 1) and takes header-like lines
    until it has met the job title (a line with a role word) or has two lines. A title
    that comes first may be followed by one more line, if that looks like a company name.
    When two lines held no title but one of them is a place or a site (hh.ru: company, then
    city or site, then the title), the lines below are read past further places until the line
    with a role word, and only that line is added.
    """
    found: list[str] = []
    skipped_blank = False
    j = index + step
    while 0 <= j < len(lines) and len(found) < 2:
        stripped = lines[j].strip()
        if not stripped:
            if found or skipped_blank:
                break
            skipped_blank = True
        elif _DURATION.fullmatch(stripped):
            pass  # "2 года 4 месяца" under a date range: not a header
        elif _is_candidate(lines[j]):
            if found and _signal(found[0]) == 2 and not _plausible_company(stripped):
                break  # the title is already found, and this is not an employer
            found.append(stripped)
        else:
            break
        j += step
    if (
        len(found) == 2
        and not any(_signal(line) == 2 for line in found)
        and any(_is_location_line(line) for line in found)
    ):
        # A job title usually follows a place or a site; a plain sentence below an ordinary
        # header ("Менеджер по продажам", "Разработка планов продаж") must not become a title.
        for reach in range(_HEADER_LOOKAHEAD):
            position = j + reach * step
            if not 0 <= position < len(lines) or not _is_candidate(lines[position]):
                break
            if _signal(lines[position]) == 2:
                found.append(lines[position].strip())
                break
            if not _is_location_line(lines[position]):
                break  # an ordinary line is not a title and not a place: stop reading
    return found[::-1] if step < 0 else found


# --- positions -----------------------------------------------------------------------------------
_ROLE_RE = re.compile(
    r"разработчик|разработк|программист|developer|programmer|software|devops"
    r"|девопс|\bsre\b|тестировщик|\bqa\b|\bsdet\b|инженер\w*\s+по\s+тестирован|backend"
    r"|frontend|fullstack|full[- ]stack|бэкенд|бекенд|фронтенд|фулстек"
    r"|data\s+(?:scientist|engineer|analyst)|аналитик\s+данных|системн\w+\s+аналитик"
    r"|бизнес[- ]аналитик|продуктов\w+\s+аналитик|bi[- ]аналитик|системн\w+\s+администратор"
    r"|сисадмин|sysadmin|\bdba\b|администратор\s+баз\s+данных|тимлид|тим[- ]лид|team[- ]?lead"
    r"|tech[- ]?lead|техлид|\bcto\b|верстальщик|machine\s+learning|машинн\w+\s+обучени"
    r"|\bml\b|solution\s+architect|software\s+architect|пентест"
    # security: information security engineers, SOC, application security, researchers
    r"|appsec|devsecops|\bsoc\b|\bsiem\b|пентестер|security\s+(?:engineer|analyst|researcher|specialist)"
    r"|кибер\w*безопасн|информационн\w+\s+безопасност|защит\w+\s+информаци"
    r"|безопасност\w*\s+(?:приложен|информаци|систем|данных|сет)"
    r"|исследовател\w+\s+(?:по\s+)?безопасност|reverse\s+engineer|реверс[- ]инженер"
    # embedded and robotics
    r"|embedded|встраиваем\w+\s+систем|firmware|прошивк"
    # analysts and data (any "аналитик" except the ones named in _NON_IT_ROLE_RE)
    r"|аналитик|\banalyst\b|инженер\w*\s+данных|bi[- ]?developer"
    # engineers by name
    r"|системн\w+\s+инженер|инженер[- ]программист|инженер\s+по$"
    r"|инженер\w*\s+по\s+качеств\w+\s+(?:по\b|программн|software|тестирован)"
)
# Analyst jobs outside IT; these phrases are cut out of a title before the role words are sought.
_NON_IT_ROLE_RE = re.compile(
    r"(?:финансов|маркетингов|кредитн|инвестиционн|рыночн|фондов|политическ|торгов|ценов)\w*"
    r"\s+аналитик\w*"
    r"|аналитик\w*\s+(?:по\s+)?(?:рынк|продаж|цен|закупк|кредит|финанс|маркетинг)\w*"
    r"|(?:financial|market|marketing|credit|investment|equity|sales|price|pricing)\s+analyst"
)
_WEAK_IT_RE = re.compile(r"\bit\b|\bит\b")
_EDU_WORD_RE = re.compile(
    r"университет|институт|колледж|лицей|гимназ|школ[аыу]|академи|бакалавр|магистр"
    r"|специалитет|аспирантур|курс[ыа]?\b|курсов|обучени|техникум|училищ|\bвуз\b|факультет"
)
_LEAD_RE = re.compile(
    r"тимлид|тим[- ]лид|team[- ]?lead|руководител\w+\s+(?:группы|команды|разработки)"
)
_SEGMENT_SPLIT = re.compile(r"\s+[—–-]\s+|\s*[|·•]\s*|\s*[;,]\s*|\s+в\s+(?=[A-ZА-ЯЁ«\"])")


def _split_segments(line: str) -> list[str]:
    """Pieces of a header line: "Python-разработчик, ООО «Вектор»" -> two segments."""
    protected = re.sub(
        r"\([^)]*\)",
        lambda m: m.group(0).replace(",", "\x00").replace(";", "\x01"),
        line,
    )
    segments: list[str] = []
    for part in _SEGMENT_SPLIT.split(protected):
        cleaned = re.sub(r"\(\s*\)", "", part.replace("\x00", ",").replace("\x01", ";"))
        cleaned = " ".join(cleaned.split()).strip(" -–—|·•:;,")
        if cleaned:
            segments.append(cleaned)
    return segments


def _signal(segment: str) -> int:
    """2 for a role word, 1 for a stack or a weak IT word, 0 for nothing IT-like."""
    normalized = norm_key(segment)
    if _ROLE_RE.search(_NON_IT_ROLE_RE.sub(" ", normalized)):
        return 2
    if _WEAK_IT_RE.search(normalized) or find_skill_mentions(segment, respect_negation=False):
        return 1
    return 0


class _Position:
    def __init__(
        self,
        title: str,
        company: str | None,
        period: str,
        start: date,
        end: date,
        is_it: bool,
        is_lead: bool,
    ) -> None:
        self.title = title
        self.company = company
        self.period = period
        self.start = start
        self.end = end
        self.is_it = is_it
        self.is_lead = is_lead

    @property
    def years(self) -> float:
        return round((self.end - self.start).days / cfg.DAYS_PER_YEAR, cfg.EXPERIENCE_DECIMALS)


def _detect_layout(lines: list[str], skip: set[int]) -> int:
    """-1 when the title stands above the dates, 1 when below (by the first bare date line)."""
    for index, line in enumerate(lines):
        if index in skip:
            continue
        match = _RANGE.search(line)
        if match is None:
            continue
        if sum(ch.isalpha() for ch in _around(line, match)) >= 3:
            continue
        return -1 if _neighbour_lines(lines, index, -1) else 1
    return 1


def _around(line: str, match: re.Match[str]) -> str:
    """The text next to a date range on its line, without the range itself.

    `line` must already be cleared of contacts. Whitespace is collapsed here, so a hostile
    line of many spaces stays cheap for the patterns that split the header into segments.
    """
    reach = cfg.RESUME_CONTEXT_CHARS
    before_start = max(0, match.start() - reach)
    after_end = match.end() + reach
    before = _trim_marker_edges(
        line[before_start : match.start()], cut_start=before_start > 0, cut_end=False
    )
    after = _trim_marker_edges(
        line[match.end() : after_end], cut_start=False, cut_end=after_end < len(line)
    )
    return " ".join(f"{before} {after}".split())


def _extract_positions(lines: list[str], skip: set[int], today: date) -> list[_Position]:
    """Positions of a resume. `lines` have been cleared of contacts, see `_clear_line`."""
    layout = _detect_layout(lines, skip)
    positions: list[_Position] = []
    seen: set[tuple[date, date, str]] = set()
    examined = 0
    for index, line in enumerate(lines):
        if index in skip:
            continue
        for match in _RANGE.finditer(line):
            examined += 1
            if examined > cfg.RESUME_MAX_RANGES or len(positions) >= cfg.RESUME_MAX_POSITIONS:
                return positions
            bounds = _period_bounds(match, today)
            if bounds is None:
                continue
            segments = _split_segments(_around(line, match))
            if not any(_signal(s) for s in segments):
                for neighbour in _neighbour_lines(lines, index, layout):
                    segments.extend(_split_segments(neighbour))
            position = _build_position(segments, " ".join(match.group(0).split()), bounds)
            if position is None:
                continue
            identity = (position.start, position.end, norm_key(position.title))
            if identity not in seen:
                seen.add(identity)
                positions.append(position)
    return positions


def _build_position(
    segments: list[str], period: str, bounds: tuple[date, date]
) -> _Position | None:
    if not segments:
        return None
    signals = [_signal(s) for s in segments]
    best = max(signals)
    if best < 2 and any(_EDU_WORD_RE.search(norm_key(s)) for s in segments):
        return None  # a study record, not a job
    title_index = signals.index(best) if best else 0
    title = segments[title_index]
    company = next((s for i, s in enumerate(segments) if i != title_index), None)
    is_lead = any(_LEAD_RE.search(norm_key(s)) for s in segments) and best > 0
    return _Position(title, company, period, bounds[0], bounds[1], best > 0, is_lead)


# --- other fields --------------------------------------------------------------------------------
_FORMAT_ALIASES: dict[str, list[str]] = {
    "remote": ["удалённо", "удалёнка", "дистанционно", "remote"],
    "office": ["офис", "офисе", "on-site", "onsite"],
    "hybrid": ["гибрид", "hybrid"],
}
_FORMAT_ORDER = ("remote", "office", "hybrid")
_FORMAT_CONTEXT = re.compile(
    r"формат|график|занятост|услови|готов|предпочита|желаем|рассматрива|работ|schedule|work",
    re.IGNORECASE,
)
_FORMAT_PATTERNS: dict[str, AliasPattern] = {
    key: pattern
    for key, aliases in _FORMAT_ALIASES.items()
    if (pattern := compile_aliases(aliases)) is not None
}


_FORMAT_PURE_LETTERS = 4  # letters that may stand next to the format words on a "pure" line
_HEADER_LINE_MAX_CHARS = 80


def _only_cities_left(rest: str) -> bool:
    """True for a header such as "Москва · удалённо": besides the format words only a city."""
    if len(rest) > _HEADER_LINE_MAX_CHARS:
        return False
    for loose, _prefixed, _exact in _CITY_PATTERNS.values():
        rest = loose.sub(" ", rest)
    return sum(ch.isalpha() for ch in rest) <= _FORMAT_PURE_LETTERS


def _work_formats(lines: list[str]) -> list[str]:
    found: set[str] = set()
    for line in lines:
        mentions = scan_mentions(line, _FORMAT_PATTERNS)
        if not mentions:
            continue
        masked = list(line)
        for mention in mentions:
            for i in range(mention.start, mention.end):
                masked[i] = " "
        pure = sum(ch.isalpha() for ch in masked) <= _FORMAT_PURE_LETTERS
        if pure or _FORMAT_CONTEXT.search(line) or _only_cities_left("".join(masked)):
            found.update(m.key for m in mentions)
    return [f for f in _FORMAT_ORDER if f in found]


_CITY_ALIASES: dict[str, list[str]] = {
    "Санкт-Петербург": ["спб", "питер", "петербург"],
    "Екатеринбург": ["екб"],
    "Ростов-на-Дону": ["ростов"],
}
_CITY_LABEL = re.compile(
    r"город|проживаю|проживание|локация|местоположение|регион|\bcity\b|location|адрес",
    re.IGNORECASE,
)
_CITY_HEAD_LINES = 12


def _city_pattern_body(name: str) -> str:
    """Stem form of a city name: every word loses its last vowel/soft sign and gets endings."""
    words = []
    for word in re.split(r"[\s-]+", norm_key(name)):
        if word.endswith(("ий", "ый", "ой")) and len(word) >= 5:
            stem = word[:-2]  # "нижний" -> "нижн": нижнего, нижнем
        elif len(word) >= 4 and word[-1] in "аеиоуыэюяьй":
            stem = word[:-1]
        else:
            stem = word
        suffix = cfg.STEM_SUFFIX_MAX if len(word) >= cfg.STEM_MIN_LENGTH else 2
        words.append(rf"{stem.replace('е', '[её]')}\w{{0,{suffix}}}")
    return r"[ \t -]+".join(words)


_CITY_PREPOSITION = r"(?:\bв|\bво|\bг\.?|\bгород|\bиз)[ \t]+"
# Applied to a line with collapsed whitespace: a pattern that begins with `\s*` or `\s+` is
# quadratic on a long run of spaces.
_CITY_SEGMENT_SPLIT = re.compile(r"[,;|/·•()]|\s[—–-]\s")


def _city_patterns() -> dict[str, tuple[re.Pattern[str], re.Pattern[str], frozenset[str]]]:
    """Per city: a pattern with endings, the same behind a preposition, and exact names."""
    patterns = {}
    for city in load_cities():
        aliases = _CITY_ALIASES.get(city, [])
        bodies = "|".join([_city_pattern_body(city), *(re.escape(a) for a in aliases)])
        loose = rf"(?<![\w-])(?:{bodies})(?![\w-])"
        exact = frozenset(norm_key(name) for name in (city, *aliases))
        patterns[city] = (
            re.compile(loose, re.IGNORECASE),
            re.compile(_CITY_PREPOSITION + loose, re.IGNORECASE),
            exact,
        )
    return patterns


_CITY_PATTERNS = _city_patterns()


def _first_city(line: str, *, strict: bool) -> str | None:
    """The city named in a line.

    Strict mode is for lines without a label ("Город:"): a surname such as "Иванова" must
    not become Иваново, so the city has to stand alone ("Москва, Россия") or follow a
    preposition ("живу в Казани").
    """
    best: tuple[int, str] | None = None
    segments = [norm_key(s) for s in _CITY_SEGMENT_SPLIT.split(" ".join(line.split()))]
    for city, (loose, prefixed, exact) in _CITY_PATTERNS.items():
        if not strict:
            match = loose.search(line)
        else:
            match = prefixed.search(line)
            if match is None and exact.intersection(segments):
                match = loose.search(line)
        if match and (best is None or match.start() < best[0]):
            best = (match.start(), city)
    return best[1] if best else None


def _city(lines: list[str]) -> str | None:
    """A city from a labelled line ("Город: Казань"), else from the head of the resume."""
    for line in lines:
        if _CITY_LABEL.search(line) and (city := _first_city(line, strict=False)):
            return city
    head = [line for line in lines if line.strip()][:_CITY_HEAD_LINES]
    for line in head:
        if city := _first_city(line, strict=True):
            return city
    return None


_SALARY_KEY = re.compile(
    r"зарплат|заработн|\bз/?п\b|оклад|доход|ожидани|вознагражд|salary|compensation",
    re.IGNORECASE,
)
_FOREIGN_CURRENCY = re.compile(
    r"[$€£]|usd|eur\b|долл|евро|тенге|kzt|byn|uah|грн|gbp|cny|юан", re.IGNORECASE
)
_GROSS = re.compile(r"до\s+вычета|gross|брутто|до\s+налог|before\s+tax", re.IGNORECASE)
_AMOUNT = re.compile(
    r"(?<![\d.,])(?:(?P<thousands>\d{2,3})[ \t]*(?:тыс\.?|тысяч\w*|т\.[ \t]?р\.?|к|k)(?![a-zа-я])"
    r"|(?P<full>\d{1,3}(?:[ \t  ]\d{3})+|\d{4,8}))(?![\d])",
    re.IGNORECASE,
)


def _salary_in(segment: str) -> int | None:
    """The expectation in one text segment; None at any ambiguity."""
    if _FOREIGN_CURRENCY.search(segment) or _GROSS.search(segment):
        return None
    amounts: list[tuple[int, int]] = []
    for match in _AMOUNT.finditer(segment):
        if match.group("thousands"):
            value = int(match.group("thousands")) * 1000
        else:
            value = int(re.sub(r"\D", "", match.group("full")))
        amounts.append((match.start(), value))
    if not amounts:
        return None
    first_start, first_value = amounts[0]
    before = norm_key(segment[:first_start]).rstrip()
    if before.endswith("до"):
        return None  # only an upper bound
    if len(amounts) > 1 and not before.endswith("от"):
        return None  # a range without "от"
    if not cfg.SALARY_MIN <= first_value <= cfg.SALARY_MAX:
        return None
    return first_value


def _salary(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if not _SALARY_KEY.search(line):
            continue
        segment = line
        if not re.search(r"\d", segment):
            following = lines[index + 1] if index + 1 < len(lines) else ""
            if not following.strip() or _heading_kind(following) or len(following) > 80:
                continue
            segment = following
        return _salary_in(segment)
    return None


# --- evidence quotes -----------------------------------------------------------------------------
_ELLIPSIS = "…"
_WHITESPACE = re.compile(r"\s")


def _last_space(text: str, low: int, high: int) -> int:
    """Index of the last whitespace in text[low:high], -1 if there is none."""
    return max((m.start() for m in _WHITESPACE.finditer(text, low, high)), default=-1)


def _window(cleared: str, first: int, last: int) -> str:
    """At most `EVIDENCE_MAX_CHARS` characters around `cleared[first:last]`.

    The cut falls between words and a cut edge gets an ellipsis; only a word longer than the
    window is cut in the middle (and then a half of a `[скрыто]` mark is removed).
    """
    room = cfg.EVIDENCE_MAX_CHARS - 2 * len(_ELLIPSIS)  # the worst case: a mark on both sides
    start = max(0, first - room // 2)
    end = min(len(cleared), start + room)

    hard_start = hard_end = False
    if start > 0 and not cleared[start - 1].isspace() and not cleared[start].isspace():
        space = _WHITESPACE.search(cleared, start, first)
        if space is None:
            hard_start = True
        else:
            start = space.end()
    if end < len(cleared) and not cleared[end - 1].isspace() and not cleared[end].isspace():
        space_at = _last_space(cleared, last, end)
        if space_at == -1:
            hard_end = True
        else:
            end = space_at

    piece = _trim_marker_edges(cleared[start:end], cut_start=hard_start, cut_end=hard_end)
    piece = " ".join(piece.split()).strip(" -–—•*·▪●■◦►")
    if not piece:
        return ""
    return (_ELLIPSIS if start > 0 else "") + piece + (_ELLIPSIS if end < len(cleared) else "")


def _quote(text: str, start: int, end: int, full_name: str | None = None) -> str | None:
    """The line around an occurrence, cleared of contacts and then shortened.

    The order matters (SPEC section 8): the window is cut from the cleared line, so an
    e-mail or a phone number at the edge of the window cannot be left as a fragment. The
    owner's full name (a resume often starts with "Смирнов Алексей Игоревич — Python-
    разработчик") is hidden too: the quote is shown to employers before an accepted offer.
    """
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line_end = len(text) if line_end == -1 else line_end
    line = text[line_start:line_end]
    cleared = scrub_personal(_clear_line(line), full_name=full_name) or ""
    if len(cleared) > cfg.EVIDENCE_MAX_CHARS:
        # Where the occurrence stands in the cleared line: contacts before it got shorter.
        before = scrub_personal(redact_contacts(line[: start - line_start]), full_name=full_name)
        first = min(len(before or ""), len(cleared))
        return _window(cleared, first, first + (end - start)) or None
    return " ".join(cleared.split()).strip(" -–—•*·▪●■◦►") or None


# --- entry point ---------------------------------------------------------------------------------
def parse_resume(
    text: str, today: date | None = None, *, full_name: str | None = None
) -> ParsedResume:
    """Parse resume text with rules. `today` makes the result reproducible in tests.

    `full_name` is the account owner's name: it is replaced with `[скрыто]` in the quotes
    (`evidence`) that employers see, so a first line such as "Смирнов Алексей Игоревич —
    Python-разработчик" cannot carry it out.
    """
    today = today or date.today()
    text = (text or "").replace(" ", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    # Lines that belong to study sections never count as experience.
    skip: set[int] = set()
    in_education = False
    for index, line in enumerate(lines):
        kind = _heading_kind(line)
        if kind is not None:
            in_education = kind == "edu"
            skip.add(index)
        elif in_education or _INLINE_EDU.match(line):
            skip.add(index)

    # Positions are read from lines without contacts, so no title or company can carry one.
    positions = _extract_positions([_clear_line(line) for line in lines], skip, today)
    it_positions = [p for p in positions if p.is_it]
    days = _merged_days([(p.start, p.end) for p in it_positions])
    years = round(days / cfg.DAYS_PER_YEAR, cfg.EXPERIENCE_DECIMALS)
    is_lead = any(p.is_lead for p in it_positions)

    skill_level = 2 if years >= cfg.RESUME_SKILL_LEVEL2_MIN_YEARS else 1
    skills: list[ParsedSkill] = []
    facts: list[FactData] = []
    seen_skills: set[str] = set()
    for mention in find_skill_mentions(text):
        if mention.key in seen_skills:
            continue
        seen_skills.add(mention.key)
        skills.append(
            ParsedSkill(
                skill=mention.key,
                title=skill_title(mention.key),
                level=skill_level,  # type: ignore[arg-type]
            )
        )
        facts.append(
            skill_fact(
                mention.key,
                skill_level,
                "resume",
                evidence=_quote(text, mention.start, mention.end, full_name),
            )
        )

    def hide(piece: str | None) -> str | None:
        return scrub_personal(redact_contacts(piece), full_name=full_name)

    parsed_positions = [
        ParsedPosition(
            title=hide(p.title) or "",
            company=hide(p.company),
            period=hide(p.period) or "",
            years=p.years,
            is_it=p.is_it,
        )
        for p in positions
    ]
    if years > 0:
        value_positions: list[dict[str, Any]] = [
            {"title": p.title, "company": p.company, "period": p.period, "years": p.years}
            for p in parsed_positions
            if p.is_it
        ]
        longest = max(it_positions, key=lambda p: p.years)
        facts.append(
            experience_fact(
                years,
                value_positions,
                evidence=hide(f"{longest.title}, {longest.period}"),
            )
        )
    if is_lead:
        lead = next(p for p in it_positions if p.is_lead)
        facts.append(
            FactData(
                kind="role",
                key="resume_lead",
                title="Тимлид (по резюме)",
                value={"reason": "В резюме указана должность руководителя группы или тимлида"},
                source="resume",
                verification="parsed",
                evidence=hide(f"{lead.title}, {lead.period}"),
            )
        )

    return ParsedResume(
        skills=skills,
        experience_years=years,
        positions=parsed_positions,
        work_formats=_work_formats(lines),  # type: ignore[arg-type]
        city=_city(lines),
        salary_expectation=_salary(lines),
        is_lead=is_lead,
        facts=facts,
    )
