from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

import discord

from bot.domain.modes import ModeSpec
from bot.domain.ui_style import SYMBOLS_MAP
from bot.matchmaking.queue_manager import QueueManager
from bot.storage.ui_style_store import UI_STYLE_EMOJI, UI_STYLE_SYMBOLS
from bot.storage.lobby_store import LobbyStateStore

log = logging.getLogger(__name__)


MODE_PADDING: Dict[str, int] = {
    "solo": 15,
    "duo": 16,
    "squad": 14,
    "showdown": 10,
    "king_of_the_zeal": 5,
    "overdrive": 10,
    "nightfall": 10,
    "deathmatch": 8,
    "random": 12,
}

def _mode_line(*, spec: ModeSpec, count: int) -> str:
    mode_title_source = spec.title_en
    mode_title = (mode_title_source or "").upper()
    count_part = f"{count}/{spec.capacity}"
    pad_units = MODE_PADDING.get(spec.key, 1)
    pad = "\u2007" * max(0, pad_units)
    return f"**{mode_title}** {pad}{count_part}"


class ModeAccessoryButton(discord.ui.Button):
    def __init__(self, *, mode_key: str, emoji: Optional[str] = None, label: Optional[str] = None):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=emoji,
            label=label,
            custom_id=f"mode:{mode_key}",
        )
        self.mode_key = mode_key

    async def callback(self, interaction: discord.Interaction):
        view: LobbyLayoutView = self.view  # type: ignore[assignment]
        await view.handle_mode(interaction, self.mode_key)


class LeaveQueueButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label="Leave queue",
            style=discord.ButtonStyle.danger,
            custom_id="btn:leave_queue",
        )

    async def callback(self, interaction: discord.Interaction):
        view: LobbyLayoutView = self.view  # type: ignore[assignment]
        await view.handle_leave(interaction)


class LobbyLayoutView(discord.ui.LayoutView):
    def __init__(
        self,
        *,
        queue_manager: QueueManager,
        mode_specs: Dict[str, ModeSpec],
        lobby_state_store: LobbyStateStore,
        on_request_refresh: Callable[[], None],
        on_build_view: Optional[Callable[[], Any]] = None,
        ui_style: str = UI_STYLE_EMOJI,
    ):
        super().__init__(timeout=None)
        self.qm = queue_manager
        self.mode_specs = mode_specs
        self.lobby_state_store = lobby_state_store
        self.on_request_refresh = on_request_refresh
        self.on_build_view = on_build_view
        self.ui_style = ui_style

        self._build_layout()

    def _build_layout(self) -> None:
        sizes = self.qm.sizes()

        container = discord.ui.Container(accent_color=0x3B82F6)
        container.add_item(discord.ui.TextDisplay("# Votes for game modes"))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=True))
        container.add_item(discord.ui.TextDisplay("## SELECT GAME MODE:"))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=True))

        for key, spec in self.mode_specs.items():
            line = _mode_line(spec=spec, count=sizes.get(key, 0))
            if self.ui_style == UI_STYLE_SYMBOLS:
                symbol = SYMBOLS_MAP.get(key, "")
                section = discord.ui.Section(
                    discord.ui.TextDisplay(line),
                    accessory=ModeAccessoryButton(mode_key=key, emoji=None, label=symbol or None),
                )
            else:
                section = discord.ui.Section(
                    discord.ui.TextDisplay(line),
                    accessory=ModeAccessoryButton(mode_key=key, emoji=spec.emoji, label=None),
                )
            container.add_item(section)
            if key == "deathmatch":
                container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=True))

        footer = "Press the button on the right to join the queue."
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=True))
        container.add_item(discord.ui.TextDisplay(footer))

        self.add_item(container)
        self.add_item(discord.ui.ActionRow(LeaveQueueButton()))

    async def on_error(self, error: Exception, item, interaction: discord.Interaction) -> None:
        log.exception("view error: %s", error)
        if interaction.response.is_done():
            return
        await interaction.response.send_message("Error.", ephemeral=True)

    async def handle_mode(self, interaction: discord.Interaction, mode_key: str) -> None:
        user_id = int(interaction.user.id)

        existing_mode = self.qm.get_user_mode(user_id)
        if self.qm.is_mode_locked(mode_key):
            mode_spec = self.mode_specs.get(mode_key)
            mode_title = (mode_spec.title_en or mode_key).upper()

            mode_bold = f"**{mode_title}**"
            if existing_mode == mode_key:
                text = (
                    "Switching your queue to another game mode is **unavailable** — "
                    f"you are already in the {mode_bold} mode queue."
                )
            else:
                text = (
                    f"The {mode_bold} mode queue is currently **unavailable** — "
                    "a match for this mode is being processed. Please try again in a moment."
                )

            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)
            return

        ok, reason = self.qm.add(user_id, mode_key)

        if not ok and reason == "already_in_other_queue":
            text = "You are already in another queue. Please leave it first using the red button below."
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)
            return

        if not ok and reason == "already_in_this_queue":
            text = "You are already in this queue."
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)
            return

        mode_spec = self.mode_specs.get(mode_key)
        mode_title = mode_spec.title_en.upper() if mode_spec else mode_key.upper()
        join_text = f"You joined the **{mode_title}** queue."
        if interaction.response.is_done():
            await interaction.followup.send(join_text, ephemeral=True)
        else:
            await interaction.response.send_message(join_text, ephemeral=True)

        if ok:
            if self.on_build_view and interaction.message:
                try:
                    new_view = self.on_build_view()
                    await interaction.message.edit(content="", embeds=[], view=new_view)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
            self.on_request_refresh()

    async def handle_leave(self, interaction: discord.Interaction) -> None:
        user_id = int(interaction.user.id)
        mode_key = self.qm.get_user_mode(user_id)

        if mode_key and self.qm.is_mode_locked(mode_key):
            text = "You can't leave right now — your match is pending (READY). Please wait until it finishes."
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)
            return

        removed = self.qm.remove(user_id)

        if removed and mode_key:
            mode_spec = self.mode_specs.get(mode_key)
            mode_title = mode_spec.title_en.upper() if mode_spec else mode_key.upper()
            text = f"You left the **{mode_title}** queue."
        elif not mode_key:
            text = "You are not in any queue."
        else:
            text = "Failed to leave the queue. Try again."

        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)

        if removed:
            if self.on_build_view and interaction.message:
                try:
                    new_view = self.on_build_view()
                    await interaction.message.edit(content="", embeds=[], view=new_view)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
            self.on_request_refresh()

