"""Mock FSP registry backed by `data/registry.json` (fictional data)."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY_PATH = Path(__file__).parent / "data" / "registry.json"

# Typographic dashes people get when copying an id from a document or a chat.
_DASHES = re.compile("[‐‑‒–—−]")


def normalize_fsp_id(fsp_id: str) -> str:
    return _DASHES.sub("-", fsp_id).strip().upper()


class MockFspRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_REGISTRY_PATH
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"{self._path} is missing: run `python -m app.fsp_registry.generate` in backend/"
            ) from exc
        self._athletes: dict[str, dict[str, Any]] = {
            athlete["fsp_id"]: athlete for athlete in payload["athletes"]
        }

    def get_athlete(self, fsp_id: str) -> dict[str, Any] | None:
        athlete = self._athletes.get(normalize_fsp_id(fsp_id))
        return copy.deepcopy(athlete) if athlete is not None else None

    def athletes(self) -> list[dict[str, Any]]:
        """All records in registry order (copies), for the seed script."""
        return [copy.deepcopy(athlete) for athlete in self._athletes.values()]
