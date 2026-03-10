from __future__ import annotations

from bot.domain.modes import ModeSpec
from bot.domain.ready import ServerReadyConfig
from bot.storage.simulate_config_store import SimulateConfig


def compute_ready_ramp(
    *,
    spec: ModeSpec,
    ready_cfg: ServerReadyConfig,
    simulate_cfg: SimulateConfig,
    is_simulated: bool,
) -> tuple[int, int, float]:
    """
    Compute (auto_ready, ramp_to, ramp_interval) for READY simulation.
    - For simulated matches: ramp_to = capacity-1 and interval depends on
      lobby_step_seconds, ready_window and auto_ramp_aggressiveness.
    - For real matches: ramp_to = 0 and uses ready_step_seconds.
    """
    auto_ready = 0
    ramp_to = (spec.capacity - 1) if is_simulated else 0

    if is_simulated and ramp_to > 0:
        # Try to smoothly fill to near-full within a portion of ready_window.
        k = max(0.0, min(simulate_cfg.auto_ramp_aggressiveness, 1.0))
        computed = max(0.05, (ready_cfg.ready_window / max(1, ramp_to)) * k)
        ramp_interval = min(float(simulate_cfg.lobby_step_seconds), computed)
    else:
        ramp_interval = float(simulate_cfg.ready_step_seconds)

    return auto_ready, ramp_to, ramp_interval

