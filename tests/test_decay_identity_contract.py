import json
from pathlib import Path

import pytest

from entropyos.identity import (
    AliasCycleError,
    IdentityError,
    build_prune_plan,
    canonicalize_aliases,
    canonicalize_identity,
    canonicalize_persisted_records,
    canonicalize_state_key,
    renew_record,
    resolve_alias,
    state_identity_from_key,
)


def test_canonicalization_stable_and_rejects_invalid_ids() -> None:
    assert canonicalize_identity("  api:core/users.get  ") == "api:core/users.get"
    assert canonicalize_state_key(" cache/feature_flags ") == "cache/feature_flags"
    assert state_identity_from_key("session/user:1234") == "state:session/user:1234"

    with pytest.raises(IdentityError):
        canonicalize_identity("api:core users.get")
    with pytest.raises(IdentityError):
        canonicalize_identity("api:core/../users.get")
    with pytest.raises(IdentityError):
        canonicalize_identity("api:core\\users.get")
    with pytest.raises(IdentityError):
        canonicalize_identity("unknown:core/users.get")


def test_alias_resolution_is_deterministic_and_detects_cycles() -> None:
    aliases = canonicalize_aliases(
        {
            "api:core/users.fetch": "api:core/users.get",
            "api:legacy/users.fetch": "api:core/users.fetch",
        }
    )
    assert resolve_alias("api:legacy/users.fetch", aliases) == "api:core/users.get"
    assert resolve_alias("api:core/users.fetch", aliases) == "api:core/users.get"

    with pytest.raises(AliasCycleError):
        canonicalize_aliases(
            {
                "api:core/a": "api:core/b",
                "api:core/b": "api:core/a",
            }
        )


def test_renewal_through_alias_renews_canonical_record() -> None:
    records = {
        "api:core/users.get": {
            "ttl_ticks": 10,
            "last_renewed_tick": 0,
            "expires_at_tick": 10,
        }
    }
    aliases = {"api:core/users.fetch": "api:core/users.get"}

    renewed_id = renew_record(records, identity="api:core/users.fetch", aliases=aliases, now_tick=7)

    assert renewed_id == "api:core/users.get"
    assert records["api:core/users.get"]["last_renewed_tick"] == 7
    assert records["api:core/users.get"]["expires_at_tick"] == 17


def test_prune_plan_output_is_stable_and_sorted() -> None:
    plan_a = build_prune_plan(
        generated_at_tick=123,
        expired_ids=[
            "fn:core/zeta",
            "api:core/b",
            "state:cache/feature_flags",
            "api:core/a",
        ],
        prunable_ids=["fn:core/alpha", "state:session/user:1", "api:core/c"],
        aliases_applied=True,
        notes=["second", "first"],
    )

    plan_b = build_prune_plan(
        generated_at_tick=123,
        expired_ids=[
            "api:core/a",
            "state:cache/feature_flags",
            "api:core/b",
            "fn:core/zeta",
        ],
        prunable_ids=["api:core/c", "state:session/user:1", "fn:core/alpha"],
        aliases_applied=True,
        notes=["first", "second"],
    )

    assert plan_a == plan_b
    assert plan_a["expired"]["api"] == ["api:core/a", "api:core/b"]
    assert plan_a["expired"]["fn"] == ["fn:core/zeta"]
    assert plan_a["expired"]["state"] == ["state:cache/feature_flags"]
    assert plan_a["prunable"]["api"] == ["api:core/c"]
    assert plan_a["prunable"]["fn"] == ["fn:core/alpha"]
    assert plan_a["prunable"]["state"] == ["state:session/user:1"]


def test_persisted_state_contains_only_canonical_ids() -> None:
    raw_records = {
        "api:core/users.fetch": {"ttl_ticks": 5},
        "fn:core/onboarding.audit": {"ttl_ticks": 9},
    }
    aliases = {
        "api:core/users.fetch": "api:core/users.get",
        "fn:core/onboarding.audit": "fn:core/onboarding.audit_docs",
    }

    canonical = canonicalize_persisted_records(raw_records, aliases)

    assert "api:core/users.fetch" not in canonical
    assert "fn:core/onboarding.audit" not in canonical
    assert "api:core/users.get" in canonical
    assert "fn:core/onboarding.audit_docs" in canonical


def test_alias_schema_file_has_contract_shape() -> None:
    schema_path = Path("schemas/entropy.aliases.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == "entropy.aliases.json"
    assert schema["properties"]["version"]["const"] == 1
    assert schema["properties"]["aliases"]["type"] == "object"
