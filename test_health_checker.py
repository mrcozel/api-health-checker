import os
import tempfile
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

    
    @patch("health_checker.send_alert")
    def test_alert_after_three_consecutive_failures(self, mock_alert):
        health_checker.endpoint_states.clear()

        result = {
            "name": "Test API",
            "url": "https://example.com/api",
            "status": "FAIL",
            "http_code": 500,
            "response_ms": 10,
            "error": "Server error",
            "timestamp": "2026-10-14 12:00:00"
        }

        for _ in range(3):
            health_checker.update_endpoint_state(result)

        mock_alert.assert_called_once()

    
    @patch("health_checker.send_alert")
    def test_recovery_alert_after_failure(self, mock_alert):
        health_checker.endpoint_states.clear()

        failed_result = {
            "name": "Test API",
            "url": "https://example.com/api",
            "status": "FAIL",
            "http_code": 500,
            "response_ms": 10,
            "error": "Server error",
            "timestamp": "2026-10-14 12:00:00"
        }

        recovered_result = {
            **failed_result,
            "status": "UP",
            "http_code": 200,
            "error": None
        }

        for _ in range(3):
            health_checker.update_endpoint_state(failed_result)

        health_checker.update_endpoint_state(recovered_result)

        self.assertEqual(mock_alert.call_count, 2)
        self.assertIn("API FAILURE", mock_alert.call_args_list[0].args[0])
        self.assertIn("API RECOVERED", mock_alert.call_args_list[1].args[0])

    
    @patch("health_checker.send_alert")
    def test_slow_response_does_not_trigger_recovery(
        self, mock_alert
    ):
        health_checker.endpoint_states.clear()

        failed_result = {
            "name": "Test API",
            "url": "https://example.com/api",
            "status": "FAIL",
            "http_code": 500,
            "response_ms": 10,
            "error": "Server error",
            "timestamp": "2026-10-14 12:00:00"
        }

        slow_result = {
            **failed_result,
            "status": "SLOW",
            "http_code": 200,
            "error": None
        }

        for _ in range(3):
            health_checker.update_endpoint_state(failed_result)

        mock_alert.reset_mock()

        health_checker.update_endpoint_state(slow_result)

        mock_alert.assert_not_called()

        self.assertEqual(
            health_checker.endpoint_states["Test API"][
                "consecutive_failures"
            ],
            3
        )
        self.assertTrue(
            health_checker.endpoint_states["Test API"]["alert_sent"]
        )


class TestEndpointStatePersistence(unittest.TestCase):

    def test_failure_state_persists_after_reload(self):
        original_states = health_checker.endpoint_states

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                state_file = os.path.join(
                    temp_dir, "endpoint_state.json"
                )

                with patch.object(
                    health_checker, "STATE_FILE", state_file
                ):
                    health_checker.endpoint_states = {
                        "Persistence Test API": {
                            "consecutive_failures": 2,
                            "alert_sent": False
                        }
                    }

                    health_checker.save_endpoint_states()

                    # Simulate restarting the checker.
                    health_checker.endpoint_states = {}

                    loaded_states = health_checker.load_endpoint_states()

                    self.assertEqual(
                        loaded_states["Persistence Test API"][
                            "consecutive_failures"
                        ],
                        2
                    )
                    self.assertFalse(
                        loaded_states["Persistence Test API"]["alert_sent"]
                    )
        finally:
            health_checker.endpoint_states = original_states


class TestAlertRetries(unittest.TestCase):

    @patch("health_checker.save_endpoint_states")
    @patch("health_checker.send_alert")
    def test_failure_alert_retries_if_email_fails(
        self, mock_alert, mock_save
    ):
        original_states = health_checker.endpoint_states

        try:
            health_checker.endpoint_states = {}

            # First email fails; second succeeds.
            mock_alert.side_effect = [False, True]

            failed_result = {
                "name": "Retry Test API",
                "url": "https://example.com/api",
                "status": "FAIL",
                "http_code": 500,
                "response_ms": 10,
                "error": "Server error",
                "timestamp": "2026-10-14 12:00:00"
            }

            # Reach the three-failure threshold.
            for _ in range(3):
                health_checker.update_endpoint_state(failed_result)

            self.assertEqual(mock_alert.call_count, 1)
            self.assertFalse(
                health_checker.endpoint_states["Retry Test API"][
                    "alert_sent"
                ]
            )

            # Another failure should retry the email.
            health_checker.update_endpoint_state(failed_result)

            self.assertEqual(mock_alert.call_count, 2)
            self.assertTrue(
                health_checker.endpoint_states["Retry Test API"][
                    "alert_sent"
                ]
            )
        finally:
            health_checker.endpoint_states = original_states

    @patch("health_checker.save_endpoint_states")
    @patch("health_checker.send_alert")
    def test_recovery_alert_retries_if_email_fails(
        self, mock_alert, mock_save
    ):
        original_states = health_checker.endpoint_states

        try:
            health_checker.endpoint_states = {
                "Recovery Test API": {
                    "consecutive_failures": 3,
                    "alert_sent": True
                }
            }

            # First recovery email fails; second succeeds.
            mock_alert.side_effect = [False, True]

            recovered_result = {
                "name": "Recovery Test API",
                "url": "https://example.com/api",
                "status": "UP",
                "http_code": 200,
                "response_ms": 10,
                "error": None,
                "timestamp": "2026-10-14 12:00:00"
            }

            health_checker.update_endpoint_state(recovered_result)

            # Incident remains recorded because the email failed.
            self.assertTrue(
                health_checker.endpoint_states["Recovery Test API"][
                    "alert_sent"
                ]
            )
            self.assertEqual(
                health_checker.endpoint_states["Recovery Test API"][
                    "consecutive_failures"
                ],
                3
            )

            # Try recovery notification again.
            health_checker.update_endpoint_state(recovered_result)

            self.assertEqual(mock_alert.call_count, 2)
            self.assertFalse(
                health_checker.endpoint_states["Recovery Test API"][
                    "alert_sent"
                ]
            )
            self.assertEqual(
                health_checker.endpoint_states["Recovery Test API"][
                    "consecutive_failures"
                ],
                0
            )
        finally:
            health_checker.endpoint_states = original_states


if __name__ == "__main__":
    unittest.main()
