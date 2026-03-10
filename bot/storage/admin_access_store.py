from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, TypedDict


class _GuildAccessConfig(TypedDict, total=False):
    # command_name -> [role_ids...]
    lobby: List[int]
    simulate_mode: List[int]
    ready_config: List[int]
    simulate_settings: List[int]
    role_access: List[int]


@dataclass
class AdminAccessStore:
    path: Path

    def _load(self) -> Dict[str, Dict[str, List[int]]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except FileNotFoundError:
            return {}
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}

    def _save(self, data: Dict[str, Dict[str, List[int]]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_roles(self, guild_id: int, command: str) -> List[int]:
        data = self._load()
        guild_key = str(guild_id)
        guild_cfg = data.get(guild_key, {})
        role_ids = guild_cfg.get(command, [])
        if not isinstance(role_ids, list):
            return []
        out: List[int] = []
        for rid in role_ids:
            try:
                out.append(int(rid))
            except Exception:
                continue
        return out

    def set_roles(self, guild_id: int, command: str, role_ids: List[int]) -> None:
        data = self._load()
        guild_key = str(guild_id)
        guild_cfg = data.get(guild_key)
        if not isinstance(guild_cfg, dict):
            guild_cfg = {}
            data[guild_key] = guild_cfg
        guild_cfg[command] = [int(rid) for rid in role_ids]
        self._save(data)

    def get_all_for_guild(self, guild_id: int) -> Dict[str, List[int]]:
        data = self._load()
        guild_cfg = data.get(str(guild_id), {})
        if not isinstance(guild_cfg, dict):
            return {}
        out: Dict[str, List[int]] = {}
        for cmd, role_ids in guild_cfg.items():
            if not isinstance(role_ids, list):
                continue
            cleaned: List[int] = []
            for rid in role_ids:
                try:
                    cleaned.append(int(rid))
                except Exception:
                    continue
            out[cmd] = cleaned
        return out

