#!/usr/bin/env python3
"""Reload Home Assistant automations (equivalent to Dev Tools → Reload).

Usage:
    tools/reload_automations.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ha import HA  # noqa: E402


def main() -> int:
    with HA() as ha:
        ha.rpc({"type": "call_service", "domain": "automation", "service": "reload"})
    print("automations reloaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
