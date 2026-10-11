from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentEmployer
from app.core.errors import error_responses
from app.schemas.employer import EmployerProfile

router = APIRouter(prefix="/employer", tags=["Работодатель"])


@router.get(
    "/profile",
    response_model=EmployerProfile,
    summary="Профиль работодателя",
    description=(
        "Данные компании текущего работодателя. Флаг `verified` ставит платформа, "
        "работодатель его изменить не может."
    ),
    responses=error_responses(
        {
            401: "UNAUTHORIZED — нет токена, он неверный или истёк",
            403: "FORBIDDEN — маршрут только для работодателей",
        }
    ),
)
def get_employer_profile(employer: CurrentEmployer) -> EmployerProfile:
    return EmployerProfile.model_validate(employer)
