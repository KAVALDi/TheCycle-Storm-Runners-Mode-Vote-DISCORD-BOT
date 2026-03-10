from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


UI_STYLE_EMOJI = "emoji"
UI_STYLE_SYMBOLS = "symbols"


@dataclass
class UIStyleStore:
    """
    Per-guild UI style storage.

    Data format (JSON):
    {
      "<guild_id>": "emoji" | "symbols",
      ...
    }
    """

    path: Path

    def _load(self) -> Dict[str, str]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except FileNotFoundError:
            return {}
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}

    def _save(self, data: Dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_style(self, guild_id: int) -> str:
        data = self._load()
        val = data.get(str(guild_id), UI_STYLE_SYMBOLS)
        return val if val in (UI_STYLE_EMOJI, UI_STYLE_SYMBOLS) else UI_STYLE_SYMBOLS

    def set_style(self, guild_id: int, style: str) -> None:
        if style not in (UI_STYLE_EMOJI, UI_STYLE_SYMBOLS):
            style = UI_STYLE_SYMBOLS
        data = self._load()
        data[str(guild_id)] = style
        self._save(data)

