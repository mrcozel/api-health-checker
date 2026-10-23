import csv
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import health_checker as checker


EXPECTED = {"ok": True, "status": "healthy", "service": "zavv-link-api"}
ENDPOINT = {"name": "ZAVV Link API", "url": "https://api.zavv.link/healthz",
            "expected_json": EXPECTED}


class TestJsonHealth(unittest.TestCase):
    def check(self, payload, elapsed=0.1, code=200):
        response = Mock(status_code=code)
        response.json.return_value = payload
        with patch.object(checker.requests, "get", return_value=response), patch.object(
            checker.time, "perf_counter", side_effect=[0, elapsed]
        ):
            return checker.check_endpoint(ENDPOINT["name"], ENDPOINT["url"],
                                          expected_json=EXPECTED)

    def test_healthy_and_slow(self):
        self.assertEqual(self.check({**EXPECTED, "purpose": "healthcheck"})["status"], "UP")
        self.assertEqual(self.check(EXPECTED, elapsed=2)["status"], "SLOW")

    def test_invalid_health_overrides_slow(self):
        for payload in (None, [], "healthy", {}, {**EXPECTED, "ok": False},
                        {**EXPECTED, "ok": 1}, {**EXPECTED, "ok": "true"},
                        {**EXPECTED, "status": "unhealthy"},
                        {**EXPECTED, "service": "other"}):
            with self.subTest(payload=payload):
                result = self.check(payload, elapsed=2)
                self.assertEqual(result["status"], "FAIL")
                self.assertEqual(result["http_code"], 200)
                self.assertEqual(result["response_ms"], 2000)
                self.assertTrue(result["error"])

    def test_malformed_json(self):
        response = Mock(status_code=200)
        response.json.side_effect = json.JSONDecodeError("invalid", "x", 0)
        with patch.object(checker.requests, "get", return_value=response):
            result = checker.check_endpoint("ZAVV", ENDPOINT["url"], expected_json=EXPECTED)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["http_code"], 200)
        self.assertIn("not valid JSON", result["error"])

    def test_http_failure_does_not_parse_json(self):
        response = Mock(status_code=503)
        with patch.object(checker.requests, "get", return_value=response):
            result = checker.check_endpoint("ZAVV", ENDPOINT["url"], expected_json=EXPECTED)
        self.assertEqual(result["status"], "FAIL")
        response.json.assert_not_called()

    def test_invalid_configuration(self):
        for expected in ({}, [], "healthy", {"ok": []}, {"": True}):
            with self.subTest(expected=expected), patch("builtins.open", unittest.mock.mock_open(
                read_data=json.dumps([{**ENDPOINT, "expected_json": expected}])
            )):
                with self.assertRaisesRegex(ValueError, "expected_json"):
                    checker.load_endpoints()

    def test_shipped_configs_preserve_existing_monitors(self):
        for path in ("endpoints.json", "k8s/endpoints.json"):
            endpoints = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            self.assertEqual([e["name"] for e in endpoints],
                             ["JSONPlaceholder API", "HTTPBin API", "ZAVV Link API"])
            self.assertEqual(endpoints[-1], ENDPOINT)

    def test_cycle_reports_and_alert_recovery(self):
        original_dir = os.getcwd()
        with tempfile.TemporaryDirectory() as directory, patch.object(
            checker, "endpoint_states", {}
        ), patch.object(checker, "load_endpoints", return_value=[ENDPOINT]), patch.object(
            checker, "send_alert", return_value=True
        ) as alert, patch.object(checker.requests, "get") as get:
            try:
                os.chdir(directory)
                response = Mock(status_code=200)
                get.return_value = response
                response.json.return_value = {**EXPECTED, "ok": False}
                for _ in range(3):
                    checker.main()
                self.assertEqual(alert.call_count, 1)
                self.assertIn("API FAILURE", alert.call_args.args[0])
                self.assertIn("ok", alert.call_args.args[1])
                response.json.return_value = EXPECTED
                with patch.object(checker.time, "perf_counter", side_effect=[0, 0.1]):
                    checker.main()
                self.assertEqual(alert.call_count, 2)
                self.assertIn("API RECOVERED", alert.call_args.args[0])
                report = json.loads(Path("health_report.json").read_text())
                self.assertEqual(report[0]["status"], "UP")
                with open("health_history.csv", newline="") as file:
                    rows = list(csv.DictReader(file))
                self.assertEqual([r["status"] for r in rows], ["FAIL"] * 3 + ["UP"])
                self.assertEqual(set(rows[0]), set(report[0]))
            finally:
                os.chdir(original_dir)
