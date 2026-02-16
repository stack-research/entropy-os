"""Logical time primitives."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LogicalClock:
    """Monotonic logical clock advanced only by explicit ticks."""

    epoch: int = 0

    def now(self) -> int:
        return self.epoch

    def tick(self, n: int = 1) -> int:
        if n < 0:
            raise ValueError("tick increment must be non-negative")
        self.epoch += n
        return self.epoch


@dataclass(frozen=True, slots=True)
class TTLWindow:
    """A TTL window anchored at creation tick."""

    created_at: int
    ttl_ticks: int

    def expires_at(self) -> int:
        return self.created_at + self.ttl_ticks

    def is_expired(self, now: int) -> bool:
        return now >= self.expires_at()
