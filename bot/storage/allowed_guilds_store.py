from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Set

import json
import logging


log = logging.getLogger(__name__)


@dataclass
class AllowedGuildsStore:
    path: Path

    def load(self) -> Set[int]:
        """
        Load allowed guild IDs from JSON.

        Expected format:
        {
          "allowed_guilds": [1349686180878225430, 1211384495589171280]
        }

        - If file is missing or empty / invalid, returns an empty set (no restriction).
        - Invalid entries (non-numeric) are ignored.
        """
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return set()
        except Exception:
            log.exception("failed to read allowed guilds file: %s", self.path)
            return set()

        if not raw.strip():
            return set()

        try:
            data = json.loads(raw)
        except Exception:
            log.exception("failed to parse allowed guilds json: %s", self.path)
            return set()

        items = data.get("allowed_guilds")
        if not isinstance(items, list):
            return set()

        out: Set[int] = set()
        for item in items:
            try:
                out.add(int(item))
            except Exception:
                continue
        return out

