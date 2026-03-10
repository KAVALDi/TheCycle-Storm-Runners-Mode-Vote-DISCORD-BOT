from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SimulateConfig:
    # Message update intervals for lobby and READY (seconds)
    lobby_step_seconds: float = 0.5
    ready_step_seconds: float = 0.5
    # READY auto-fill behavior
    auto_ramp_aggressiveness: float = 0.80
    # LOBBY: how many fake players to add per second during simulation
    lobby_add_min: int = 1
    lobby_add_max: int = 4
    lobby_add_random: bool = False


@dataclass
class SimulateConfigStore:
    path: Path

    def load(self) -> SimulateConfig:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except FileNotFoundError:
            return SimulateConfig()
        except Exception:
            return SimulateConfig()

        def f(key: str, default: float, *, clamp_01: bool = False) -> float:
            try:
                v = float(data.get(key, default))
                if clamp_01:
                    v = max(0.0, min(v, 1.0))
                return v if v > 0 else default
            except Exception:
                return default

        def g(key: str, default: int, lo: int = 1, hi: int = 5) -> int:
            try:
                v = int(data.get(key, default))
                return max(lo, min(hi, v))
            except Exception:
                return default

        def h(key: str, default: bool) -> bool:
            try:
                v = data.get(key, default)
                return bool(v) if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes")
            except Exception:
                return default

        add_min = g("lobby_add_min", 1)
        add_max = g("lobby_add_max", 4)
        return SimulateConfig(
            lobby_step_seconds=f("lobby_step_seconds", 0.5),
            ready_step_seconds=f("ready_step_seconds", 0.5),
            auto_ramp_aggressiveness=f("auto_ramp_aggressiveness", 0.80, clamp_01=True),
            lobby_add_min=add_min,
            lobby_add_max=max(add_max, add_min),
            lobby_add_random=h("lobby_add_random", False),
        )

    def save(self, config: SimulateConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")

