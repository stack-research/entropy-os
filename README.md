# Entropy OS

Software that expires.

Entropy OS is a deterministic Python runtime for time-bound APIs, decaying code paths, and state forgetting.

## Features

- Ephemeral API framework with renewal and deterministic `ExpiredError` behavior.
- Code path decay engine with deterministic prune-plan output (JSON).
- TTL key-value store that permanently forgets expired state.
- Logical-time scheduler driven only by explicit ticks.
- Formal entropy score in `status` (`pressure / mass`) for measurable decay.
- CLI for init/tick/status/prune/patch/renew/simulate workflows.

## Install

```bash
uv sync
```

## CLI

```bash
entropy init
entropy tick --n 10
entropy status
entropy prune
entropy patch
entropy renew <api_name>
entropy simulate
```

`entropy prune` writes deterministic `.entropy/prune-plan.json` from runtime state only.
`entropy patch` writes `.entropy/prune.patch` as an optional best-effort developer preview.
JSON artifacts are emitted through a canonical serializer with sorted keys and a trailing newline.

## Determinism

- No `time.time()` or `datetime.now()`.
- No randomness or UUIDs.
- All transitions depend on explicit logical ticks.

## Run tests

```bash
pytest
```
