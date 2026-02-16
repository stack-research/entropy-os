from entropyos.runtime import EntropyRuntime


def test_prune_plan_is_deterministic_and_state_only() -> None:
    runtime = EntropyRuntime()

    @runtime.apis.ephemeral_api(ttl_ticks=1)
    def old_api() -> dict[str, str]:
        return {"status": "ok"}

    runtime.decay.register("unused_func", ttl_ticks=1, decay_id="core/unused_func")

    runtime.tick(1)
    plan = runtime.prune_plan()
    plan_again = runtime.prune_plan()

    assert plan == plan_again
    assert plan["version"] == 1
    assert plan["tick"] == 1
    assert plan["expired_apis"] == [
        {
            "id": "api:old_api",
            "name": "old_api",
            "ttl_ticks": 1,
            "expired_at": 1,
        }
    ]
    assert plan["decayed_functions"] == [
        {
            "id": "fn:core/unused_func",
            "name": "unused_func",
            "decay_id": "core/unused_func",
            "ttl_ticks": 1,
            "decayed_at": 1,
        }
    ]


def test_patch_preview_is_labeled_best_effort() -> None:
    runtime = EntropyRuntime()
    runtime.decay.register("missing_fn", ttl_ticks=1)
    runtime.tick(1)
    patch = runtime.patch_preview()

    assert "best-effort" in patch
    assert "fn:missing_fn" in patch
