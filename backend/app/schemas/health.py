from __future__ import annotations

from typing import Literal

from app.schemas.base import ApiModel


class HealthResponse(ApiModel):
    status: Literal["ok"] = "ok"
    version: str
    database: Literal["ok", "error"]
