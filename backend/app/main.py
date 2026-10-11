"""Application factory. Run with `uvicorn app.main:app` from `backend/`."""

from __future__ import annotations

import importlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from anyio import to_thread
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth,
    candidate_achievements,
    candidate_fsp,
    candidate_offers,
    candidate_profile,
    candidate_resume,
    candidate_tests,
    employer_offers,
    employer_profile,
    employer_search,
    fsp_mock,
    health,
    reference,
    vacancies,
)
from app.core.config import APP_VERSION, Settings, get_settings
from app.core.errors import TRACE_HEADER, TraceMiddleware, register_exception_handlers

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"

OPENAPI_TAGS = [
    {"name": "Служебные", "description": "Проверка работоспособности сервиса."},
    {"name": "Авторизация", "description": "Регистрация, вход и текущий пользователь."},
    {
        "name": "Соискатель",
        "description": (
            "Профиль соискателя: анкета, привязка ФСП ID, резюме, экспресс-тесты, "
            "достижения и входящие офферы. Только для роли `candidate`."
        ),
    },
    {
        "name": "Работодатель",
        "description": (
            "Матрица категорий, поиск кандидатов, карточки, вакансии и офферы. "
            "Только для роли `employer`."
        ),
    },
    {"name": "Справочники", "description": "Справочники платформы без авторизации."},
    {
        "name": "Мок реестра ФСП",
        "description": (
            "Смоделированный реестр ФСП: вымышленные данные в предлагаемом формате интеграции."
        ),
    },
]

API_DESCRIPTION = (
    "Платформа подбора ИТ-специалистов с обратной механикой: соискатели распределяются по "
    "категориям на основе подтверждаемого профиля, работодатель сам находит категорию и "
    "отправляет кандидату оффер с зарплатой.\n\n"
    "Ошибки приходят в едином формате: `success`, `error_code`, `message`, `trace_id`, "
    "`details`; `trace_id` дублируется в заголовке `X-Trace-Id`. "
    "Реестр ФСП в этой версии смоделирован, все его данные вымышлены."
)


def _seed_demo_data() -> None:
    """Fill an empty database with demo data, if the seed module exists (step 3)."""
    try:
        seed = importlib.import_module("app.seed")
    except ImportError as exc:
        if exc.name == "app.seed":
            logger.warning("SEED_DEMO_DATA is on, but app.seed does not exist yet: skipped")
        else:
            # The module exists but one of its own imports is broken: keep the traceback.
            logger.exception("SEED_DEMO_DATA is on, but importing app.seed failed: skipped")
        return
    seed.seed_if_empty()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    if settings.uses_default_jwt_secret:
        logger.warning(
            "JWT_SECRET is the built-in development value, a placeholder or shorter than 32 "
            "bytes: set your own secret (openssl rand -hex 32) before exposing this service"
        )
    if settings.SEED_DEMO_DATA:
        # Seeding hashes passwords and writes many rows: keep it off the event loop.
        await to_thread.run_sync(_seed_demo_data)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="ФСП.Карьера API",
        version=APP_VERSION,
        description=API_DESCRIPTION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        swagger_ui_oauth2_redirect_url=None,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Added first = innermost. TraceMiddleware must sit inside CORS so that even a 500 it
    # produces gets CORS headers.
    app.add_middleware(TraceMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[TRACE_HEADER],
    )
    register_exception_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    for module in (
        health,
        auth,
        candidate_profile,
        candidate_fsp,
        candidate_resume,
        candidate_tests,
        candidate_achievements,
        candidate_offers,
        employer_profile,
        vacancies,
        employer_search,
        employer_offers,
        reference,
    ):
        api.include_router(module.router)
    if settings.FSP_MOCK_ROUTES_ENABLED:
        api.include_router(fsp_mock.router)
    app.include_router(api)
    return app


app = create_app()
