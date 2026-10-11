"""Unified error format (SPEC section 8) and the middleware that carries `trace_id`.

Every 4xx/5xx answer looks like
``{"success": false, "error_code": "...", "message": "по-русски", "trace_id": "...",
"details": {}}`` and carries the same id in the ``X-Trace-Id`` header.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_core import to_jsonable_python
from sqlalchemy.exc import DataError, IntegrityError
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

TRACE_HEADER = "X-Trace-Id"
INTERNAL_ERROR_MESSAGE = "Внутренняя ошибка сервера. Попробуйте позже."


class ApiError(BaseModel):
    """Error body, used for OpenAPI documentation of error responses."""

    success: Literal[False] = False
    error_code: str = Field(examples=["NOT_FOUND"])
    message: str = Field(examples=["Объект не найден"])
    trace_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class AppError(Exception):
    """Business error rendered in the unified format.

    ``details`` must be JSON-serializable (datetimes are converted to ISO strings).
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(f"{error_code}: {message}")
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.headers = headers


def unauthorized(message: str = "Требуется авторизация") -> AppError:
    return AppError(
        "UNAUTHORIZED",
        message,
        401,
        headers={"WWW-Authenticate": "Bearer"},
    )


def field_validation_error(errors: list[tuple[list[str | int], str]]) -> AppError:
    """A `VALIDATION_ERROR` shaped exactly like one produced by request validation.

    ``errors`` is a list of ``(loc, message)``, e.g. ``(["body", "company_name"], "...")``.
    """
    items = [_error_item(loc, message, "value_error") for loc, message in errors]
    return AppError(
        "VALIDATION_ERROR",
        _validation_message(items),
        422,
        {"errors": items},
    )


def error_responses(codes: dict[int, str]) -> dict[int | str, dict[str, Any]]:
    """Build the ``responses=`` argument of a route from ``{status: "CODE: when"}``."""
    return {
        status: {"model": ApiError, "description": description}
        for status, description in codes.items()
    }


def get_trace_id(request: Request) -> str:
    trace_id = getattr(request.state, "trace_id", None)
    return trace_id if isinstance(trace_id, str) else str(uuid.uuid4())


def error_response(
    trace_id: str,
    status_code: int,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = {
        "success": False,
        "error_code": error_code,
        "message": message,
        "trace_id": trace_id,
        "details": to_jsonable_python(details or {}, fallback=str),
    }
    response = JSONResponse(body, status_code=status_code, headers=headers)
    response.headers[TRACE_HEADER] = trace_id
    return response


# --- request validation ------------------------------------------------------------------

_REQUEST_PARTS = {"body", "query", "path", "header", "cookie"}


def _translate(error: dict[str, Any]) -> str:
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}
    message = str(error.get("msg", ""))
    match kind:
        case "missing":
            return "Обязательное поле"
        case "string_too_short":
            return f"Минимальная длина — {ctx.get('min_length')} симв."
        case "string_too_long":
            return f"Максимальная длина — {ctx.get('max_length')} симв."
        case "too_short":
            return f"Минимальное число элементов — {ctx.get('min_length')}"
        case "too_long":
            return f"Максимальное число элементов — {ctx.get('max_length')}"
        case "greater_than":
            return f"Значение должно быть больше {ctx.get('gt')}"
        case "greater_than_equal":
            return f"Значение должно быть не меньше {ctx.get('ge')}"
        case "less_than":
            return f"Значение должно быть меньше {ctx.get('lt')}"
        case "less_than_equal":
            return f"Значение должно быть не больше {ctx.get('le')}"
        case "literal_error" | "enum":
            return "Недопустимое значение"
        case "int_parsing" | "int_type" | "int_from_float" | "int_parsing_size":
            return "Ожидается целое число"
        case "float_parsing" | "float_type":
            return "Ожидается число"
        case "bool_parsing" | "bool_type":
            return "Ожидается значение true или false"
        case "string_type":
            return "Ожидается строка"
        case "list_type" | "set_type" | "tuple_type":
            return "Ожидается список"
        case "dict_type" | "model_type" | "model_attributes_type":
            return "Ожидается объект"
        case "date_parsing" | "date_type" | "date_from_datetime_parsing":
            return "Ожидается дата в формате ГГГГ-ММ-ДД"
        case "datetime_parsing" | "datetime_type":
            return "Ожидается дата и время в формате ISO 8601"
        case "json_invalid":
            return "Тело запроса не является корректным JSON"
        case "string_pattern_mismatch":
            return "Недопустимый формат значения"
        case "extra_forbidden":
            return "Лишнее поле"
        case "value_error":
            return message.removeprefix("Value error, ")
        case "assertion_error":
            return message.removeprefix("Assertion failed, ")
        case _:
            return message


def _error_item(loc: list[str | int], message: str, kind: str) -> dict[str, Any]:
    parts = loc[1:] if loc and loc[0] in _REQUEST_PARTS else loc
    return {
        "loc": loc,
        "field": ".".join(str(part) for part in parts),
        "message": message,
        "type": kind,
    }


def _validation_message(items: list[dict[str, Any]]) -> str:
    if not items:
        return "Некорректные данные запроса"
    first = items[0]
    if first["field"]:
        return f"Некорректные данные запроса: {first['field']} — {first['message']}"
    return f"Некорректные данные запроса: {first['message']}"


def _validation_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    # The offending `input` is intentionally not echoed back (it may be a password).
    items = []
    for error in exc.errors():
        kind = str(error.get("type", ""))
        loc = list(error["loc"])
        if kind == "json_invalid":
            # The JSON parser appends the character offset to `loc`; shown to a user as a
            # "field name" it is just a stray number.
            loc = [part for part in loc if not isinstance(part, int)]
        items.append(_error_item(loc, _translate(error), kind))
    return items


# --- handlers ----------------------------------------------------------------------------

_HTTP_STATUS_ERRORS: dict[int, tuple[str, str]] = {
    400: ("BAD_REQUEST", "Некорректный запрос"),
    401: ("UNAUTHORIZED", "Требуется авторизация"),
    403: ("FORBIDDEN", "Недостаточно прав для этого действия"),
    404: ("NOT_FOUND", "Объект не найден"),
    405: ("METHOD_NOT_ALLOWED", "Метод не поддерживается для этого адреса"),
    409: ("CONFLICT", "Конфликт с текущим состоянием данных"),
    413: ("PAYLOAD_TOO_LARGE", "Слишком большой запрос"),
    415: ("UNSUPPORTED_MEDIA_TYPE", "Неподдерживаемый тип данных"),
    422: ("VALIDATION_ERROR", "Некорректные данные запроса"),
    429: ("RATE_LIMITED", "Слишком много запросов"),
}


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(
        get_trace_id(request),
        exc.status_code,
        exc.error_code,
        exc.message,
        exc.details,
        exc.headers,
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    trace_id = get_trace_id(request)
    if exc.status_code >= 500:
        logger.error("HTTP %s trace_id=%s detail=%r", exc.status_code, trace_id, exc.detail)
        return error_response(
            trace_id, exc.status_code, "INTERNAL_ERROR", INTERNAL_ERROR_MESSAGE, None, exc.headers
        )
    code, message = _HTTP_STATUS_ERRORS.get(exc.status_code, ("HTTP_ERROR", "Ошибка запроса"))
    return error_response(trace_id, exc.status_code, code, message, None, exc.headers)


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    items = _validation_details(exc)
    return error_response(
        get_trace_id(request),
        422,
        "VALIDATION_ERROR",
        _validation_message(items),
        {"errors": items},
    )


async def integrity_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Safety net: a database integrity error must never surface as a 500."""
    trace_id = get_trace_id(request)
    logger.warning("Integrity error trace_id=%s path=%s: %s", trace_id, request.url.path, exc)
    return error_response(
        trace_id,
        409,
        "CONFLICT",
        "Операция конфликтует с уже сохранёнными данными",
    )


async def data_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Safety net: a value the database refuses to store is the client's mistake."""
    trace_id = get_trace_id(request)
    logger.warning("Data error trace_id=%s path=%s: %s", trace_id, request.url.path, exc)
    return error_response(
        trace_id,
        422,
        "VALIDATION_ERROR",
        "Некорректные данные запроса: значение не может быть сохранено",
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = get_trace_id(request)
    logger.error(
        "Unhandled error trace_id=%s %s %s",
        trace_id,
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return error_response(trace_id, 500, "INTERNAL_ERROR", INTERNAL_ERROR_MESSAGE)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(DataError, data_error_handler)
    # Served by Starlette's outermost middleware: no CORS headers. TraceMiddleware answers
    # first for everything raised inside the app; this one is the last line of defence.
    app.add_exception_handler(Exception, unhandled_exception_handler)


class TraceMiddleware:
    """Assigns `trace_id`, mirrors it into ``X-Trace-Id`` and turns crashes into 500 answers.

    It must stay *inside* CORSMiddleware: Starlette's own handler for ``Exception`` sits outside
    every middleware, so a 500 produced there would carry no CORS headers and the browser would
    report an opaque network error instead of the message.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trace_id = str(uuid.uuid4())
        scope.setdefault("state", {})["trace_id"] = trace_id
        response_started = False

        async def send_with_trace(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = MutableHeaders(scope=message)
                headers[TRACE_HEADER] = trace_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_trace)
        except Exception as exc:
            logger.error(
                "Unhandled error trace_id=%s %s %s",
                trace_id,
                scope.get("method"),
                scope.get("path"),
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            if response_started:
                raise
            response = error_response(trace_id, 500, "INTERNAL_ERROR", INTERNAL_ERROR_MESSAGE)
            await response(scope, receive, send_with_trace)
