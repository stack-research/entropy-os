# Entropy Model

Logical time advances only through explicit `tick()` calls.

For any entity with `(created_at, ttl_ticks)`, the expiration predicate is:

`expired(now) := now >= created_at + ttl_ticks`

The same initial state and identical tick/action sequence always produce identical outputs. This makes decay behavior replayable and testable.
