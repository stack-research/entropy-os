"""CLI shell for deterministic entropy runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .errors import ExpiredError
from .identity import IdentityError, canonicalize_aliases, canonicalize_identity
from .runtime import EntropyRuntime
from .serde import dumps_canonical_json, write_canonical_json

STATE_DIR = Path(".entropy")
STATE_FILE = STATE_DIR / "state.json"
PLAN_FILE = STATE_DIR / "prune-plan.json"
PATCH_FILE = STATE_DIR / "prune.patch"
ALIASES_FILE = Path("entropy.aliases.json")


def _load_aliases() -> dict[str, str]:
    """Load and validate aliases from entropy.aliases.json (optional, no-op if absent)."""
    if not ALIASES_FILE.exists():
        return {}
    data = json.loads(ALIASES_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "aliases" not in data:
        raise IdentityError("invalid entropy.aliases.json: missing 'aliases' key")
    return canonicalize_aliases(data["aliases"])


def _load_runtime() -> EntropyRuntime:
    aliases = _load_aliases()
    if not STATE_FILE.exists():
        return EntropyRuntime(aliases=aliases)
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return EntropyRuntime.from_dict(data, aliases=aliases)


def _save_runtime(runtime: EntropyRuntime) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    write_canonical_json(STATE_FILE, runtime.to_dict())


def cmd_init(_: argparse.Namespace) -> int:
    runtime = _load_runtime()
    _save_runtime(runtime)
    print(f"initialized logical runtime at tick {runtime.clock.now()}")
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    runtime = _load_runtime()
    runtime.tick(args.n)
    _save_runtime(runtime)
    print(f"tick advanced to {runtime.clock.now()}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    runtime = _load_runtime()
    print(dumps_canonical_json(runtime.status()), end="")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    runtime = _load_runtime()
    if args.apply:
        pruned = runtime.apply_prune()
        _save_runtime(runtime)
        total = sum(len(ids) for ids in pruned.values())
        print(f"pruned {total} entities")
        print(dumps_canonical_json(pruned), end="")
        return 0
    plan = runtime.prune_plan()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    write_canonical_json(PLAN_FILE, plan)
    print(f"wrote deterministic prune plan to {PLAN_FILE.as_posix()}")
    print(dumps_canonical_json(plan), end="")
    return 0


def cmd_patch(_: argparse.Namespace) -> int:
    runtime = _load_runtime()
    patch = runtime.patch_preview()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PATCH_FILE.write_text(patch, encoding="utf-8")
    print(f"wrote best-effort patch preview to {PATCH_FILE.as_posix()}")
    print(patch, end="")
    return 0


def cmd_renew(args: argparse.Namespace) -> int:
    runtime = _load_runtime()
    ttl_override = getattr(args, "ttl", None)
    runtime.renew(args.identity, ttl_override=ttl_override)
    _save_runtime(runtime)
    label = f" with TTL={ttl_override}" if ttl_override is not None else ""
    print(f"renewed '{args.identity}'{label} at tick {runtime.clock.now()}")
    return 0


def cmd_migrate(_: argparse.Namespace) -> int:
    """Best-effort advisory migration from v0.1 bare names to v0.2 canonical identities."""
    if not STATE_FILE.exists():
        print("no state file found; nothing to migrate")
        return 0

    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    suggested_aliases: dict[str, str] = {}

    # Suggest API identity mappings
    for name in sorted(data.get("apis", {})):
        try:
            canonicalize_identity(name)
        except IdentityError:
            canonical = f"api:default/{name}"
            suggested_aliases[name] = canonical
            print(f"  api: {name} -> {canonical}")

    # Suggest function identity mappings
    for name in sorted(data.get("decay", {})):
        try:
            canonicalize_identity(name)
        except IdentityError:
            canonical = f"fn:default/{name}"
            suggested_aliases[name] = canonical
            print(f"  fn:  {name} -> {canonical}")

    # Suggest state key mappings
    for key in sorted(data.get("state", {})):
        try:
            canonicalize_identity(f"state:{key}")
        except IdentityError:
            canonical_key = key.replace(" ", "_")
            suggested_aliases[key] = f"state:default/{canonical_key}"
            print(f"  state: {key} -> state:default/{canonical_key}")

    if not suggested_aliases:
        print("all identities are already canonical; no migration needed")
        return 0

    # Output suggested aliases file
    output = {
        "version": 1,
        "aliases": suggested_aliases,
    }
    print(f"\nsuggested entropy.aliases.json ({len(suggested_aliases)} mappings):")
    print(dumps_canonical_json(output), end="")
    return 0


def cmd_simulate(_: argparse.Namespace) -> int:
    runtime = EntropyRuntime()

    @runtime.apis.ephemeral_api("api:sim/fast", ttl_ticks=2)
    def fast_api() -> dict[str, str]:
        return {"api": "fast"}

    @runtime.apis.ephemeral_api("api:sim/medium", ttl_ticks=4)
    def medium_api() -> dict[str, str]:
        return {"api": "medium"}

    @runtime.apis.ephemeral_api("api:sim/slow", ttl_ticks=8)
    def slow_api() -> dict[str, str]:
        return {"api": "slow"}

    runtime.decay.register("fn:sim/cold_path", ttl_ticks=3)
    runtime.decay.register("fn:sim/warm_path", ttl_ticks=7)
    runtime.store.set("session", {"user": "alice"}, ttl_ticks=2)

    print("simulate: registered 3 APIs, 2 code paths, 1 state key")
    runtime.tick(5)
    print("simulate: advanced 5 ticks")
    try:
        runtime.apis.call("api:sim/fast")
    except ExpiredError as exc:
        print(f"simulate: expected expiration -> {exc}")

    runtime.apis.renew("api:sim/medium")
    print("simulate: renewed api:sim/medium")

    plan = runtime.prune_plan()
    print("simulate: prune plan")
    print(dumps_canonical_json(plan), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="entropy", description="Deterministic entropy runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    init_cmd = sub.add_parser("init", help="Initialize entropy state")
    init_cmd.set_defaults(func=cmd_init)

    tick_cmd = sub.add_parser("tick", help="Advance logical time")
    tick_cmd.add_argument("--n", type=int, default=1)
    tick_cmd.set_defaults(func=cmd_tick)

    status_cmd = sub.add_parser("status", help="Show runtime status")
    status_cmd.set_defaults(func=cmd_status)

    prune_cmd = sub.add_parser("prune", help="Generate deterministic prune plan")
    prune_cmd.add_argument("--apply", action="store_true", help="Apply prune: mark prunable entities as pruned")
    prune_cmd.set_defaults(func=cmd_prune)

    patch_cmd = sub.add_parser("patch", help="Generate best-effort patch preview from prune plan")
    patch_cmd.set_defaults(func=cmd_patch)

    renew_cmd = sub.add_parser("renew", help="Renew entity TTL")
    renew_cmd.add_argument("identity", help="Canonical identity (api:ns/name or fn:ns/name)")
    renew_cmd.add_argument("--ttl", type=int, default=None, help="Override TTL ticks on renewal")
    renew_cmd.set_defaults(func=cmd_renew)

    migrate_cmd = sub.add_parser("migrate", help="Advisory v0.1 to v0.2 identity migration")
    migrate_cmd.set_defaults(func=cmd_migrate)

    simulate_cmd = sub.add_parser("simulate", help="Run scripted entropy scenario")
    simulate_cmd.set_defaults(func=cmd_simulate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
