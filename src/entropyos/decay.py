"""Code path decay tracking and deterministic prune planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .api import APIRegistry
from .identity import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_EXPIRED,
    LIFECYCLE_PRUNABLE,
    LIFECYCLE_PRUNED,
    IdentityError,
    build_prune_plan,
    canonicalize_identity,
    resolve_alias,
    state_identity_from_key,
)
from .store import TTLStore


@dataclass(slots=True)
class FunctionRecord:
    identity: str
    ttl_ticks: int
    registered_at: int
    last_seen_at: int
    decay_id: str | None = None
    lifecycle: str = LIFECYCLE_ACTIVE

    def expires_at(self) -> int:
        return self.last_seen_at + self.ttl_ticks

    def should_decay(self, now: int) -> bool:
        return now >= self.expires_at()


class CodePathDecayEngine:
    """Tracks function activity and marks unused functions as decayed."""

    def __init__(self, now_provider, *, grace_ticks: int = 0) -> None:
        self._now = now_provider
        self._records: dict[str, FunctionRecord] = {}
        self._grace_ticks = grace_ticks

    def register(self, identity: str, ttl_ticks: int, decay_id: str | None = None) -> None:
        identity = canonicalize_identity(identity)
        if not identity.startswith("fn:"):
            raise IdentityError("function identity must have 'fn:' prefix")
        now = self._now()
        self._records[identity] = FunctionRecord(
            identity=identity,
            ttl_ticks=ttl_ticks,
            registered_at=now,
            last_seen_at=now,
            decay_id=decay_id,
        )

    def track(self, identity: str, ttl_ticks: int = 1, decay_id: str | None = None):
        """Decorator that tracks function usage deterministically."""

        def decorator(func):
            self.register(identity=identity, ttl_ticks=ttl_ticks, decay_id=decay_id)

            def wrapper(*args, **kwargs):
                self.touch(identity)
                return func(*args, **kwargs)

            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper

        return decorator

    def touch(self, identity: str, now: int | None = None) -> None:
        record = self._records[identity]
        current = self._now() if now is None else now
        record.last_seen_at = current
        record.lifecycle = LIFECYCLE_ACTIVE

    def renew(
        self,
        identity: str,
        now: int | None = None,
        *,
        aliases: Mapping[str, str] | None = None,
        ttl_override: int | None = None,
    ) -> FunctionRecord:
        resolved = self._resolve_identity(identity, aliases)
        record = self._records.get(resolved)
        if record is None:
            raise KeyError(f"Unknown function '{resolved}'")
        if record.lifecycle == LIFECYCLE_PRUNED:
            raise IdentityError(f"Function '{resolved}' is pruned and cannot be renewed")
        current = self._now() if now is None else now
        record.last_seen_at = current
        if ttl_override is not None:
            if ttl_override < 0:
                raise ValueError("ttl_override must be non-negative")
            record.ttl_ticks = ttl_override
        record.lifecycle = LIFECYCLE_ACTIVE
        return record

    def evaluate(self, now: int | None = None) -> list[str]:
        current = self._now() if now is None else now
        newly_decayed: list[str] = []
        for identity in sorted(self._records):
            record = self._records[identity]
            if record.lifecycle == LIFECYCLE_ACTIVE and record.should_decay(current):
                record.lifecycle = LIFECYCLE_EXPIRED
                newly_decayed.append(identity)
            if record.lifecycle == LIFECYCLE_EXPIRED:
                grace_elapsed = current - record.expires_at()
                if grace_elapsed >= self._grace_ticks:
                    record.lifecycle = LIFECYCLE_PRUNABLE
        return newly_decayed

    def mark_pruned(self, identity: str) -> None:
        record = self._records.get(identity)
        if record is None:
            raise KeyError(f"Unknown function '{identity}'")
        if record.lifecycle not in (LIFECYCLE_EXPIRED, LIFECYCLE_PRUNABLE):
            raise IdentityError(f"can only prune expired/prunable entities, got '{record.lifecycle}'")
        record.lifecycle = LIFECYCLE_PRUNED

    def decayed_names(self) -> list[str]:
        return [
            identity for identity in sorted(self._records)
            if self._records[identity].lifecycle in (LIFECYCLE_EXPIRED, LIFECYCLE_PRUNABLE)
        ]

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

    def get_record(self, identity: str) -> FunctionRecord:
        return self._records[identity]

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {
            identity: {
                "identity": rec.identity,
                "ttl_ticks": rec.ttl_ticks,
                "registered_at": rec.registered_at,
                "last_seen_at": rec.last_seen_at,
                "decay_id": rec.decay_id,
                "lifecycle": rec.lifecycle,
            }
            for identity, rec in sorted(self._records.items())
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, dict[str, Any]],
        now_provider,
        *,
        grace_ticks: int = 0,
    ) -> "CodePathDecayEngine":
        engine = cls(now_provider=now_provider, grace_ticks=grace_ticks)
        for key in sorted(payload):
            item = payload[key]
            # Support v0.1 format ("name" + "decayed" fields)
            if "name" in item and "identity" not in item:
                engine._records[key] = FunctionRecord(
                    identity=key,
                    ttl_ticks=item["ttl_ticks"],
                    registered_at=item["registered_at"],
                    last_seen_at=item["last_seen_at"],
                    decay_id=item.get("decay_id"),
                    lifecycle=LIFECYCLE_EXPIRED if item.get("decayed", False) else LIFECYCLE_ACTIVE,
                )
            else:
                engine._records[key] = FunctionRecord(
                    identity=item["identity"],
                    ttl_ticks=item["ttl_ticks"],
                    registered_at=item["registered_at"],
                    last_seen_at=item["last_seen_at"],
                    decay_id=item.get("decay_id"),
                    lifecycle=item.get("lifecycle", LIFECYCLE_ACTIVE),
                )
        return engine

    def _resolve_identity(self, identity: str, aliases: Mapping[str, str] | None = None) -> str:
        canonical = canonicalize_identity(identity)
        if aliases:
            canonical = resolve_alias(canonical, aliases)
        return canonical


def generate_prune_plan(
    api_registry: APIRegistry,
    decay_engine: "CodePathDecayEngine",
    store: TTLStore,
    tick: int,
    *,
    aliases_applied: bool = False,
) -> dict[str, Any]:
    """Generate deterministic v0.2 prune plan from runtime state."""
    expired_ids: list[str] = []
    prunable_ids: list[str] = []

    # APIs
    for identity in api_registry.expired_names():
        expired_ids.append(identity)
    for identity in api_registry.prunable_names():
        prunable_ids.append(identity)

    # Functions
    for identity in decay_engine.expired_names():
        expired_ids.append(identity)
    for identity in decay_engine.prunable_names():
        prunable_ids.append(identity)

    # State entries
    for key in store.expired_keys(now=tick):
        expired_ids.append(state_identity_from_key(key))

    return build_prune_plan(
        generated_at_tick=tick,
        expired_ids=expired_ids,
        prunable_ids=prunable_ids,
        aliases_applied=aliases_applied,
    )


def render_best_effort_patch(prune_plan: dict[str, Any]) -> str:
    """Render an optional developer patch view from a deterministic prune plan."""
    lines = [
        "*** Entropy Patch (best-effort)",
        "# Environment-dependent convenience output from prune plan.",
        "# Apply changes manually after review.",
    ]

    expired = prune_plan.get("expired", {})
    prunable = prune_plan.get("prunable", {})

    has_entries = any(expired.get(k) for k in ("api", "fn", "state")) or any(
        prunable.get(k) for k in ("api", "fn", "state")
    )

    if not has_entries:
        lines.append("# Nothing to patch.")
        return "\n".join(lines) + "\n"

    for kind in ("api", "fn", "state"):
        ids = expired.get(kind, [])
        if ids:
            lines.append(f"## Expired {kind}")
            for entity_id in ids:
                lines.append(f"- {entity_id}")

    for kind in ("api", "fn", "state"):
        ids = prunable.get(kind, [])
        if ids:
            lines.append(f"## Prunable {kind}")
            for entity_id in ids:
                lines.append(f"- {entity_id}")

    return "\n".join(lines) + "\n"
