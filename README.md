# API Health Checker

A Python-based monitoring tool that checks HTTP API availability, measures response times, detects persistent failures, and sends email notifications when an endpoint fails or recovers.

This portfolio project demonstrates practical application-support skills: troubleshooting, monitoring, incident alerting, persistent state management, logging, reporting, configuration validation, automated testing, and CI.

## Features

- **Endpoint monitoring:** Monitor multiple HTTP/REST endpoints configured in `endpoints.json`.
- **Health classification:** Report each check as `UP`, `SLOW`, or `FAIL`.
- **Response-time measurement:** Record request duration in milliseconds.
- **Failure handling:** Detect unsuccessful HTTP responses, timeouts, and connection/request errors.
- **Threshold-based alerting:** Send a failure email after three consecutive failed checks.
- **Recovery notifications:** Send an email when an alerted endpoint returns to a healthy `UP` state.
- **Alert retry handling:** Retry failure or recovery notifications on later checks if an email could not be sent.
- **Persistent incident state:** Save failure counters and alert status in `endpoint_state.json`, so they survive application restarts.
- **Configurable settings:** Set the monitoring interval and request timeout using environment variables or a local `.env` file.
- **Reporting:** Write the latest results to JSON and append historical results to CSV.
- **Rotating logs:** Record diagnostic and alert activity in `health_checker.log`, with log rotation to limit file size.
- **Historical statistics:** Calculate availability, total checks, slow/failed checks, average response time, and slowest response.
- **Automated tests and CI:** Run unit tests locally and through GitHub Actions on pushes and pull requests.

## Technologies

- Python
- Requests and HTTP/REST APIs
- JSON and CSV
- `python-dotenv`
- Python logging and rotating file handlers
- Unit testing with `unittest`, `unittest.mock`, and `pytest`
- Brevo email API
- Git, GitHub, and GitHub Actions

## Docker and Kubernetes

The same Docker image runs either the health checker or the dashboard. Docker
Compose starts both and shares a named volume for reports, history, logs, and
incident state. Kubernetes runs them together in one Pod with persistent storage.

### Docker Compose

With Docker Desktop running in **Linux containers** mode, run from the repository
folder:

```bash
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 checker
```

Open **http://127.0.0.1:8080** after the first monitoring cycle. This port avoids
the existing local Python dashboard on 8000. Change it with `DASHBOARD_PORT` in
your local `.env` file. Compose also reads `CHECK_INTERVAL`, `TIMEOUT`, and the
optional `BREVO_API_KEY` from `.env`. For authenticated APIs, add the relevant
credential environment-variable names under the checker service's `environment`
section. Credentials and generated monitoring data are excluded from the image.

Edit `endpoints.json` to configure monitoring. Both containers run as a non-root
user. The dashboard mounts the monitoring volume read-only and its published
port is restricted to localhost. It refreshes data without restarting containers.
The volume starts empty; existing host CSV files are not automatically imported.

```bash
docker compose logs -f checker
docker compose exec checker python /app/incident_history.py
docker compose down
```

`down` stops the stack and preserves its volume. Do not add `--volumes` unless
you intend to delete the monitoring history. Without `BREVO_API_KEY`, checks still
run, but email notifications cannot be delivered. A dashboard health check confirms
that its server responds; it does not claim that monitored APIs are healthy.

### Kubernetes

See [the Kubernetes quickstart](k8s/README.md) for building/loading the image,
deploying configuration and persistent storage, optional Secrets, port-forwarding,
and troubleshooting. The application stays at one replica to avoid simultaneous
writers to the CSV and state files.

## Verified deployment and recovery tests

The following results were observed during a local deployment on **16 October
2026**, using Windows, Docker Desktop 4.95.0, Docker Engine 29.8.2, and a Docker
Desktop Kubernetes cluster running v1.36.1. Results below are recorded from the
terminal output collected during the walkthrough; counts and Pod names will
differ on another run.

### Docker Compose: container restart

From the repository root, the image built successfully and both services started:

```powershell
docker compose up --build -d
docker compose ps
```

Incident history was inspected before and after restarting the containers:

```powershell
docker compose exec checker python /app/incident_history.py
docker compose restart
docker compose exec checker python /app/incident_history.py
docker compose ps
```

**Observed result:** both recorded HTTPBin incidents remained after the restart.
The first retained its 122-second duration and original timestamps. The second,
previously ongoing, recorded recovery after monitoring resumed, with an observed
duration of 85 seconds. Both containers were running, and the dashboard reported
`healthy` at **http://127.0.0.1:8080**.

### Kubernetes: deployment and Pod replacement

The active context was `docker-desktop`, and the control-plane node was `Ready`.
The existing locally built image was available to this cluster.

```powershell
kubectl --context docker-desktop apply -k k8s
kubectl --context docker-desktop -n api-monitor rollout status deployment/api-health-checker --timeout=120s
kubectl --context docker-desktop -n api-monitor get pods,pvc,svc
```

**Observed result:** the Pod was `2/2 Running` with zero container restarts,
the `monitoring-data` claim was `Bound` with 1 GiB of ReadWriteOnce storage,
and the dashboard Service was available internally on port 8000.

In another PowerShell window, history rows were counted before replacing the
Pod. The command counts CSV data rows, excluding the header:

```powershell
kubectl --context docker-desktop -n api-monitor exec deployment/api-health-checker -c checker -- python -c "import csv; print(sum(1 for _ in csv.DictReader(open('/data/health_history.csv'))))"
kubectl --context docker-desktop -n api-monitor rollout restart deployment/api-health-checker
kubectl --context docker-desktop -n api-monitor rollout status deployment/api-health-checker --timeout=120s
kubectl --context docker-desktop -n api-monitor exec deployment/api-health-checker -c checker -- python -c "import csv; print(sum(1 for _ in csv.DictReader(open('/data/health_history.csv'))))"
```

| Verification | Observed result |
| --- | --- |
| History before Pod replacement | 22 recorded checks |
| Replacement rollout | Successfully completed |
| History after Pod replacement | 24 recorded checks |
| Monitoring after replacement | Continued collecting checks |

The retained and increasing check count is evidence that monitoring history
persisted across the planned Pod replacement and collection resumed. This test
does not establish byte-for-byte file integrity, node-failure recovery, backups,
or high availability. The single-replica `Recreate` deployment has brief downtime
during replacement.

### Reconnect the Kubernetes dashboard

Pod replacement can stop an existing port-forward. Start it again and keep that
terminal open:

```powershell
kubectl --context docker-desktop -n api-monitor port-forward service/dashboard 8081:8000
```

Open **http://127.0.0.1:8081**. Forwarding and connection messages were observed
successfully after the replacement. Port 8080 serves the separate Docker Compose
deployment; port 8081 serves Kubernetes. Each deployment has its own monitoring
storage. Stopping port-forwarding with Ctrl+C closes browser access through that
forward; it does not stop monitoring in Kubernetes.

## Prometheus metrics

The dashboard exposes a read-only `/metrics` endpoint in Prometheus text format.
Docker Compose includes **Prometheus v3.15.0**, scraping `dashboard:8000/metrics`
every 15 seconds. After pulling this version, run from the repository folder:

```powershell
docker compose up --build -d
docker compose ps
```

Open the dashboard metrics at **http://127.0.0.1:8080/metrics** and Prometheus at
**http://127.0.0.1:9090**. In Prometheus, open **Status > Target health** and check
the `api-health-checker` target, or query `up{job="api-health-checker"}`. A value
of 1 means Prometheus successfully scraped the exporter, not that the monitored
APIs are healthy or that the checker is still running. Use the freshness metrics
alongside the last recorded API status.

| Metric | Meaning |
| --- | --- |
| `api_monitor_endpoints` | Number of endpoints with recorded observations. |
| `api_monitor_history_available` | 1 when the history CSV exists; otherwise 0. |
| `api_monitor_last_status{status="UP\|SLOW\|FAIL"}` | Three separate one-hot series per endpoint, one for each status; the last recorded status has value 1. |
| `api_monitor_response_seconds` | Latest recorded response time, converted from milliseconds; omitted when unavailable or invalid. |
| `api_monitor_last_check_timestamp_seconds` | Last check as a Unix timestamp. |
| `api_monitor_stale` | 1 when the endpoint observation is overdue; otherwise 0. |
| `api_monitor_clock_skew` | 1 when a check timestamp is more than five seconds in the future. |
| `api_monitor_stale_after_seconds` | Configured freshness limit, default 180 seconds. |
| `api_monitor_recorded_checks{status="UP\|SLOW\|FAIL"}` | Retained CSV check count for each endpoint/status combination. |

All exported application metrics are **gauges**. In the table, `UP\|SLOW\|FAIL`
denotes the three possible label values, not a literal combined value. CSV counts
can decrease if history is removed or archived; do not apply `rate()` or
`increase()` to them. Scraping does not create checks or increment counts.

Each endpoint has `endpoint` (configured name) and `endpoint_id` (a stable hash of
its name and URL) labels, so duplicate names remain distinct. Raw URLs, error
messages and credentials are not exported. Keep credentials out of endpoint names.

Try these PromQL expressions:

```promql
api_monitor_response_seconds * 1000
time() - api_monitor_last_check_timestamp_seconds
api_monitor_stale == 1
sum by (status) (api_monitor_recorded_checks)
api_monitor_last_status{status="FAIL"} == 1
```

Select a time range in Prometheus to see sampled response-time trends. These are
snapshots of the latest observations, not a histogram of every request: checks
between scrapes can be missed. Existing CSV history provides the retained counts;
Prometheus does not backfill historical response-time samples from the CSV.
The exporter reads the CSV on every scrape, so large histories increase scrape
cost. Missing files expose zero endpoints/history availability; unreadable or
invalid data returns HTTP 503, making the target's `up` value 0 instead of
silently reporting healthy data. Clock/timezone rules match dashboard freshness.

Prometheus stores its own samples in the `prometheus-data` named volume, with
15-day time retention and a 1 GB size-retention limit (WAL/head data add overhead).
`docker compose down` preserves it; `down --volumes` deletes it along with the
checker history. To change the host port, set `PROMETHEUS_PORT` in `.env`.
Dashboard and Prometheus ports are bound to localhost. Kubernetes Prometheus
deployment is not included in this setup.

Configuration: [`monitoring/prometheus.yml`](monitoring/prometheus.yml).
CI builds the application image, validates the Prometheus configuration, and
launches real Prometheus and Grafana to verify scraping, dashboard/data-source
provisioning, and every provisioned panel query using isolated test observations.
This does not modify the running local monitoring stack.

## Grafana dashboard

Docker Compose includes **Grafana 13.2.4**, automatically connected to Prometheus
with a provisioned **API Health Monitor** dashboard. From the repository folder:

```powershell
docker compose up --build -d
docker compose ps
```

Open **http://127.0.0.1:3000**. On a new Grafana volume, sign in with username
`admin` and password `admin`, then complete Grafana's password-change prompt.
If you already changed the password, use your saved password. Sign-up and
anonymous access are disabled; the published port is bound to localhost.
Change `GRAFANA_PORT` in `.env` if port 3000 is already in use.

The provisioned dashboard opens as the home dashboard, or find it under
**Dashboards > API Monitoring > API Health Monitor**. Its direct path is
**http://127.0.0.1:3000/d/api-monitor**. It refreshes every 15 seconds and defaults
to the last hour. Prometheus collects new samples as the stack runs; earlier
CSV response times are not backfilled.

Panels cover:

- Exporter scrape health, overdue observations, and clock warnings.
- Response-time trends in milliseconds and last-check ages in seconds.
- Last recorded API status per endpoint and freshness per endpoint.
- CSV check counts by status, recorded endpoints, and the freshness limit.

Read the scrape-health and freshness panels first. A successful scrape does not
prove the checker is running; a last recorded `UP` status may be stale. Empty
panels display **NO DATA**, not a healthy value. CSV counts are gauges and may
decrease when history is archived. These panels reuse the metric definitions and
limits described above; no alert rules or notification routes are configured.

Grafana users, preferences and password changes persist in `grafana-data`.
Prometheus samples remain in its separate `prometheus-data` volume.
`docker compose down` preserves both; adding `--volumes` deletes them. The
provisioned dashboard and data source come from files in `monitoring/grafana/`.
Edit those tracked files to change them; direct saving of this dashboard in the
UI is disabled so the repository remains the source of truth. Grafana uses its
built-in panels and requires no additional plugins.

If charts are empty, allow a scrape cycle, confirm the time range includes recent
checks, and query `up{job="api-health-checker"}` in Prometheus. If login or
provisioning fails, inspect `docker compose logs --tail=100 grafana`. This Grafana
integration currently runs in Docker Compose, not the Kubernetes deployment.

### Verified Grafana monitoring recovery test

The deployed Docker Compose stack was tested by stopping only the checker while
leaving the dashboard exporter, Prometheus, and Grafana running. The freshness
limit was 180 seconds. The following observations were captured in the supplied
Grafana screenshots during the local walkthrough:

| Observation | Checker stopped | After checker restart |
| --- | --- | --- |
| Exporter scrape health | SCRAPING | SCRAPING |
| Overdue observations | 2 | 0 |
| Clock warnings | 0 | 0 |
| Checks retained in CSV | 698 | 702 |
| Last-check age | Rose above eight minutes | Dropped back below the freshness limit |

Commands used from the repository folder, with time allowed between them to
observe the overdue state and subsequent recovery:

```powershell
docker compose stop checker
```

After the last observations exceeded the freshness limit, the overdue state was
confirmed in Grafana. Monitoring was then resumed:

```powershell
docker compose start checker
```

The recovery screenshot shows the last-check-age trend dropping and the retained
check count increasing. This verifies that new observations resumed and Grafana
cleared the overdue state after collection and refresh. It also demonstrates that
successful exporter scraping alone does not establish fresh monitoring data:
SCRAPING remained visible while both endpoint observations were overdue.

These results validate freshness visibility and recovery in the local Docker
Compose observability stack. They do not demonstrate an API outage, notification
delivery, or a Grafana deployment in Kubernetes.

## Run directly with Python

### 1. Clone the repository

```bash
git clone https://github.com/mrcozel/api-health-checker.git
cd api-health-checker
```

### 2. Create and activate a virtual environment

On Windows Command Prompt:

```bat
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
python -m pip install requests python-dotenv pytest
```

### 4. Configure monitoring

The application reads endpoint definitions from `endpoints.json`. Add or edit entries using this format:

```json
[
  {
    "name": "Example API",
    "url": "https://example.com/health"
  }
]
```

Use real endpoints that you own or are authorised to monitor. The repository includes example public endpoints in its default configuration.

Create a local file named `.env` in the project directory to set monitoring options:

```dotenv
CHECK_INTERVAL=60
TIMEOUT=5
```

- `CHECK_INTERVAL`: Seconds to wait between monitoring cycles (default: `60`).
- `TIMEOUT`: Maximum time to wait for each HTTP request, in seconds (default: `5`).

Both settings must be positive whole numbers. If they are missing, the defaults are used. The slow-response threshold is currently 1,000 ms, and the failure-alert threshold is three consecutive failed checks.

### 5. Configure API authentication (optional)

Public endpoints need no authentication. For protected endpoints, add an `auth` object to that endpoint in `endpoints.json`. Store the credential itself in an environment variable, not in the JSON file.

**Bearer token**

```json
{
  "name": "Protected API",
  "url": "https://api.example.com/resource",
  "auth": {
    "type": "bearer",
    "token_env": "EXAMPLE_API_TOKEN"
  }
}
```

Set the token in your environment. For a temporary Windows Command Prompt session:

```bat
set EXAMPLE_API_TOKEN=your_token_value
```

Or add `EXAMPLE_API_TOKEN=your_token_value` to your local `.env` file, which should not be committed.

**API key**

```json
{
  "name": "API Key Protected API",
  "url": "https://api.example.com/resource",
  "auth": {
    "type": "api_key",
    "key_env": "EXAMPLE_API_KEY",
    "header": "X-API-Key"
  }
}
```

Set `EXAMPLE_API_KEY` in the environment or local `.env` file. The `header` field is optional and defaults to `X-API-Key`; use the header name required by your API provider.

If a configured credential is missing, the checker reports a configuration error rather than silently making an unauthenticated request. Never use real secrets in examples, commits, or screenshots.


### 6. Configure email alerts (optional)

Email notifications use the Brevo API. Create an API key in your Brevo account and configure it as an environment variable. On Windows Command Prompt:

```bat
setx BREVO_API_KEY "your_brevo_api_key"
```

Replace the placeholder with your key, then open a **new** Command Prompt so the variable is available. Ensure the sender address is verified in Brevo and that the sender and recipient settings in `email_alerts.py` are correct.

Keep API keys and credentials out of source control. Do not paste real keys into README files, source code, screenshots, or commits.

## Usage

Start continuous monitoring:

```bash
python health_checker.py
```

The checker runs through the configured endpoints, prints a summary, updates report files, and repeats after the configured interval. Stop it with **Ctrl+C**.

### Test the email alert workflow

```bash
python health_checker.py --test-alert
```

This deliberately checks an endpoint that returns HTTP 500 and exercises the failure threshold. **It can send a real email**, so run it only when you intend to test notifications.

You can also test the email integration separately:

```bash
python email_alerts.py
```

This may send a real email as well.

### Generate historical statistics

After the checker has created `health_history.csv`, run:

```bash
python health_stats.py
```

The report summarises the recorded checks for each endpoint, including observed availability (where `UP` and `SLOW` count as available), average response time, slowest response, and the number of successful, slow, and failed checks.

## Understanding statuses

| Status | Meaning |
|---|---|
| `UP` | The endpoint returned a successful 2xx response within the response-time threshold. |
| `SLOW` | The endpoint returned a successful 2xx response, but took longer than the threshold. |
| `FAIL` | The endpoint returned a non-2xx response or the request failed, timed out, or could not connect. |

A `SLOW` result does not increment the consecutive-failure counter or clear an existing incident state. A healthy `UP` result resets failures below the alert threshold. After a failure alert has been sent, the recovery notification must succeed before the saved incident state is cleared.

## Output files

| File | Purpose |
|---|---|
| `health_report.json` | Latest results from a monitoring cycle. |
| `health_history.csv` | Append-only history used for trend analysis and statistics. |
| `health_checker.log` | Application activity, errors, and alert events; rotated to limit log size. |
| `endpoint_state.json` | Persistent consecutive-failure counts and alert status. |

Generated reports, logs, saved state, local environment files, and the virtual environment are excluded from version control by `.gitignore`.

## Run the tests

Run the full test suite:

```bash
python -m pytest -v
```

Or use Python's built-in test runner:

```bash
python -m unittest -v
```

The tests cover successful responses, HTTP errors, timeouts, connection failures, failure and recovery alerts, retry behaviour when email sending fails, persistence of endpoint state, configuration validation, and statistics calculations. HTTP responses and email sending are mocked in unit tests, so the suite does not need to send real alert emails.

## Continuous integration

GitHub Actions runs the automated tests on pushes and pull requests.

[View GitHub Actions runs](https://github.com/mrcozel/api-health-checker/actions)

## Support-engineering skills demonstrated

- API availability and response-time monitoring
- Incident detection, alerting, and recovery handling
- Persistent incident state and duplicate-alert prevention
- Troubleshooting through structured logs and error handling
- Historical reporting and operational metrics
- Configuration validation and secure handling of secrets
- Unit testing, mocking, and CI validation

## Cyberpunk monitoring dashboard

Run the local, read-only dashboard from the project directory:

```bash
python dashboard.py
```

Open **http://127.0.0.1:8000** in your browser. Keep the dashboard server running
and run the health checker in another terminal to collect fresh observations.
The dashboard reads `health_report.json` and `health_history.csv`; it does not
run checks or send alerts. It uses Python's standard library and has no additional
dependencies or external fonts/scripts.

The dark interface includes high-contrast status labels, response times, observed
availability, ongoing/recovered incident tables, search and status filters, and
an incident CSV export of the currently filtered rows. Data refreshes every 30
seconds while the page is visible, or when you press **Refresh data**. Disable
auto-refresh using the checkbox. Recorded check timestamps remain visible, so
an old observation is not mistaken for a new connectivity test.

**View demo** displays clearly labeled illustrative services without modifying
your monitoring files. Press **Use local data** to return to real observations.
Empty and unreadable data files are reported explicitly; a failed refresh retains
the previous snapshot with a visible error message.

For another data directory or port:

```bash
python dashboard.py --data-dir path/to/checker-outputs --port 8080
```

The server binds only to `127.0.0.1` and serves the dashboard and its data endpoint;
it does not expose the project directory. Endpoint history is retained across
runs, so an endpoint removed from your checker configuration may still appear
with its last recorded observation. Availability is calculated across all
historical checks (`UP` and `SLOW` count as available); average response uses the
latest endpoint checks with numeric response data. Incidents use the same rules
and observation limits as the report below.

### Monitoring freshness

Each endpoint shows its last-check age. At **180 seconds** without another check,
it gains a **STALE** label and the dashboard displays a monitoring-overdue banner.
The last recorded API status remains visible: an old `UP` result does not establish
current health, and stale monitoring does not by itself mean the API failed.
The warning clears when the dashboard loads a new check within the freshness limit.

Set a positive whole-number limit for direct Python use:

```bash
python dashboard.py --stale-after 180
```

Alternatively set `STALE_AFTER_SECONDS` in the dashboard process environment.
For Docker Compose, put `STALE_AFTER_SECONDS=180` in the local `.env` file and
recreate the dashboard with `docker compose up -d dashboard`. For Kubernetes, edit
the literal in `k8s/kustomization.yaml`, then apply `kubectl apply -k k8s`.
Choose a limit that allows for the check interval, the time needed to check every
endpoint, and normal request delays.

Ages are computed using the dashboard server's clock, not the browser's wall
clock. Offset-free timestamps use the server's local timezone; run the checker
and dashboard with matching timezone settings. Timestamps more than five seconds
in the future produce a clock warning. Endpoints retained only in old history
also become stale. A failed data refresh keeps the prior snapshot, with a refresh
error; its age continues increasing. Turning auto-refresh off does not freeze
ages or warnings. Demo mode uses illustrative ages and is not a live freshness test.

To test on Docker Compose, open the dashboard and run `docker compose stop checker`.
After the configured limit, confirm the STALE label and warning banner. Run
`docker compose start checker`, then refresh after the next completed check and
confirm the warning clears. This temporarily pauses monitoring; existing history
is preserved.

#### Verified Docker Compose freshness test

This procedure was verified on **16 October 2026** using the Docker Compose
dashboard at **http://127.0.0.1:8080**, with auto-refresh enabled and the default
180-second freshness limit.

| Step | Observed result |
| --- | --- |
| Run `docker compose stop checker` | The checker container stopped successfully. |
| Leave the dashboard running until checks are overdue | The banner reported: “MONITORING OVERDUE — 2 of 2 endpoints have no check within 3m 0s.” It also stated that last recorded statuses were shown and current health was unknown. |
| Run `docker compose start checker` | Checks resumed, and the dashboard warning cleared, as confirmed during the walkthrough. |

The overdue state was captured in a dashboard screenshot, and warning clearance
was confirmed after restarting the checker. This validates overdue-data detection
and recovery in the deployed Docker Compose application; it does not establish
that the monitored APIs failed. The screenshot confirms the banner, rather than
independently verifying each endpoint's STALE badge. This stop/start test was not
performed against the Kubernetes deployment.

## Incident history

After the checker has recorded checks in `health_history.csv`, run:

```bash
python incident_history.py
```

To read a history file from another location:

```bash
python incident_history.py --history path/to/health_history.csv
```

This read-only report shows each API's incident start, recovery, observed duration
in seconds, and failed/slow check counts. It uses the existing CSV without changing
the health checker or sending notifications.

An incident starts at the first `FAIL` or `SLOW` check and ends at the next `UP`
check for the same endpoint name and URL. Consecutive failures and slow responses
remain one incident, including transitions between them. An endpoint that has not
recorded recovery is marked **ongoing**, with duration measured only through its
last recorded check. A single ongoing check therefore has an observed duration of
zero seconds. Incidents are independent of the email alert threshold: even one
failed or slow check appears here.

For example, `FAIL` at 12:00, `SLOW` at 12:01, and `UP` at 12:03 produces:

```text
Type: FAIL + SLOW
Started: 2026-10-15 12:00:00
Recovered: 2026-10-15 12:03:00
Observed duration: 180 seconds
Failed checks: 1 | Slow checks: 1
```

Checks are processed in timestamp order; equal timestamps preserve CSV order.
Missing required columns or values, invalid timestamps, and unknown statuses
produce an error instead of an incomplete report. The checker's timestamps have
no timezone offset and are interpreted in their recorded local time. History with
consistent timezone-aware timestamps is also supported, but mixing timestamps
with and without offsets is rejected.

Durations are observations, not exact outage measurements: failures and recoveries
may happen between checks, and gaps in monitoring cannot establish continued
failure or availability. The report does not infer a root cause.

## Disclaimer

Only monitor endpoints you own or are authorised to test. Never commit API keys, credentials, or other sensitive information to a public repository.

### Run the local authentication test API

The repository includes a small test server for trying the health checker against public, bearer-token, and API-key endpoints. It binds to `127.0.0.1` only and is intended for local testing.

1. In the project directory, start the server:

   ```bash
   python test_api.py
   ```

   Keep this terminal open. In a second terminal, run the requests below.

2. Check the public endpoint and valid bearer token:

   ```bash
   curl -i http://127.0.0.1:8001/health
   curl -i -H "Authorization: Bearer demo-bearer-123" http://127.0.0.1:8001/bearer
   ```

   Both should return **HTTP 200 OK**.

3. Try an invalid bearer token:

   ```bash
   curl -i -H "Authorization: Bearer wrong-token" http://127.0.0.1:8001/bearer
   ```

   This should return **HTTP 401 Unauthorized**.

4. Check API-key authentication:

   ```bash
   curl -i -H "X-API-Key: demo-api-key-456" http://127.0.0.1:8001/api-key
   curl -i -H "X-API-Key: wrong-key" http://127.0.0.1:8001/api-key
   ```

   The valid key should return **HTTP 200 OK**; the invalid key should return **HTTP 401 Unauthorized**.

These demo credentials are for this local test server only. Do not use them for real services or production credentials.

