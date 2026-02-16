"""Deterministic JSON serialization helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dumps_canonical_json(payload: Any) -> str:
    """Serialize JSON with stable formatting and a trailing newline."""
    text = json.dumps(
        payload,
        sort_keys=True,
        indent=2,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ": "),
    )
    if not text.endswith("\n"):
        text += "\n"
    return text


def write_canonical_json(path: Path, payload: Any) -> None:
    path.write_text(dumps_canonical_json(payload), encoding="utf-8")
