#!/usr/bin/env python3
"""Fetch the HA system log, optionally filtered by substring.

Usage:
    tools/system_log.py                 # all entries
    tools/system_log.py bilresa         # only entries mentioning "bilresa"
    tools/system_log.py -l ERROR foo    # ERROR-level entries mentioning "foo"

The log is deduplicated by HA (each unique message is kept with a count
and first/last occurrence timestamps) — this tool prints that metadata.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ha import HA  # noqa: E402


def _fmt_ts(ts: float | None) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("substring", nargs="?", default="",
                        help="Case-insensitive filter across message + source")
    parser.add_argument("-l", "--level", choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
                        help="Only show entries at this level or above")
    parser.add_argument("-n", "--limit", type=int, default=20,
                        help="Max entries to print (default 20)")
    args = parser.parse_args()

    level_order = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
    min_level = level_order[args.level] if args.level else -1
    needle = args.substring.lower()

    with HA() as ha:
        entries = ha.rpc({"type": "system_log/list"})

    matches: list[dict] = []
    for e in entries:
        msg = e.get("message", "")
        if isinstance(msg, list):
            msg = " ".join(msg)
        name = e.get("name") or ""
        if needle and needle not in msg.lower() and needle not in name.lower():
            continue
        if min_level >= 0 and level_order.get(e.get("level", "INFO"), 1) < min_level:
            continue
        matches.append({"entry": e, "message": msg, "name": name})

    if not matches:
        print("(no matching log entries)")
        return 0

    # Most recent last, so the latest shows up at the bottom of the terminal.
    matches.sort(key=lambda m: m["entry"].get("timestamp", 0))
    for m in matches[-args.limit:]:
        e = m["entry"]
        print(f"[{e.get('level','?'):8}] count={e.get('count',1):<4} "
              f"first={_fmt_ts(e.get('first_occurred'))}  "
              f"last={_fmt_ts(e.get('timestamp'))}  "
              f"{m['name']}")
        # Wrap long messages but keep meaningful prefix
        msg = m["message"].strip()
        if len(msg) > 500:
            msg = msg[:500] + " …"
        for line in msg.splitlines():
            print(f"    {line}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
