#!/usr/bin/env python3
"""Integrate the local emulator input engine as an exclusive route in the generated PC host."""
from __future__ import annotations

import sys
from pathlib import Path

VALID_EVENT = '''def valid_event(obj: object) -> bool:
    return isinstance(obj, dict) and obj.get("type") in {"button", "joystick", "heartbeat", "hero", "gesture"}'''

HELPERS = r'''
# MLBB Link Emulator Tools: relay only to this user's local daemon, never over the LAN.
_MLBB_EMULATOR_SETTINGS = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")),
    "mlbb-link-emulator", "settings.json")
_MLBB_EMULATOR_READY = os.path.join(os.path.dirname(_MLBB_EMULATOR_SETTINGS), "engine.ready")
_MLBB_EMULATOR_RELAY_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def _mlbb_emulator_route_enabled() -> bool:
    try:
        with open(_MLBB_EMULATOR_SETTINGS, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except FileNotFoundError:
        return False
    except Exception:
        # Fail closed: a broken config must not silently send the same event to two backends.
        return True
    route = str(data.get("route", "bridge")).strip().lower()
    return route != "bridge"


def _mlbb_emulator_engine_ready() -> bool:
    try:
        return (time.time() - os.path.getmtime(_MLBB_EMULATOR_READY)) < 3.0
    except OSError:
        return False


def _mlbb_emulator_relay_event(obj: dict) -> bool:
    try:
        payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(payload) > 8192:
            return False
        _MLBB_EMULATOR_RELAY_SOCKET.sendto(payload, ("127.0.0.1", 28743))
        return True
    except (OSError, TypeError, ValueError):
        return False

'''


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: integrate_emulator_engine.py source/mlbb-link")
    root = Path(sys.argv[1])
    host_path = root / "host/mlbb_link_host.py"
    if not host_path.is_file():
        raise SystemExit(f"Host script not found: {host_path}")
    host = host_path.read_text(encoding="utf-8")
    for statement in ("import json", "import os", "import socket", "import time"):
        if statement not in host:
            host = statement + "\n" + host
    if "_mlbb_emulator_route_enabled" not in host:
        if host.count(VALID_EVENT) != 1:
            raise SystemExit("The expected host valid_event function was not found exactly once")
        host = host.replace(VALID_EVENT, VALID_EVENT + "\n\n" + HELPERS, 1)
    elif "engine.ready" not in host or '("127.0.0.1", 28743)' not in host:
        raise SystemExit("Partial emulator route exists but readiness/loopback relay markers are missing")

    route_marker = "            forwarded = False"
    route_block = '''            # Route to exactly one backend. The marker is refreshed by the local engine every 0.75s.
            if _mlbb_emulator_route_enabled():
                if not _mlbb_emulator_engine_ready():
                    with STATE_LOCK:
                        STATE["last_error"] = "Emulator route selected but input engine is not ready on 127.0.0.1:28743"
                    continue
                if not _mlbb_emulator_relay_event(obj):
                    with STATE_LOCK:
                        STATE["last_error"] = "Could not relay event to emulator input engine"
                    continue
                now = time.time()
                with STATE_LOCK:
                    STATE["last_error"] = None
                    STATE["last_phone"] = addr[0]
                    STATE["phone_seen_epoch"] = now
                    STATE["phone_connected"] = True
                    STATE["last_event"] = "Input routed to emulator engine"
                continue

            forwarded = False'''
    if "Input routed to emulator engine" not in host:
        if host.count(route_marker) != 1:
            raise SystemExit("Could not find the unique host event-forwarding point")
        host = host.replace(route_marker, route_block, 1)

    for required in ("_mlbb_emulator_route_enabled()", "_mlbb_emulator_engine_ready()",
                     "_mlbb_emulator_relay_event(obj)", '"Input routed to emulator engine"',
                     '("127.0.0.1", 28743)'):
        if required not in host:
            raise SystemExit(f"Emulator host integration check failed: {required}")
    host_path.write_text(host, encoding="utf-8")
    print("Integrated emulator input engine as an exclusive host route; legacy bridge remains the default.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
