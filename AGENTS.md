# AGENTS Rules

- Never introduce wall-clock time.
- Never add background threads.
- All state transitions must be explicit.
- Any new feature must include TTL semantics.
- Complexity must decay, not accumulate.
- If adding a new module, include a removal strategy.
