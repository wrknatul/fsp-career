"""Resume: upload and rule-based parsing, removal and the demo text (SPEC section 6.2)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import AppSettings, CurrentCandidate, DbSession
from app.core.errors import AppError, error_responses, field_validation_error
from app.core.timeutil import utcnow
from app.domain import resume_parser
from app.domain.resume_parser import ResumeError
from app.domain.types import ParsedResume
from app.models import Candidate
from app.schemas.candidate import CandidateProfile
from app.schemas.resume import ResumeDemo, ResumeExtracted, ResumeParseResult
from app.services.profile import (
    build_profile,
    commit_profile,
    recompute_candidate,
    replace_facts,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidate", tags=["Соискатель"])

MAX_TEXT_CHARS = 100_000
MAX_TEXT_LABEL = "100 000"
ALLOWED_EXTENSIONS = (".txt", ".pdf")
DEMO_RESUME_PATH = Path(__file__).resolve().parents[2] / "seed_data" / "demo_resume.txt"

# HTTP status of every code `ResumeError` can carry.
_RESUME_ERROR_STATUS = {
    "RESUME_EMPTY": 422,
    "UNSUPPORTED_FILE": 415,
    "FILE_TOO_LARGE": 413,
}


def _resume_error(error: ResumeError) -> AppError:
    return AppError(error.code, error.message, _RESUME_ERROR_STATUS.get(error.code, 422))


def _base_name(filename: str) -> str:
    """The file name without any directory part, cut to the column size."""
    return filename.replace("\\", "/").rsplit("/", 1)[-1].strip()[:255]


def _size_label(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):g} МБ"
    if size >= 1024:
        return f"{size / 1024:g} КБ"
    return f"{size} байт"


def _read_file(upload: UploadFile, max_bytes: int) -> tuple[str, str]:
    """Text and clean file name of an uploaded resume."""
    filename = _base_name(upload.filename or "")
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise AppError("UNSUPPORTED_FILE", "Поддерживаются только файлы .txt и .pdf", 415)
    # One byte over the limit is enough to know the file is too large.
    content = upload.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise AppError(
            "FILE_TOO_LARGE",
            f"Файл слишком большой: допустимо не больше {_size_label(max_bytes)}",
            413,
            {"max_bytes": max_bytes},
        )
    try:
        text = resume_parser.extract_text(filename, content)
    except ResumeError as error:
        raise _resume_error(error) from error
    if len(text) > MAX_TEXT_CHARS:
        # The rule parser slows down quickly on huge inputs: a file is held to the same
        # length as the `text` field, however small it is in bytes.
        raise AppError(
            "FILE_TOO_LARGE",
            f"В файле слишком много текста: допустимо не больше {MAX_TEXT_LABEL} символов",
            413,
            {"max_chars": MAX_TEXT_CHARS},
        )
    return text, filename


def _read_text(raw: str) -> str:
    text = raw.replace("\x00", "").strip()
    if not text:
        raise AppError("RESUME_EMPTY", "Текст резюме пуст", 422)
    if len(text) > MAX_TEXT_CHARS:
        raise field_validation_error(
            [(["body", "text"], f"Текст резюме не длиннее {MAX_TEXT_LABEL} символов")]
        )
    return text


def _fill_empty_prefs(candidate: Candidate, parsed: ParsedResume) -> list[str]:
    """Copy city, work formats and salary from the resume into empty fields only."""
    applied: list[str] = []
    if not candidate.city and parsed.city:
        candidate.city = parsed.city
        applied.append("city")
    if not candidate.work_formats and parsed.work_formats:
        candidate.work_formats = list(parsed.work_formats)
        applied.append("work_formats")
    if candidate.salary_expectation is None and parsed.salary_expectation is not None:
        candidate.salary_expectation = parsed.salary_expectation
        applied.append("salary_expectation")
    return applied


@router.post(
    "/resume",
    response_model=ResumeParseResult,
    summary="Загрузить резюме",
    description=(
        "Принимает резюме формой `multipart/form-data`: файл `.txt` или `.pdf` (поле `file`, "
        "до 2 МБ, PDF не длиннее 20 страниц, текста в файле не больше 100 000 символов) либо "
        "текст (поле `text`, до 100 000 символов); если присланы оба, берётся файл. "
        "Разбор только правилами, без внешних сервисов: "
        "навыки, ИТ-опыт, формат работы, город и зарплатные ожидания. Все факты «Из резюме» "
        "заменяются новыми. Пустые город, форматы работы и зарплатные ожидания анкеты "
        "заполняются из резюме (их имена — в `applied_prefs`), заполненные не перезаписываются. "
        "Контакты из резюме в факты не попадают."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
            409: "CONFLICT — профиль одновременно изменён другим запросом",
            413: "FILE_TOO_LARGE — файл больше допустимого размера или в нём больше "
            "100 000 символов текста",
            415: "UNSUPPORTED_FILE — не .txt/.pdf, PDF не читается или длиннее 20 страниц",
            422: "RESUME_EMPTY — нет ни файла, ни текста, либо текст пуст; "
            "VALIDATION_ERROR — текст длиннее 100 000 символов",
        }
    ),
)
def upload_resume(
    candidate: CurrentCandidate,
    db: DbSession,
    settings: AppSettings,
    file: Annotated[
        UploadFile | None, File(description="Файл резюме .txt или .pdf, до 2 МБ")
    ] = None,
    text: Annotated[
        str | None, Form(description="Текст резюме, до 100 000 символов")
    ] = None,
) -> ResumeParseResult:
    filename: str | None
    if file is not None and file.filename:
        resume_text, filename = _read_file(file, settings.MAX_UPLOAD_BYTES)
    elif text is not None:
        resume_text, filename = _read_text(text), None
    else:
        raise AppError("RESUME_EMPTY", "Загрузите файл резюме или вставьте его текст", 422)

    parsed = resume_parser.parse_resume(resume_text, full_name=candidate.user.full_name)

    replace_facts(db, candidate, "resume", parsed.facts)
    candidate.resume_text = resume_text
    candidate.resume_filename = filename
    candidate.resume_parsed_at = utcnow()
    applied = _fill_empty_prefs(candidate, parsed)
    recompute_candidate(db, candidate)
    commit_profile(db)

    return ResumeParseResult(
        extracted=ResumeExtracted(
            skills=parsed.skills,
            experience_years=parsed.experience_years,
            positions=parsed.positions,
            work_formats=parsed.work_formats,
            city=parsed.city,
            salary_expectation=parsed.salary_expectation,
            is_lead=parsed.is_lead,
        ),
        applied_prefs=applied,
        profile=build_profile(db, candidate),
    )


@router.delete(
    "/resume",
    response_model=CandidateProfile,
    summary="Удалить резюме",
    description=(
        "Стирает текст резюме и имя файла и удаляет все факты «Из резюме»; категория "
        "пересчитывается. Город, форматы работы и зарплатные ожидания, которые были "
        "заполнены из резюме, остаются в анкете."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
            409: "CONFLICT — профиль одновременно изменён другим запросом",
        }
    ),
)
def delete_resume(candidate: CurrentCandidate, db: DbSession) -> CandidateProfile:
    candidate.resume_text = None
    candidate.resume_filename = None
    candidate.resume_parsed_at = None
    replace_facts(db, candidate, "resume", [])
    recompute_candidate(db, candidate)
    commit_profile(db)
    return build_profile(db, candidate)


@router.get(
    "/resume/demo",
    response_model=ResumeDemo,
    summary="Пример резюме",
    description=(
        "Текст демо-резюме для кнопки «Подставить пример»: его можно отправить в "
        "`POST /candidate/resume` как поле `text`. Контакты в примере вымышленные."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для соискателей",
            404: "NOT_FOUND — файл примера отсутствует на сервере",
        }
    ),
)
def get_demo_resume(candidate: CurrentCandidate) -> ResumeDemo:
    try:
        return ResumeDemo(text=DEMO_RESUME_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Demo resume %s is not readable: %s", DEMO_RESUME_PATH, exc)
        raise AppError("NOT_FOUND", "Пример резюме недоступен", 404) from exc
