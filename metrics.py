"""Read-only Prometheus gauges for persisted monitoring observations."""

import hashlib
import math
from datetime import datetime


def label_value(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def render_metrics(snapshot):
    lines = []

    def family(name, help_text):
        lines.extend([f"# HELP {name} {help_text}", f"# TYPE {name} gauge"])

    def sample(name, value, labels=None):
        suffix = ""
        if labels:
            suffix = "{" + ",".join(f'{key}="{label_value(value)}"'
                                      for key, value in labels.items()) + "}"
        lines.append(f"{name}{suffix} {value}")

    endpoints = snapshot["endpoints"]

    def labels(endpoint):
        # Distinguish equal names without exposing URLs, query tokens or errors.
        identity = endpoint["name"] + "\0" + endpoint["url"]
        return {"endpoint": endpoint["name"],
                "endpoint_id": hashlib.sha256(identity.encode()).hexdigest()[:16]}

    family("api_monitor_endpoints", "Number of endpoints with recorded observations.")
    sample("api_monitor_endpoints", len(endpoints))
    family("api_monitor_history_available", "Whether a monitoring history CSV exists (1 or 0).")
    sample("api_monitor_history_available", int(snapshot["history_available"]))
    family("api_monitor_stale_after_seconds", "Configured observation freshness limit in seconds.")
    sample("api_monitor_stale_after_seconds", snapshot["stale_after_seconds"])

    family("api_monitor_last_status", "Last recorded API status; one-hot UP, SLOW and FAIL. May be stale.")
    for endpoint in endpoints:
        for status in ("UP", "SLOW", "FAIL"):
            sample("api_monitor_last_status", int(endpoint["status"] == status),
                   {**labels(endpoint), "status": status})

    family("api_monitor_response_seconds", "Latest recorded response time in seconds; omitted when unavailable.")
    for endpoint in endpoints:
        try:
            value = float(endpoint["response_ms"]) / 1000
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value >= 0:
            sample("api_monitor_response_seconds", value, labels(endpoint))

    family("api_monitor_last_check_timestamp_seconds", "Unix timestamp of the last recorded endpoint check.")
    for endpoint in endpoints:
        timestamp = datetime.fromisoformat(endpoint["timestamp"]).astimezone().timestamp()
        sample("api_monitor_last_check_timestamp_seconds", timestamp, labels(endpoint))

    family("api_monitor_stale", "Whether the last recorded check is overdue (1 or 0); inspect clock skew separately.")
    for endpoint in endpoints:
        sample("api_monitor_stale", int(endpoint["freshness"] == "STALE"), labels(endpoint))

    family("api_monitor_clock_skew", "Whether a recorded timestamp is more than five seconds in the future.")
    for endpoint in endpoints:
        sample("api_monitor_clock_skew", int(endpoint["freshness"] == "CLOCK_SKEW"), labels(endpoint))

    family("api_monitor_recorded_checks", "Checks retained in the CSV by endpoint and status; decreases if history is removed.")
    for endpoint in endpoints:
        for status in ("UP", "SLOW", "FAIL"):
            sample("api_monitor_recorded_checks", endpoint["checks_by_status"][status],
                   {**labels(endpoint), "status": status})

    family("api_monitor_consecutive_failures", "Consecutive FAIL rows at the end of this endpoint's retained CSV history; UP or SLOW resets the streak.")
    for endpoint in endpoints:
        sample("api_monitor_consecutive_failures", endpoint["consecutive_failures"], labels(endpoint))

    return "\n".join(lines) + "\n"
