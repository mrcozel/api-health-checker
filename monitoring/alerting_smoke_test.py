"""Validate alert rules and captured firing/resolved email delivery in CI."""

import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def docker(*args):
    return subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout.strip()


def wait_for(operation, timeout=90):
    deadline = time.monotonic() + timeout
    last_error = "Expected result not seen"
    while time.monotonic() < deadline:
        try:
            result = operation()
            if result:
                return result
        except (OSError, ValueError, KeyError) as error:
            last_error = str(error)
        time.sleep(2)
    raise RuntimeError(last_error)


def read(url):
    with urlopen(url, timeout=5) as response:
        return json.load(response)


def main():
    directory = Path("monitoring").resolve()
    prometheus_image = "prom/prometheus:v3.15.0"
    docker("run", "--rm", "--mount", f"type=bind,src={directory},dst=/tests,readonly",
           "--workdir", "/tests", "--entrypoint", "/bin/promtool", prometheus_image,
           "test", "rules", "alerts.test.yml")
    print("PASS: alert rule firing, pending, recovery, absence, and freshness suppression tests.")
    network = "api-monitor-alerting-ci"
    mailpit = "api-monitor-mailpit-ci"
    manager = "api-monitor-alertmanager-ci"
    created = []
    network_created = False
    try:
        docker("network", "create", network)
        network_created = True
        docker("run", "-d", "--name", mailpit, "--network", network,
               "--network-alias", "mailpit", "-p", "127.0.0.1::8025", "axllent/mailpit:v1.31.6")
        created.append(mailpit)
        config = directory / "alertmanager.yml"
        image = "prom/alertmanager:v0.34.1"
        mount = f"type=bind,src={config},dst=/etc/alertmanager/alertmanager.yml,readonly"
        docker("run", "--rm", "--mount", mount, "--entrypoint", "/bin/amtool", image,
               "check-config", "/etc/alertmanager/alertmanager.yml")
        docker("run", "-d", "--name", manager, "--network", network,
               "-p", "127.0.0.1::9093", "--mount", mount, image,
               "--config.file=/etc/alertmanager/alertmanager.yml", "--cluster.listen-address=")
        created.append(manager)
        mail_port = docker("port", mailpit, "8025/tcp").splitlines()[0].rsplit(":", 1)[1]
        manager_port = docker("port", manager, "9093/tcp").splitlines()[0].rsplit(":", 1)[1]
        base = f"http://127.0.0.1:{manager_port}"
        def ready():
            with urlopen(base + "/-/ready", timeout=3) as response:
                return response.status == 200
        wait_for(ready)
        started = datetime.now(timezone.utc) - timedelta(seconds=1)
        labels = {"alertname": "DeliverySmokeTest", "severity": "warning", "endpoint_id": "ci"}
        def send(ends):
            payload = [{"labels": labels, "annotations": {"summary": "Isolated CI notification test"},
                        "startsAt": started.isoformat(), "endsAt": ends.isoformat()}]
            request = Request(base + "/api/v2/alerts", data=json.dumps(payload).encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=5) as response:
                assert response.status == 200
        inbox = f"http://127.0.0.1:{mail_port}/api/v1/messages"
        send(datetime.now(timezone.utc) + timedelta(minutes=5))
        wait_for(lambda: any("FIRING" in message["Subject"] for message in read(inbox)["messages"]))
        send(datetime.now(timezone.utc))
        wait_for(lambda: any("RESOLVED" in message["Subject"] for message in read(inbox)["messages"]))
        print("PASS: Alertmanager delivered FIRING and RESOLVED emails to the isolated local inbox.")
    finally:
        for name in reversed(created):
            subprocess.run(["docker", "logs", name], check=False)
            subprocess.run(["docker", "rm", "-f", name], check=False)
        if network_created:
            subprocess.run(["docker", "network", "rm", network], check=False)


if __name__ == "__main__":
    main()
