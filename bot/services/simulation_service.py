from __future__ import annotations

import asyncio
import logging
import random

import discord

from bot.domain.modes import ModeSpec
from bot.matchmaking.matchmaker import Matchmaker
from bot.matchmaking.queue_manager import QueueManager
from bot.services.lobby_service import LobbyController
from bot.storage.simulate_config_store import SimulateConfigStore

log = logging.getLogger(__name__)


async def run_mode_simulation(
    *,
    qm: QueueManager,
    controller: LobbyController,
    matchmaker: Matchmaker,
    simulate_config_store: SimulateConfigStore,
    channel: discord.TextChannel,
    mode_key: str,
    spec: ModeSpec,
    fake_id_base: int,
) -> None:
    """Smoothly fill the given mode queue up to capacity (server-side only).
    Updates lobby every `lobby_step_seconds`; adds 1..N players per second (configurable, random or fixed)."""
    sim_cfg = simulate_config_store.load()
    qm.lock_mode(mode_key)
    log.info(
        "simulate_mode: start mode=%s channel_id=%s guild_id=%s",
        mode_key,
        getattr(channel, "id", None),
        getattr(channel.guild, "id", None) if getattr(channel, "guild", None) else None,
    )

    try:
        sizes = qm.sizes()
        current = sizes.get(mode_key, 0)
        capacity = spec.capacity
        log.info("simulate_mode: current size=%s capacity=%s", current, capacity)

        if current >= capacity:
            log.info("simulate_mode: queue already full, nothing to simulate")
            return

        i = 0
        while current < capacity:
            remaining = capacity - current
            if sim_cfg.lobby_add_random:
                add_this_second = random.randint(
                    sim_cfg.lobby_add_min,
                    min(sim_cfg.lobby_add_max, remaining),
                )
            else:
                add_this_second = min(sim_cfg.lobby_add_max, remaining)
            add_this_second = max(1, add_this_second)

            for _ in range(add_this_second):
                if current >= capacity:
                    break
                fake_id = fake_id_base + i
                ok, _ = qm.add(fake_id, mode_key)
                if ok:
                    current += 1
                i += 1
            await controller.refresh_all()
            if current < capacity:
                await asyncio.sleep(max(0.1, sim_cfg.lobby_step_seconds))

        log.info("simulate_mode: finished filling mode=%s to size=%s", mode_key, current)
        await controller.refresh_all()
    finally:
        qm.unlock_mode(mode_key)
        try:
            await matchmaker.tick()
        except Exception:
            pass

