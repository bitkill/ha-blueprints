#!/usr/bin/env python3
"""Push an automation YAML file to Home Assistant via the REST API.

The YAML file must contain either a single automation dict with a top-level
`id:` field, or a list of such dicts (all will be pushed).

Usage:
    tools/push_automation.py my_automation.yaml
    tools/push_automation.py my_automation.yaml --no-reload

If an automation with the same id already exists it will be overwritten.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.request
import urllib.error

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ha import HA, load_env, die  # noqa: E402

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    die("pyyaml is required: pip install pyyaml")


def push(url_base: str, token: str, automation: dict) -> None:
    automation_id = automation.get("id")
    if not automation_id:
        die(f"automation is missing required 'id' field: {automation.get('alias', '?')}")
    url = f"{url_base}/api/config/automation/config/{automation_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = json.dumps(automation).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            if result.get("result") != "ok":
                raise RuntimeError(f"unexpected response: {result}")
    except urllib.error.HTTPError as e:
        die(f"HTTP {e.code}: {e.read().decode()}")


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=pathlib.Path, help="Local automation YAML file")
    parser.add_argument("--no-reload", action="store_true",
                        help="Skip automation.reload after pushing")
    args = parser.parse_args()

    if not args.path.is_file():
        die(f"not a file: {args.path}")

    ha_url = os.environ.get("HA_URL", "").rstrip("/")
    ha_token = os.environ.get("HA_TOKEN", "")
    if not ha_url or not ha_token:
        die("HA_URL and HA_TOKEN must be set in the environment or .env")

    raw = yaml.safe_load(args.path.read_text())
    automations = raw if isinstance(raw, list) else [raw]

    for a in automations:
        push(ha_url, ha_token, a)
        print(f"pushed  {a.get('id')!r}  ({a.get('alias', '?')})")

    if not args.no_reload:
        with HA() as ha:
            ha.rpc({"type": "call_service", "domain": "automation", "service": "reload"})
        print("reloaded automations")

    return 0


if __name__ == "__main__":
    sys.exit(main())
