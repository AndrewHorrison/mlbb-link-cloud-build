#!/usr/bin/env python3
"""Validated local configuration for MLBB Link Emulator Tools."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

APP_DIR_NAME = "mlbb-link-emulator"
DEFAULT_PROFILE_NAME = "MLBB Landscape"
KEY_PATTERN = re.compile(r"^[A-Z0-9_+\-]{1,20}$")
MAX_MAPPINGS = 48


def config_dir() -> Path:
    root = os.environ.get("XDG_CONFIG_HOME")
    return Path(root).expanduser() if root else Path.home() / ".config"


def user_config_dir() -> Path:
    return config_dir() / APP_DIR_NAME


def user_data_dir() -> Path:
    root = os.environ.get("XDG_DATA_HOME")
    return (Path(root).expanduser() if root else Path.home() / ".local" / "share") / APP_DIR_NAME


def settings_path() -> Path:
    return user_config_dir() / "settings.json"


def profile_path() -> Path:
    return user_config_dir() / "profile.json"


def default_settings() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "route": "bridge",
        "udpListenAddress": "127.0.0.1",
        "udpListenPort": 28743,
        "keyboardCaptureEnabled": False,
        "screenWidth": 1920,
        "screenHeight": 1080,
    }


def load_settings(path: str | Path | None = None) -> dict[str, Any]:
    file_path = Path(path).expanduser() if path else settings_path()
    value = default_settings()
    if file_path.is_file():
        try:
            source = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(source, dict):
                raise ValueError("Settings file must contain a JSON object")
            value.update(source)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read settings file {file_path}: {exc}") from exc
    if value.get("route") not in ("bridge", "emulator"):
        raise ValueError("settings.route must be 'bridge' or 'emulator'")
    port = int(value.get("udpListenPort", 28743))
    if port != 28743:
        raise ValueError("Emulator relay port is intentionally fixed to 28743")
    width, height = int(value.get("screenWidth", 1920)), int(value.get("screenHeight", 1080))
    if not (320 <= width <= 16384 and 200 <= height <= 16384):
        raise ValueError("Screen size is outside the supported range")
    value["udpListenPort"] = port
    value["screenWidth"], value["screenHeight"] = width, height
    value["keyboardCaptureEnabled"] = bool(value.get("keyboardCaptureEnabled", False))
    return value


def save_json_atomic(path: str | Path, value: dict[str, Any]) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def _normalise_key(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return ""
    key = str(value).strip().upper().replace(" ", "_")
    if not KEY_PATTERN.fullmatch(key):
        raise ValueError(f"Invalid key binding: {value!r}")
    return key


def validate_profile(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Profile must be a JSON object")
    profile = dict(raw)
    if int(profile.get("schemaVersion", 0)) != 1:
        raise ValueError("Unsupported profile schemaVersion; expected 1")

    screen = profile.get("screen")
    if not isinstance(screen, dict):
        raise ValueError("Profile screen object is missing")
    width, height = int(screen.get("width", 0)), int(screen.get("height", 0))
    if not (320 <= width <= 16384 and 200 <= height <= 16384):
        raise ValueError("Profile screen width/height is invalid")
    target = screen.get("targetRect")
    if not isinstance(target, dict):
        raise ValueError("screen.targetRect is missing")
    left, top = int(target.get("x", 0)), int(target.get("y", 0))
    target_width, target_height = int(target.get("width", width)), int(target.get("height", height))
    if left < 0 or top < 0 or target_width < 1 or target_height < 1:
        raise ValueError("Target rectangle must have positive size and non-negative origin")
    if left + target_width > width or top + target_height > height:
        raise ValueError("Target rectangle extends past configured screen dimensions")
    screen = dict(screen)
    screen.update(width=width, height=height, targetRect={
        "x": left, "y": top, "width": target_width, "height": target_height
    })

    rows = profile.get("mappings")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Profile must include at least one mapping")
    if len(rows) > MAX_MAPPINGS:
        raise ValueError(f"Too many mappings (maximum {MAX_MAPPINGS})")
    checked = []
    ids = set()
    accepted_kinds = {"tap", "skill", "joystick"}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each mapping must be a JSON object")
        item = dict(row)
        identifier = str(item.get("id", "")).strip()
        if not identifier or len(identifier) > 48 or not re.fullmatch(r"[a-zA-Z0-9_.-]+", identifier):
            raise ValueError(f"Invalid mapping id: {identifier!r}")
        if identifier in ids:
            raise ValueError(f"Duplicate mapping id: {identifier}")
        ids.add(identifier)
        kind = str(item.get("kind", "tap")).lower()
        if kind not in accepted_kinds:
            raise ValueError(f"Mapping {identifier}: kind must be one of {sorted(accepted_kinds)}")
        x, y = float(item.get("x", 0.5)), float(item.get("y", 0.5))
        radius, deadzone = float(item.get("radius", 0.08)), float(item.get("deadzone", 0.02))
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError(f"Mapping {identifier}: x/y must be normalized to 0..1")
        if not (0.005 <= radius <= 0.35):
            raise ValueError(f"Mapping {identifier}: radius must be from 0.005 to 0.35")
        if not (0.0 <= deadzone <= 0.35):
            raise ValueError(f"Mapping {identifier}: deadzone must be from 0 to 0.35")
        names = item.get("buttonNames", [identifier])
        if not isinstance(names, list) or not names:
            raise ValueError(f"Mapping {identifier}: buttonNames must be a non-empty list")
        normal_names = []
        for name in names:
            text = re.sub(r"[^a-z0-9]+", "", str(name).lower())
            if text and text not in normal_names:
                normal_names.append(text)
        if not normal_names:
            raise ValueError(f"Mapping {identifier}: no usable button names")
        key = _normalise_key(item.get("key", ""))
        checked.append({
            **item,
            "id": identifier,
            "label": str(item.get("label", identifier))[:64],
            "kind": kind,
            "x": x,
            "y": y,
            "radius": radius,
            "deadzone": deadzone,
            "buttonNames": normal_names,
            "key": key,
            "enabled": bool(item.get("enabled", True)),
        })
    profile.update(schemaVersion=1, name=str(profile.get("name", DEFAULT_PROFILE_NAME))[:80],
                   screen=screen, mappings=checked)
    profile.setdefault("description", "Customizable MLBB-style key mapping. Not an official game profile.")
    return profile


def load_profile(path: str | Path | None = None) -> dict[str, Any]:
    file_path = Path(path).expanduser() if path else profile_path()
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Profile not found at {file_path}. Open the MLBB Link Emulator launcher to create it.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in profile {file_path}, line {exc.lineno}: {exc.msg}") from exc
    except OSError as exc:
        raise ValueError(f"Cannot read profile {file_path}: {exc}") from exc
    return validate_profile(raw)


def save_profile(profile: dict[str, Any], path: str | Path | None = None) -> dict[str, Any]:
    checked = validate_profile(profile)
    save_json_atomic(Path(path).expanduser() if path else profile_path(), checked)
    return checked
