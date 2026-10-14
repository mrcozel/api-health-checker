
import unittest
from unittest.mock import patch

from health_checker import load_positive_integer


class TestConfiguration(unittest.TestCase):

    @patch.dict("os.environ", {"CHECK_INTERVAL": "30"})
    def test_load_valid_setting(self):
        self.assertEqual(
            load_positive_integer("CHECK_INTERVAL", 60),
            30
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_use_default_when_setting_missing(self):
        self.assertEqual(
            load_positive_integer("TIMEOUT", 5),
            5
        )

    @patch.dict("os.environ", {"TIMEOUT": "abc"})
    def test_reject_non_numeric_setting(self):
        with self.assertRaisesRegex(
            ValueError, "TIMEOUT must be a positive whole number"
        ):
            load_positive_integer("TIMEOUT", 5)

    @patch.dict("os.environ", {"TIMEOUT": "0"})
    def test_reject_zero(self):
        with self.assertRaisesRegex(
            ValueError, "TIMEOUT must be at least 1"
        ):
            load_positive_integer("TIMEOUT", 5)

    @patch.dict("os.environ", {"TIMEOUT": "-2"})
    def test_reject_negative_number(self):
        with self.assertRaisesRegex(
            ValueError, "TIMEOUT must be at least 1"
        ):
            load_positive_integer("TIMEOUT", 5)


if __name__ == "__main__":
    unittest.main()
