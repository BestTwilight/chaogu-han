from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketClock:
    """A replay clock that can move through historical or generated bars."""

    timeline: list[datetime]
    index: int = 0
    speed: float = 1.0
    paused: bool = False

    @property
    def now(self) -> datetime:
        if not self.timeline:
            raise ValueError("clock timeline is empty")
        return self.timeline[self.index]

    @property
    def is_finished(self) -> bool:
        return self.index >= len(self.timeline) - 1

    def step(self, bars: int = 1) -> datetime:
        if self.paused:
            return self.now
        self.index = min(self.index + bars, len(self.timeline) - 1)
        return self.now

    def rewind(self, bars: int = 1) -> datetime:
        self.index = max(self.index - bars, 0)
        return self.now

    def jump_to(self, index: int) -> datetime:
        if not 0 <= index < len(self.timeline):
            raise IndexError(f"clock index {index} outside timeline")
        self.index = index
        return self.now

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
