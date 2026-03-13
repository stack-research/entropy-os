"""Ephemeral API registration and expiration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .errors import EntityNotFoundError, ExpiredError
from .identity import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_EXPIRED,
    LIFECYCLE_PRUNABLE,
    LIFECYCLE_PRUNED,
    IdentityError,
    canonicalize_identity,
    resolve_alias,
)
from .ttl import TTLWindow

Handler = Callable[..., Any]


@dataclass(slots=True)
class APIRecord:
    identity: str
    ttl_ticks: int
    registered_at: int
    renewed_at: int
    lifecycle: str = LIFECYCLE_ACTIVE

    def expires_at(self) -> int:
        return self.renewed_at + self.ttl_ticks

    def should_expire(self, now: int) -> bool:
        return TTLWindow(self.renewed_at, self.ttl_ticks).is_expired(now)


class APIRegistry:
    """Deterministic registry for expiring API endpoints."""

    def __init__(self, now_provider: Callable[[], int] | None = None, *, grace_ticks: int = 0) -> None:
        self._now = now_provider or (lambda: 0)
        self._records: dict[str, APIRecord] = {}
        self._handlers: dict[str, Handler] = {}
        self._grace_ticks = grace_ticks

    def register(self, identity: str, handler: Handler | None, ttl_ticks: int, now: int | None = None) -> APIRecord:
        identity = canonicalize_identity(identity)
        if not identity.startswith("api:"):
            raise IdentityError("API identity must have 'api:' prefix")
        if ttl_ticks < 0:
            raise ValueError("ttl_ticks must be non-negative")
        current = self._resolve_now(now)
        record = APIRecord(identity=identity, ttl_ticks=ttl_ticks, registered_at=current, renewed_at=current)
        self._records[identity] = record
        if handler is not None:
            self._handlers[identity] = handler
        return record

    def ephemeral_api(self, identity: str, ttl_ticks: int) -> Callable[[Handler], Handler]:
        def decorator(func: Handler) -> Handler:
            self.register(identity, func, ttl_ticks)
            return func

        return decorator

    def renew(
        self,
        identity: str,
        now: int | None = None,
        *,
        aliases: Mapping[str, str] | None = None,
        ttl_override: int | None = None,
    ) -> APIRecord:
        resolved = self._resolve_identity(identity, aliases)
        record = self._require(resolved)
        if record.lifecycle == LIFECYCLE_PRUNED:
            raise ExpiredError(f"API '{resolved}' is pruned and cannot be renewed")
        current = self._resolve_now(now)
        record.renewed_at = current
        if ttl_override is not None:
            if ttl_override < 0:
                raise ValueError("ttl_override must be non-negative")
            record.ttl_ticks = ttl_override
        record.lifecycle = LIFECYCLE_ACTIVE
        return record

    def evaluate_expiry(self, now: int | None = None) -> list[str]:
        current = self._resolve_now(now)
        newly_expired: list[str] = []
        for identity in sorted(self._records):
            record = self._records[identity]
            if record.lifecycle == LIFECYCLE_ACTIVE and record.should_expire(current):
                record.lifecycle = LIFECYCLE_EXPIRED
                newly_expired.append(identity)
            if record.lifecycle == LIFECYCLE_EXPIRED:
                grace_elapsed = current - record.expires_at()
                if grace_elapsed >= self._grace_ticks:
                    record.lifecycle = LIFECYCLE_PRUNABLE
        return newly_expired

    def call(self, identity: str, *args: Any, aliases: Mapping[str, str] | None = None, **kwargs: Any) -> Any:
        resolved = self._resolve_identity(identity, aliases)
        record = self._require(resolved)
        self.evaluate_expiry()
        if record.lifecycle != LIFECYCLE_ACTIVE:
            raise ExpiredError(f"API '{resolved}' expired at tick {record.expires_at()}")
        handler = self._handlers.get(resolved)
        if handler is None:
            raise EntityNotFoundError(f"API '{resolved}' has no callable handler")
        return handler(*args, **kwargs)

    def mark_pruned(self, identity: str) -> None:
        record = self._require(identity)
        if record.lifecycle not in (LIFECYCLE_EXPIRED, LIFECYCLE_PRUNABLE):
            raise IdentityError(f"can only prune expired/prunable entities, got '{record.lifecycle}'")
        record.lifecycle = LIFECYCLE_PRUNED

    def get(self, identity: str) -> APIRecord:
        return self._require(identity)

    def expired_names(self) -> list[str]:
        return [
            identity for identity in sorted(self._records)
            if self._records[identity].lifecycle == LIFECYCLE_EXPIRED
        ]

    def prunable_names(self) -> list[str]:
        return [
            identity for identity in sorted(self._records)
            if self._records[identity].lifecycle == LIFECYCLE_PRUNABLE
        ]

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {
            identity: {
                "identity": rec.identity,
                "ttl_ticks": rec.ttl_ticks,
                "registered_at": rec.registered_at,
                "renewed_at": rec.renewed_at,
                "lifecycle": rec.lifecycle,
            }
            for identity, rec in sorted(self._records.items())
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, dict[str, Any]],
        now_provider: Callable[[], int],
        *,
        grace_ticks: int = 0,
    ) -> "APIRegistry":
        registry = cls(now_provider=now_provider, grace_ticks=grace_ticks)
        for key in sorted(payload):
            item = payload[key]
            # Support v0.1 format ("name" + "expired" fields)
            if "name" in item and "identity" not in item:
                record = APIRecord(
                    identity=key,
                    ttl_ticks=item["ttl_ticks"],
                    registered_at=item["registered_at"],
                    renewed_at=item["renewed_at"],
                    lifecycle=LIFECYCLE_EXPIRED if item.get("expired", False) else LIFECYCLE_ACTIVE,
                )
            else:
                record = APIRecord(
                    identity=item["identity"],
                    ttl_ticks=item["ttl_ticks"],
                    registered_at=item["registered_at"],
                    renewed_at=item["renewed_at"],
                    lifecycle=item.get("lifecycle", LIFECYCLE_ACTIVE),
                )
            registry._records[key] = record
        return registry

    def _require(self, identity: str) -> APIRecord:
        record = self._records.get(identity)
        if record is None:
            raise EntityNotFoundError(f"Unknown API '{identity}'")
        return record

    def _resolve_now(self, now: int | None = None) -> int:
        return self._now() if now is None else now

    def _resolve_identity(self, identity: str, aliases: Mapping[str, str] | None = None) -> str:
        canonical = canonicalize_identity(identity)
        if aliases:
            canonical = resolve_alias(canonical, aliases)
        return canonical
