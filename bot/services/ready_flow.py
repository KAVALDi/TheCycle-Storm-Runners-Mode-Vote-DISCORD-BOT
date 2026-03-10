from __future__ import annotations

import asyncio
from typing import List, Optional

import discord

from bot.discord_ui.server_ready_view import (
    ServerReadyState,
    accent_green,
    accent_red,
    accent_yellow,
    build_ready_layout_view,
    render_countdown_lines,
    render_final_fail_lines,
    render_final_success_lines,
    total_ready,
)
from bot.discord_ui.safe_ops import safe_delete_message, safe_edit_message
from bot.domain.ready import ServerReadyConfig
from bot.domain.ui_style import get_dm_ready_text
from bot.storage.ui_style_store import UI_STYLE_EMOJI, UI_STYLE_SYMBOLS


async def start_server_ready_flow(
    *,
    bot: Optional[discord.Client] = None,
    channel: discord.TextChannel | discord.Thread,
    mode_title: str,
    emoji: str,
    capacity: int,
    auto_ready: int = 0,
    auto_ready_ramp_to: int = 0,
    auto_ready_ramp_interval: float = 0.35,
    config: Optional[ServerReadyConfig] = None,
    player_ids: Optional[List[int]] = None,
    ui_style: str = UI_STYLE_SYMBOLS,
) -> None:
    cfg = config or ServerReadyConfig()
    state = ServerReadyState(
        mode_title=mode_title.upper(),
        emoji=emoji,
        capacity=capacity,
        auto_ready=max(0, min(auto_ready, capacity)),
        remaining=cfg.ready_window,
        success_ttl=cfg.success_ttl,
        fail_ttl=cfg.fail_ttl,
    )

    ramp_target = max(state.auto_ready, min(int(auto_ready_ramp_to), capacity))

    title, ready, timer = render_countdown_lines(state, ui_style)
    layout_view = build_ready_layout_view(
        accent_color=accent_yellow(),
        with_button=True,
        state=state,
        title=title,
        mid=ready,
        bottom=timer,
    )
    message = await channel.send(content="", embeds=[], view=layout_view)
    state.message = message

    if bot is not None and player_ids:
        dm_messages: List[discord.Message] = []
        dm_mid, dm_bottom = get_dm_ready_text(ui_style, cfg.ready_window)

        for uid in player_ids:
            try:
                user = bot.get_user(uid) or await bot.fetch_user(uid)
                if user is None:
                    continue
                dm = user.dm_channel or await user.create_dm()
                dm_view = build_ready_layout_view(
                    accent_color=accent_yellow(),
                    with_button=True,
                    state=state,
                    title=title,
                    mid=dm_mid,
                    bottom=dm_bottom,
                )
                dm_msg = await dm.send(content="", embeds=[], view=dm_view)
                dm_messages.append(dm_msg)
            except Exception:
                continue
        state.dm_messages = dm_messages

    async def maybe_wait_manual_delete(server_msg: discord.Message) -> None:
        """Wait for the server message to be manually deleted. DM deletes (e.g. /clear) must not trigger full cleanup."""
        if bot is None:
            await asyncio.Future()  # never completes
            return

        target_ids = {int(server_msg.id)}

        def check_single(p) -> bool:
            return int(p.message_id) in target_ids

        def check_bulk(p) -> bool:
            return any(int(x) in target_ids for x in p.message_ids)

        done, pending = await asyncio.wait(
            [
                asyncio.create_task(bot.wait_for("raw_message_delete", check=check_single)),
                asyncio.create_task(bot.wait_for("raw_bulk_message_delete", check=check_bulk)),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        for t in done:
            _ = t.result()

    async def ramp_task() -> None:
        if ramp_target <= state.auto_ready:
            return
        while state.remaining > 0 and state.message is not None and state.auto_ready < ramp_target:
            if total_ready(state) >= state.capacity:
                return
            await asyncio.sleep(max(0.05, float(auto_ready_ramp_interval)))
            state.auto_ready = min(state.auto_ready + 1, ramp_target)

    async def countdown_task() -> None:
        while state.remaining > 0:
            if total_ready(state) >= state.capacity:
                break
            await asyncio.sleep(1)
            state.remaining -= 1
            if state.message is None:
                return
            t, r, tm = render_countdown_lines(state, ui_style)
            new_view = build_ready_layout_view(
                accent_color=accent_yellow(),
                with_button=True,
                state=state,
                title=t,
                mid=r,
                bottom=tm,
            )
            ok = await safe_edit_message(state.message, content="", embeds=[], view=new_view)
            if not ok:
                state.message = None
                return

        success = total_ready(state) >= state.capacity
        if success:
            t, r, info = render_final_success_lines(state, ui_style)
            ttl = cfg.success_ttl
            accent = accent_green()
        else:
            t, r, info = render_final_fail_lines(state, ui_style)
            ttl = cfg.fail_ttl
            accent = accent_red()

        final_view = build_ready_layout_view(
            accent_color=accent,
            with_button=False,
            state=state,
            title=t,
            mid=r,
            bottom=info,
        )
        await safe_edit_message(message, content="", embeds=[], view=final_view)
        for dm_msg in list(state.dm_messages):
            ok = await safe_edit_message(dm_msg, content="", embeds=[], view=final_view)
            if not ok:
                try:
                    state.dm_messages.remove(dm_msg)
                except ValueError:
                    pass

        done, pending = await asyncio.wait(
            [
                asyncio.create_task(asyncio.sleep(ttl)),
                asyncio.create_task(maybe_wait_manual_delete(message)),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t2 in pending:
            t2.cancel()

        await safe_delete_message(message)

        for dm_msg in list(state.dm_messages):
            await safe_delete_message(dm_msg)

    ramp = asyncio.create_task(ramp_task(), name="ready_auto_ramp")
    try:
        await countdown_task()
    finally:
        ramp.cancel()

