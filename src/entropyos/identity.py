"""v0.2 decay identity contract helpers."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping, MutableMapping

ID_PATTERN = re.compile(r"^(api|fn|state):[A-Za-z0-9._:/#-]+$")
STATE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:/#-]+$")


class IdentityError(ValueError):
    """Raised when an identity violates the contract."""


class AliasCycleError(IdentityError):
    """Raised when alias mappings contain a cycle."""


def canonicalize_identity(identity: str, *, max_length: int = 256) -> str:
    """Normalize and validate a canonical entity identity."""
    if not isinstance(identity, str):
        raise IdentityError("identity must be a string")

    normalized = unicodedata.normalize("NFC", identity.strip())
    if not normalized:
        raise IdentityError("identity cannot be empty")
    if len(normalized) > max_length:
        raise IdentityError(f"identity exceeds max length {max_length}")
    if any(char.isspace() for char in normalized):
        raise IdentityError("identity cannot contain whitespace")
    if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        raise IdentityError("identity cannot contain control characters")
    if "\\" in normalized:
        raise IdentityError("identity cannot contain backslash separators")
    if not ID_PATTERN.fullmatch(normalized):
        raise IdentityError("identity must match kind-prefixed contract format")

    _, body = normalized.split(":", 1)
    segments = body.split("/")
    if any(segment == ".." for segment in segments):
        raise IdentityError("identity cannot contain '..' namespace segments")
    return normalized


def canonicalize_state_key(key: str, *, max_length: int = 512) -> str:
    """Normalize and validate a deterministic state key payload."""
    if not isinstance(key, str):
        raise IdentityError("state key must be a string")

    normalized = unicodedata.normalize("NFC", key.strip())
    if not normalized:
        raise IdentityError("state key cannot be empty")
    if len(normalized) > max_length:
        raise IdentityError(f"state key exceeds max length {max_length}")
    if any(char.isspace() for char in normalized):
        raise IdentityError("state key cannot contain whitespace")
    if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        raise IdentityError("state key cannot contain control characters")
    if "\\" in normalized:
        raise IdentityError("state key cannot contain backslash separators")
    if not STATE_KEY_PATTERN.fullmatch(normalized):
        raise IdentityError("state key must match canonical allowed characters")

    segments = normalized.split("/")
    if any(segment == ".." for segment in segments):
        raise IdentityError("state key cannot contain '..' namespace segments")
    return normalized


def state_identity_from_key(key: str) -> str:
    """Build deterministic state identity from a canonicalized state key."""
    canonical_key = canonicalize_state_key(key)
    return canonicalize_identity(f"state:{canonical_key}")


def canonicalize_aliases(aliases: Mapping[str, str]) -> dict[str, str]:
    """Canonicalize and validate alias mapping for deterministic resolution."""
    canonical: dict[str, str] = {}
    for raw_source in sorted(aliases):
        raw_target = aliases[raw_source]
        source = canonicalize_identity(raw_source)
        target = canonicalize_identity(raw_target)
        canonical[source] = target

    _assert_acyclic_aliases(canonical)
    return canonical


def resolve_alias(identity: str, aliases: Mapping[str, str]) -> str:
    """Resolve aliases deterministically to canonical ID with cycle detection."""
    current = canonicalize_identity(identity)
    visited: set[str] = set()

    while current in aliases:
        if current in visited:
            raise AliasCycleError(f"alias cycle detected at '{current}'")
        visited.add(current)
        current = canonicalize_identity(aliases[current])

    return current


def renew_record(
    records: MutableMapping[str, MutableMapping[str, Any]],
    *,
    identity: str,
    aliases: Mapping[str, str],
    now_tick: int,
    ttl_override: int | None = None,
) -> str:
    """Renew a canonical record, resolving aliases before mutation."""
    canonical_aliases = canonicalize_aliases(aliases)
    canonical_id = resolve_alias(identity, canonical_aliases)
    if canonical_id not in records:
        raise KeyError(canonical_id)

    record = records[canonical_id]
    ttl_ticks = record.get("ttl_ticks") if ttl_override is None else ttl_override
    if not isinstance(ttl_ticks, int) or ttl_ticks < 0:
        raise IdentityError("ttl_ticks must be a non-negative integer")

    record["ttl_ticks"] = ttl_ticks
    record["last_renewed_tick"] = now_tick
    record["expires_at_tick"] = now_tick + ttl_ticks
    return canonical_id


def canonicalize_persisted_records(records: Mapping[str, Mapping[str, Any]], aliases: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    """Rewrite records so persisted keys are canonical IDs only."""
    canonical_aliases = canonicalize_aliases(aliases)
    canonical_records: dict[str, dict[str, Any]] = {}

    for raw_id in sorted(records):
        canonical_id = resolve_alias(raw_id, canonical_aliases)
        record_data = dict(records[raw_id])
        if canonical_id in canonical_records and canonical_records[canonical_id] != record_data:
            raise IdentityError(f"conflicting records map to canonical id '{canonical_id}'")
        canonical_records.setdefault(canonical_id, record_data)

    return canonical_records


def build_prune_plan(
    *,
    generated_at_tick: int,
    expired_ids: list[str],
    prunable_ids: list[str] | None = None,
    aliases_applied: bool,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic v0.2 prune plan."""
    return {
        "version": 1,
        "generated_at_tick": generated_at_tick,
        "expired": _group_sorted_ids(expired_ids),
        "prunable": _group_sorted_ids(prunable_ids or []),
        "aliases_applied": aliases_applied,
        "notes": sorted(notes or []),
    }


def _group_sorted_ids(ids: list[str]) -> dict[str, list[str]]:
    grouped = {"api": [], "fn": [], "state": []}
    canonical_ids = sorted({canonicalize_identity(entity_id) for entity_id in ids})

    for entity_id in canonical_ids:
        kind, _ = entity_id.split(":", 1)
        grouped[kind].append(entity_id)

    return grouped


def _assert_acyclic_aliases(aliases: Mapping[str, str]) -> None:
    for start in sorted(aliases):
        visited: set[str] = set()
        current = start
        while current in aliases:
            if current in visited:
                raise AliasCycleError(f"alias cycle detected at '{current}'")
            visited.add(current)
            current = aliases[current]
