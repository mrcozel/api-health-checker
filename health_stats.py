import csv
import os
from collections import defaultdict


HISTORY_FILE = "health_history.csv"


def calculate_stats():
    if not os.path.exists(HISTORY_FILE):
        print("No history file found. Run the health checker first.")
        return

    stats = defaultdict(lambda: {
        "total": 0,
        "available": 0,
        "slow": 0,
        "failed": 0,
        "response_times": []
    })

    with open(HISTORY_FILE, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            name = row["name"]
            status = row["status"]
            endpoint = stats[name]

            endpoint["total"] += 1

            # A slow but successful response still means
            # the API is available, although degraded.
            if status in ("UP", "SLOW"):
                endpoint["available"] += 1

            if status == "SLOW":
                endpoint["slow"] += 1
            elif status == "FAIL":
                endpoint["failed"] += 1

            try:
                response_ms = float(row["response_ms"])
                endpoint["response_times"].append(response_ms)
            except (ValueError, TypeError):
                pass

    print("\nAPI HEALTH STATISTICS")
    print("=" * 40)

    if not stats:
        print("No historical checks found.")
        return

    for name, data in stats.items():
        total = data["total"]
        uptime = data["available"] / total * 100

        print(f"\nAPI: {name}")
        print("-" * 40)
        print(f"Total checks: {total}")
        print(f"Availability: {uptime:.2f}%")
        print(f"Slow checks: {data['slow']}")
        print(f"Failed checks: {data['failed']}")

        times = data["response_times"]

        if times:
            average = sum(times) / len(times)
            slowest = max(times)

            print(f"Average response: {average:.2f} ms")
            print(f"Slowest response: {slowest:.2f} ms")
        else:
            print("Response times: No data available")


if __name__ == "__main__":
    calculate_stats()