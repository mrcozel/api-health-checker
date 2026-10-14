import os
import unittest
from unittest.mock import Mock, patch

import health_checker


class TestAuthenticationHeaders(unittest.TestCase):

    def test_public_endpoint_has_no_auth_headers(self):
        self.assertEqual(health_checker.build_auth_headers(), {})

    @patch.dict(os.environ, {"TEST_API_TOKEN": "test-token-value"})
    def test_bearer_token_header(self):
        headers = health_checker.build_auth_headers({
            "type": "bearer",
            "token_env": "TEST_API_TOKEN"
        })

        self.assertEqual(
            headers,
            {"Authorization": "Bearer test-token-value"}
        )

    @patch.dict(os.environ, {"TEST_API_KEY": "test-api-key-value"})
    def test_api_key_header_uses_configured_header_name(self):
        headers = health_checker.build_auth_headers({
            "type": "api_key",
            "key_env": "TEST_API_KEY",
            "header": "X-Custom-Key"
        })

        self.assertEqual(headers, {"X-Custom-Key": "test-api-key-value"})

    @patch.dict(os.environ, {"TEST_API_KEY": "test-api-key-value"})
    def test_api_key_header_defaults_to_x_api_key(self):
        headers = health_checker.build_auth_headers({
            "type": "api_key",
            "key_env": "TEST_API_KEY"
        })

        self.assertEqual(headers, {"X-API-Key": "test-api-key-value"})

    def test_missing_bearer_token_environment_variable_raises_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "Missing environment variable"):
                health_checker.build_auth_headers({
                    "type": "bearer",
                    "token_env": "MISSING_TEST_API_TOKEN"
                })

    def test_unsupported_auth_type_raises_error(self):
        with self.assertRaisesRegex(ValueError, "Unsupported authentication type"):
            health_checker.build_auth_headers({"type": "basic"})

    @patch("health_checker.requests.get")
    @patch.dict(os.environ, {"TEST_API_TOKEN": "test-token-value"})
    def test_check_endpoint_sends_bearer_header(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = health_checker.check_endpoint(
            "Authenticated API",
            "https://example.com",
            {"type": "bearer", "token_env": "TEST_API_TOKEN"}
        )

        self.assertEqual(result["status"], "UP")
        mock_get.assert_called_once()
        self.assertEqual(
            mock_get.call_args.kwargs["headers"],
            {"Authorization": "Bearer test-token-value"}
        )

    @patch("health_checker.requests.get")
    @patch.dict(os.environ, {"TEST_API_KEY": "test-api-key-value"})
    def test_check_endpoint_sends_api_key_header(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = health_checker.check_endpoint(
            "API key authenticated API",
            "https://example.com",
            {"type": "api_key", "key_env": "TEST_API_KEY"}
        )

        self.assertEqual(result["status"], "UP")
        mock_get.assert_called_once()
        self.assertEqual(
            mock_get.call_args.kwargs["headers"],
            {"X-API-Key": "test-api-key-value"}
        )

    @patch("health_checker.requests.get")
    def test_check_endpoint_marks_401_as_fail(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        # Use a mocked response to verify that HTTP 401 is treated as failure.
        with patch.dict(os.environ, {"TEST_API_TOKEN": "wrong-token"}):
            result = health_checker.check_endpoint(
                "Invalid credentials",
                "https://example.com",
                {"type": "bearer", "token_env": "TEST_API_TOKEN"}
            )

        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["http_code"], 401)


if __name__ == "__main__":
    unittest.main()
