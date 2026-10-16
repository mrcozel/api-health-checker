"""CI smoke test: launch real Prometheus and verify an actual scrape."""

import json
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def docker(*args):
    return subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout.strip()


def main():
    network = "api-monitor-metrics-ci"
    dashboard = "api-monitor-dashboard-ci"
    prometheus = "api-monitor-prometheus-ci"
    created = []
    network_created = False
    try:
        docker("network", "create", network)
        network_created = True
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            data.chmod(0o755)
            report = [{"name": "CI sample", "url": "https://example.com", "status": "UP",
                       "timestamp": datetime.now(timezone.utc).isoformat(), "response_ms": 125}]
            (data / "health_report.json").write_text(json.dumps(report), encoding="utf-8")
            (data / "health_report.json").chmod(0o644)
            docker("run", "-d", "--name", dashboard, "--network", network,
                   "--network-alias", "dashboard", "--mount", f"type=bind,src={data.resolve()},dst=/data,readonly",
                   "api-health-checker:test", "python", "/app/dashboard.py", "--host", "0.0.0.0")
            created.append(dashboard)
            config = Path("monitoring/prometheus.yml").resolve()
            image = "prom/prometheus:v3.15.0"
            docker("run", "--rm", "--mount", f"type=bind,src={config},dst=/etc/prometheus/prometheus.yml,readonly",
                   "--entrypoint", "/bin/promtool", image, "check", "config", "/etc/prometheus/prometheus.yml")
            docker("run", "-d", "--name", prometheus, "--network", network,
                   "-p", "127.0.0.1::9090", "--mount",
                   f"type=bind,src={config},dst=/etc/prometheus/prometheus.yml,readonly", image)
            created.append(prometheus)
            port = docker("port", prometheus, "9090/tcp").splitlines()[0].rsplit(":", 1)[1]
            query = 'api_monitor_response_seconds{job="api-health-checker",endpoint="CI sample"}'
            endpoint = f"http://127.0.0.1:{port}/api/v1/query?" + urlencode({"query": query})
            deadline = time.monotonic() + 90
            last_error = "No sample scraped yet"
            while time.monotonic() < deadline:
                try:
                    with urlopen(endpoint, timeout=3) as response:
                        result = json.load(response)["data"]["result"]
                    if result and float(result[0]["value"][1]) == 0.125:
                        print("PASS: real Prometheus scraped dashboard response-time metric (0.125 seconds).")
                        return
                except (OSError, ValueError, KeyError) as error:
                    last_error = str(error)
                time.sleep(2)
            raise RuntimeError(f"Prometheus scrape did not produce the expected sample: {last_error}")
    finally:
        for name in reversed(created):
            subprocess.run(["docker", "logs", name], check=False)
            subprocess.run(["docker", "rm", "-f", name], check=False)
        if network_created:
            subprocess.run(["docker", "network", "rm", network], check=False)


if __name__ == "__main__":
    main()
