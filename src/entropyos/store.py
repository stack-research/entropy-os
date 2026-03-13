"""State forgetting layer with explicit TTL semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ExpiredStateError
from .identity import canonicalize_state_key
from .ttl import TTLWindow


@dataclass(slots=True)
class StoreEntry:
    value: Any
    created_at: int
    ttl_ticks: int

    def expires_at(self) -> int:
        return self.created_at + self.ttl_ticks


class TTLStore:
    """Deterministic key-value store with enforced expiry on access."""

    def __init__(self, now_provider) -> None:
        self._now = now_provider
        self._entries: dict[str, StoreEntry] = {}

    def set(self, key: str, value: Any, ttl_ticks: int, now: int | None = None) -> None:
        if ttl_ticks < 0:
            raise ValueError("ttl_ticks must be non-negative")
        key = canonicalize_state_key(key)
        current = self._now() if now is None else now
        self._entries[key] = StoreEntry(value=value, created_at=current, ttl_ticks=ttl_ticks)

    def get(self, key: str, now: int | None = None) -> Any:
        key = canonicalize_state_key(key)
        if key not in self._entries:
            raise KeyError(key)
        current = self._now() if now is None else now
        entry = self._entries[key]
        if TTLWindow(entry.created_at, entry.ttl_ticks).is_expired(current):
            del self._entries[key]
            raise ExpiredStateError(f"State key '{key}' expired at tick {entry.expires_at()}")
        return entry.value

    def purge_expired(self, now: int | None = None) -> list[str]:
        current = self._now() if now is None else now
        removed: list[str] = []
        for key in sorted(list(self._entries)):
            entry = self._entries[key]
            if TTLWindow(entry.created_at, entry.ttl_ticks).is_expired(current):
                del self._entries[key]
                removed.append(key)
        return removed

    def expired_keys(self, now: int | None = None) -> list[str]:
        """Return keys that are expired, without purging them."""
        current = self._now() if now is None else now
        return [
            key for key in sorted(self._entries)
            if TTLWindow(self._entries[key].created_at, self._entries[key].ttl_ticks).is_expired(current)
        ]

    def keys(self) -> list[str]:
        return sorted(self._entries)

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {
            key: {
                "value": entry.value,
                "created_at": entry.created_at,
                "ttl_ticks": entry.ttl_ticks,
            }
            for key, entry in sorted(self._entries.items())
        }

    @classmethod
    def from_dict(cls, payload: dict[str, dict[str, Any]], now_provider) -> "TTLStore":
        store = cls(now_provider=now_provider)
        for key in sorted(payload):
            item = payload[key]
            store._entries[key] = StoreEntry(
                value=item["value"],
                created_at=item["created_at"],
                ttl_ticks=item["ttl_ticks"],
            )
        return store
