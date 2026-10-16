"""CI smoke test: real Prometheus scrape and provisioned Grafana queries."""

import json
import base64
import os
import secrets
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def docker(*args):
    return subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout.strip()


def verify_grafana(network, created, prometheus_query):
    name = "api-monitor-grafana-ci"
    provisioning = Path("monitoring/grafana/provisioning").resolve()
    dashboards = Path("monitoring/grafana/dashboards").resolve()
    password = secrets.token_urlsafe(24)
    # Pass the temporary CI-only password through the process environment,
    # without embedding it in command arguments or logs.
    previous = os.environ.get("GF_SECURITY_ADMIN_PASSWORD")
    os.environ["GF_SECURITY_ADMIN_PASSWORD"] = password
    try:
        docker("run", "-d", "--name", name, "--network", network,
               "-p", "127.0.0.1::3000", "--env", "GF_SECURITY_ADMIN_PASSWORD",
               "--env", "GF_ANALYTICS_REPORTING_ENABLED=false",
               "--env", "GF_ANALYTICS_CHECK_FOR_UPDATES=false",
               "--mount", f"type=bind,src={provisioning},dst=/etc/grafana/provisioning,readonly",
               "--mount", f"type=bind,src={dashboards},dst=/var/lib/grafana/dashboards,readonly",
               "grafana/grafana:13.2.4")
    finally:
        if previous is None:
            os.environ.pop("GF_SECURITY_ADMIN_PASSWORD", None)
        else:
            os.environ["GF_SECURITY_ADMIN_PASSWORD"] = previous
    created.append(name)
    port = docker("port", name, "3000/tcp").splitlines()[0].rsplit(":", 1)[1]
    base = f"http://127.0.0.1:{port}"
    auth = "Basic " + base64.b64encode(f"admin:{password}".encode()).decode()

    def read(path):
        request = Request(base + path, headers={"Authorization": auth})
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    deadline = time.monotonic() + 120
    last_error = "Grafana is not ready"
    while time.monotonic() < deadline:
        try:
            provisioned = read("/api/dashboards/uid/api-monitor")
            health = read("/api/datasources/uid/prometheus/health")
            if health.get("status") != "OK":
                raise ValueError("Provisioned data source is unhealthy")
            panels = provisioned["dashboard"]["panels"]
            if len(panels) != 13:
                raise ValueError("Expected provisioned dashboard panels not found")
            proxy = "/api/datasources/proxy/uid/prometheus/api/v1/query?"
            sample = read(proxy + urlencode({"query": prometheus_query}))
            if float(sample["data"]["result"][0]["value"][1]) != 0.125:
                raise ValueError("Grafana did not return the expected response-time sample")
            for panel in panels:
                for target in panel.get("targets", []):
                    result = read(proxy + urlencode({"query": target["expr"]}))
                    if result.get("status") != "success" or not result["data"]["result"]:
                        raise ValueError(f"Panel query failed or returned no data: {panel['title']}")
            print("PASS: Grafana provisioned dashboard and data source; every panel query returned data.")
            return
        except (OSError, ValueError, KeyError, IndexError) as error:
            last_error = str(error)
        time.sleep(2)
    raise RuntimeError(f"Grafana verification failed: {last_error}")


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
            rules = Path("monitoring/alerts.yml").resolve()
            image = "prom/prometheus:v3.15.0"
            docker("run", "--rm", "--mount", f"type=bind,src={config},dst=/etc/prometheus/prometheus.yml,readonly",
                   "--mount", f"type=bind,src={rules},dst=/etc/prometheus/alerts.yml,readonly",
                   "--entrypoint", "/bin/promtool", image, "check", "config", "/etc/prometheus/prometheus.yml")
            docker("run", "-d", "--name", prometheus, "--network", network,
                   "--network-alias", "prometheus",
                   "-p", "127.0.0.1::9090", "--mount",
                   f"type=bind,src={config},dst=/etc/prometheus/prometheus.yml,readonly",
                   "--mount", f"type=bind,src={rules},dst=/etc/prometheus/alerts.yml,readonly", image)
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
                        verify_grafana(network, created, query)
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
