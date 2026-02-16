"""Ephemeral API registration and expiration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .errors import EntityNotFoundError, ExpiredError
from .ttl import TTLWindow

Handler = Callable[..., Any]


@dataclass(slots=True)
class APIRecord:
    name: str
    ttl_ticks: int
    registered_at: int
    renewed_at: int
    expired: bool = False

    def expires_at(self) -> int:
        return self.renewed_at + self.ttl_ticks

    def should_expire(self, now: int) -> bool:
        return TTLWindow(self.renewed_at, self.ttl_ticks).is_expired(now)


class APIRegistry:
    """Deterministic registry for expiring API endpoints."""

    def __init__(self, now_provider: Callable[[], int] | None = None) -> None:
        self._now = now_provider or (lambda: 0)
        self._records: dict[str, APIRecord] = {}
        self._handlers: dict[str, Handler] = {}

    def register(self, name: str, handler: Handler | None, ttl_ticks: int, now: int | None = None) -> APIRecord:
        if ttl_ticks < 0:
            raise ValueError("ttl_ticks must be non-negative")
        current = self._resolve_now(now)
        record = APIRecord(name=name, ttl_ticks=ttl_ticks, registered_at=current, renewed_at=current)
        self._records[name] = record
        if handler is not None:
            self._handlers[name] = handler
        return record

    def ephemeral_api(self, ttl_ticks: int) -> Callable[[Handler], Handler]:
        def decorator(func: Handler) -> Handler:
            self.register(func.__name__, func, ttl_ticks)
            return func

        return decorator

    def renew(self, name: str, now: int | None = None) -> APIRecord:
        record = self._require(name)
        current = self._resolve_now(now)
        record.renewed_at = current
        record.expired = False
        return record

    def evaluate_expiry(self, now: int | None = None) -> list[str]:
        current = self._resolve_now(now)
        expired: list[str] = []
        for name in sorted(self._records):
            record = self._records[name]
            if not record.expired and record.should_expire(current):
                record.expired = True
                expired.append(name)
        return expired

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        record = self._require(name)
        self.evaluate_expiry()
        if record.expired:
            raise ExpiredError(f"API '{name}' expired at tick {record.expires_at()}")
        handler = self._handlers.get(name)
        if handler is None:
            raise EntityNotFoundError(f"API '{name}' has no callable handler")
        return handler(*args, **kwargs)

    def get(self, name: str) -> APIRecord:
        return self._require(name)

    def expired_names(self) -> list[str]:
        return [name for name in sorted(self._records) if self._records[name].expired]

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "name": rec.name,
                "ttl_ticks": rec.ttl_ticks,
                "registered_at": rec.registered_at,
                "renewed_at": rec.renewed_at,
                "expired": rec.expired,
            }
            for name, rec in sorted(self._records.items())
        }

    @classmethod
    def from_dict(cls, payload: dict[str, dict[str, Any]], now_provider: Callable[[], int]) -> "APIRegistry":
        registry = cls(now_provider=now_provider)
        for name in sorted(payload):
            item = payload[name]
            record = APIRecord(
                name=item["name"],
                ttl_ticks=item["ttl_ticks"],
                registered_at=item["registered_at"],
                renewed_at=item["renewed_at"],
                expired=item["expired"],
            )
            registry._records[name] = record
        return registry

    def _require(self, name: str) -> APIRecord:
        record = self._records.get(name)
        if record is None:
            raise EntityNotFoundError(f"Unknown API '{name}'")
        return record

    def _resolve_now(self, now: int | None = None) -> int:
        return self._now() if now is None else now
