"""Pure runtime composition for entropy-driven behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .api import APIRegistry
from .decay import CodePathDecayEngine, generate_prune_plan, render_best_effort_patch
from .identity import LIFECYCLE_ACTIVE, LIFECYCLE_EXPIRED, LIFECYCLE_PRUNABLE, LIFECYCLE_PRUNED
from .scheduler import DecayScheduler, SchedulerEvent
from .store import TTLStore
from .ttl import LogicalClock


@dataclass(slots=True)
class EntropyRuntime:
    clock: LogicalClock = field(default_factory=LogicalClock)
    scheduler: DecayScheduler = field(default_factory=DecayScheduler)
    aliases: dict[str, str] = field(default_factory=dict)
    grace_ticks: int = 0
    apis: APIRegistry = field(init=False)
    decay: CodePathDecayEngine = field(init=False)
    store: TTLStore = field(init=False)

    def __post_init__(self) -> None:
        now_provider = self.clock.now
        self.apis = APIRegistry(now_provider=now_provider, grace_ticks=self.grace_ticks)
        self.decay = CodePathDecayEngine(now_provider=now_provider, grace_ticks=self.grace_ticks)
        self.store = TTLStore(now_provider=now_provider)

    def tick(self, n: int = 1) -> list[SchedulerEvent]:
        events: list[SchedulerEvent] = []
        for _ in range(n):
            current = self.clock.tick(1)
            events.append(self.scheduler.run_tick(current, self.apis, self.decay, self.store))
        return events

    def renew(self, identity: str, *, ttl_override: int | None = None) -> None:
        """Renew an entity by canonical identity, dispatching by kind prefix."""
        if identity.startswith("api:"):
            self.apis.renew(identity, aliases=self.aliases, ttl_override=ttl_override)
        elif identity.startswith("fn:"):
            self.decay.renew(identity, aliases=self.aliases, ttl_override=ttl_override)
        else:
            raise ValueError(f"cannot renew identity with unknown kind: {identity}")

    def apply_prune(self) -> dict[str, list[str]]:
        """Mark all prunable entities as pruned. Returns pruned IDs by kind."""
        pruned: dict[str, list[str]] = {"api": [], "fn": [], "state": []}
        for identity in self.apis.prunable_names():
            self.apis.mark_pruned(identity)
            pruned["api"].append(identity)
        for identity in self.decay.prunable_names():
            self.decay.mark_pruned(identity)
            pruned["fn"].append(identity)
        # State entries are purged (deleted) rather than marked
        purged_keys = self.store.purge_expired(now=self.clock.now())
        for key in purged_keys:
            pruned["state"].append(f"state:{key}")
        return pruned

    def status(self) -> dict[str, Any]:
        entropy_score = self.entropy_score()
        return {
            "tick": self.clock.now(),
            "entropy_score": entropy_score,
            "apis": self.apis.to_dict(),
            "decay": self.decay.to_dict(),
            "state": self.store.to_dict(),
        }

    def prune_plan(self) -> dict[str, Any]:
        return generate_prune_plan(
            self.apis,
            self.decay,
            self.store,
            tick=self.clock.now(),
            aliases_applied=bool(self.aliases),
        )

    def patch_preview(self) -> str:
        return render_best_effort_patch(self.prune_plan())

    def to_dict(self) -> dict[str, Any]:
        return self.status()

    def entropy_score(self) -> dict[str, Any]:
        """
        Formal model:
          pressure = expired_apis + decayed_functions
          mass = total_apis + total_functions + total_state_keys
          score = pressure / max(mass, 1)
        """
        apis = self.apis.to_dict()
        decay = self.decay.to_dict()
        state = self.store.to_dict()

        total_apis = len(apis)
        expired_apis = sum(
            1 for item in apis.values()
            if item.get("lifecycle", LIFECYCLE_ACTIVE) != LIFECYCLE_ACTIVE
        )
        total_functions = len(decay)
        decayed_functions = sum(
            1 for item in decay.values()
            if item.get("lifecycle", LIFECYCLE_ACTIVE) != LIFECYCLE_ACTIVE
        )
        total_state_keys = len(state)

        pressure = expired_apis + decayed_functions
        mass = total_apis + total_functions + total_state_keys
        score = pressure / (mass if mass else 1)

        return {
            "score": round(score, 6),
            "pressure": pressure,
            "mass": mass,
            "expired_apis": expired_apis,
            "decayed_functions": decayed_functions,
            "active_apis": total_apis - expired_apis,
            "active_functions": total_functions - decayed_functions,
            "state_keys": total_state_keys,
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
        *,
        aliases: dict[str, str] | None = None,
        grace_ticks: int = 0,
    ) -> "EntropyRuntime":
        runtime = cls(
            clock=LogicalClock(epoch=payload["tick"]),
            aliases=aliases or {},
            grace_ticks=grace_ticks,
        )
        runtime.apis = APIRegistry.from_dict(
            payload.get("apis", {}),
            now_provider=runtime.clock.now,
            grace_ticks=grace_ticks,
        )
        runtime.decay = CodePathDecayEngine.from_dict(
            payload.get("decay", {}),
            now_provider=runtime.clock.now,
            grace_ticks=grace_ticks,
        )
        runtime.store = TTLStore.from_dict(
            payload.get("state", {}),
            now_provider=runtime.clock.now,
        )
        return runtime
