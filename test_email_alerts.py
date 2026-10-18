import os
import unittest
from unittest.mock import patch

from email_alerts import send_alert


class TestEmailSettings(unittest.TestCase):
    def setUp(self):
        self.environment = {
            "BREVO_API_KEY": "test-key",
            "ALERT_SENDER_EMAIL": "sender@example.com",
            "ALERT_RECIPIENT_EMAIL": "recipient@example.com",
        }

    @patch("email_alerts.load_dotenv")
    @patch("email_alerts.requests.post")
    def test_configured_addresses_are_used(self, post, dotenv):
        post.return_value.status_code = 201
        with patch.dict(os.environ, self.environment, clear=True):
            self.assertTrue(send_alert("Subject", "Body"))
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["sender"]["email"], "sender@example.com")
        self.assertEqual(payload["to"], [{"email": "recipient@example.com"}])

    @patch("email_alerts.load_dotenv")
    @patch("email_alerts.requests.post")
    def test_missing_settings_do_not_send(self, post, dotenv):
        for setting in self.environment:
            for value in ("", "   "):
                with self.subTest(setting=setting, value=value):
                    environment = dict(self.environment)
                    environment[setting] = value
                    with patch.dict(os.environ, environment, clear=True):
                        with patch("builtins.print") as output:
                            self.assertFalse(send_alert("Subject", "Body"))
                    output.assert_any_call(f"ERROR: {setting} is not configured.")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
