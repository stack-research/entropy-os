Now we stop building “systems that grow” and start building systems that decay on purpose.

We are not building a feature set.
We are building controlled entropy.

This is designed to create a serious v0, not a gimmick.

Project:
Tagline: Software that expires.

Project Name:
Version: 0.1.0

Philosophy:
All software systems naturally accumulate complexity and technical debt. reverses this trend by engineering decay as a first-class behavior.

This system must:
- Delete unused code paths automatically.
- Expire APIs unless renewed.
- Permanently forget state unless explicitly preserved.
- Enforce time-bound logic at the architecture level.

This is not a metaphor.
The system must actively remove itself over time.

============================================================
CORE PRINCIPLES
============================================================

1. Time is a first-class input.
2. State must justify its existence.
3. Code must have a TTL (time-to-live).
4. APIs must expire unless renewed.
5. Memory must decay.
6. No infinite retention by default.

============================================================
MVP SCOPE
============================================================

Build a minimal runtime platform in Python 3.12+ with the following capabilities:

1) Ephemeral API Framework
- Developers define API endpoints with TTL metadata.
- Example:

    @ephemeral_api(ttl_days=30)
    def get_user_data(user_id: str) -> dict:
        ...

- If not renewed before expiration:
    - The endpoint is automatically disabled.
    - Calls return deterministic ExpiredError.
    - Expired APIs are flagged for deletion.

2) Code Path Decay Engine
- Instrument function usage frequency.
- If a function is not invoked within its TTL window:
    - It is marked as decayed.
    - A CLI command `entropy prune` generates a patch removing dead paths.
- Dead code detection must be deterministic.

3) State Forgetting Layer
- Provide a key-value store with TTL enforced at read-time.
- Expired keys are permanently removed.
- No silent refresh.
- Accessing expired state raises ExpiredStateError.

4) Entropy Monitor
- A background deterministic decay scheduler.
- It runs based on logical time (not system clock).
- Logical time advances only via explicit ticks.
- No implicit wall-clock dependence.

============================================================
ARCHITECTURE REQUIREMENTS
============================================================

- Pure core logic separated from IO shell.
- No hidden background threads.
- No reliance on real wall clock.
- All decay decisions based on explicit time input.
- Deterministic behavior: same inputs + same tick sequence = identical results.

Logical Time Model:
- Platform has an internal "epoch".
- Each `tick()` increments logical time by 1 unit.
- TTL values are measured in ticks.
- Expiration is computed relative to tick counts.

============================================================
CLI
============================================================

entropy init
entropy tick --n 10
entropy status
entropy prune
entropy renew <api_name>
entropy simulate

entropy simulate:
- Runs a scripted decay scenario.
- Demonstrates APIs expiring and code being pruned.

============================================================
REPOSITORY STRUCTURE
============================================================

src/
  __init__.py
  runtime.py
  ttl.py
  api.py
  decay.py
  store.py
  scheduler.py
  cli.py
  errors.py
  version.py

tests/
  test_api_expiry.py
  test_state_forgetting.py
  test_decay_pruning.py
  test_determinism.py

docs/
  philosophy.md
  architecture.md
  entropy_model.md

AGENTS.md
README.md
LICENSE (MIT)
pyproject.toml
uv.lock
.github/workflows/ci.yml

============================================================
DETERMINISM REQUIREMENTS
============================================================

- No random.
- No time.time().
- No datetime.now().
- No UUIDs.
- All time flows through LogicalClock.
- All expiration decisions must be testable and reproducible.
- Add tests that replay tick sequences and assert identical outcomes.

============================================================
PRUNING DESIGN
============================================================

`entropy prune` must:
- Scan registered APIs and tracked function metadata.
- Identify expired entities.
- Generate a deterministic diff/patch file.
- Never modify files automatically.
- Always output the same patch for same state.

============================================================
AGENTS.md RULES
============================================================

- Never introduce wall-clock time.
- Never add background threads.
- All state transitions must be explicit.
- Any new feature must have TTL semantics.
- Complexity must decay, not accumulate.
- If adding a new module, require a removal strategy.

============================================================
EXAMPLE USE CASE
============================================================

1. Define 3 APIs with different TTLs.
2. Tick logical clock 5 times.
3. Observe one API expire.
4. Attempt call -> ExpiredError.
5. Run entropy prune -> patch suggests removal.
6. Renew another API -> TTL reset.

============================================================
DELIVERABLES
============================================================

- Full working repository.
- Deterministic logical clock.
- Expiration registry.
- Function instrumentation mechanism.
- Patch generation system.
- Tests covering decay and determinism.
- CI workflow.
- Clear README explaining philosophy and usage.

Do not output a plan only.
Generate all repository files and code.

This must be a runnable, testable system.


⸻

Now — strategically.

Why this direction is powerful:
	•	It attacks software bloat at the architecture level.
	•	It forces developers to justify retention.
	•	It introduces decay as policy, not accident.
	•	It’s conceptually opposite of SaaS (which optimizes retention, permanence, and accumulation).

If you want to go even further after v0:

Phase 2 ideas:
	•	Expiring dependencies in pyproject.
	•	Auto-deleting feature flags.
	•	Entropic microservices that shut themselves down.
	•	“Memory half-life” functions for AI agents.
	•	Entropy scoring for codebases.

This is not just creative.
This could become a serious research direction in software lifecycle design.

If you want, next we can refine:
	•	The patch generation model (AST-based vs text diff),
	•	Or define a “Formal Entropy Model” that quantifies system decay mathematically.
