#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

from profiles import validate_profile

DEFAULT = Path(__file__).resolve().parents[1] / "profile_default.json"


class ProfileValidationTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(DEFAULT.read_text(encoding="utf-8"))

    def test_default_profile_validates(self):
        result = validate_profile(self.profile)
        self.assertEqual(result["name"], "MLBB Landscape")
        self.assertGreaterEqual(len(result["mappings"]), 6)

    def test_rejects_duplicate_ids(self):
        clone = json.loads(json.dumps(self.profile))
        clone["mappings"][1]["id"] = clone["mappings"][0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_profile(clone)

    def test_rejects_coordinates_outside_normalized_screen(self):
        clone = json.loads(json.dumps(self.profile))
        clone["mappings"][0]["x"] = 1.5
        with self.assertRaisesRegex(ValueError, "normalized"):
            validate_profile(clone)

    def test_rejects_target_rect_outside_screen(self):
        clone = json.loads(json.dumps(self.profile))
        clone["screen"]["targetRect"]["x"] = 1800
        with self.assertRaisesRegex(ValueError, "extends past"):
            validate_profile(clone)

    def test_key_names_normalized(self):
        clone = json.loads(json.dumps(self.profile))
        clone["mappings"][1]["key"] = "q"
        self.assertEqual(validate_profile(clone)["mappings"][1]["key"], "Q")


if __name__ == "__main__":
    unittest.main()
