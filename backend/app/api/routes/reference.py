from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AppSettings
from app.domain import ontology
from app.schemas.reference import Dictionaries

router = APIRouter(prefix="/reference", tags=["Справочники"])


@router.get(
    "/dictionaries",
    response_model=Dictionaries,
    summary="Справочники платформы",
    description=(
        "Стеки, грейды, роли в команде, форматы работы, источники и уровни подтверждения "
        "(с весами), дисциплины ФСП, уровни соревнований, спортивные разряды, онтология навыков "
        "(id, подпись, стеки) и список городов. Поле `fsp_registry_mode` показывает режим "
        "реестра ФСП: `mock` — данные смоделированы, `live` — рабочий реестр. "
        "Авторизация не нужна."
    ),
)
def get_dictionaries(settings: AppSettings) -> Dictionaries:
    return Dictionaries(
        **ontology.dictionaries(),
        fsp_registry_mode=settings.FSP_REGISTRY_MODE,
    )
