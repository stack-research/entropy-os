from entropyos.serde import dumps_canonical_json


def test_canonical_json_is_stable_and_trailing_newline() -> None:
    payload = {"b": 1, "a": 2}
    rendered = dumps_canonical_json(payload)

    assert rendered == '{\n  "a": 2,\n  "b": 1\n}\n'
