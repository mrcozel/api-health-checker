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

## Getting started

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

