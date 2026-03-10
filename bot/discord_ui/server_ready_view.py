from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import discord

from bot.domain.ready import ServerReadyState, total_ready
from bot.domain.ui_style import get_ready_icon, get_timer_icon
from bot.text.ready_messages import already_marked_ready, internal_error, marked_ready


def _format_time(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    return f"{m}:{s:02d}"


def render_countdown_lines(state: ServerReadyState, ui_style: str) -> Tuple[str, str, str]:
    total = total_ready(state)
    title = f"# {state.emoji} {state.mode_title} {state.emoji}"
    ready_icon = get_ready_icon("pending", ui_style)
    timer_icon = get_timer_icon(ui_style)
    ready = f"## {ready_icon} {total}/{state.capacity} READY PLAYERS"
    timer = f"## {timer_icon} {_format_time(state.remaining)}"
    return title, ready, timer


def render_final_success_lines(state: ServerReadyState, ui_style: str) -> Tuple[str, str, str]:
    total = total_ready(state)
    title = f"# {state.emoji} {state.mode_title} {state.emoji}"
    ready_icon = get_ready_icon("success", ui_style)
    ready = f"## {ready_icon} {total}/{state.capacity} READY PLAYERS"
    info = f"ⓘ Enter the game and select the {state.mode_title} game mode"
    return title, ready, info


def _format_ttl(seconds: int) -> str:
    """Format TTL for display: '15 seconds', '2 minutes', '1 min 30 sec'."""
    if seconds < 60:
        return f"{seconds} seconds"
    m, s = divmod(seconds, 60)
    if s == 0:
        return f"{m} minute{'s' if m != 1 else ''}"
    return f"{m} min {s} sec"


def render_final_fail_lines(state: ServerReadyState, ui_style: str) -> Tuple[str, str, str]:
    total = total_ready(state)
    ttl_text = _format_ttl(state.fail_ttl)
    title = f"# {state.emoji} {state.mode_title} {state.emoji}"
    ready_icon = get_ready_icon("fail", ui_style)
    ready = f"## {ready_icon} {total}/{state.capacity} READY PLAYERS"
    info = f"ⓘ This message deletes in {ttl_text}"
    return title, ready, info


def accent_yellow() -> int:
    return 0xFACC15


def accent_green() -> int:
    return 0x22C55E


def accent_red() -> int:
    return 0xEF4444


class ServerReadyLayoutView(discord.ui.LayoutView):
    def __init__(self, *, state: ServerReadyState, accent_color: int, title: str, mid: str, bottom: str, with_button: bool):
        super().__init__(timeout=None)
        self.state = state

        container = discord.ui.Container(accent_color=accent_color)
        container.add_item(discord.ui.TextDisplay(title))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=True))
        container.add_item(discord.ui.TextDisplay(mid))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=True))
        container.add_item(discord.ui.TextDisplay(bottom))
        self.add_item(container)

        if with_button:
            self.add_item(discord.ui.ActionRow(ServerReadyButton()))


def build_ready_layout_view(*, accent_color: int, with_button: bool, state: ServerReadyState, title: str, mid: str, bottom: str) -> discord.ui.LayoutView:
    return ServerReadyLayoutView(state=state, accent_color=accent_color, title=title, mid=mid, bottom=bottom, with_button=with_button)


class ServerReadyButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label="READY",
            style=discord.ButtonStyle.secondary,
            custom_id="btn:server_ready",
        )

    async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        view = self.view
        state = getattr(view, "state", None)
        if not isinstance(state, ServerReadyState):
            await interaction.response.send_message(internal_error(), ephemeral=True)
            return

        user_id = int(interaction.user.id)
        if user_id in state.ready_user_ids:
            msg = already_marked_ready()
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        state.ready_user_ids.add(user_id)

        if not interaction.response.is_done():
            await interaction.response.send_message(marked_ready(), ephemeral=True)

