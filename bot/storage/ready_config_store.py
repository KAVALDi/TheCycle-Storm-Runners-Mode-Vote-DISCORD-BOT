from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from bot.domain.ready import ServerReadyConfig


@dataclass
class ReadyConfigStore:
    path: Path

    def load(self) -> ServerReadyConfig:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return ServerReadyConfig()
        except Exception:
            return ServerReadyConfig()

        return ServerReadyConfig(
            ready_window=int(data.get("ready_window", 90)),
            success_ttl=int(data.get("success_ttl", 600)),
            fail_ttl=int(data.get("fail_ttl", 15)),
        )

    def save(self, config: ServerReadyConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")

