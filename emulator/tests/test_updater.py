#!/usr/bin/env python3
import unittest

from updater import is_newer, version_tuple


class VersionComparisonTests(unittest.TestCase):
    def test_new_minor_version_is_newer(self):
        self.assertTrue(is_newer("0.16.0", "0.15.9"))

    def test_equal_version_is_not_newer(self):
        self.assertFalse(is_newer("0.15.0", "0.15.0"))

    def test_short_semver_is_zero_padded(self):
        self.assertFalse(is_newer("0.15", "0.15.0"))
        self.assertTrue(is_newer("0.15.1", "0.15"))

    def test_numeric_not_lexicographic(self):
        self.assertTrue(is_newer("0.15.10", "0.15.2"))

    def test_rejects_non_numeric_version(self):
        with self.assertRaises(ValueError):
            version_tuple("latest")


if __name__ == "__main__":
    unittest.main()
