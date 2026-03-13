# Next Steps

## Phase 1: v0.2 Identity Wiring

The identity contract is fully specced in `docs/decay_identity_v0_2.md` and the core functions exist in `identity.py`, but they are not integrated into the runtime, registries, or CLI. This phase wires them in.

### 1.1 Canonical identities in registries

- `APIRegistry` accepts and stores canonical `api:namespace/name` identities instead of bare name strings.
- `CodePathDecayEngine` accepts and stores canonical `fn:namespace/name` identities.
- `TTLStore` derives `state:key` identities via `state_identity_from_key()`.
- All registration and lookup paths run through `canonicalize_identity()`.
- Invalid identities are rejected at registration time with `IdentityError`.

### 1.2 Alias file loading

- Load `entropy.aliases.json` at runtime startup (optional file, no-op if absent).
- Validate against `schemas/entropy.aliases.schema.json` on load.
- Resolve aliases at registration, renewal, and call boundaries.
- CLI commands that accept an identity resolve aliases before dispatch.

### 1.3 `--ttl` override on `entropy renew`

- `entropy renew <id> --ttl <ticks>` overrides the original TTL on renewal.
- Without `--ttl`, renewal uses the entity's original TTL (current behavior).

### 1.4 Lifecycle states

The v0.2 contract defines four states: `active`, `expired`, `prunable`, `pruned`.

- Add `prunable` grace phase: expired entities enter `prunable` after a configurable grace window (default: 0 ticks, immediate).
- Add `pruned` terminal state: entities marked pruned by `entropy prune --apply` (or equivalent) are recorded as pruned and cannot be renewed without `--resurrect` (future extension).
- Prune plan groups entities by `expired` and `prunable` as separate sections.

### 1.5 `entropy migrate` command

- Best-effort CLI command that reads v0.1 state and suggests canonical identity mappings.
- Outputs suggested `entropy.aliases.json` entries for old bare-name keys.
- Not part of deterministic core — labeled as advisory.

### 1.6 Tests

- Extend existing `test_decay_identity_contract.py` with integration tests that exercise the full runtime path (register with canonical ID, tick, expire, renew via alias).
- Add tests for alias file loading and validation.
- Add tests for `--ttl` override behavior.
- Add tests for lifecycle state transitions (`active` -> `expired` -> `prunable` -> `pruned`).

---

## Phase 2: Memory Half-Life for AI Agents

Build a real application on top of entropy-os that demonstrates decay as a load-bearing architectural feature, not just a demo.

### Concept

An agent memory system where context and knowledge literally decay unless refreshed. Connects entropy-os (decaying software) with the agent catalog project (composable AI agents).

### Design sketch

- Agent memories (facts, observations, conversation history) are stored with TTL in the entropy-os state store.
- Each memory has a half-life: its confidence/weight degrades over ticks.
- Memories that are accessed (used in reasoning) get their TTL refreshed — things the agent actively uses survive.
- Memories that go untouched expire and are permanently forgotten.
- The agent must decide what to reinforce and what to let go.
- Entropy score measures how much of the agent's knowledge is decaying vs. active.

### Why this matters

Most AI agent memory systems accumulate indefinitely — context windows grow, vector stores bloat, nothing is ever removed. This inverts that pattern. The agent's memory is bounded not by token limits but by relevance decay. Old, unused knowledge disappears. The agent stays lean by forgetting.

### Open questions

- Should half-life be continuous (fractional confidence) or binary (alive/expired)?
- What triggers a "tick" — each conversation turn? Each reasoning step?
- How does the agent decide what to reinforce? Explicit policy or implicit via access patterns?
- Standalone project or extension module within entropy-os?
