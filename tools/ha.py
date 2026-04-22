"""Tiny Home Assistant WebSocket helper for the tools/ scripts.

- Loads credentials from a `.env` file at the repo root.
- Provides a synchronous `HA` context manager wrapping `websocket-client`.
- No external deps beyond the `websocket-client` package (which is
  already available in the system Python environment).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any, Iterator

import websocket  # type: ignore[import-untyped]

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_env(path: pathlib.Path | None = None) -> None:
    """Parse a simple KEY=VALUE `.env` file into `os.environ`.

    Existing env vars win (so callers can override via the shell).
    Lines starting with `#` and blank lines are ignored. No quoting
    tricks — values are taken as-is after the first `=`.
    """
    env_path = path or _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _ws_url(ha_url: str) -> str:
    if ha_url.startswith("https://"):
        return "wss://" + ha_url[len("https://"):].rstrip("/") + "/api/websocket"
    if ha_url.startswith("http://"):
        return "ws://" + ha_url[len("http://"):].rstrip("/") + "/api/websocket"
    # Already a ws(s):// URL? Assume the caller knows what they're doing.
    return ha_url


class HA:
    """Minimal authenticated WebSocket client with id-indexed RPC."""

    def __init__(self, ha_url: str | None = None, token: str | None = None, timeout: float = 10.0) -> None:
        load_env()
        self._url = ha_url or os.environ.get("HA_URL")
        self._token = token or os.environ.get("HA_TOKEN")
        if not self._url or not self._token:
            raise RuntimeError(
                "HA_URL and HA_TOKEN must be set in the environment or .env "
                "(copy .env.example to .env and fill it in)."
            )
        self._ws_url = _ws_url(self._url)
        self._timeout = timeout
        self._ws: websocket.WebSocket | None = None
        self._next_id = 0

    # --- context manager ---------------------------------------------------
    def __enter__(self) -> "HA":
        self._ws = websocket.create_connection(self._ws_url, timeout=self._timeout)
        self._recv()  # auth_required
        self._ws.send(json.dumps({"type": "auth", "access_token": self._token}))
        msg = self._recv()
        if msg.get("type") != "auth_ok":
            raise RuntimeError(f"auth failed: {msg}")
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            finally:
                self._ws = None

    # --- low-level ---------------------------------------------------------
    def _recv(self) -> dict[str, Any]:
        assert self._ws is not None
        return json.loads(self._ws.recv())

    def rpc(self, payload: dict[str, Any]) -> Any:
        """Send a command and return its `result`, raising on failure."""
        assert self._ws is not None
        self._next_id += 1
        mid = self._next_id
        self._ws.send(json.dumps({"id": mid, **payload}))
        while True:
            m = self._recv()
            if m.get("id") == mid and m.get("type") == "result":
                if not m.get("success", True):
                    raise RuntimeError(f"RPC failed: {m.get('error')}")
                return m.get("result")

    def subscribe(self, event_type: str) -> int:
        """Subscribe to an event stream. Returns the subscription id."""
        assert self._ws is not None
        self._next_id += 1
        mid = self._next_id
        self._ws.send(json.dumps({
            "id": mid, "type": "subscribe_events", "event_type": event_type,
        }))
        # Swallow the ack
        while True:
            m = self._recv()
            if m.get("id") == mid and m.get("type") == "result":
                break
        return mid

    def events(self, timeout: float | None = None) -> Iterator[dict[str, Any]]:
        """Yield `event` messages. Set timeout to limit the blocking read."""
        assert self._ws is not None
        if timeout is not None:
            self._ws.settimeout(timeout)
        try:
            while True:
                msg = self._recv()
                if msg.get("type") == "event":
                    yield msg["event"]
        except (websocket.WebSocketTimeoutException, websocket.WebSocketConnectionClosedException):
            return


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)
