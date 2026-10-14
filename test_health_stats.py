
import csv
import os
import tempfile
import unittest
from unittest.mock import patch

import health_stats


class TestHealthStats(unittest.TestCase):

    def test_calculate_stats_with_known_results(self):
        rows = [
            {
                "name": "Test API",
                "status": "UP",
                "response_ms": "100"
            },
            {
                "name": "Test API",
                "status": "SLOW",
                "response_ms": "300"
            },
            {
                "name": "Test API",
                "status": "FAIL",
                "response_ms": "200"
            }
        ]

        with tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8",
            suffix=".csv",
            delete=False
        ) as temp_file:
            writer = csv.DictWriter(
                temp_file,
                fieldnames=["name", "status", "response_ms"]
            )
            writer.writeheader()
            writer.writerows(rows)
            temp_path = temp_file.name

        try:
            with patch.object(
                health_stats, "HISTORY_FILE", temp_path
            ):
                with patch("builtins.print") as mock_print:
                    health_stats.calculate_stats()

            output = "\n".join(
                str(call.args[0])
                for call in mock_print.call_args_list
                if call.args
            )

            self.assertIn("Total checks: 3", output)
            self.assertIn("Availability: 66.67%", output)
            self.assertIn("Slow checks: 1", output)
            self.assertIn("Failed checks: 1", output)
            self.assertIn("Average response: 200.00 ms", output)
            self.assertIn("Slowest response: 300.00 ms", output)

        finally:
            os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
