"""Integration tests for v0.2 identity wiring across the full runtime path."""

import json
from pathlib import Path

import pytest

from entropyos.errors import EntityNotFoundError, ExpiredError
from entropyos.identity import (
    AliasCycleError,
    IdentityError,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_EXPIRED,
    LIFECYCLE_PRUNABLE,
    LIFECYCLE_PRUNED,
    canonicalize_aliases,
)
from entropyos.runtime import EntropyRuntime


# --- 1.1 Canonical identities in registries ---


class TestCanonicalIdentities:
    def test_api_registry_requires_canonical_identity(self) -> None:
        runtime = EntropyRuntime()
        with pytest.raises(IdentityError):
            runtime.apis.register("bare_name", None, ttl_ticks=5)

    def test_api_registry_requires_api_prefix(self) -> None:
        runtime = EntropyRuntime()
        with pytest.raises(IdentityError):
            runtime.apis.register("fn:wrong/prefix", None, ttl_ticks=5)

    def test_api_register_and_call_with_canonical_id(self) -> None:
        runtime = EntropyRuntime()
        runtime.apis.register("api:core/users.get", lambda: {"ok": True}, ttl_ticks=5)
        assert runtime.apis.call("api:core/users.get") == {"ok": True}

    def test_decay_engine_requires_canonical_identity(self) -> None:
        runtime = EntropyRuntime()
        with pytest.raises(IdentityError):
            runtime.decay.register("bare_name", ttl_ticks=5)

    def test_decay_engine_requires_fn_prefix(self) -> None:
        runtime = EntropyRuntime()
        with pytest.raises(IdentityError):
            runtime.decay.register("api:wrong/prefix", ttl_ticks=5)

    def test_decay_register_and_track(self) -> None:
        runtime = EntropyRuntime()
        runtime.decay.register("fn:ml/embed", ttl_ticks=3)
        runtime.tick(2)
        runtime.decay.touch("fn:ml/embed")
        runtime.tick(2)
        # Should still be active because touch reset the timer
        record = runtime.decay.get_record("fn:ml/embed")
        assert record.lifecycle == LIFECYCLE_ACTIVE

    def test_ttl_store_validates_keys(self) -> None:
        runtime = EntropyRuntime()
        with pytest.raises(IdentityError):
            runtime.store.set("key with spaces", 1, ttl_ticks=5)
        with pytest.raises(IdentityError):
            runtime.store.set("key/../traversal", 1, ttl_ticks=5)

    def test_ttl_store_accepts_valid_keys(self) -> None:
        runtime = EntropyRuntime()
        runtime.store.set("session/user:1234", {"name": "alice"}, ttl_ticks=5)
        assert runtime.store.get("session/user:1234") == {"name": "alice"}

    def test_full_registration_path_with_canonical_ids(self) -> None:
        runtime = EntropyRuntime()
        runtime.apis.register("api:core/users.get", lambda uid: uid, ttl_ticks=3)
        runtime.decay.register("fn:core/onboard", ttl_ticks=5)
        runtime.store.set("cache/feature_flags", {"dark_mode": True}, ttl_ticks=10)

        status = runtime.status()
        assert "api:core/users.get" in status["apis"]
        assert "fn:core/onboard" in status["decay"]
        assert "cache/feature_flags" in status["state"]


# --- 1.2 Alias file loading and resolution ---


class TestAliasResolution:
    def test_alias_resolution_on_api_call(self) -> None:
        aliases = canonicalize_aliases({
            "api:legacy/users.fetch": "api:core/users.get",
        })
        runtime = EntropyRuntime(aliases=aliases)
        runtime.apis.register("api:core/users.get", lambda: "ok", ttl_ticks=5)
        assert runtime.apis.call("api:legacy/users.fetch", aliases=aliases) == "ok"

    def test_alias_resolution_on_renew(self) -> None:
        aliases = canonicalize_aliases({
            "api:old/endpoint": "api:core/endpoint",
        })
        runtime = EntropyRuntime(aliases=aliases)
        runtime.apis.register("api:core/endpoint", lambda: "ok", ttl_ticks=2)
        runtime.tick(2)
        # Renew via alias
        runtime.apis.renew("api:old/endpoint", aliases=aliases)
        record = runtime.apis.get("api:core/endpoint")
        assert record.lifecycle == LIFECYCLE_ACTIVE

    def test_alias_chain_resolution(self) -> None:
        aliases = canonicalize_aliases({
            "api:v1/users": "api:v2/users",
            "api:v2/users": "api:v3/users",
        })
        runtime = EntropyRuntime(aliases=aliases)
        runtime.apis.register("api:v3/users", lambda: "v3", ttl_ticks=5)
        assert runtime.apis.call("api:v1/users", aliases=aliases) == "v3"

    def test_alias_cycle_rejected(self) -> None:
        with pytest.raises(AliasCycleError):
            canonicalize_aliases({
                "api:core/a": "api:core/b",
                "api:core/b": "api:core/a",
            })

    def test_runtime_renew_resolves_aliases(self) -> None:
        aliases = canonicalize_aliases({
            "fn:old/path": "fn:new/path",
        })
        runtime = EntropyRuntime(aliases=aliases)
        runtime.decay.register("fn:new/path", ttl_ticks=3)
        runtime.tick(3)
        runtime.renew("fn:old/path")
        record = runtime.decay.get_record("fn:new/path")
        assert record.lifecycle == LIFECYCLE_ACTIVE


# --- 1.3 --ttl override on renew ---


class TestTTLOverride:
    def test_api_renew_with_ttl_override(self) -> None:
        runtime = EntropyRuntime()
        runtime.apis.register("api:core/fast", None, ttl_ticks=2)
        runtime.tick(2)
        runtime.apis.renew("api:core/fast", ttl_override=10)
        record = runtime.apis.get("api:core/fast")
        assert record.ttl_ticks == 10
        assert record.lifecycle == LIFECYCLE_ACTIVE

    def test_api_renew_without_override_keeps_original_ttl(self) -> None:
        runtime = EntropyRuntime()
        runtime.apis.register("api:core/fast", None, ttl_ticks=5)
        runtime.tick(5)
        runtime.apis.renew("api:core/fast")
        record = runtime.apis.get("api:core/fast")
        assert record.ttl_ticks == 5

    def test_fn_renew_with_ttl_override(self) -> None:
        runtime = EntropyRuntime()
        runtime.decay.register("fn:core/compute", ttl_ticks=3)
        runtime.tick(3)
        runtime.decay.renew("fn:core/compute", ttl_override=20)
        record = runtime.decay.get_record("fn:core/compute")
        assert record.ttl_ticks == 20
        assert record.lifecycle == LIFECYCLE_ACTIVE

    def test_runtime_renew_with_ttl_override(self) -> None:
        runtime = EntropyRuntime()
        runtime.apis.register("api:core/slow", None, ttl_ticks=1)
        runtime.tick(1)
        runtime.renew("api:core/slow", ttl_override=50)
        record = runtime.apis.get("api:core/slow")
        assert record.ttl_ticks == 50

    def test_negative_ttl_override_rejected(self) -> None:
        runtime = EntropyRuntime()
        runtime.apis.register("api:core/x", None, ttl_ticks=5)
        runtime.tick(5)
        with pytest.raises(ValueError):
            runtime.apis.renew("api:core/x", ttl_override=-1)


# --- 1.4 Lifecycle states ---


class TestLifecycleStates:
    def test_active_to_expired_transition(self) -> None:
        runtime = EntropyRuntime()
        runtime.apis.register("api:core/ephemeral", None, ttl_ticks=3)
        runtime.tick(3)
        record = runtime.apis.get("api:core/ephemeral")
        # With grace_ticks=0, goes straight to prunable
        assert record.lifecycle == LIFECYCLE_PRUNABLE

    def test_grace_window_delays_prunable(self) -> None:
        runtime = EntropyRuntime(grace_ticks=2)
        runtime.apis.register("api:core/graceful", None, ttl_ticks=3)
        runtime.tick(3)
        record = runtime.apis.get("api:core/graceful")
        assert record.lifecycle == LIFECYCLE_EXPIRED

        runtime.tick(1)
        record = runtime.apis.get("api:core/graceful")
        assert record.lifecycle == LIFECYCLE_EXPIRED

        runtime.tick(1)
        record = runtime.apis.get("api:core/graceful")
        assert record.lifecycle == LIFECYCLE_PRUNABLE

    def test_pruned_terminal_state(self) -> None:
        runtime = EntropyRuntime()
        runtime.apis.register("api:core/old", None, ttl_ticks=1)
        runtime.tick(1)
        runtime.apis.mark_pruned("api:core/old")
        record = runtime.apis.get("api:core/old")
        assert record.lifecycle == LIFECYCLE_PRUNED

    def test_pruned_cannot_be_renewed(self) -> None:
        runtime = EntropyRuntime()
        runtime.apis.register("api:core/dead", None, ttl_ticks=1)
        runtime.tick(1)
        runtime.apis.mark_pruned("api:core/dead")
        with pytest.raises(ExpiredError):
            runtime.apis.renew("api:core/dead")

    def test_renewal_resets_lifecycle_to_active(self) -> None:
        runtime = EntropyRuntime(grace_ticks=5)
        runtime.apis.register("api:core/temp", None, ttl_ticks=2)
        runtime.tick(2)
        record = runtime.apis.get("api:core/temp")
        assert record.lifecycle == LIFECYCLE_EXPIRED
        runtime.apis.renew("api:core/temp")
        assert record.lifecycle == LIFECYCLE_ACTIVE

    def test_function_lifecycle_states(self) -> None:
        runtime = EntropyRuntime()
        runtime.decay.register("fn:core/old_func", ttl_ticks=2)
        runtime.tick(2)
        record = runtime.decay.get_record("fn:core/old_func")
        assert record.lifecycle == LIFECYCLE_PRUNABLE  # grace_ticks=0

    def test_function_grace_window(self) -> None:
        runtime = EntropyRuntime(grace_ticks=3)
        runtime.decay.register("fn:core/slow_decay", ttl_ticks=2)
        runtime.tick(2)
        record = runtime.decay.get_record("fn:core/slow_decay")
        assert record.lifecycle == LIFECYCLE_EXPIRED
        runtime.tick(3)
        record = runtime.decay.get_record("fn:core/slow_decay")
        assert record.lifecycle == LIFECYCLE_PRUNABLE

    def test_apply_prune_marks_prunable_as_pruned(self) -> None:
        runtime = EntropyRuntime()
        runtime.apis.register("api:core/a", None, ttl_ticks=1)
        runtime.decay.register("fn:core/b", ttl_ticks=1)
        runtime.store.set("cache/c", "val", ttl_ticks=1)
        runtime.tick(1)

        pruned = runtime.apply_prune()
        assert "api:core/a" in pruned["api"]
        assert "fn:core/b" in pruned["fn"]
        assert "state:cache/c" in pruned["state"]

        # APIs and functions are marked pruned
        assert runtime.apis.get("api:core/a").lifecycle == LIFECYCLE_PRUNED
        assert runtime.decay.get_record("fn:core/b").lifecycle == LIFECYCLE_PRUNED
        # State entries are actually deleted
        assert "cache/c" not in runtime.store.keys()

    def test_prune_plan_groups_by_expired_and_prunable(self) -> None:
        runtime = EntropyRuntime(grace_ticks=5)
        runtime.apis.register("api:core/soon", None, ttl_ticks=1)
        runtime.apis.register("api:core/later", None, ttl_ticks=1)
        runtime.tick(1)
        # Both expired, not yet prunable (grace_ticks=5)
        plan = runtime.prune_plan()
        assert "api:core/soon" in plan["expired"]["api"]
        assert "api:core/later" in plan["expired"]["api"]
        assert plan["prunable"]["api"] == []

        runtime.tick(5)
        plan = runtime.prune_plan()
        assert plan["expired"]["api"] == []
        assert "api:core/soon" in plan["prunable"]["api"]
        assert "api:core/later" in plan["prunable"]["api"]

    def test_cannot_prune_active_entity(self) -> None:
        runtime = EntropyRuntime()
        runtime.apis.register("api:core/active", None, ttl_ticks=100)
        with pytest.raises(IdentityError):
            runtime.apis.mark_pruned("api:core/active")


# --- 1.5 entropy migrate (CLI test) ---


class TestMigrateCLI:
    def test_migrate_suggests_canonical_mappings(self, tmp_path) -> None:
        """Migrate reads v0.1 state and suggests canonical identities."""
        from entropyos.cli import main

        state_dir = tmp_path / ".entropy"
        state_dir.mkdir()
        state_file = state_dir / "state.json"
        # v0.1 state with bare names
        v01_state = {
            "tick": 5,
            "entropy_score": {"score": 0.5, "pressure": 1, "mass": 2,
                              "expired_apis": 1, "decayed_functions": 0,
                              "active_apis": 0, "active_functions": 1, "state_keys": 1},
            "apis": {
                "fast_api": {
                    "name": "fast_api",
                    "ttl_ticks": 2,
                    "registered_at": 0,
                    "renewed_at": 0,
                    "expired": True,
                }
            },
            "decay": {
                "cold_path": {
                    "name": "cold_path",
                    "ttl_ticks": 3,
                    "registered_at": 0,
                    "last_seen_at": 0,
                    "decay_id": None,
                    "decayed": True,
                }
            },
            "state": {
                "session": {
                    "value": {"user": "alice"},
                    "created_at": 0,
                    "ttl_ticks": 2,
                }
            },
        }
        state_file.write_text(json.dumps(v01_state), encoding="utf-8")

        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main(["migrate"])
            assert result == 0
        finally:
            os.chdir(old_cwd)


# --- Full integration: register, tick, expire, renew via alias ---


class TestFullRuntimeIntegration:
    def test_register_tick_expire_renew_via_alias(self) -> None:
        aliases = canonicalize_aliases({
            "api:legacy/fetch": "api:core/users.get",
        })
        runtime = EntropyRuntime(aliases=aliases)

        # Register with canonical ID
        runtime.apis.register("api:core/users.get", lambda: {"users": []}, ttl_ticks=3)

        # Active and callable
        assert runtime.apis.call("api:core/users.get") == {"users": []}

        # Tick past TTL
        runtime.tick(3)
        with pytest.raises(ExpiredError):
            runtime.apis.call("api:core/users.get")

        # Renew via alias
        runtime.renew("api:legacy/fetch")
        assert runtime.apis.call("api:core/users.get") == {"users": []}

    def test_serialization_roundtrip_with_canonical_ids(self) -> None:
        runtime = EntropyRuntime()
        runtime.apis.register("api:core/endpoint", None, ttl_ticks=5)
        runtime.decay.register("fn:ml/pipeline", ttl_ticks=10)
        runtime.store.set("session/token", "abc123", ttl_ticks=20)
        runtime.tick(3)

        state = runtime.to_dict()
        restored = EntropyRuntime.from_dict(state)

        assert restored.status() == runtime.status()

    def test_v01_state_loads_with_compat(self) -> None:
        """v0.1 state with bare names loads via from_dict compat path."""
        v01_state = {
            "tick": 5,
            "apis": {
                "fast_api": {
                    "name": "fast_api",
                    "ttl_ticks": 2,
                    "registered_at": 0,
                    "renewed_at": 0,
                    "expired": True,
                }
            },
            "decay": {
                "cold_path": {
                    "name": "cold_path",
                    "ttl_ticks": 3,
                    "registered_at": 0,
                    "last_seen_at": 0,
                    "decay_id": None,
                    "decayed": True,
                }
            },
            "state": {},
        }
        runtime = EntropyRuntime.from_dict(v01_state)
        status = runtime.status()
        assert status["tick"] == 5
        # v0.1 records loaded with lifecycle mapping
        api_record = status["apis"]["fast_api"]
        assert api_record["lifecycle"] == "expired"

    def test_expired_state_keys_appear_in_prune_plan(self) -> None:
        runtime = EntropyRuntime()
        runtime.store.set("cache/temp", "data", ttl_ticks=2)
        runtime.tick(3)

        plan = runtime.prune_plan()
        assert "state:cache/temp" in plan["expired"]["state"]
