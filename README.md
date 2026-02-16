# Entropy OS

Software that expires.

Entropy OS is a deterministic Python runtime for time-bound APIs, decaying code paths, and state forgetting.

## Backstory

Most software is designed like a storage unit with no lease expiration. We put features in, we keep old data forever, we keep compatibility forever, and we keep old decisions forever. At first this feels responsible. Nothing gets lost. Nothing breaks. But over time the system becomes harder to understand, harder to change, and more expensive to trust. Teams start spending more effort protecting yesterday than building tomorrow.

Entropy OS was built as a deliberate counterweight to that pattern. The project starts from a simple idea: if complexity naturally accumulates, then healthy systems should have built-in ways to remove themselves. Not by accident, and not after a crisis, but continuously and predictably. In this model, time is not a logging detail. Time is part of architecture. If something still matters, it can be renewed. If it no longer matters, it should decay.

For non-engineers, a good analogy is a refrigerator with clear labels and expiration dates. In many software systems, there are no dates, so old ingredients pile up indefinitely. Entropy OS adds those dates to APIs, code paths, and runtime state. When something expires, the system does not politely ignore that fact. It enforces it. That enforcement is the teaching tool: it turns maintenance from a vague aspiration into an observable behavior.

For new engineers, this project is meant to teach a mindset that is usually learned late: retention is a decision, not a default. Every endpoint, every piece of state, and every code path should have a reason to continue existing. By modeling decay explicitly, the project makes software lifecycle visible and testable. You can watch a system age across logical ticks, watch dead behavior surface in prune plans, and practice renewal only where it is justified.

This is why Entropy OS is a frontier education project, not just a framework demo. It gives teams a controlled sandbox to explore uncomfortable but important questions. What should expire? What should be renewed? What should be forgotten? How do we design systems that remain legible after years of change? The goal is not destruction. The goal is discipline: software that stays alive by learning how to let go.

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
