from entropyos.errors import ExpiredError
from entropyos.runtime import EntropyRuntime


def test_api_expires_and_can_be_renewed() -> None:
    runtime = EntropyRuntime()

    @runtime.apis.ephemeral_api(ttl_ticks=3)
    def get_user_data(user_id: str) -> dict[str, str]:
        return {"id": user_id}

    assert runtime.apis.call("get_user_data", "u1") == {"id": "u1"}

    runtime.tick(3)
    try:
        runtime.apis.call("get_user_data", "u1")
        assert False, "expected ExpiredError"
    except ExpiredError:
        pass

    runtime.apis.renew("get_user_data")
    assert runtime.apis.call("get_user_data", "u2") == {"id": "u2"}
