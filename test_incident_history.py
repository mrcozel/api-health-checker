import csv
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

from incident_history import find_incidents, load_checks, main


class TestIncidentHistory(unittest.TestCase):
    def checks(self, statuses, name="API", url="https://example.com"):
        return [(datetime(2026, 10, 15, 12, minute), name, url, status)
                for minute, status in enumerate(statuses)]

    def test_failure_recovers_and_later_failure_is_separate(self):
        incidents = find_incidents(self.checks(["UP", "FAIL", "FAIL", "UP", "FAIL", "UP"]))
        self.assertEqual(len(incidents), 2)
        self.assertEqual(incidents[0].duration_seconds, 120)
        self.assertEqual(incidents[0].failed_checks, 2)
        self.assertEqual(incidents[1].duration_seconds, 60)
        self.assertIsNotNone(incidents[1].recovered_at)

    def test_slow_failure_and_slow_remain_one_incident_until_up(self):
        incident, = find_incidents(self.checks(["SLOW", "FAIL", "SLOW", "UP"]))
        self.assertEqual(incident.kind, "FAIL + SLOW")
        self.assertEqual(incident.slow_checks, 2)
        self.assertEqual(incident.failed_checks, 1)
        self.assertEqual(incident.duration_seconds, 180)

    def test_ongoing_is_bounded_by_its_own_last_observation(self):
        checks = self.checks(["FAIL", "SLOW"])
        checks += [(datetime(2026, 10, 15, 13), "Other", "https://other.com", "UP")]
        incident, = find_incidents(checks)
        self.assertIsNone(incident.recovered_at)
        self.assertEqual(incident.duration_seconds, 60)

    def test_same_name_different_urls_are_independent(self):
        checks = self.checks(["FAIL", "UP"])
        checks += self.checks(["SLOW", "SLOW"], url="https://other.com")
        first, second = find_incidents(checks)
        self.assertIsNotNone(first.recovered_at)
        self.assertIsNone(second.recovered_at)

    def test_unsorted_history_and_equal_timestamp_order(self):
        checks = self.checks(["FAIL", "SLOW", "UP"])
        self.assertEqual(find_incidents(list(reversed(checks)))[0].duration_seconds, 120)
        timestamp = checks[0][0]
        incident, = find_incidents([(timestamp, "API", "url", "FAIL"),
                                    (timestamp, "API", "url", "UP")])
        self.assertEqual(incident.duration_seconds, 0)
        self.assertIsNotNone(incident.recovered_at)

    def write_history(self, directory, rows, fields=None):
        path = Path(directory) / "history.csv"
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(fields or ["timestamp", "name", "url", "status"])
            writer.writerows(rows)
        return path

    def test_cli_reads_csv_and_reports_slow_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_history(directory, [
                ["2026-10-15T12:02:00", "API", "url", "UP"],
                ["2026-10-15T12:00:00", "API", "url", "SLOW"],
            ])
            output = io.StringIO()
            with redirect_stdout(output):
                result = main(["--history", str(path)])
            self.assertEqual(result, 0)
            self.assertIn("Type: SLOW", output.getvalue())
            self.assertIn("Recovered: 2026-10-15 12:02:00", output.getvalue())
            self.assertIn("Observed duration: 120 seconds", output.getvalue())

    def test_invalid_history_is_rejected_with_row_number(self):
        for timestamp, status in [("bad-date", "FAIL"), ("2026-10-15T12:00:00", "BAD"),
                                  ("2026-10-15T12:00:00", "")]:
            with self.subTest(timestamp=timestamp, status=status), tempfile.TemporaryDirectory() as directory:
                path = self.write_history(directory, [[timestamp, "API", "url", status]])
                with self.assertRaisesRegex(ValueError, "Row 2"):
                    load_checks(path)

    def test_missing_columns_and_mixed_timezones_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_history(directory, [], fields=["name", "status"])
            with self.assertRaisesRegex(ValueError, "columns"):
                load_checks(path)
            path = self.write_history(directory, [
                ["2026-10-15T12:00:00", "API", "url", "FAIL"],
                ["2026-10-15T12:01:00+00:00", "API", "url", "UP"],
            ])
            with self.assertRaisesRegex(ValueError, "timezone"):
                load_checks(path)

    def test_offset_timestamps_are_compared_as_instants(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_history(directory, [
                ["2026-10-15T13:00:00+01:00", "API", "url", "FAIL"],
                ["2026-10-15T12:02:00+00:00", "API", "url", "UP"],
            ])
            self.assertEqual(find_incidents(load_checks(path))[0].duration_seconds, 120)

    def test_empty_and_healthy_history(self):
        self.assertEqual(find_incidents(self.checks(["UP", "UP"])), [])
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_history(directory, [])
            self.assertEqual(load_checks(path), [])

    def test_missing_file_and_bad_csv_cli_fail_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.csv"
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--history", str(path)]), 1)
            self.assertIn("Run the health checker first", output.getvalue())
            path = self.write_history(directory, [], fields=["wrong"])
            with redirect_stdout(output):
                self.assertEqual(main(["--history", str(path)]), 1)
            self.assertIn("Cannot read incident history", output.getvalue())


if __name__ == "__main__":
    unittest.main()
