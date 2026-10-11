from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession
from app.core.config import APP_VERSION
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Служебные"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверка работоспособности",
    description=(
        "Всегда отвечает 200, пока жив процесс. Поле `database` показывает, отвечает ли база "
        "данных на `SELECT 1` (`ok` или `error`)."
    ),
)
def health(db: DbSession) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        logger.exception("Health check: database is not reachable")
        database = "error"
    return HealthResponse(status="ok", version=APP_VERSION, database=database)
