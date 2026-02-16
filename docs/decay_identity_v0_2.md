# Decay Identity Contract v0.2.0

This contract defines how entropy-os identifies decaying entities so behavior is deterministic, portable, auditable, and independent of filesystem metadata.

## 1. Terminology

- Identity: stable string key for one decaying entity.
- Entity: decaying unit (`api`, `fn`, `state`).
- Decay record: TTL and lifecycle metadata for one canonical identity.
- Renewal: explicit TTL reset/update for an identity.
- Alias: legacy identity that resolves to a canonical identity.

## 2. Design goals

- Deterministic across identical inputs and tick sequence.
- Portable across machines and checkout locations.
- Human-legible IDs with namespaced structure.
- Refactor-resistant via explicit alias maps.
- Auditable identity changes via versioned mapping files.

## 3. Identity format

Canonical grammar:

`<kind>:<namespace>/<name>[#<qualifier>]`

- `kind` is one of `api`, `fn`, `state`.
- `namespace` is slash-delimited.
- `name` is a developer-defined slug.
- `qualifier` is optional.

Examples:

- `api:core/users.get`
- `api:billing/invoices.create`
- `fn:core/onboarding.audit_docs`
- `fn:ml/pipeline.embed#v2`
- `state:session/user:1234`
- `state:cache/feature_flags`

Constraints:

- No whitespace.
- No absolute paths or OS separators.
- No backslashes.
- No `..` namespace segments.
- Recommended max length: 256 (configurable).

## 4. Canonicalization rules

Canonicalization is applied at registration, CLI boundaries, and persistence boundaries.

- Unicode normalization: NFC.
- Trim leading/trailing whitespace.
- Reject internal whitespace.
- Reject control characters.
- Enforce allowed characters: `[A-Za-z0-9._:/#-]`.
- Enforce known kind prefix.
- Reject namespace traversal segments (`..`).

## 5. Identity declaration sources

Identity is always explicit in v0.2.

- APIs require explicit ID.
- Function/code-path decay requires explicit ID.
- State identity is derived deterministically from canonicalized state keys:
  - `state:<canonical_state_key>`

No filesystem introspection or code-object metadata is part of identity.

## 6. Uniqueness and conflict rules

Within a runtime registry:

- Canonical IDs must be unique.
- Same canonical ID with conflicting record metadata is an error.
- Identity reuse after prune requires explicit resurrection semantics (future extension).

## 7. Alias mapping and refactor survival

Alias mappings live in `entropy.aliases.json`.

Rules:

- Keys are old IDs; values are canonical IDs.
- Alias chains are allowed.
- Cycles are fatal errors.
- CLI and runtime resolve aliases before operations.

Resolution algorithm:

1. `id = canonicalize(id)`
2. While `id in aliases`, set `id = aliases[id]`
3. Track visited IDs and fail on cycles
4. Return final canonical ID

## 8. Lifecycle states

Entity states are tick-driven and explicit:

- `active`
- `expired`
- `prunable` (optional grace-phase)
- `pruned`

Transitions depend only on logical tick progression and explicit actions.

## 9. Renewal semantics

`entropy renew <id> [--ttl <ticks>]`

- Resolve aliases to canonical ID.
- Set `last_renewed_tick = now_tick`.
- Set `expires_at_tick = now_tick + ttl_ticks`.
- No implicit resurrection of pruned entities (future `--resurrect` extension).

## 10. Prune plan semantics

Prune plan is deterministic and path-free.

Suggested schema:

- `version`
- `generated_at_tick`
- `expired` grouped by kind
- `prunable` grouped by kind
- `aliases_applied`
- `notes`

Ordering:

- Lexicographic sorting by canonical ID for every entity list.
- Canonical JSON serialization with stable formatting (`sort_keys=True`, `indent=2`, explicit separators), `ensure_ascii=True`, `allow_nan=False`, and trailing newline.

## 11. Persistence contract

Persisted runtime state stores canonical IDs only.

State payload should include:

- schema version
- clock tick
- canonical-ID keyed records
- optional alias-mapping fingerprint/version hash
- optional deterministic fingerprint metadata

## 12. Security constraints

- Reject path traversal forms.
- Reject control characters.
- Enforce max lengths.
- Validate alias file before use.

## 13. Migration guidance (v0.1 to v0.2)

- Registrations without explicit IDs fail in v0.2.
- `entropy migrate` may provide best-effort suggestions for IDs and alias mappings, but migration tooling is not part of deterministic core.

## 14. Test requirements

v0.2 invariant tests must assert:

- canonicalization stability and invalid input rejection
- deterministic alias resolution and cycle detection
- renewal through alias updates canonical record
- prune plan output stability and sorting
- persisted state canonical IDs only

## 15. Developer guidance

- Treat decay IDs as public contracts.
- Use explicit aliases for renames.
- Do not derive IDs from paths/function objects.
- Keep namespaces meaningful and maintainable.
