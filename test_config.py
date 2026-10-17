
import json
import unittest
from unittest.mock import mock_open, patch

from health_checker import load_endpoints, load_positive_integer


class TestConfiguration(unittest.TestCase):

    def test_reject_duplicate_endpoint_names_with_different_urls(self):
        endpoints = [
            {"name": "Payments", "url": "https://example.com/first"},
            {"name": "Payments", "url": "https://example.com/second"},
        ]
        with patch("builtins.open", mock_open(read_data=json.dumps(endpoints))):
            with self.assertRaisesRegex(ValueError, "Duplicate endpoint name 'Payments'"):
                load_endpoints()

    def test_accept_unique_names_for_shared_url(self):
        endpoints = [
            {"name": "Payments", "url": "https://example.com/health"},
            {"name": "Orders", "url": "https://example.com/health"},
        ]
        with patch("builtins.open", mock_open(read_data=json.dumps(endpoints))):
            self.assertEqual(load_endpoints(), endpoints)

    def test_reject_invalid_endpoint_names(self):
        for name in ("   ", 42, ["Payments"]):
            with self.subTest(name=name):
                endpoints = [{"name": name, "url": "https://example.com"}]
                with patch("builtins.open", mock_open(read_data=json.dumps(endpoints))):
                    with self.assertRaisesRegex(ValueError, "name must be a non-empty string"):
                        load_endpoints()

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
