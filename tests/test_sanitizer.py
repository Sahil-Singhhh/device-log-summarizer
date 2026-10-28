"""
Unit tests for Section 1 — sanitizer.py
"""

import unittest
from sanitizer import sanitize_readings


class TestSanitizeReadings(unittest.TestCase):

    def test_valid_numeric_inputs(self):
        """Test conversion of standard integers, floats, and numeric strings."""
        data = [10, 25.5, "42.0", "100"]
        expected = [10.0, 25.5, 42.0, 100.0]
        self.assertEqual(sanitize_readings(data), expected)

    def test_discard_none_and_non_convertible(self):
        """Test that None and non-numeric strings are discarded."""
        data = [None, "invalid", "N/A", 15.0, None, "error"]
        expected = [15.0]
        self.assertEqual(sanitize_readings(data), expected)

    def test_discard_negative_values(self):
        """Test that negative numbers and negative numeric strings are discarded."""
        data = [-1, -0.1, "-50.5", 0, 0.0, 20.0]
        expected = [0.0, 0.0, 20.0]
        self.assertEqual(sanitize_readings(data), expected)

    def test_cap_values_above_500(self):
        """Test that values strictly above 500.0 are capped at 500.0, and 500.0 remains 500.0."""
        data = [500.0, 500.1, 750, "999.9", 250.0]
        expected = [500.0, 500.0, 500.0, 500.0, 250.0]
        self.assertEqual(sanitize_readings(data), expected)

    def test_empty_input(self):
        """Test that empty input returns an empty list without errors."""
        self.assertEqual(sanitize_readings([]), [])

    def test_entirely_invalid_input(self):
        """Test that list containing only invalid or negative values returns an empty list."""
        data = [None, "corrupt", -10.0, "-99", "abc"]
        self.assertEqual(sanitize_readings(data), [])

    def test_mixed_comprehensive_cases(self):
        """Comprehensive test combining valid, invalid, negative, and capped values."""
        data = [35.5, None, "bad_data", -5.0, 600.0, "120.5", 500.0, -0.001]
        expected = [35.5, 500.0, 120.5, 500.0]
        self.assertEqual(sanitize_readings(data), expected)


if __name__ == "__main__":
    unittest.main()

