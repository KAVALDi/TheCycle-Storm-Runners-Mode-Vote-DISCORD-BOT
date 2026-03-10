from __future__ import annotations

import asyncio
from typing import List, Optional

import discord

from bot.domain.modes import MODE_SPECS
from bot.discord_ui.lobby_view import LobbyLayoutView
from bot.discord_ui.safe_ops import safe_edit_message
from bot.matchmaking.queue_manager import QueueManager
from bot.storage.lobby_store import LobbyStateStore
from bot.storage.ui_style_store import UIStyleStore, UI_STYLE_SYMBOLS
from bot.storage.user_prefs_store import UserPrefsStore


class LobbyController:
    def __init__(
        self,
        bot: discord.Client,
        qm: QueueManager,
        lobby_store: LobbyStateStore,
        users_store: UserPrefsStore,
        ui_style_store: UIStyleStore,
    ):
        self.bot = bot
        self.qm = qm
        self.lobby_store = lobby_store
        self.users_store = users_store
        self.ui_style_store = ui_style_store
        self._refresh_lock = asyncio.Lock()
        self._refresh_scheduled: Optional[asyncio.Task] = None
        self._refresh_pending: bool = False

    def get_locale(self) -> str:
        state = self.lobby_store.load()
        loc = state.get("locale", "ru")
        return "ru" if loc not in ("ru", "en") else loc

    def get_channel_id(self) -> Optional[int]:
        state = self.lobby_store.load()
        cid = state.get("channel_id")
        return int(cid) if cid else None

    def get_message_id(self) -> Optional[int]:
        state = self.lobby_store.load()
        mid = state.get("message_id")
        return int(mid) if mid else None

    def _get_server_panels(self) -> List[tuple]:
        state = self.lobby_store.load()
        panels = state.get("server_panels")
        if isinstance(panels, list) and panels:
            return [(int(p["channel_id"]), int(p["message_id"])) for p in panels if p.get("channel_id") and p.get("message_id")]
        cid, mid = state.get("channel_id"), state.get("message_id")
        if cid and mid:
            return [(int(cid), int(mid))]
        return []

    def save_lobby_message(self, channel_id: int, message_id: int) -> None:
        state = self.lobby_store.load()
        if "locale" not in state:
            state["locale"] = "ru"
        panels = state.get("server_panels")
        if not isinstance(panels, list):
            panels = []
            if state.get("channel_id") and state.get("message_id"):
                panels.append({"channel_id": state["channel_id"], "message_id": state["message_id"]})
        for p in panels:
            if int(p.get("channel_id", 0)) == channel_id:
                p["message_id"] = message_id
                break
        else:
            panels.append({"channel_id": channel_id, "message_id": message_id})
        state["server_panels"] = panels
        state["channel_id"] = channel_id
        state["message_id"] = message_id
        self.lobby_store.save(state)

    def _remove_server_panel(self, channel_id: int, message_id: int) -> None:
        state = self.lobby_store.load()
        panels = state.get("server_panels")
        if isinstance(panels, list):
            panels[:] = [p for p in panels if int(p.get("channel_id", 0)) != channel_id or int(p.get("message_id", 0)) != message_id]
            state["server_panels"] = panels
        if state.get("channel_id") == channel_id and state.get("message_id") == message_id:
            state.pop("channel_id", None)
            state.pop("message_id", None)
            if panels:
                state["channel_id"] = panels[0]["channel_id"]
                state["message_id"] = panels[0]["message_id"]
        if "locale" not in state:
            state["locale"] = "ru"
        self.lobby_store.save(state)

    def clear_lobby_message(self) -> None:
        state = self.lobby_store.load()
        state.pop("channel_id", None)
        state.pop("message_id", None)
        state.pop("server_panels", None)
        if "locale" not in state:
            state["locale"] = "ru"
        self.lobby_store.save(state)

    def request_refresh(self) -> None:
        if self._refresh_scheduled and not self._refresh_scheduled.done():
            self._refresh_pending = True
            return
        self._refresh_pending = False
        self._refresh_scheduled = asyncio.create_task(self.refresh_all(), name="lobby_refresh")

    def _get_ui_style_for_guild(self) -> str:
        """
        Determine UI style based on the first known lobby panel's guild.
        Defaults to symbols style if guild is unknown.
        """
        panels = self._get_server_panels()
        if not panels:
            return UI_STYLE_SYMBOLS

        channel_id, _ = panels[0]
        channel = self.bot.get_channel(channel_id)
        # We deliberately do not fetch here to avoid extra HTTP calls;
        # style will switch on next refresh once channel is cached.
        if isinstance(channel, (discord.TextChannel, discord.Thread)) and channel.guild is not None:
            return self.ui_style_store.get_style(channel.guild.id)

        return UI_STYLE_SYMBOLS

    def build_view(self) -> LobbyLayoutView:
        ui_style = self._get_ui_style_for_guild()
        return LobbyLayoutView(
            queue_manager=self.qm,
            mode_specs=MODE_SPECS,
            lobby_state_store=self.lobby_store,
            on_request_refresh=self.request_refresh,
            on_build_view=self.build_view,
            ui_style=ui_style,
        )

    async def refresh_lobby_message(self) -> None:
        async with self._refresh_lock:
            view = self.build_view()
            for channel_id, message_id in self._get_server_panels():
                try:
                    channel = self.bot.get_channel(channel_id)
                    if channel is None:
                        channel = await self.bot.fetch_channel(channel_id)
                    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                        continue
                    msg = await channel.fetch_message(message_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    self._remove_server_panel(channel_id, message_id)
                    continue

                ok = await safe_edit_message(msg, content="", embeds=[], view=view)
                if not ok:
                    self._remove_server_panel(channel_id, message_id)

    async def refresh_dm_panels(self) -> None:
        async with self._refresh_lock:
            panels = self.users_store.iter_panels()
            if not panels:
                return
            for uid, ids in panels.items():
                try:
                    channel = self.bot.get_channel(ids["channel_id"])
                    if channel is None:
                        channel = await self.bot.fetch_channel(ids["channel_id"])
                    if not isinstance(channel, discord.DMChannel):
                        continue
                    msg = await channel.fetch_message(ids["message_id"])
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    self.users_store.clear_panel_message(uid)
                    continue

                view = self.build_view()
                ok = await safe_edit_message(msg, content="", embeds=[], view=view)
                if not ok:
                    self.users_store.clear_panel_message(uid)

    async def refresh_all(self) -> None:
        await self.refresh_lobby_message()
        await self.refresh_dm_panels()
        if self._refresh_pending:
            self._refresh_pending = False
            self._refresh_scheduled = asyncio.create_task(self.refresh_all(), name="lobby_refresh")

    async def create_or_update_lobby(self, channel: discord.TextChannel) -> discord.Message:
        view = self.build_view()
        for cid, mid in self._get_server_panels():
            if cid == channel.id:
                try:
                    msg = await channel.fetch_message(mid)
                except discord.NotFound:
                    self._remove_server_panel(cid, mid)
                    break

                ok = await safe_edit_message(msg, content="", embeds=[], view=view)
                if ok:
                    return msg
                self._remove_server_panel(cid, mid)
                break

        msg = await channel.send(content="", view=view)
        self.save_lobby_message(channel.id, msg.id)
        return msg

    async def create_or_update_dm_lobby(self, user: discord.abc.User) -> discord.Message:
        dm = user.dm_channel or await user.create_dm()
        panels = self.users_store.iter_panels()
        existing = panels.get(int(user.id))
        view = self.build_view()

        if existing and existing.get("channel_id") == dm.id:
            try:
                msg = await dm.fetch_message(int(existing["message_id"]))
            except (discord.NotFound, discord.HTTPException):
                self.users_store.clear_panel_message(int(user.id))
            else:
                ok = await safe_edit_message(msg, content="", embeds=[], view=view)
                if ok:
                    return msg
                self.users_store.clear_panel_message(int(user.id))

        msg = await dm.send(content="", view=view)
        self.users_store.set_panel_message(int(user.id), dm.id, msg.id)
        return msg

