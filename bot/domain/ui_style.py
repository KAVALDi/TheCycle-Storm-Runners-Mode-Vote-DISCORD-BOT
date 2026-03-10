from __future__ import annotations

from typing import Literal, Tuple

from bot.storage.ui_style_store import UI_STYLE_EMOJI, UI_STYLE_SYMBOLS


ModeKey = Literal[
    "solo",
    "duo",
    "squad",
    "showdown",
    "king_of_the_zeal",
    "overdrive",
    "nightfall",
    "deathmatch",
    "random",
]


SYMBOLS_MAP = {
    "solo": "①",
    "duo": "②",
    "squad": "④",
    "showdown": "⚔",
    "king_of_the_zeal": "♕",
    "overdrive": "☄",
    "nightfall": "☽︎",
    "deathmatch": "☠",
    "random": "↺",
}


def get_mode_icon(mode_key: str, style: str, fallback_emoji: str) -> str:
    """
    Unified place to choose icon for a game mode depending on UI style.
    - emoji style: always returns fallback_emoji
    - symbols style: returns mapped symbol or fallback_emoji if unknown
    """
    if style != UI_STYLE_SYMBOLS:
        return fallback_emoji
    return SYMBOLS_MAP.get(mode_key, fallback_emoji)


def get_ready_icon(status: Literal["pending", "success", "fail"], style: str) -> str:
    if style == UI_STYLE_SYMBOLS:
        if status == "pending":
            return "✆"
        if status == "success":
            return "✓︎"
        return "✗︎"
    else:
        if status == "pending":
            return "🟡"
        if status == "success":
            return "🟢"
        return "🔴"


def get_timer_icon(style: str) -> str:
    return "⏱" if style == UI_STYLE_SYMBOLS else "⏳"


def get_dm_ready_text(style: str, ready_window: int) -> Tuple[str, str]:
    """
    Returns (mid_line, bottom_line) for DM READY panel.
    Timer text is static and based on ready_window.
    """
    minutes, seconds = divmod(max(0, int(ready_window)), 60)
    dm_timer = f"{minutes}:{seconds:02d}"
    if style == UI_STYLE_SYMBOLS:
        mid = "## ✆ PRESS READY"
        bottom = f"## ⏱ {dm_timer} seconds left..."
    else:
        mid = "## 🟡 PRESS READY"
        bottom = f"## ⏳ {dm_timer} seconds left..."
    return mid, bottom

