from __future__ import annotations

import discord

import random

from bot.domain.modes import MODE_SPECS, ModeSpec
from bot.domain.ui_style import get_mode_icon
from bot.matchmaking.matchmaker import Matchmaker
from bot.services.simulation_strategy import compute_ready_ramp
from bot.storage.ready_config_store import ReadyConfigStore
from bot.storage.simulate_config_store import SimulateConfigStore
from bot.storage.ui_style_store import UIStyleStore, UI_STYLE_SYMBOLS, UI_STYLE_EMOJI
from bot.services.ready_flow import start_server_ready_flow


def make_handle_match_ready(
    *,
    bot: discord.Client,
    ready_config_store: ReadyConfigStore,
    simulate_config_store: SimulateConfigStore,
    ui_style_store: UIStyleStore,
    fake_id_base: int,
):
    async def handle_match_ready(channel: discord.abc.Messageable, spec: ModeSpec, players: list[int]) -> None:
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return

        cfg = ready_config_store.load()
        sim_cfg = simulate_config_store.load()

        is_simulated = any(uid >= fake_id_base for uid in players)
        auto_ready, ramp_to, ramp_interval = compute_ready_ramp(
            spec=spec,
            ready_cfg=cfg,
            simulate_cfg=sim_cfg,
            is_simulated=is_simulated,
        )

        # Determine UI style based on guild that owns the channel
        ui_style = UI_STYLE_SYMBOLS
        if isinstance(channel, (discord.TextChannel, discord.Thread)) and channel.guild is not None:
            ui_style = ui_style_store.get_style(channel.guild.id)

        # RANDOM behaves as a meta-mode: when a match is formed in RANDOM,
        # redirect READY to one of the concrete modes.
        display_spec = spec
        if spec.key == "random":
            candidate_keys = [
                "solo",
                "duo",
                "squad",
                "showdown",
                "king_of_the_zeal",
                "overdrive",
                "nightfall",
                "deathmatch",
            ]
            real_modes = [MODE_SPECS[k] for k in candidate_keys if k in MODE_SPECS]
            if real_modes:
                display_spec = random.choice(real_modes)

        ready_emoji = get_mode_icon(display_spec.key, ui_style, display_spec.emoji)

        await start_server_ready_flow(
            bot=bot,
            channel=channel,
            mode_title=display_spec.title_en,
            emoji=ready_emoji,
            capacity=spec.capacity,
            auto_ready=auto_ready,
            auto_ready_ramp_to=ramp_to,
            auto_ready_ramp_interval=ramp_interval,
            config=cfg,
            player_ids=players,
            ui_style=ui_style,
        )

    return handle_match_ready

