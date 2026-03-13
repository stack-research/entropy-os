from entropyos.runtime import EntropyRuntime


def test_prune_plan_is_deterministic_and_state_only() -> None:
    runtime = EntropyRuntime()

    @runtime.apis.ephemeral_api("api:test/old_api", ttl_ticks=1)
    def old_api() -> dict[str, str]:
        return {"status": "ok"}

    runtime.decay.register("fn:core/unused_func", ttl_ticks=1, decay_id="core/unused_func")

    runtime.tick(1)
    plan = runtime.prune_plan()
    plan_again = runtime.prune_plan()

    assert plan == plan_again
    assert plan["version"] == 1
    assert plan["generated_at_tick"] == 1
    assert "api:test/old_api" in plan["prunable"]["api"]
    assert "fn:core/unused_func" in plan["prunable"]["fn"]


def test_patch_preview_is_labeled_best_effort() -> None:
    runtime = EntropyRuntime()
    runtime.decay.register("fn:test/missing_fn", ttl_ticks=1)
    runtime.tick(1)
    patch = runtime.patch_preview()

    assert "best-effort" in patch
    assert "fn:test/missing_fn" in patch
