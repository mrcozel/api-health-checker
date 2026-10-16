import csv
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from datetime import datetime, timedelta, timezone

from dashboard import build_snapshot, make_handler, positive_seconds
import argparse


class TestDashboard(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def history(self):
        with (self.directory / "health_history.csv").open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["timestamp", "name", "url", "status"])
            writer.writerows([
                ["2026-10-15T12:00:00", "API", "https://example.com", "FAIL"],
                ["2026-10-15T12:02:00", "API", "https://example.com", "UP"],
            ])

    def test_empty_directory_has_no_fabricated_checks(self):
        data = build_snapshot(self.directory)
        self.assertEqual(data["endpoints"], [])
        self.assertEqual(data["incidents"], [])
        self.assertFalse(data["history_available"])

    def test_freshness_boundary_and_recovery_preserve_recorded_status(self):
        self.history()
        checked = datetime(2026, 10, 15, 12, 2)
        fresh = build_snapshot(self.directory, now=checked + timedelta(seconds=179))
        self.assertEqual(fresh["endpoints"][0]["freshness"], "FRESH")
        stale = build_snapshot(self.directory, now=checked + timedelta(seconds=180))
        self.assertEqual(stale["endpoints"][0]["freshness"], "STALE")
        self.assertEqual(stale["endpoints"][0]["status"], "UP")
        self.assertEqual(stale["endpoints"][0]["age_seconds"], 180)
        report = [{"name": "API", "url": "https://example.com", "status": "UP",
                   "timestamp": "2026-10-15T12:05:00"}]
        (self.directory / "health_report.json").write_text(json.dumps(report))
        recovered = build_snapshot(self.directory, now=checked + timedelta(seconds=181))
        self.assertEqual(recovered["endpoints"][0]["freshness"], "FRESH")

    def test_custom_limit_and_future_clock_warning(self):
        self.history()
        checked = datetime(2026, 10, 15, 12, 2)
        self.assertEqual(build_snapshot(self.directory, 30, checked + timedelta(seconds=30))
                         ["endpoints"][0]["freshness"], "STALE")
        future = build_snapshot(self.directory, now=checked - timedelta(seconds=60))
        self.assertEqual(future["endpoints"][0]["freshness"], "CLOCK_SKEW")

    def test_offset_timestamps_use_elapsed_time(self):
        report = [{"name": "API", "url": "url", "status": "FAIL",
                   "timestamp": "2026-10-15T13:00:00+01:00"}]
        (self.directory / "health_report.json").write_text(json.dumps(report))
        snapshot = build_snapshot(self.directory, now=datetime(2026, 10, 15, 12, 3, tzinfo=timezone.utc))
        endpoint = snapshot["endpoints"][0]
        self.assertEqual(endpoint["age_seconds"], 180)
        self.assertEqual(endpoint["freshness"], "STALE")
        self.assertEqual(endpoint["status"], "FAIL")

    def test_freshness_is_per_endpoint_and_invalid_limits_rejected(self):
        self.history()
        report = [{"name": "Other", "url": "url", "status": "UP",
                   "timestamp": "2026-10-15T12:05:00"}]
        (self.directory / "health_report.json").write_text(json.dumps(report))
        snapshot = build_snapshot(self.directory, now=datetime(2026, 10, 15, 12, 5))
        self.assertEqual([e["freshness"] for e in snapshot["endpoints"]], ["STALE", "FRESH"])
        for value in ["0", "-1", "bad", "1.5"]:
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                positive_seconds(value)

    def test_history_provides_health_and_recovered_incident(self):
        self.history()
        data = build_snapshot(self.directory)
        self.assertEqual(data["endpoints"][0]["status"], "UP")
        self.assertEqual(data["incidents"][0]["duration_seconds"], 120)
        self.assertEqual(data["check_count"], 2)
        self.assertEqual(data["available_checks"], 1)

    def test_report_response_times_and_whitelisted_fields(self):
        row = {"name": "API", "url": "https://example.com", "status": "UP",
               "timestamp": "2026-10-15T12:02:00", "response_ms": 50,
               "http_code": 200, "error": "private detail", "headers": {"secret": "token"}}
        self.history()
        (self.directory / "health_report.json").write_text(json.dumps([row]))
        data = build_snapshot(self.directory)
        self.assertEqual(data["endpoints"][0]["response_ms"], 50)
        self.assertNotIn("secret", json.dumps(data))
        self.assertNotIn("private detail", json.dumps(data))
        row["timestamp"] = "2026-10-15T11:00:00"
        row["status"] = "FAIL"
        (self.directory / "health_report.json").write_text(json.dumps([row]))
        self.assertEqual(build_snapshot(self.directory)["endpoints"][0]["status"], "UP")

    def test_invalid_report_rejected(self):
        (self.directory / "health_report.json").write_text('{"not": "a list"}')
        with self.assertRaises(ValueError):
            build_snapshot(self.directory)

    def test_server_routes_and_data_errors(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.directory))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(base) as response:
                self.assertIn(b"API OBSERVABILITY", response.read())
            with urlopen(base + "/api/dashboard") as response:
                self.assertEqual(json.load(response)["endpoints"], [])
                self.assertEqual(response.headers["Cache-Control"], "no-store")
            for path in ["/.env", "/health_history.csv", "/../health_checker.py"]:
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + path)
                self.assertEqual(error.exception.code, 404)
            (self.directory / "health_report.json").write_text("invalid")
            with self.assertRaises(HTTPError) as error:
                urlopen(base + "/api/dashboard")
            self.assertEqual(error.exception.code, 503)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
