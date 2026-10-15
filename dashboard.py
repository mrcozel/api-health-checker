"""Serve a read-only local dashboard for the existing checker output files."""

import argparse
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from incident_history import find_incidents, load_checks


ASSET = Path(__file__).parent / "dashboard" / "index.html"


def build_snapshot(data_dir):
    data_dir = Path(data_dir)
    history = data_dir / "health_history.csv"
    report = data_dir / "health_report.json"
    checks = load_checks(history) if history.exists() else []
    endpoints = {}
    for timestamp, name, url, status in checks:
        endpoints[(name, url)] = {
            "name": name, "url": url, "status": status,
            "timestamp": timestamp.isoformat(), "response_ms": None,
            "http_code": None,
        }
    # The JSON report contains response times from the most recent checker run.
    # Prefer history when it contains a newer observation for the same endpoint.
    if report.exists():
        with report.open(encoding="utf-8") as file:
            rows = json.load(file)
        if not isinstance(rows, list):
            raise ValueError("Health report must be a list of checks.")
        for row in rows:
            if not isinstance(row, dict) or any(not row.get(k) for k in ("name", "url", "timestamp")):
                raise ValueError("Health report contains an incomplete check.")
            if row.get("status") not in {"UP", "SLOW", "FAIL"}:
                raise ValueError("Health report contains an unknown status.")
            timestamp = datetime.fromisoformat(row["timestamp"])
            key = (row["name"], row["url"])
            previous = endpoints.get(key)
            if previous and timestamp < datetime.fromisoformat(previous["timestamp"]):
                continue
            endpoints[key] = {k: row.get(k) for k in (
                "name", "url", "status", "timestamp", "response_ms", "http_code")}
    incidents = []
    for incident in find_incidents(checks):
        incidents.append({
            "name": incident.name, "url": incident.url, "kind": incident.kind,
            "started_at": incident.started_at.isoformat(),
            "recovered_at": incident.recovered_at.isoformat() if incident.recovered_at else None,
            "last_observed_at": incident.last_observed_at.isoformat(),
            "duration_seconds": incident.duration_seconds,
            "failed_checks": incident.failed_checks, "slow_checks": incident.slow_checks,
        })
    return {
        "endpoints": list(endpoints.values()), "incidents": incidents,
        "check_count": len(checks),
        "available_checks": sum(check[3] in {"UP", "SLOW"} for check in checks),
        "history_available": history.exists(), "report_available": report.exists(),
    }


def make_handler(data_dir):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/api/dashboard":
                try:
                    payload = build_snapshot(data_dir)
                    body = json.dumps(payload, allow_nan=False).encode()
                except (OSError, ValueError, TypeError, KeyError) as error:
                    self.respond(503, json.dumps({"error": f"Cannot read monitoring data: {error}"}).encode(),
                                 "application/json")
                    return
                self.respond(200, body, "application/json")
            elif path in {"/", "/index.html"}:
                self.respond(200, ASSET.read_bytes(), "text/html; charset=utf-8")
            else:
                self.respond(404, b"Not found", "text/plain")

        def respond(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind address (use 0.0.0.0 inside a container)")
    parser.add_argument("--data-dir", type=Path, default=Path.cwd(),
                        help="Directory containing checker outputs (default: current directory)")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.data_dir))
    print(f"Dashboard: http://{args.host}:{server.server_port}", flush=True)
    print(f"Reading monitoring data from {args.data_dir.resolve()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
