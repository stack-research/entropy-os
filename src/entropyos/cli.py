"""CLI shell for deterministic entropy runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .errors import ExpiredError
from .runtime import EntropyRuntime
from .serde import dumps_canonical_json, write_canonical_json

STATE_DIR = Path(".entropy")
STATE_FILE = STATE_DIR / "state.json"
PLAN_FILE = STATE_DIR / "prune-plan.json"
PATCH_FILE = STATE_DIR / "prune.patch"


def _load_runtime() -> EntropyRuntime:
    if not STATE_FILE.exists():
        return EntropyRuntime()
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return EntropyRuntime.from_dict(data)


def _save_runtime(runtime: EntropyRuntime) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    write_canonical_json(STATE_FILE, runtime.to_dict())


def cmd_init(_: argparse.Namespace) -> int:
    runtime = EntropyRuntime()
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


def cmd_prune(_: argparse.Namespace) -> int:
    runtime = _load_runtime()
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
    runtime.apis.renew(args.api_name)
    _save_runtime(runtime)
    print(f"renewed API '{args.api_name}' at tick {runtime.clock.now()}")
    return 0


def cmd_simulate(_: argparse.Namespace) -> int:
    runtime = EntropyRuntime()

    @runtime.apis.ephemeral_api(ttl_ticks=2)
    def fast_api() -> dict[str, str]:
        return {"api": "fast"}

    @runtime.apis.ephemeral_api(ttl_ticks=4)
    def medium_api() -> dict[str, str]:
        return {"api": "medium"}

    @runtime.apis.ephemeral_api(ttl_ticks=8)
    def slow_api() -> dict[str, str]:
        return {"api": "slow"}

    runtime.decay.register("cold_path", ttl_ticks=3)
    runtime.decay.register("warm_path", ttl_ticks=7)
    runtime.store.set("session", {"user": "alice"}, ttl_ticks=2)

    print("simulate: registered 3 APIs, 2 code paths, 1 state key")
    runtime.tick(5)
    print("simulate: advanced 5 ticks")
    try:
        runtime.apis.call("fast_api")
    except ExpiredError as exc:
        print(f"simulate: expected expiration -> {exc}")

    runtime.apis.renew("medium_api")
    print("simulate: renewed medium_api")

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
    prune_cmd.set_defaults(func=cmd_prune)

    patch_cmd = sub.add_parser("patch", help="Generate best-effort patch preview from prune plan")
    patch_cmd.set_defaults(func=cmd_patch)

    renew_cmd = sub.add_parser("renew", help="Renew API TTL")
    renew_cmd.add_argument("api_name")
    renew_cmd.set_defaults(func=cmd_renew)

    simulate_cmd = sub.add_parser("simulate", help="Run scripted entropy scenario")
    simulate_cmd.set_defaults(func=cmd_simulate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
