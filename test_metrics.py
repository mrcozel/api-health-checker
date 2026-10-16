import csv
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from dashboard import build_snapshot
from metrics import render_metrics


class TestMetrics(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def snapshot(self, response_ms=250):
        url = "https://example.com/health?token=private-token"
        rows = [{"name": 'API "east"\\node\nline', "url": url, "status": "UP",
                 "timestamp": "2026-10-16T12:00:00+00:00", "response_ms": response_ms,
                 "error": "private-error"}]
        (self.directory / "health_report.json").write_text(json.dumps(rows), encoding="utf-8")
        with (self.directory / "health_history.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["timestamp", "name", "url", "status"])
            for minute, status in enumerate(["FAIL", "SLOW", "UP"]):
                writer.writerow([f"2026-10-16T11:5{minute}:00+00:00", rows[0]["name"], url, status])
        return build_snapshot(self.directory, now=datetime(2026, 10, 16, 12, 3, tzinfo=timezone.utc))

    def test_counts_and_last_status_do_not_increase_on_scrape(self):
        snapshot = self.snapshot()
        output = render_metrics(snapshot)
        self.assertEqual(render_metrics(snapshot), output)
        counts = [line for line in output.splitlines() if line.startswith("api_monitor_recorded_checks{")]
        self.assertEqual(len(counts), 3)
        self.assertTrue(all(line.endswith(" 1") for line in counts))
        self.assertIn("# TYPE api_monitor_recorded_checks gauge", output)
        statuses = [line for line in output.splitlines() if line.startswith("api_monitor_last_status{")]
        self.assertEqual(sum(line.endswith(" 1") for line in statuses), 1)
        self.assertTrue(any('status="UP"} 1' in line for line in statuses))

    def test_seconds_timestamp_freshness_and_private_fields(self):
        snapshot = self.snapshot()
        output = render_metrics(snapshot)
        self.assertIn("} 0.25\n", output)
        epoch = datetime(2026, 10, 16, 12, tzinfo=timezone.utc).timestamp()
        self.assertIn(f"}} {epoch}\n", output)
        self.assertTrue(any(line.startswith("api_monitor_stale{") and line.endswith(" 1")
                            for line in output.splitlines()))
        self.assertNotIn("private-token", output)
        self.assertNotIn("private-error", output)
        self.assertNotIn("https://", output)

    def test_labels_escaped_and_final_newline(self):
        output = render_metrics(self.snapshot())
        self.assertIn('endpoint="API \\"east\\"\\\\node\\nline"', output)
        self.assertTrue(output.endswith("\n"))

    def test_missing_invalid_and_nonfinite_response_omitted(self):
        for value in [None, "bad", "NaN", float("inf"), -10]:
            with self.subTest(value=value):
                output = render_metrics(self.snapshot(value))
                self.assertFalse(any(line.startswith("api_monitor_response_seconds{")
                                     for line in output.splitlines()))

    def test_endpoint_identity_distinguishes_duplicate_names(self):
        snapshot = self.snapshot()
        other = dict(snapshot["endpoints"][0], url="https://other.com")
        snapshot["endpoints"].append(other)
        samples = [line for line in render_metrics(snapshot).splitlines()
                   if line.startswith("api_monitor_last_check_timestamp_seconds{")]
        self.assertEqual(len(set(samples)), 2)

    def test_empty_directory_reports_zero_endpoints(self):
        output = render_metrics(build_snapshot(self.directory))
        self.assertIn("api_monitor_endpoints 0\n", output)
        self.assertIn("api_monitor_history_available 0\n", output)
        self.assertNotIn('endpoint="', output)

    def test_failure_streak_counts_retained_checks_and_resets_on_slow(self):
        path = self.directory / "health_history.csv"
        rows = ["FAIL", "FAIL", "FAIL"]
        def write(statuses):
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["timestamp", "name", "url", "status"])
                for minute, status in enumerate(statuses):
                    writer.writerow([f"2026-10-16T12:0{minute}:00+00:00", "API", "url", status])
        write(rows)
        snapshot = build_snapshot(self.directory)
        self.assertEqual(snapshot["endpoints"][0]["consecutive_failures"], 3)
        self.assertTrue(any(line.startswith("api_monitor_consecutive_failures{") and line.endswith(" 3")
                            for line in render_metrics(snapshot).splitlines()))
        write(rows + ["SLOW", "FAIL"])
        self.assertEqual(build_snapshot(self.directory)["endpoints"][0]["consecutive_failures"], 1)
        write(rows + ["UP"])
        self.assertEqual(build_snapshot(self.directory)["endpoints"][0]["consecutive_failures"], 0)


if __name__ == "__main__":
    unittest.main()
