"""Public face of the mock FSP registry (enabled by `FSP_MOCK_ROUTES_ENABLED`).

The router is attached in `create_app()` only when the flag is on; with the flag off the
path does not exist and the generic 404 `NOT_FOUND` answers.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path

from app.core.errors import AppError, error_responses
from app.fsp_registry.client import FspRegistryClient, get_registry, short_name
from app.schemas.fsp import FspAthletePublic

router = APIRouter(prefix="/fsp-mock", tags=["Мок реестра ФСП"])


def to_public(athlete: dict[str, Any]) -> FspAthletePublic:
    """Registry record -> public representation.

    `birth_date`, `city` and the full name are internal matching fields and are dropped.
    """
    return FspAthletePublic.model_validate(
        {
            "fsp_id": athlete["fsp_id"],
            "short_name": short_name(athlete["full_name"]),
            "region": athlete.get("region"),
            "ranks": athlete.get("ranks", []),
            "results": athlete.get("results", []),
        }
    )


@router.get(
    "/athletes/{fsp_id}",
    response_model=FspAthletePublic,
    summary="Спортсмен из реестра ФСП (мок)",
    description=(
        "Смоделированная запись реестра: разряды и результаты соревнований. Все данные "
        "вымышлены. Дата рождения и город спортсмена наружу не отдаются никогда; "
        "полное ФИО заменено на краткое («Смирнов А. И.»)."
    ),
    responses=error_responses(
        {
            404: "FSP_ATHLETE_NOT_FOUND — нет такого ФСП ID; "
            "NOT_FOUND — мок-маршруты выключены",
            422: "VALIDATION_ERROR — некорректный ФСП ID в адресе",
        }
    ),
)
def get_athlete(
    fsp_id: Annotated[str, Path(min_length=1, max_length=64, description="ФСП ID")],
    registry: Annotated[FspRegistryClient, Depends(get_registry)],
) -> FspAthletePublic:
    athlete = registry.get_athlete(fsp_id)
    if athlete is None:
        raise AppError("FSP_ATHLETE_NOT_FOUND", "Спортсмен с таким ФСП ID не найден", 404)
    return to_public(athlete)
