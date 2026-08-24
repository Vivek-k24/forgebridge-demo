#!/usr/bin/env python3
"""Pretty-format generated PartGraph Honda JSON files for human review."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HONDA_DATA = ROOT / "public" / "data" / "honda"
FIRST_MODEL_YEAR = 1996


def format_file(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    for path in sorted(HONDA_DATA.glob("*.json")):
        format_file(path)

    year_dir = HONDA_DATA / "years"
    for path in sorted(year_dir.glob("*.json")):
        if int(path.stem) < FIRST_MODEL_YEAR:
            path.unlink()
            continue
        format_file(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
