#!/usr/bin/env python3
"""Unit tests for the mapping engine; these never open /dev/uinput."""
from __future__ import annotations

import contextlib
import io
import json
import math
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import input_engine
from input_engine import InputEngine, STUCK_TOUCH_TIMEOUT_SECONDS
from profiles import validate_profile

DEFAULT_PROFILE = Path(__file__).resolve().parents[1] / "profile_default.json"


class RecordingBackend:
    def __init__(self):
        self.active: set[str] = set()
        self.events: list[tuple[str, str, float | None, float | None]] = []

    def touch_down(self, token: str, x: float, y: float) -> None:
        if token in self.active:
            raise AssertionError(f"duplicate down for active token: {token}")
        self.active.add(token)
        self.events.append(("down", token, x, y))

    def touch_move(self, token: str, x: float, y: float) -> None:
        if token in self.active:
            self.events.append(("move", token, x, y))

    def touch_up(self, token: str) -> None:
        if token in self.active:
            self.active.remove(token)
        self.events.append(("up", token, None, None))

    def release_all(self) -> None:
        for token in list(self.active):
            self.touch_up(token)

    def close(self) -> None:
        self.release_all()


class InputEngineTests(unittest.TestCase):
    def setUp(self):
        profile = json.loads(DEFAULT_PROFILE.read_text(encoding="utf-8"))
        self.profile = validate_profile(profile)
        self.backend = RecordingBackend()
        self.engine = InputEngine(self.profile, self.backend)

    def mapping_alias(self, identifier: str) -> str:
        mapping = next(m for m in self.profile["mappings"] if m["id"] == identifier)
        return mapping["buttonNames"][0]

    def test_button_down_and_up_release_the_same_contact(self):
        alias = self.mapping_alias("attack")
        self.engine.handle({"type": "button", "name": alias, "state": "down"})
        self.assertIn("phone:attack", self.backend.active)
        self.engine.handle({"type": "button", "name": alias, "state": "up"})
        self.assertNotIn("phone:attack", self.backend.active)

    def test_skill_gesture_moves_and_releases(self):
        alias = self.mapping_alias("skill1")
        self.engine.handle({"type": "gesture", "name": alias, "state": "down", "x": 0.3, "y": 0.4})
        self.engine.handle({"type": "gesture", "name": alias, "state": "move", "x": 0.8, "y": 0.55})
        self.engine.handle({"type": "gesture", "name": alias, "state": "up", "x": 0.8, "y": 0.55})
        self.assertEqual([e[0] for e in self.backend.events].count("down"), 1)
        self.assertGreaterEqual([e[0] for e in self.backend.events].count("move"), 1)
        self.assertNotIn("gesture:skill1", self.backend.active)
        self.assertNotIn("skill1", self.engine.gestures)

    def test_duplicate_skill_down_does_not_restart_contact(self):
        alias = self.mapping_alias("skill1")
        self.engine.handle({"type": "gesture", "name": alias, "state": "down", "x": 0.2, "y": 0.3})
        self.engine.handle({"type": "gesture", "name": alias, "state": "down", "x": 0.6, "y": 0.5})
        self.assertEqual([e[0] for e in self.backend.events].count("down"), 1)
        self.assertEqual([e[0] for e in self.backend.events].count("move"), 1)
        self.assertEqual(self.engine.gestures["skill1"]["origin"], (0.6, 0.5))

    def test_joystick_duplicate_down_and_move_keep_one_contact(self):
        alias = self.mapping_alias("joystick")
        self.engine.handle({"type": "joystick", "name": alias, "state": "down", "x": 0.2, "y": 0.8})
        self.engine.handle({"type": "joystick", "name": alias, "state": "down", "x": 0.25, "y": 0.8})
        self.engine.handle({"type": "joystick", "name": alias, "state": "move", "x": 0.4, "y": 0.8})
        self.assertEqual([e[0] for e in self.backend.events].count("down"), 1)
        self.assertEqual([e[0] for e in self.backend.events].count("move"), 2)
        self.engine.handle({"type": "joystick", "name": alias, "state": "up", "x": 0.4, "y": 0.8})
        self.assertNotIn("joystick:joystick", self.backend.active)

    def test_non_finite_coordinates_are_ignored(self):
        alias = self.mapping_alias("skill1")
        self.engine.handle({"type": "gesture", "name": alias, "state": "down", "x": math.nan, "y": 0.5})
        self.engine.handle({"type": "joystick", "name": self.mapping_alias("joystick"),
                            "state": "down", "x": 0.3, "y": math.inf})
        self.assertFalse(self.backend.active)
        self.assertFalse(self.engine.gestures)
        self.assertFalse(self.engine.joystick_origin)

    def test_idle_watchdog_releases_all_contacts_and_engine_state(self):
        alias = self.mapping_alias("attack")
        self.engine.handle({"type": "button", "name": alias, "state": "down"})
        self.assertTrue(self.backend.active)
        self.engine.last_input = time.monotonic() - STUCK_TOUCH_TIMEOUT_SECONDS - 1
        self.engine.release_stale_contacts()
        self.assertFalse(self.backend.active)
        self.assertFalse(self.engine.button_tokens)
        self.assertFalse(self.engine.gestures)
        self.assertFalse(self.engine.joystick_origin)

    def test_profile_check_cli_never_starts_input_server(self):
        args = ["input_engine.py", "--profile", str(DEFAULT_PROFILE), "--check-profile"]
        with patch.object(sys, "argv", args), contextlib.redirect_stdout(io.StringIO()) as output:
            result = input_engine.main()
        self.assertEqual(result, 0)
        self.assertIn("Profile OK:", output.getvalue())
        self.assertIn("no input device opened", output.getvalue())


if __name__ == "__main__":
    unittest.main()
