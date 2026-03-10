from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ModeSpec:
    key: str
    title_en: str
    capacity: int
    emoji: str
    match_size: int
    teams: Optional[int] = None  # None = FFA style; otherwise number of teams


MODE_SPECS: Dict[str, ModeSpec] = {
    "solo": ModeSpec(
        key="solo",
        title_en="Solo",
        capacity=20,
        emoji="👤",
        match_size=20,
        teams=None,
    ),
    "duo": ModeSpec(
        key="duo",
        title_en="Duo",
        capacity=20,
        emoji="👥",
        match_size=20,
        teams=None,
    ),
    "squad": ModeSpec(
        key="squad",
        title_en="Squad",
        capacity=20,
        emoji="👨‍👨‍👦‍👦",
        match_size=20,
        teams=None,
    ),
    "showdown": ModeSpec(
        key="showdown",
        title_en="Showdown",
        capacity=20,
        emoji="⚔️",
        match_size=20,
        teams=None,
    ),
    "king_of_the_zeal": ModeSpec(
        key="king_of_the_zeal",
        title_en="King of the Zeal",
        capacity=20,
        emoji="👑",
        match_size=20,
        teams=None,
    ),
    "overdrive": ModeSpec(
        key="overdrive",
        title_en="Overdrive",
        capacity=20,
        emoji="🚀",
        match_size=20,
        teams=None,
    ),
    "nightfall": ModeSpec(
        key="nightfall",
        title_en="Nightfall",
        capacity=20,
        emoji="🌙",
        match_size=20,
        teams=None,
    ),
    "deathmatch": ModeSpec(
        key="deathmatch",
        title_en="Deathmatch",
        capacity=10,
        emoji="💀",
        match_size=10,
        teams=None,
    ),
    "random": ModeSpec(
        key="random",
        title_en="Random",
        capacity=20,
        emoji="🎲",
        match_size=20,
        teams=None,
    ),
}

