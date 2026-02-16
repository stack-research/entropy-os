"""Code path decay tracking and deterministic prune planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .api import APIRegistry


@dataclass(slots=True)
class FunctionRecord:
    name: str
    ttl_ticks: int
    registered_at: int
    last_seen_at: int
    decay_id: str | None = None
    decayed: bool = False

    def expires_at(self) -> int:
        return self.last_seen_at + self.ttl_ticks

    def should_decay(self, now: int) -> bool:
        return now >= self.expires_at()


class CodePathDecayEngine:
    """Tracks function activity and marks unused functions as decayed."""

    def __init__(self, now_provider) -> None:
        self._now = now_provider
        self._records: dict[str, FunctionRecord] = {}

    def register(self, name: str, ttl_ticks: int, decay_id: str | None = None) -> None:
        now = self._now()
        self._records[name] = FunctionRecord(
            name=name,
            ttl_ticks=ttl_ticks,
            registered_at=now,
            last_seen_at=now,
            decay_id=decay_id,
        )

    def track(self, name: str, ttl_ticks: int = 1, decay_id: str | None = None):
        """Decorator that tracks function usage deterministically."""

        def decorator(func):
            self.register(name=name, ttl_ticks=ttl_ticks, decay_id=decay_id)

            def wrapper(*args, **kwargs):
                self.touch(name)
                return func(*args, **kwargs)

            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper

        return decorator

    def touch(self, name: str, now: int | None = None) -> None:
        record = self._records[name]
        current = self._now() if now is None else now
        record.last_seen_at = current
        record.decayed = False

    def evaluate(self, now: int | None = None) -> list[str]:
        current = self._now() if now is None else now
        decayed: list[str] = []
        for name in sorted(self._records):
            record = self._records[name]
            if not record.decayed and record.should_decay(current):
                record.decayed = True
                decayed.append(name)
        return decayed

    def decayed_names(self) -> list[str]:
        return [name for name in sorted(self._records) if self._records[name].decayed]

    def get_record(self, name: str) -> FunctionRecord:
        return self._records[name]

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "name": rec.name,
                "ttl_ticks": rec.ttl_ticks,
                "registered_at": rec.registered_at,
                "last_seen_at": rec.last_seen_at,
                "decay_id": rec.decay_id,
                "decayed": rec.decayed,
            }
            for name, rec in sorted(self._records.items())
        }

    @classmethod
    def from_dict(cls, payload: dict[str, dict[str, Any]], now_provider) -> "CodePathDecayEngine":
        engine = cls(now_provider=now_provider)
        for name in sorted(payload):
            item = payload[name]
            engine._records[name] = FunctionRecord(
                name=item["name"],
                ttl_ticks=item["ttl_ticks"],
                registered_at=item["registered_at"],
                last_seen_at=item["last_seen_at"],
                decay_id=item.get("decay_id"),
                decayed=item["decayed"],
            )
        return engine


def generate_prune_plan(api_registry: APIRegistry, decay_engine: CodePathDecayEngine, tick: int) -> dict[str, Any]:
    """Generate deterministic prune plan from runtime state only."""
    expired_apis = []
    for name in api_registry.expired_names():
        record = api_registry.get(name)
        expired_apis.append(
            {
                "id": f"api:{name}",
                "name": name,
                "ttl_ticks": record.ttl_ticks,
                "expired_at": record.expires_at(),
            }
        )

    decayed_functions = []
    for name in decay_engine.decayed_names():
        record = decay_engine.get_record(name)
        decayed_functions.append(
            {
                "id": f"fn:{record.decay_id or name}",
                "name": name,
                "decay_id": record.decay_id,
                "ttl_ticks": record.ttl_ticks,
                "decayed_at": record.expires_at(),
            }
        )

    return {
        "version": 1,
        "tick": tick,
        "expired_apis": expired_apis,
        "decayed_functions": decayed_functions,
    }


def render_best_effort_patch(prune_plan: dict[str, Any]) -> str:
    """Render an optional developer patch view from a deterministic prune plan."""
    lines = [
        "*** Entropy Patch (best-effort)",
        "# Environment-dependent convenience output from prune plan.",
        "# Apply changes manually after review.",
    ]

    expired_apis = prune_plan.get("expired_apis", [])
    decayed_functions = prune_plan.get("decayed_functions", [])

    if not expired_apis and not decayed_functions:
        lines.append("# Nothing to patch.")
        return "\n".join(lines) + "\n"

    if expired_apis:
        lines.append("## Remove expired APIs")
        for item in expired_apis:
            lines.append(f"- {item['id']}")

    if decayed_functions:
        lines.append("## Remove decayed functions")
        for item in decayed_functions:
            lines.append(f"- {item['id']}")

    return "\n".join(lines) + "\n"
