from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from bot.config import (
    ADMIN_ACCESS_JSON,
    DATA_DIR,
    FAKE_ID_BASE,
    LOBBY_JSON,
    READY_CONFIG_JSON,
    SIMULATE_CONFIG_JSON,
    UI_STYLE_JSON,
    USERS_JSON,
    find_secret_env,
    ALLOWED_GUILDS_JSON,
)
from bot.domain.modes import MODE_SPECS, ModeSpec
from bot.matchmaking.matchmaker import Matchmaker
from bot.matchmaking.queue_manager import QueueManager
from bot.services.lobby_service import LobbyController
from bot.storage.user_prefs_store import UserPrefsStore
from bot.storage.lobby_store import LobbyStateStore
from bot.discord_ui.lobby_view import LobbyLayoutView
from bot.storage.ready_config_store import ReadyConfigStore
from bot.storage.simulate_config_store import SimulateConfigStore
from bot.storage.admin_access_store import AdminAccessStore
from bot.storage.ui_style_store import UIStyleStore
from bot.storage.allowed_guilds_store import AllowedGuildsStore
from bot.app.commands import register_commands
from bot.services.match_ready_service import make_handle_match_ready


log = logging.getLogger("bot")


def make_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    return bot


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    setup_logging()
    secret_path = find_secret_env()
    load_dotenv(dotenv_path=secret_path)

    # Support both historical DISCORD_TOKEN and README-documented DISCORD_BOT_TOKEN.
    token = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit(
            f"Discord token is missing. Expected DISCORD_TOKEN or DISCORD_BOT_TOKEN in {secret_path}"
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    bot = make_bot()

    # Allowed guilds restriction (optional)
    allowed_store = AllowedGuildsStore(path=ALLOWED_GUILDS_JSON)
    allowed_guilds = allowed_store.load()

    def is_guild_allowed(gid: int | None) -> bool:
        if gid is None:
            return False
        if not allowed_guilds:
            return True
        return int(gid) in allowed_guilds
    qm = QueueManager(modes=list(MODE_SPECS.keys()))
    lobby_store = LobbyStateStore(path=LOBBY_JSON)
    users_store = UserPrefsStore(path=USERS_JSON)
    ready_config_store = ReadyConfigStore(path=READY_CONFIG_JSON)
    simulate_config_store = SimulateConfigStore(path=SIMULATE_CONFIG_JSON)
    admin_access_store = AdminAccessStore(path=ADMIN_ACCESS_JSON)
    ui_style_store = UIStyleStore(path=UI_STYLE_JSON)
    controller = LobbyController(bot, qm, lobby_store, users_store, ui_style_store)

    handle_match_ready = make_handle_match_ready(
        bot=bot,
        ready_config_store=ready_config_store,
        simulate_config_store=simulate_config_store,
        ui_style_store=ui_style_store,
        fake_id_base=FAKE_ID_BASE,
    )

    matchmaker = Matchmaker(
        bot=bot,
        queue_manager=qm,
        mode_specs=MODE_SPECS,
        lobby_channel_id_provider=controller.get_channel_id,
        lobby_locale_provider=controller.get_locale,
        on_queue_changed=controller.request_refresh,
        on_match_ready=handle_match_ready,
        interval_seconds=5.0,
    )

    @bot.event
    async def on_ready():
        # Enforce allowed guilds: leave any disallowed servers on startup.
        if allowed_guilds:
            for g in list(bot.guilds):
                if not is_guild_allowed(g.id):
                    log.warning("Leaving disallowed guild on startup: id=%s name=%s", g.id, g.name)
                    try:
                        await g.leave()
                    except Exception:
                        log.exception("failed to leave disallowed guild id=%s", g.id)

        bot.add_view(controller.build_view())
        matchmaker.start()
        controller.request_refresh()
        try:
            await bot.tree.sync()
        except Exception:
            log.exception("failed to sync app commands")
        log.info("Logged in as %s", bot.user)

    @bot.event
    async def on_guild_join(guild: discord.Guild) -> None:
        if not allowed_guilds:
            return
        if not is_guild_allowed(guild.id):
            log.warning("Auto-leaving disallowed guild: id=%s name=%s", guild.id, guild.name)
            try:
                await guild.leave()
            except Exception:
                log.exception("failed to auto-leave disallowed guild id=%s", guild.id)

    register_commands(
        bot=bot,
        qm=qm,
        controller=controller,
        matchmaker=matchmaker,
        ready_config_store=ready_config_store,
        simulate_config_store=simulate_config_store,
        admin_access_store=admin_access_store,
        ui_style_store=ui_style_store,
        fake_id_base=FAKE_ID_BASE,
    )

    bot.run(token)


if __name__ == "__main__":
    main()

