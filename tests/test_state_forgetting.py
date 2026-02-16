import pytest

from entropyos.errors import ExpiredStateError
from entropyos.runtime import EntropyRuntime


def test_state_forgetting_removes_expired_keys() -> None:
    runtime = EntropyRuntime()
    runtime.store.set("token", "abc", ttl_ticks=2)

    assert runtime.store.get("token") == "abc"

    runtime.tick(2)

    with pytest.raises(ExpiredStateError):
        runtime.store.get("token")

    assert "token" not in runtime.store.keys()
