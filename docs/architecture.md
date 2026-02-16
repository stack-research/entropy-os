# Architecture

The platform is split into pure core logic and an IO shell.

- Core modules (`runtime`, `ttl`, `api`, `decay`, `store`, `scheduler`) are deterministic and pure with explicit logical time input.
- CLI (`cli`) is the stateful shell that persists snapshots for repeated commands.
- Expiration is computed only from `LogicalClock` tick values.
- Core pruning emits deterministic plans from runtime state only (`prune_plan`).
- Best-effort patch generation is separated as developer tooling (`entropy patch`).
- JSON artifacts are serialized through a canonical serializer for stable hashes.

No wall-clock time, random inputs, or background threads are used.
