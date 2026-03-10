from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

import discord
from discord import app_commands

from bot.domain.modes import MODE_SPECS
from bot.domain.ready import ServerReadyConfig
from bot.matchmaking.matchmaker import Matchmaker
from bot.matchmaking.queue_manager import QueueManager
from bot.services.lobby_service import LobbyController
from bot.storage.ready_config_store import ReadyConfigStore
from bot.storage.simulate_config_store import SimulateConfig, SimulateConfigStore
from bot.services.simulation_service import run_mode_simulation
from bot.storage.admin_access_store import AdminAccessStore
from bot.storage.ui_style_store import UIStyleStore, UI_STYLE_EMOJI, UI_STYLE_SYMBOLS
from bot.config import REPO_URL
from bot.text.commands_messages import (
    dm_only,
    guild_only,
    invalid_m_ss,
    invalid_seconds,
    must_be_admin,
    must_specify_command,
    no_permission,
    unknown_mode,
)


ADMIN_COMMAND_KEYS = (
    "lobby",
    "simulate_mode",
    "ready_config",
    "simulate_settings",
    "role_access",
)


def _has_command_access(interaction: discord.Interaction, command_key: str, store: AdminAccessStore) -> bool:
    if interaction.guild is None:
        return False
    perms = getattr(interaction.user, "guild_permissions", None)
    if perms is not None and getattr(perms, "administrator", False):
        return True

    role_ids = set(store.get_roles(interaction.guild.id, command_key))
    if not role_ids:
        return False

    user_roles = getattr(interaction.user, "roles", [])
    user_role_ids = {getattr(r, "id", 0) for r in user_roles}
    return bool(user_role_ids & role_ids)


async def _require_guild(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        await interaction.response.send_message(guild_only(), ephemeral=True)
        return False
    return True


async def _require_dm(interaction: discord.Interaction) -> bool:
    if interaction.guild is not None:
        await interaction.response.send_message(dm_only(), ephemeral=True)
        return False
    return True


async def _require_admin_or_role(
    interaction: discord.Interaction,
    command_key: str,
    store: AdminAccessStore,
) -> bool:
    if _has_command_access(interaction, command_key, store):
        return True
    await interaction.response.send_message(no_permission(), ephemeral=True)
    return False


async def _require_admin(interaction: discord.Interaction) -> bool:
    perms = getattr(interaction.user, "guild_permissions", None)
    if perms is not None and getattr(perms, "administrator", False):
        return True
    await interaction.response.send_message(must_be_admin(), ephemeral=True)
    return False


def register_commands(
    *,
    bot: discord.Client,
    qm: QueueManager,
    controller: LobbyController,
    matchmaker: Matchmaker,
    ready_config_store: ReadyConfigStore,
    simulate_config_store: SimulateConfigStore,
    admin_access_store: AdminAccessStore,
    ui_style_store: UIStyleStore,
    fake_id_base: int,
) -> None:
    # When allowed_guilds is empty, the bot is allowed everywhere.
    from bot.storage.allowed_guilds_store import AllowedGuildsStore  # local import to avoid cycles
    from bot.config import ALLOWED_GUILDS_JSON

    allowed_ids = AllowedGuildsStore(path=ALLOWED_GUILDS_JSON).load()

    def _is_guild_allowed_for_commands(gid: Optional[int]) -> bool:
        if gid is None:
            return False
        if not allowed_ids:
            return True
        return int(gid) in allowed_ids
    @bot.tree.command(name="lobby", description="Show or refresh the storm mode vote / matchmaking lobby panel in this channel")
    async def lobby(interaction: discord.Interaction):
        if not _is_guild_allowed_for_commands(interaction.guild.id if interaction.guild else None):
            # on_guild_join / on_ready in main.py will clean up disallowed guilds; just no-op here
            return
        if not await _require_guild(interaction):
            return
        if not await _require_admin_or_role(interaction, "lobby", admin_access_store):
            return

        await interaction.response.defer(ephemeral=True, thinking=False)
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send("Command `/lobby` can only be used in a text channel.", ephemeral=True)
            return
        await controller.create_or_update_lobby(interaction.channel)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass

    @bot.tree.command(name="simulate_mode", description="Simulate filling votes / queue for a game mode")
    @app_commands.describe(mode="Game mode key to simulate")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="SOLO", value="solo"),
            app_commands.Choice(name="DUO", value="duo"),
            app_commands.Choice(name="SQUAD", value="squad"),
            app_commands.Choice(name="SHOWDOWN", value="showdown"),
            app_commands.Choice(name="KING OF THE ZEAL", value="king_of_the_zeal"),
            app_commands.Choice(name="OVERDRIVE", value="overdrive"),
            app_commands.Choice(name="NIGHTFALL", value="nightfall"),
            app_commands.Choice(name="DEATHMATCH", value="deathmatch"),
            app_commands.Choice(name="RANDOM", value="random"),
        ]
    )
    async def simulate_mode(interaction: discord.Interaction, mode: app_commands.Choice[str]):
        if not _is_guild_allowed_for_commands(interaction.guild.id if interaction.guild else None):
            return
        if not await _require_guild(interaction):
            return
        if not await _require_admin_or_role(interaction, "simulate_mode", admin_access_store):
            return

        mode_key = mode.value
        spec = MODE_SPECS.get(mode_key)
        if spec is None:
            await interaction.response.send_message(unknown_mode(), ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "This command can only be used in a text channel.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=False)

        # Ensure this channel is the active lobby target so READY appears here
        try:
            await controller.create_or_update_lobby(interaction.channel)
        except Exception:
            pass

        asyncio.create_task(
            run_mode_simulation(
                qm=qm,
                controller=controller,
                matchmaker=matchmaker,
                simulate_config_store=simulate_config_store,
                channel=interaction.channel,
                mode_key=mode_key,
                spec=spec,
                fake_id_base=fake_id_base,
            )
        )

        mode_label = spec.title_en.upper()
        await interaction.followup.send(
            f"Simulating queue fill for mode: **{mode_label}**.",
            ephemeral=True,
        )

    @bot.tree.command(name="clear", description="[No permission required] Delete recent messages sent by this bot in DM")
    async def clear_cmd(interaction: discord.Interaction):
        if not await _require_dm(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=False)
        channel = interaction.channel
        if channel is None:
            return

        deleted = 0
        try:
            async for msg in channel.history(limit=200):  # type: ignore[attr-defined]
                if msg.author == bot.user:
                    try:
                        await msg.delete()
                        deleted += 1
                    except Exception:
                        continue
        except Exception:
            pass

        try:
            await interaction.edit_original_response(content=f"Deleted bot messages: {deleted}.")
        except Exception:
            pass

    @bot.tree.command(name="ready_config", description="Configure READY timers in M:SS format")
    @app_commands.describe(
        target="Which timer to change",
        value="New value in M:SS format, e.g. 1:30",
    )
    @app_commands.choices(
        target=[
            app_commands.Choice(name="ready_window", value="ready_window"),
            app_commands.Choice(name="success_ttl", value="success_ttl"),
            app_commands.Choice(name="fail_ttl", value="fail_ttl"),
        ]
    )
    async def ready_config(
        interaction: discord.Interaction,
        target: app_commands.Choice[str],
        value: str,
    ):
        if not _is_guild_allowed_for_commands(interaction.guild.id if interaction.guild else None):
            return
        if not await _require_guild(interaction):
            return
        if not await _require_admin_or_role(interaction, "ready_config", admin_access_store):
            return

        def parse_m_ss(v: str) -> Optional[int]:
            try:
                parts = v.strip().split(":")
                if len(parts) != 2:
                    return None
                m = int(parts[0])
                s = int(parts[1])
                if m < 0 or s < 0 or s >= 60:
                    return None
                return m * 60 + s
            except Exception:
                return None

        seconds = parse_m_ss(value)
        if seconds is None:
            await interaction.response.send_message(invalid_m_ss(), ephemeral=True)
            return

        current = ready_config_store.load()
        if target.value == "ready_window":
            cfg = ServerReadyConfig(ready_window=seconds, success_ttl=current.success_ttl, fail_ttl=current.fail_ttl)
        elif target.value == "success_ttl":
            cfg = ServerReadyConfig(ready_window=current.ready_window, success_ttl=seconds, fail_ttl=current.fail_ttl)
        else:
            cfg = ServerReadyConfig(ready_window=current.ready_window, success_ttl=current.success_ttl, fail_ttl=seconds)

        ready_config_store.save(cfg)
        await interaction.response.send_message(
            f"READY config updated: {target.value} = {value}",
            ephemeral=True,
        )

    @bot.tree.command(name="simulate_settings", description="Configure simulation for READY menu and lobby")
    @app_commands.describe(
        scope="What to configure (LOBBY or READY_MENU)",
        target="What exactly to change (bots or message_update)",
        value="For LOBBY bots: 1-4 (per second, random 1..N). For message_update: seconds as float, e.g. 1.0",
    )
    @app_commands.choices(
        scope=[
            app_commands.Choice(name="LOBBY", value="lobby"),
            app_commands.Choice(name="READY_MENU", value="ready"),
        ],
        target=[
            app_commands.Choice(name="bots", value="bots"),
            app_commands.Choice(name="message_update", value="message"),
        ],
    )
    async def simulate_settings(
        interaction: discord.Interaction,
        scope: app_commands.Choice[str],
        target: app_commands.Choice[str],
        value: str,
    ):
        if not _is_guild_allowed_for_commands(interaction.guild.id if interaction.guild else None):
            return
        if not await _require_guild(interaction):
            return
        if not await _require_admin_or_role(interaction, "simulate_settings", admin_access_store):
            return

        cfg = simulate_config_store.load()

        if scope.value == "lobby":
            if target.value == "bots":
                # Configure how many fake players per second in lobby (random 1..N).
                try:
                    n = int(value.strip())
                    n = max(1, min(4, n))
                except Exception:
                    await interaction.response.send_message(
                        "Invalid value. Use an integer between 1 and 4 for LOBBY bots.",
                        ephemeral=True,
                    )
                    return
                new_cfg = SimulateConfig(
                    lobby_step_seconds=cfg.lobby_step_seconds,
                    ready_step_seconds=cfg.ready_step_seconds,
                    auto_ramp_aggressiveness=cfg.auto_ramp_aggressiveness,
                    lobby_add_min=1,
                    lobby_add_max=n,
                    lobby_add_random=True,
                )
                simulate_config_store.save(new_cfg)
                await interaction.response.send_message(
                    f"LOBBY bots per second: random between 1 and {n}.",
                    ephemeral=True,
                )
                return

            # message_update for LOBBY: how often to refresh the lobby panel during simulation.
            try:
                seconds = float(value.strip().replace(",", "."))
            except Exception:
                seconds = -1.0

            if not (seconds > 0):
                await interaction.response.send_message(invalid_seconds(), ephemeral=True)
                return

            new_cfg = SimulateConfig(
                lobby_step_seconds=seconds,
                ready_step_seconds=cfg.ready_step_seconds,
                auto_ramp_aggressiveness=cfg.auto_ramp_aggressiveness,
                lobby_add_min=cfg.lobby_add_min,
                lobby_add_max=cfg.lobby_add_max,
                lobby_add_random=cfg.lobby_add_random,
            )
            simulate_config_store.save(new_cfg)
            await interaction.response.send_message(
                f"LOBBY message update interval set to {seconds} seconds.",
                ephemeral=True,
            )
            return

        # READY menu configuration
        if target.value == "bots":
            # Controls how fast auto READY fills during simulation (smaller = faster).
            try:
                seconds = float(value.strip().replace(",", "."))
            except Exception:
                seconds = -1.0

            if not (seconds > 0):
                await interaction.response.send_message(invalid_seconds(), ephemeral=True)
                return

            new_cfg = SimulateConfig(
                lobby_step_seconds=cfg.lobby_step_seconds,
                ready_step_seconds=seconds,
                auto_ramp_aggressiveness=cfg.auto_ramp_aggressiveness,
                lobby_add_min=cfg.lobby_add_min,
                lobby_add_max=cfg.lobby_add_max,
                lobby_add_random=cfg.lobby_add_random,
            )
            simulate_config_store.save(new_cfg)
            await interaction.response.send_message(
                f"READY auto-fill step seconds set to {seconds}.",
                ephemeral=True,
            )
            return

        # message_update for READY: currently tied to auto-fill step seconds.
        try:
            seconds = float(value.strip().replace(",", "."))
        except Exception:
            seconds = -1.0

        if not (seconds > 0):
            await interaction.response.send_message(invalid_seconds(), ephemeral=True)
            return

        new_cfg = SimulateConfig(
            lobby_step_seconds=cfg.lobby_step_seconds,
            ready_step_seconds=seconds,
            auto_ramp_aggressiveness=cfg.auto_ramp_aggressiveness,
            lobby_add_min=cfg.lobby_add_min,
            lobby_add_max=cfg.lobby_add_max,
            lobby_add_random=cfg.lobby_add_random,
        )
        simulate_config_store.save(new_cfg)
        await interaction.response.send_message(
            f"READY message/update interval (auto-fill) set to {seconds} seconds.",
            ephemeral=True,
        )

    @bot.tree.command(name="role_access", description="Configure which roles can use restricted commands")
    @app_commands.describe(
        action="Choose what to do",
        command="Target command to configure (for 'set' or filtered 'list')",
        role="Role to grant access (for 'set')",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="set", value="set"),
            app_commands.Choice(name="list", value="list"),
        ],
        command=[
            app_commands.Choice(name=key, value=key)
            for key in ADMIN_COMMAND_KEYS
        ],
    )
    async def role_access(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        command: Optional[app_commands.Choice[str]] = None,
        role: Optional[discord.Role] = None,
    ):
        if not _is_guild_allowed_for_commands(interaction.guild.id if interaction.guild else None):
            return
        if not await _require_guild(interaction):
            return
        if not await _require_admin(interaction):
            return

        guild = interaction.guild
        if guild is None:
            return

        if action.value == "set":
            if command is None:
                await interaction.response.send_message(must_specify_command(), ephemeral=True)
                return

            command_key = command.value
            role_ids: List[int] = []
            mentions: List[str] = []

            if role is not None:
                role_ids.append(role.id)
                mentions.append(role.mention)

            admin_access_store.set_roles(guild.id, command_key, role_ids)

            if role_ids:
                msg = f'Admin access for "{command_key}" updated: ' + ", ".join(mentions)
            else:
                msg = f'Admin access for "{command_key}" cleared (no roles).'

            await interaction.response.send_message(msg, ephemeral=True)
            return

        # action == "list"
        if command is not None:
            command_key = command.value
            role_ids = admin_access_store.get_roles(guild.id, command_key)
            if not role_ids:
                msg = f'No roles configured for "{command_key}" — only administrators can use this command.'
            else:
                roles_str = []
                for rid in role_ids:
                    r = guild.get_role(rid)
                    roles_str.append(r.mention if r is not None else f"<@&{rid}>")
                msg = f'Roles with access to "{command_key}": ' + ", ".join(roles_str)
            await interaction.response.send_message(msg, ephemeral=True)
            return

        # list for all commands
        all_cfg = admin_access_store.get_all_for_guild(guild.id)
        lines: List[str] = []
        for cmd_key in ADMIN_COMMAND_KEYS:
            role_ids = all_cfg.get(cmd_key, [])
            if not role_ids:
                lines.append(f'- `{cmd_key}`: (no roles, only administrators)')
                continue
            parts = []
            for rid in role_ids:
                r = guild.get_role(rid)
                parts.append(r.mention if r is not None else f"<@&{rid}>")
            lines.append(f'- `{cmd_key}`: ' + ", ".join(parts))

        if not lines:
            text = "No roles configured — only administrators can use admin commands."
        else:
            text = "Roles with access to admin commands:\n" + "\n".join(lines)

        await interaction.response.send_message(text, ephemeral=True)

    @bot.tree.command(name="repo", description="[No permission required] Show the bot repository link")
    async def repo_cmd(interaction: discord.Interaction):
        await interaction.response.send_message(f"Repository: {REPO_URL}", ephemeral=True)

    @bot.tree.command(name="ui_style", description="Switch UI between emoji and symbols for this server")
    @app_commands.describe(
        action="What to do: set or show current style",
        style="Target style (for 'set')",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="set", value="set"),
            app_commands.Choice(name="show", value="show"),
        ],
        style=[
            app_commands.Choice(name="emoji", value=UI_STYLE_EMOJI),
            app_commands.Choice(name="symbols", value=UI_STYLE_SYMBOLS),
        ],
    )
    async def ui_style_cmd(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        style: Optional[app_commands.Choice[str]] = None,
    ):
        if not _is_guild_allowed_for_commands(interaction.guild.id if interaction.guild else None):
            return
        if not await _require_guild(interaction):
            return
        if not await _require_admin(interaction):
            return

        guild = interaction.guild
        if guild is None:
            return

        if action.value == "set":
            if style is None:
                await interaction.response.send_message(
                    "You must specify the style when using action 'set'.",
                    ephemeral=True,
                )
                return

            ui_style_store.set_style(guild.id, style.value)
            await interaction.response.send_message(
                f"UI style for this server set to `{style.value}`. Lobby panels will be refreshed automatically.",
                ephemeral=True,
            )

            try:
                await controller.refresh_all()
            except Exception:
                pass

            ch = interaction.channel
            if isinstance(ch, discord.TextChannel):
                try:
                    await controller.create_or_update_lobby(ch)
                except Exception:
                    pass
            return

        # action == "show"
        current = ui_style_store.get_style(guild.id)
        await interaction.response.send_message(
            f"Current UI style for this server: `{current}`.",
            ephemeral=True,
        )

