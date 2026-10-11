"""FSP registry adapter.

The only implementation in the MVP is `MockFspRegistry` (see `mock.py`); a real integration
would implement the same protocol (docs/FSP_INTEGRATION.md).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.errors import AppError


class FspRegistryClient(Protocol):
    def get_athlete(self, fsp_id: str) -> dict[str, Any] | None:
        """Full registry record (including `full_name`, `birth_date`, `city`), or None.

        The id is matched ignoring case and surrounding spaces. The caller owns the returned
        dict; internal fields (`birth_date`, `city`) must never be sent to a client as is.
        """
        ...


def short_name(full_name: str) -> str:
    """'Смирнов Алексей Игоревич' -> 'Смирнов А. И.'."""
    parts = full_name.split()
    if not parts:
        return ""
    surname, *rest = parts
    initials = " ".join(f"{part[0].upper()}." for part in rest[:2])
    return f"{surname} {initials}".strip()


@lru_cache
def get_registry() -> FspRegistryClient:
    """The configured registry client (also a FastAPI dependency)."""
    mode = get_settings().FSP_REGISTRY_MODE
    if mode == "mock":
        from app.fsp_registry.mock import MockFspRegistry

        return MockFspRegistry()
    raise AppError(
        "FSP_REGISTRY_UNAVAILABLE",
        "Подключение к реальному реестру ФСП в этой версии не реализовано",
        503,
    )
