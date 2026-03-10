from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


ModeKey = str


@dataclass
class QueueState:
    queues: Dict[ModeKey, List[int]] = field(default_factory=dict)
    user_to_mode: Dict[int, ModeKey] = field(default_factory=dict)
    locked_modes: set[ModeKey] = field(default_factory=set)
    reserved: Dict[ModeKey, set[int]] = field(default_factory=dict)


class QueueManager:
    def __init__(self, modes: List[ModeKey]):
        self._state = QueueState(
            queues={m: [] for m in modes},
            user_to_mode={},
            reserved={m: set() for m in modes},
        )

    @property
    def modes(self) -> List[ModeKey]:
        return list(self._state.queues.keys())

    def sizes(self) -> Dict[ModeKey, int]:
        return {m: len(q) + len(self._state.reserved.get(m, set())) for m, q in self._state.queues.items()}

    def get_user_mode(self, user_id: int) -> Optional[ModeKey]:
        return self._state.user_to_mode.get(user_id)

    def lock_mode(self, mode: ModeKey) -> None:
        """Prevent matchmaker from consuming this mode while locked."""
        self._state.locked_modes.add(mode)

    def unlock_mode(self, mode: ModeKey) -> None:
        self._state.locked_modes.discard(mode)

    def is_mode_locked(self, mode: ModeKey) -> bool:
        return mode in self._state.locked_modes

    def add(self, user_id: int, mode: ModeKey) -> Tuple[bool, str]:
        if mode not in self._state.queues:
            return False, "unknown_mode"
        existing = self._state.user_to_mode.get(user_id)
        if existing is not None:
            if existing == mode:
                return False, "already_in_this_queue"
            return False, "already_in_other_queue"

        self._state.queues[mode].append(user_id)
        self._state.user_to_mode[user_id] = mode
        return True, "ok"

    def remove(self, user_id: int) -> bool:
        mode = self._state.user_to_mode.pop(user_id, None)
        if mode is None:
            return False
        # If user was already reserved for a match, allow leaving too
        reserved = self._state.reserved.get(mode)
        if reserved and user_id in reserved:
            reserved.discard(user_id)
            return True

        q = self._state.queues.get(mode)
        if not q:
            return False
        try:
            q.remove(user_id)
        except ValueError:
            return False
        return True

    def pop_match(self, mode: ModeKey, count: int) -> Optional[List[int]]:
        q = self._state.queues.get(mode)
        if q is None or len(q) < count:
            return None
        players = q[:count]
        del q[:count]
        # Keep users mapped to mode while match is pending (reserved),
        # so lobby counters can remain "full" until READY flow fully finishes.
        self._state.reserved.setdefault(mode, set()).update(players)
        return players

    def release_reserved(self, mode: ModeKey, players: List[int]) -> None:
        reserved = self._state.reserved.get(mode)
        if reserved:
            for uid in players:
                reserved.discard(uid)
                if self._state.user_to_mode.get(uid) == mode:
                    self._state.user_to_mode.pop(uid, None)

    def transfer_reserved(self, from_mode: ModeKey, to_mode: ModeKey, players: List[int]) -> bool:
        """
        Move reserved players from one mode to another.
        Used for meta-modes like RANDOM so the chosen concrete mode becomes unavailable
        and shows full capacity while READY runs.
        """
        if from_mode == to_mode:
            return True
        if from_mode not in self._state.queues or to_mode not in self._state.queues:
            return False

        src = self._state.reserved.get(from_mode)
        if not src:
            return False

        dst = self._state.reserved.setdefault(to_mode, set())
        for uid in players:
            if uid in src:
                src.discard(uid)
            dst.add(uid)
            self._state.user_to_mode[uid] = to_mode
        return True

