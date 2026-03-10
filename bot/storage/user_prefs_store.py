from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from bot.storage.json_store import load_json, save_json

log = logging.getLogger(__name__)


@dataclass
class UserPrefsStore:
    path: Path

    def _load(self) -> Dict[str, Dict]:
        data = load_json(self.path)
        return data if isinstance(data, dict) else {}

    def _save(self, data: Dict[str, Dict]) -> None:
        save_json(self.path, data)

    def set_panel_message(self, user_id: int, channel_id: int, message_id: int) -> None:
        data = self._load()
        key = str(user_id)
        user = data.get(key, {})
        user["panel"] = {"channel_id": channel_id, "message_id": message_id}
        data[key] = user
        self._save(data)

    def clear_panel_message(self, user_id: int) -> None:
        data = self._load()
        key = str(user_id)
        user = data.get(key)
        if not user:
            return
        user.pop("panel", None)
        data[key] = user
        self._save(data)

    def iter_panels(self) -> Dict[int, Dict[str, int]]:
        data = self._load()
        out: Dict[int, Dict[str, int]] = {}
        for uid_str, payload in data.items():
            panel = (payload or {}).get("panel")
            if not panel:
                continue
            try:
                uid = int(uid_str)
                cid = int(panel.get("channel_id"))
                mid = int(panel.get("message_id"))
            except Exception:
                continue
            out[uid] = {"channel_id": cid, "message_id": mid}
        return out

