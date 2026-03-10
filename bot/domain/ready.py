from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass(frozen=True)
class ServerReadyConfig:
    ready_window: int = 90  # seconds (1.5 minutes)
    success_ttl: int = 600  # seconds (10 minutes)
    fail_ttl: int = 15  # seconds


@dataclass
class ServerReadyState:
    mode_title: str
    emoji: str
    capacity: int
    remaining: int
    auto_ready: int = 0
    ready_user_ids: Set[int] = field(default_factory=set)
    # Discord-specific fields are kept optional and typed loosely at this layer
    message: Optional[object] = None
    dm_messages: List[object] = field(default_factory=list)
    success_ttl: int = 600
    fail_ttl: int = 15


def total_ready(state: ServerReadyState) -> int:
    return min(state.auto_ready + len(state.ready_user_ids), state.capacity)

