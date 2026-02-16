from entropyos.runtime import EntropyRuntime


def replay() -> dict:
    runtime = EntropyRuntime()

    @runtime.apis.ephemeral_api(ttl_ticks=2)
    def sample() -> dict[str, str]:
        return {"ok": "yes"}

    runtime.decay.register("cold", ttl_ticks=3)
    runtime.store.set("k", 1, ttl_ticks=2)
    runtime.tick(1)
    runtime.decay.touch("cold")
    runtime.tick(2)
    return runtime.status()


def test_tick_replay_is_deterministic() -> None:
    assert replay() == replay()


def test_entropy_score_model() -> None:
    runtime = EntropyRuntime()

    @runtime.apis.ephemeral_api(ttl_ticks=1)
    def sample() -> dict[str, str]:
        return {"ok": "yes"}

    runtime.decay.register("cold", ttl_ticks=1)
    runtime.store.set("k", 1, ttl_ticks=4)
    runtime.tick(1)

    score = runtime.entropy_score()
    assert score["pressure"] == 2
    assert score["mass"] == 3
    assert score["score"] == 0.666667


def test_state_has_no_machine_specific_paths() -> None:
    runtime = EntropyRuntime()

    @runtime.apis.ephemeral_api(ttl_ticks=5)
    def sample() -> dict[str, str]:
        return {"ok": "yes"}

    runtime.decay.register("cold", ttl_ticks=5)
    status = runtime.status()
    api_entry = status["apis"]["sample"]
    decay_entry = status["decay"]["cold"]

    assert "source_path" not in api_entry
    assert "source_line" not in api_entry
    assert "source_path" not in decay_entry
    assert "source_line" not in decay_entry
