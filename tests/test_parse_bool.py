"""Offline regression tests for configuration boolean parsing."""

import unittest

from meraki_mcp_config import parse_bool


class ParseBoolTests(unittest.TestCase):
    def test_recognizes_canonical_strings_with_whitespace_and_case(self):
        self.assertTrue(parse_bool("  TrUe\t"))
        self.assertFalse(parse_bool("\nFaLsE "))

    def test_none_and_unrecognized_values_use_the_default(self):
        self.assertTrue(parse_bool(None, default=True))
        self.assertTrue(parse_bool("enabled", default=True))
        self.assertFalse(parse_bool("", default=False))

    def test_boolean_inputs_are_returned_without_string_coercion(self):
        self.assertTrue(parse_bool(True, default=False))
        self.assertFalse(parse_bool(False, default=True))

    def test_non_string_non_boolean_values_use_the_default(self):
        for value in (0, 1, [], object()):
            with self.subTest(value=value):
                self.assertTrue(parse_bool(value, default=True))


if __name__ == "__main__":
    unittest.main()
