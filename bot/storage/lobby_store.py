from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from bot.storage.json_store import load_json, save_json

log = logging.getLogger(__name__)


@dataclass
class LobbyStateStore:
    path: Path

    def load(self) -> Dict[str, Any]:
        return load_json(self.path)

    def save(self, data: Dict[str, Any]) -> None:
        save_json(self.path, data)

