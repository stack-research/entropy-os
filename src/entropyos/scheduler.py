"""Deterministic decay scheduler."""

from __future__ import annotations

from dataclasses import dataclass

from .api import APIRegistry
from .decay import CodePathDecayEngine
from .store import TTLStore


@dataclass(slots=True)
class SchedulerEvent:
    tick: int
    expired_apis: list[str]
    decayed_functions: list[str]
    purged_keys: list[str]


class DecayScheduler:
    """Evaluates all time-bound transitions for a given logical tick."""

    def run_tick(self, tick: int, api_registry: APIRegistry, decay_engine: CodePathDecayEngine, store: TTLStore) -> SchedulerEvent:
        expired_apis = api_registry.evaluate_expiry(now=tick)
        decayed_functions = decay_engine.evaluate(now=tick)
        # State expiry is enforced at read-time, so we avoid implicit purge.
        purged_keys: list[str] = []
        return SchedulerEvent(
            tick=tick,
            expired_apis=expired_apis,
            decayed_functions=decayed_functions,
            purged_keys=purged_keys,
        )
