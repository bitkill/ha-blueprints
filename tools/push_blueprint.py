#!/usr/bin/env python3
"""Push a local blueprint YAML to Home Assistant and reload automations.

Usage:
    tools/push_blueprint.py <path/to/blueprint.yaml> [--namespace NAME] [--no-reload]

Reads .env for HA_URL, HA_TOKEN, BLUEPRINT_NAMESPACE, BLUEPRINT_SOURCE_BASE.
Uses the `blueprint/save` websocket command with `allow_override: True` so
HA's cache is updated (HA does not re-fetch `source_url` on its own).
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ha import HA, load_env, die  # noqa: E402


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=pathlib.Path, help="Local blueprint YAML file")
    parser.add_argument("--namespace", default=os.environ.get("BLUEPRINT_NAMESPACE", "bitkill"),
                        help="Namespace folder (default from BLUEPRINT_NAMESPACE or 'bitkill')")
    parser.add_argument("--no-reload", action="store_true",
                        help="Skip the automation.reload service call")
    args = parser.parse_args()

    if not args.path.is_file():
        die(f"not a file: {args.path}")

    yaml_content = args.path.read_text()
    remote_path = f"{args.namespace}/{args.path.name}"
    source_base = os.environ.get("BLUEPRINT_SOURCE_BASE", "").rstrip("/")
    source_url = f"{source_base}/{args.path.name}" if source_base else ""

    payload = {
        "type": "blueprint/save",
        "domain": "automation",
        "path": remote_path,
        "yaml": yaml_content,
        "allow_override": True,
    }
    if source_url:
        payload["source_url"] = source_url

    with HA() as ha:
        ha.rpc(payload)
        print(f"saved  {remote_path}  ({len(yaml_content)} bytes)")
        if not args.no_reload:
            ha.rpc({"type": "call_service", "domain": "automation", "service": "reload"})
            print("reloaded automations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
