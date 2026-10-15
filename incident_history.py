"""Reconstruct observed incidents from the checker's existing CSV history."""

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


HISTORY_FILE = "health_history.csv"


@dataclass
class Incident:
    name: str
    url: str
    started_at: datetime
    last_observed_at: datetime
    recovered_at: datetime | None = None
    slow_checks: int = 0
    failed_checks: int = 0

    @property
    def duration_seconds(self):
        end = self.recovered_at or self.last_observed_at
        return (end - self.started_at).total_seconds()

    @property
    def kind(self):
        if self.failed_checks and self.slow_checks:
            return "FAIL + SLOW"
        return "FAIL" if self.failed_checks else "SLOW"


def load_checks(history_file=HISTORY_FILE):
    """Validate before reporting; do not silently turn bad rows into recovery."""
    checks = []
    timezone_modes = set()
    with open(history_file, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"timestamp", "name", "url", "status"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("History must contain timestamp, name, url, and status columns.")
        for line, row in enumerate(reader, start=2):
            if any(not row.get(field) or not row[field].strip() for field in required):
                raise ValueError(f"Row {line}: missing required value.")
            status = row["status"].strip()
            if status not in {"UP", "SLOW", "FAIL"}:
                raise ValueError(f"Row {line}: unknown status {status!r}.")
            try:
                timestamp = datetime.fromisoformat(row["timestamp"].strip())
            except ValueError as error:
                raise ValueError(f"Row {line}: invalid timestamp.") from error
            timezone_modes.add(timestamp.utcoffset() is not None)
            checks.append((timestamp, row["name"].strip(), row["url"].strip(), status))
    if len(timezone_modes) > 1:
        raise ValueError("History mixes timestamps with and without timezone offsets.")
    # Stable sorting preserves CSV order for checks with identical timestamps.
    return sorted(checks, key=lambda check: check[0])


def find_incidents(checks):
    """Keep a continuous degraded period open until that endpoint records UP."""
    incidents = []
    active = {}
    for timestamp, name, url, status in sorted(checks, key=lambda check: check[0]):
        key = (name, url)
        if status == "UP":
            incident = active.pop(key, None)
            if incident is not None:
                incident.recovered_at = timestamp
                incident.last_observed_at = timestamp
            continue
        if status not in {"SLOW", "FAIL"}:
            raise ValueError(f"Unknown status {status!r}.")
        if key not in active:
            active[key] = Incident(name, url, timestamp, timestamp)
            incidents.append(active[key])
        incident = active[key]
        incident.last_observed_at = timestamp
        if status == "SLOW":
            incident.slow_checks += 1
        else:
            incident.failed_checks += 1
    return incidents


def print_incidents(incidents):
    print("\nAPI INCIDENT HISTORY")
    print("=" * 60)
    if not incidents:
        print("No incidents found in the recorded checks.")
        return
    for incident in incidents:
        print(f"\nAPI: {incident.name} ({incident.url})")
        print(f"Type: {incident.kind}")
        print(f"Started: {incident.started_at.isoformat(sep=' ')}")
        if incident.recovered_at is not None:
            print(f"Recovered: {incident.recovered_at.isoformat(sep=' ')}")
        else:
            print("Recovered: Ongoing (no recovery recorded)")
            print(f"Last observed: {incident.last_observed_at.isoformat(sep=' ')}")
        qualifier = " (through last observation)" if incident.recovered_at is None else ""
        print(f"Observed duration: {incident.duration_seconds:g} seconds{qualifier}")
        print(f"Failed checks: {incident.failed_checks} | Slow checks: {incident.slow_checks}")
    print(f"\nTotal incidents: {len(incidents)}")
    print("Durations are based on recorded checks; actual onset and recovery may occur between checks.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=Path(HISTORY_FILE),
                        help="CSV history to read (default: health_history.csv)")
    args = parser.parse_args(argv)
    try:
        incidents = find_incidents(load_checks(args.history))
    except FileNotFoundError:
        print(f"No history file found: {args.history}. Run the health checker first.")
        return 1
    except (OSError, ValueError, csv.Error) as error:
        print(f"Cannot read incident history: {error}")
        return 1
    print_incidents(incidents)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
