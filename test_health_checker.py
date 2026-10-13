
import unittest
from unittest.mock import patch, Mock
import health_checker


class TestCheckEndpoint(unittest.TestCase):

    @patch("health_checker.requests.get")
    def test_successful_response(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = health_checker.check_endpoint(
            "Test API",
            "https://example.com"
        )

        self.assertEqual(result["status"], "UP")
        self.assertEqual(result["http_code"], 200)

    @patch("health_checker.requests.get")
    def test_server_error(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = health_checker.check_endpoint(
            "Test API",
            "https://example.com"
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["http_code"], 500)

    
    @patch("health_checker.requests.get")
    def test_request_timeout(self, mock_get):
        import requests

        mock_get.side_effect = requests.exceptions.Timeout

        result = health_checker.check_endpoint(
            "Slow API",
            "https://example.com"
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertIsNone(result["http_code"])
        self.assertEqual(result["error"], "Request timed out")

    
    @patch("health_checker.requests.get")
    def test_connection_error(self, mock_get):
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )

        result = health_checker.check_endpoint(
            "Unreachable API",
            "https://example.com"
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertIsNone(result["http_code"])
        self.assertIn("Connection refused", result["error"])

if __name__ == "__main__":
    unittest.main()
