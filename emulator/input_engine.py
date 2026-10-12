#!/usr/bin/env python3
"""Loopback UDP to Linux uinput touch bridge for MLBB Link Emulator Tools.

This process never binds the controller UDP port exposed on the LAN. The existing
MLBB Link host forwards validated JSON to 127.0.0.1:28743 only when settings.json
selects route='emulator'. Physical keyboard capture is opt-in.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import logging
import math
import os
import signal
import socket
import struct
import threading
import time
from typing import Any

from profiles import load_profile, load_settings, profile_path, settings_path, user_config_dir

LOG = logging.getLogger("mlbb-link-emulator")
MAX_PACKET_BYTES = 8192
MAX_EVENTS_PER_SECOND = 2500
STUCK_TOUCH_TIMEOUT_SECONDS = 3.0

# Linux input-event-codes.h / uinput.h constants.
EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
SYN_REPORT = 0
BTN_TOOL_FINGER, BTN_TOUCH = 325, 330
ABS_X, ABS_Y, ABS_PRESSURE = 0, 1, 24
ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y = 47, 53, 54
ABS_MT_TRACKING_ID, ABS_MT_PRESSURE = 57, 58
BUS_USB = 0x03
INPUT_PROP_DIRECT = 1
ABS_CNT = 0x40
UI_DEV_CREATE = 1
UI_DEV_DESTROY = 2
UI_SET_EVBIT = 100
UI_SET_KEYBIT = 101
UI_SET_ABSBIT = 103
UI_SET_PROPBIT = 110


def _ioc(direction: int, kind: int, number: int, size: int = 0) -> int:
    return (direction << 30) | (size << 16) | (kind << 8) | number


def _io(kind: int, number: int) -> int:
    return _ioc(0, kind, number)


def _iow(kind: int, number: int, size: int = 4) -> int:
    return _ioc(1, kind, number, size)


def _set_ioctl_bit(fd: int, request: int, value: int) -> None:
    fcntl.ioctl(fd, request, struct.pack("i", value))


def _normalise_name(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


class TouchBackend:
    """Direct multi-touch Protocol-B uinput device. Requires access to /dev/uinput."""

    def __init__(self, screen_width: int, screen_height: int, max_points: int = 10,
                 device_path: str = "/dev/uinput") -> None:
        self.screen_width = int(screen_width)
        self.screen_height = int(screen_height)
        self.max_points = max(1, min(int(max_points), 10))
        self.device_path = device_path
        self.fd: int | None = None
        self.active: dict[str, int] = {}
        self._tracking = 1
        self._lock = threading.Lock()
        if self.screen_width < 320 or self.screen_height < 200:
            raise ValueError("Screen dimensions are too small for touch injection")
        self._create_device()

    @staticmethod
    def _event_struct(event_type: int, code: int, value: int) -> bytes:
        now = time.time()
        seconds = int(now)
        microseconds = int((now - seconds) * 1_000_000)
        # Linux x86_64 input_event layout: timeval + type + code + value (24 bytes).
        return struct.pack("@llHHi", seconds, microseconds, event_type, code, value)

    def _create_device(self) -> None:
        try:
            fd = os.open(self.device_path, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as exc:
            raise RuntimeError(
                f"Cannot open {self.device_path}: {exc}. Run emulator/install.sh --setup-uinput, "
                "then log out and back in. The engine intentionally does not run as root."
            ) from exc
        try:
            for ev_type in (EV_KEY, EV_ABS):
                _set_ioctl_bit(fd, _iow(ord("U"), UI_SET_EVBIT), ev_type)
            for code in (BTN_TOUCH, BTN_TOOL_FINGER):
                _set_ioctl_bit(fd, _iow(ord("U"), UI_SET_KEYBIT), code)
            axes = {
                ABS_X: (0, self.screen_width - 1),
                ABS_Y: (0, self.screen_height - 1),
                ABS_PRESSURE: (0, 255),
                ABS_MT_SLOT: (0, self.max_points - 1),
                ABS_MT_TRACKING_ID: (-1, 65535),
                ABS_MT_POSITION_X: (0, self.screen_width - 1),
                ABS_MT_POSITION_Y: (0, self.screen_height - 1),
                ABS_MT_PRESSURE: (0, 255),
            }
            for code in axes:
                _set_ioctl_bit(fd, _iow(ord("U"), UI_SET_ABSBIT), code)
            try:
                _set_ioctl_bit(fd, _iow(ord("U"), UI_SET_PROPBIT), INPUT_PROP_DIRECT)
            except OSError:
                pass
            mins = [0] * ABS_CNT
            maxs = [0] * ABS_CNT
            fuzz = [0] * ABS_CNT
            flat = [0] * ABS_CNT
            for code, (minimum, maximum) in axes.items():
                mins[code] = minimum
                maxs[code] = maximum
            fmt = "<80sHHHHI" + ("i" * ABS_CNT * 4)
            name = b"MLBB Link Multi-touch"
            packed = struct.pack(fmt, name, BUS_USB, 0x1D6B, 0x0104, 1, 0,
                                 *maxs, *mins, *fuzz, *flat)
            os.write(fd, packed)
            fcntl.ioctl(fd, _io(ord("U"), UI_DEV_CREATE))
            time.sleep(0.05)
            self.fd = fd
            LOG.info("Created uinput touchscreen %s (%dx%d, %d contacts)",
                     self.device_path, self.screen_width, self.screen_height, self.max_points)
        except Exception:
            os.close(fd)
            raise

    def _emit(self, events: list[tuple[int, int, int]]) -> None:
        if self.fd is None:
            raise RuntimeError("Touch device is not created")
        body = b"".join(self._event_struct(t, c, v) for t, c, v in events)
        body += self._event_struct(EV_SYN, SYN_REPORT, 0)
        with self._lock:
            view = memoryview(body)
            while view:
                written = os.write(self.fd, view)
                view = view[written:]

    def _position(self, x: float, y: float) -> tuple[int, int]:
        xx = max(0, min(self.screen_width - 1, int(round(x))))
        yy = max(0, min(self.screen_height - 1, int(round(y))))
        return xx, yy

    def _slot_for(self, token: str) -> int:
        if token in self.active:
            return self.active[token]
        occupied = set(self.active.values())
        for slot in range(self.max_points):
            if slot not in occupied:
                self.active[token] = slot
                return slot
        raise RuntimeError(f"All {self.max_points} touch slots are in use; release a control first")

    def touch_down(self, token: str, x: float, y: float) -> None:
        xx, yy = self._position(x, y)
        first = not self.active
        slot = self._slot_for(token)
        tracking_id = self._tracking
        self._tracking = 1 if tracking_id >= 65000 else tracking_id + 1
        events = [(EV_ABS, ABS_MT_SLOT, slot),
                  (EV_ABS, ABS_MT_TRACKING_ID, tracking_id),
                  (EV_ABS, ABS_MT_POSITION_X, xx),
                  (EV_ABS, ABS_MT_POSITION_Y, yy),
                  (EV_ABS, ABS_MT_PRESSURE, 80),
                  (EV_ABS, ABS_X, xx), (EV_ABS, ABS_Y, yy), (EV_ABS, ABS_PRESSURE, 80)]
        if first:
            events.extend([(EV_KEY, BTN_TOOL_FINGER, 1), (EV_KEY, BTN_TOUCH, 1)])
        self._emit(events)

    def touch_move(self, token: str, x: float, y: float) -> None:
        slot = self.active.get(token)
        if slot is None:
            return
        xx, yy = self._position(x, y)
        self._emit([(EV_ABS, ABS_MT_SLOT, slot),
                    (EV_ABS, ABS_MT_POSITION_X, xx), (EV_ABS, ABS_MT_POSITION_Y, yy),
                    (EV_ABS, ABS_MT_PRESSURE, 80),
                    (EV_ABS, ABS_X, xx), (EV_ABS, ABS_Y, yy), (EV_ABS, ABS_PRESSURE, 80)])

    def touch_up(self, token: str) -> None:
        slot = self.active.pop(token, None)
        if slot is None:
            return
        events = [(EV_ABS, ABS_MT_SLOT, slot),
                  (EV_ABS, ABS_MT_TRACKING_ID, -1),
                  (EV_ABS, ABS_MT_PRESSURE, 0)]
        if not self.active:
            events.extend([(EV_KEY, BTN_TOUCH, 0), (EV_KEY, BTN_TOOL_FINGER, 0)])
        self._emit(events)

    def release_all(self) -> None:
        for token in list(self.active):
            try:
                self.touch_up(token)
            except OSError:
                self.active.pop(token, None)

    def close(self) -> None:
        self.release_all()
        fd, self.fd = self.fd, None
        if fd is not None:
            try:
                fcntl.ioctl(fd, _io(ord("U"), UI_DEV_DESTROY))
            except OSError:
                pass
            os.close(fd)


class LogBackend:
    """Safe dry-run backend for testing profiles without injecting input."""

    def __init__(self, screen_width: int, screen_height: int, max_points: int = 10) -> None:
        self.screen_width, self.screen_height = screen_width, screen_height
        self.active: set[str] = set()

    def touch_down(self, token: str, x: float, y: float) -> None:
        self.active.add(token)
        LOG.info("DRY-RUN DOWN %-16s (%d,%d)", token, int(x), int(y))

    def touch_move(self, token: str, x: float, y: float) -> None:
        if token in self.active:
            LOG.info("DRY-RUN MOVE %-15s (%d,%d)", token, int(x), int(y))

    def touch_up(self, token: str) -> None:
        if token in self.active:
            self.active.remove(token)
            LOG.info("DRY-RUN UP   %s", token)

    def release_all(self) -> None:
        for token in list(self.active):
            self.touch_up(token)

    def close(self) -> None:
        self.release_all()


class InputEngine:
    def __init__(self, profile: dict[str, Any], backend: Any) -> None:
        self.profile = profile
        self.backend = backend
        screen = profile["screen"]
        self.rect = screen["targetRect"]
        self.touch_options = profile.get("touch", {})
        self.by_name: dict[str, dict[str, Any]] = {}
        self.by_key: dict[str, dict[str, Any]] = {}
        self.by_id: dict[str, dict[str, Any]] = {}
        self.button_tokens: dict[str, str] = {}
        self.gestures: dict[str, dict[str, Any]] = {}
        self.joystick_origin: dict[str, tuple[float, float]] = {}
        self.last_input = time.monotonic()
        for mapping in profile["mappings"]:
            if not mapping.get("enabled", True):
                continue
            self.by_id[mapping["id"]] = mapping
            for alias in mapping["buttonNames"]:
                self.by_name[_normalise_name(alias)] = mapping
            if mapping.get("key"):
                self.by_key[str(mapping["key"]).upper()] = mapping

    def _point(self, mapping: dict[str, Any], nx: float | None = None,
               ny: float | None = None) -> tuple[float, float]:
        rect = self.rect
        x = float(mapping["x"] if nx is None else nx)
        y = float(mapping["y"] if ny is None else ny)
        return (rect["x"] + max(0.0, min(1.0, x)) * rect["width"],
                rect["y"] + max(0.0, min(1.0, y)) * rect["height"])

    def _touch_radius(self, mapping: dict[str, Any]) -> float:
        return float(mapping.get("radius", 0.08)) * min(self.rect["width"], self.rect["height"])

    def _source_delta(self, mapping: dict[str, Any], origin: tuple[float, float],
                      x: float, y: float, full_travel: float) -> tuple[float, float]:
        dx, dy = x - origin[0], y - origin[1]
        magnitude = math.hypot(dx, dy)
        deadzone = float(mapping.get("deadzone", 0.02))
        if magnitude <= deadzone:
            return self._point(mapping)
        scale = min(1.0, magnitude / max(full_travel, 0.001))
        radius = self._touch_radius(mapping) * scale
        cx, cy = self._point(mapping)
        return (cx + (dx / magnitude) * radius, cy + (dy / magnitude) * radius)

    def handle(self, event: dict[str, Any]) -> None:
        self.last_input = time.monotonic()
        event_type = str(event.get("type", "")).lower()
        if event_type == "button":
            self._button(event)
        elif event_type == "gesture":
            self._gesture(event)
        elif event_type == "joystick":
            self._joystick(event)
        elif event_type == "key":
            self._key(event)
        # Heartbeat and hero-selection events are intentionally metadata-only.

    def _button(self, event: dict[str, Any]) -> None:
        name = _normalise_name(event.get("name"))
        mapping = self.by_name.get(name)
        if mapping is None:
            return
        token = "phone:" + mapping["id"]
        state = str(event.get("state", "")).lower()
        if state == "down":
            if token in self.button_tokens.values():
                return
            x, y = self._point(mapping)
            self.backend.touch_down(token, x, y)
            self.button_tokens[mapping["id"]] = token
        elif state in ("up", "cancel"):
            self.backend.touch_up(token)
            self.button_tokens.pop(mapping["id"], None)

    def _gesture(self, event: dict[str, Any]) -> None:
        mapping = self.by_name.get(_normalise_name(event.get("name")))
        if mapping is None:
            return
        identifier = mapping["id"]
        token = "gesture:" + identifier
        state = str(event.get("state", "")).lower()
        try:
            x, y = float(event.get("x", 0.5)), float(event.get("y", 0.5))
        except (TypeError, ValueError):
            return
        if state == "down":
            self.gestures[identifier] = {"origin": (x, y), "token": token}
            px, py = self._point(mapping)
            self.backend.touch_down(token, px, py)
        elif state == "move":
            gesture = self.gestures.get(identifier)
            if gesture is None:
                return
            px, py = self._source_delta(mapping, gesture["origin"], x, y,
                                        float(self.touch_options.get("skillAimFullTravel", 0.16)))
            self.backend.touch_move(token, px, py)
        elif state in ("up", "cancel"):
            if identifier in self.gestures:
                self.backend.touch_up(token)
                self.gestures.pop(identifier, None)

    def _joystick(self, event: dict[str, Any]) -> None:
        mapping = next((m for m in self.by_id.values() if m["kind"] == "joystick"), None)
        if mapping is None:
            return
        token = "joystick:" + mapping["id"]
        state = str(event.get("state", "")).lower()
        try:
            x, y = float(event.get("x", mapping["x"])), float(event.get("y", mapping["y"]))
        except (TypeError, ValueError):
            return
        if state == "down":
            self.joystick_origin[mapping["id"]] = (x, y)
            px, py = self._point(mapping)
            self.backend.touch_down(token, px, py)
        elif state == "move":
            origin = self.joystick_origin.get(mapping["id"])
            if origin is None:
                return
            px, py = self._source_delta(mapping, origin, x, y,
                                        float(self.touch_options.get("joystickFullTravel", 0.14)))
            self.backend.touch_move(token, px, py)
        elif state in ("up", "cancel"):
            self.backend.touch_up(token)
            self.joystick_origin.pop(mapping["id"], None)

    def _key(self, event: dict[str, Any]) -> None:
        key = str(event.get("name", "")).strip().upper().replace(" ", "_")
        mapping = self.by_key.get(key)
        if mapping is None:
            return
        self._button({"type": "button", "name": mapping["id"], "state": event.get("state")})

    def release_stale_contacts(self) -> None:
        if self.backend.active and (time.monotonic() - self.last_input) > STUCK_TOUCH_TIMEOUT_SECONDS:
            LOG.warning("No input for %.1fs with fingers held; releasing all touches as a safety measure",
                        STUCK_TOUCH_TIMEOUT_SECONDS)
            self.backend.release_all()
            self.button_tokens.clear()
            self.gestures.clear()
            self.joystick_origin.clear()


class KeyboardCapture:
    """Optional global-key source via python-evdev. Only configured key bindings are forwarded."""

    def __init__(self, engine: InputEngine) -> None:
        try:
            from evdev import InputDevice, list_devices, ecodes
        except ImportError as exc:
            raise RuntimeError("Global keyboard capture requires the optional package: pip install -r requirements-keyboard.txt") from exc
        self.InputDevice, self.list_devices, self.ecodes = InputDevice, list_devices, ecodes
        self.engine = engine
        self.bindings: dict[int, str] = {}
        for key in engine.by_key:
            code = getattr(ecodes, "KEY_" + key, None)
            if code is not None:
                self.bindings[int(code)] = key
        if not self.bindings:
            raise RuntimeError("No profile keys map to Linux keyboard key codes")
        self.threads: list[threading.Thread] = []
        self.devices: list[Any] = []
        self.stop_event = threading.Event()

    def start(self) -> None:
        for path in self.list_devices():
            try:
                device = self.InputDevice(path)
                caps = device.capabilities()
                if self.ecodes.EV_KEY not in caps or not any(code in caps[self.ecodes.EV_KEY] for code in self.bindings):
                    device.close()
                    continue
                self.devices.append(device)
                thread = threading.Thread(target=self._read_device, args=(device,), daemon=True,
                                          name="keyboard-" + str(device.name)[:24])
                self.threads.append(thread)
                thread.start()
                LOG.info("Keyboard capture enabled for configured keys from %s", device.name)
            except (OSError, PermissionError):
                continue
        if not self.devices:
            raise RuntimeError("No readable keyboard devices found. Global keyboard capture is opt-in and needs /dev/input access.")

    def _read_device(self, device: Any) -> None:
        while not self.stop_event.is_set():
            try:
                for event in device.read_loop():
                    if self.stop_event.is_set():
                        return
                    if event.type != self.ecodes.EV_KEY or event.code not in self.bindings:
                        continue
                    # value 2 is key repeat; ignore it to prevent repeat casts / macro behavior.
                    if event.value not in (0, 1):
                        continue
                    self.engine.handle({"type": "key", "name": self.bindings[event.code],
                                        "state": "down" if event.value == 1 else "up"})
            except (OSError, PermissionError):
                return

    def close(self) -> None:
        self.stop_event.set()
        for device in self.devices:
            try:
                device.close()
            except OSError:
                pass


def run_server(args: argparse.Namespace) -> int:
    settings = load_settings(args.settings)
    profile = load_profile(args.profile)
    screen = profile["screen"]
    if args.screen_width:
        screen["width"] = int(args.screen_width)
    if args.screen_height:
        screen["height"] = int(args.screen_height)
    width, height = int(screen["width"]), int(screen["height"])
    target = screen["targetRect"]
    if target["x"] + target["width"] > width or target["y"] + target["height"] > height:
        raise ValueError("Profile targetRect falls outside the input screen dimensions; calibrate your profile first")
    max_points = int(profile.get("touch", {}).get("maxPoints", 10))
    if args.backend == "uinput":
        backend: Any = TouchBackend(width, height, max_points, args.device)
    else:
        backend = LogBackend(width, height, max_points)
    engine = InputEngine(profile, backend)
    keyboard: KeyboardCapture | None = None
    if args.capture_keyboard:
        keyboard = KeyboardCapture(engine)
        keyboard.start()

    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
    receiver.bind((args.bind, args.port))
    receiver.settimeout(0.05)
    stop = threading.Event()
    ready_marker = user_config_dir() / "engine.ready"
    ready_marker.parent.mkdir(parents=True, exist_ok=True)
    ready_marker.write_text(json.dumps({"pid": os.getpid(), "port": args.port, "started": time.time()}), encoding="utf-8")
    last_ready_refresh = time.monotonic()

    def stop_handler(_signum: int, _frame: Any) -> None:
        stop.set()

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)
    packets = 0
    window_start = time.monotonic()
    try:
        LOG.info("Input engine listening on %s:%d (backend=%s). It is not exposed to the LAN.",
                 args.bind, args.port, args.backend)
        while not stop.is_set():
            now_ready = time.monotonic()
            if now_ready - last_ready_refresh >= 0.75:
                try:
                    os.utime(ready_marker, None)
                except OSError:
                    pass
                last_ready_refresh = now_ready
            try:
                payload, address = receiver.recvfrom(MAX_PACKET_BYTES + 1)
            except socket.timeout:
                engine.release_stale_contacts()
                continue
            except OSError as exc:
                if stop.is_set():
                    break
                LOG.warning("UDP receiver error: %s", exc)
                continue
            if address[0] not in ("127.0.0.1", "::1"):
                continue
            if len(payload) > MAX_PACKET_BYTES:
                continue
            now = time.monotonic()
            if now - window_start >= 1.0:
                window_start, packets = now, 0
            packets += 1
            if packets > MAX_EVENTS_PER_SECOND:
                if packets == MAX_EVENTS_PER_SECOND + 1:
                    LOG.warning("Input rate limit reached; dropping excess packets")
                continue
            try:
                event = json.loads(payload.decode("utf-8"))
                if not isinstance(event, dict):
                    continue
                if event.get("type") not in ("button", "joystick", "gesture", "key", "heartbeat", "hero"):
                    continue
                engine.handle(event)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
                LOG.debug("Dropped malformed input packet: %s", exc)
            except Exception:
                LOG.exception("Input dispatch failed; releasing touches")
                engine.backend.release_all()
                engine.button_tokens.clear()
                engine.gestures.clear()
                engine.joystick_origin.clear()
    finally:
        stop.set()
        receiver.close()
        if keyboard is not None:
            keyboard.close()
        backend.close()
        try:
            marker_data = json.loads(ready_marker.read_text(encoding="utf-8"))
            if int(marker_data.get("pid", -1)) == os.getpid():
                ready_marker.unlink(missing_ok=True)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MLBB Link multi-touch emulator input engine")
    parser.add_argument("--profile", default=str(profile_path()))
    parser.add_argument("--settings", default=str(settings_path()))
    parser.add_argument("--bind", default="127.0.0.1", choices=("127.0.0.1",))
    parser.add_argument("--port", type=int, default=28743, choices=(28743,))
    parser.add_argument("--device", default="/dev/uinput")
    parser.add_argument("--backend", choices=("uinput", "log"), default="uinput")
    parser.add_argument("--capture-keyboard", action="store_true",
                        help="Opt in to reading physical keyboard EV_KEY events; can expose keystrokes, so only enable on your own trusted desktop.")
    parser.add_argument("--version", action="version", version="MLBB Link Emulator Input Engine 0.15.0")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        return run_server(args)
    except Exception as exc:
        LOG.error("%s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
