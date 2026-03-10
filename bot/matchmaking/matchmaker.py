from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Dict, List, Optional

import discord

from bot.domain.modes import ModeSpec
from bot.matchmaking.queue_manager import QueueManager

log = logging.getLogger(__name__)

class Matchmaker:
    def __init__(
        self,
        *,
        bot: discord.Client,
        queue_manager: QueueManager,
        mode_specs: Dict[str, ModeSpec],
        lobby_channel_id_provider: Callable[[], Optional[int]],
        lobby_locale_provider: Callable[[], str],
        on_queue_changed: Optional[Callable[[], None]] = None,
        on_match_ready: Optional[Callable[[discord.abc.Messageable, ModeSpec, List[int]], Awaitable[None]]] = None,
        interval_seconds: float = 5.0,
    ):
        self.bot = bot
        self.qm = queue_manager
        self.mode_specs = mode_specs
        self._get_channel_id = lobby_channel_id_provider
        self._get_locale = lobby_locale_provider
        self._on_queue_changed = on_queue_changed
        self._on_match_ready = on_match_ready
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop(), name="matchmaker_loop")

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def _run_loop(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self.tick()
            except Exception:
                log.exception("matchmaker tick failed")
            await asyncio.sleep(self.interval_seconds)

    async def tick(self) -> None:
        channel_id = self._get_channel_id()
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                log.warning("cannot fetch lobby channel_id=%s", channel_id)
                return

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return

        async with self._lock:
            for mode_key, spec in self.mode_specs.items():
                if self.qm.is_mode_locked(mode_key):
                    continue
                players = self.qm.pop_match(mode_key, spec.match_size)
                if not players:
                    continue

                # Lock mode while READY flow runs; keep reserved players in lobby until it's fully finished.
                self.qm.lock_mode(mode_key)

                # RANDOM is a meta-mode: once it forms a match, choose a concrete mode
                # and transfer the reserved players to that mode so it becomes unavailable too.
                real_mode_key = mode_key
                real_spec = spec
                if mode_key == "random":
                    candidates: List[str] = []
                    for k, sp in self.mode_specs.items():
                        if k == "random":
                            continue
                        # Only choose modes compatible with this match size.
                        if int(getattr(sp, "match_size", 0)) == int(getattr(spec, "match_size", 0)):
                            candidates.append(k)
                    if candidates:
                        import random as _random  # local import to avoid module-level cost

                        real_mode_key = _random.choice(candidates)
                        real_spec = self.mode_specs.get(real_mode_key, spec)
                        moved = self.qm.transfer_reserved("random", real_mode_key, players)
                        if moved:
                            self.qm.lock_mode(real_mode_key)
                            # RANDOM itself should not stay locked; the chosen real mode is locked.
                            self.qm.unlock_mode("random")
                            if self._on_queue_changed:
                                self._on_queue_changed()

                async def run_and_finalize(mk: str, sp: ModeSpec, pids: List[int]) -> None:
                    try:
                        if self._on_match_ready is not None:
                            await self._on_match_ready(channel, sp, pids)
                        else:
                            await self._announce_match(channel, sp, pids)
                    except Exception:
                        log.exception("match flow failed for mode=%s", mk)
                    finally:
                        self.qm.release_reserved(mk, pids)
                        self.qm.unlock_mode(mk)
                        if self._on_queue_changed:
                            self._on_queue_changed()

                asyncio.create_task(run_and_finalize(real_mode_key, real_spec, players), name=f"match_flow:{mode_key}")

    async def _announce_match(self, channel: discord.abc.Messageable, spec: ModeSpec, players: List[int]) -> None:
        title = spec.title_en

        mentions = [f"<@{uid}>" for uid in players]
        description_lines: List[str] = []

        if spec.teams and spec.teams > 1:
            per_team = max(1, len(players) // spec.teams)
            for t in range(spec.teams):
                chunk = mentions[t * per_team : (t + 1) * per_team]
                if not chunk:
                    continue
                team_name = f"Team {t + 1}"
                description_lines.append(f"**{team_name}**")
                description_lines.extend(chunk)
                description_lines.append("")
        else:
            description_lines.extend(mentions)

        header = "Match found!"
        mode_line = f"Mode: **{title.upper()}**"
        content = "\n".join([header, mode_line, "", *description_lines]).strip()
        await channel.send(content)

