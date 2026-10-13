API Health Checker

A lightweight Python tool that monitors API endpoints, measures response times, detects HTTP failures, and generates health reports.

Built as a practical project to develop skills in API troubleshooting, monitoring, incident investigation, and Python automation.


Features

Endpoint monitoring: Sends HTTP requests to configured API endpoints.

Response-time measurement: Measures request duration in milliseconds.

Failure detection: Identifies unsuccessful HTTP responses, including server errors such as HTTP 500.

Slow-response warnings: Flags successful responses that exceed a configurable threshold.

Summary reporting: Displays healthy, slow, and failed endpoint counts.

JSON reporting: Saves the latest check results to health_report.json.

Continuous monitoring: Repeats checks every 60 seconds.

Error handling: Handles request timeouts and connection-related errors.


Running Automated Tests

The project includes automated unit tests covering successful API responses, server errors, request timeouts, and connection failures.

Run the tests from the project directory:

python -m unittest -v

The tests use mocked HTTP responses, so they do not depend on external APIs being available.

All four tests should pass when the application behaves as expected.


Technologies

Python

Requests

JSON

HTTP/REST APIs

Git and GitHub

Requirements

Python 3

Internet connection

Git (optional, for version control)


Installation

Clone the repository:

git clone https://github.com/mrcozel/api-health-checker.git

Navigate to the project directory:

cd api-health-checker

Create a virtual environment:

python -m venv .venv

Activate the virtual environment on Windows:

.venv\Scripts\activate

Install the dependency:

python -m pip install requests


Configuration

Edit health_checker.py to configure the endpoints you want to monitor.

Example:

ENDPOINTS = [
    {
        "name": "JSONPlaceholder API",
        "url": "https://jsonplaceholder.typicode.com/posts/1"
    }
]

TIMEOUT = 5
SLOW_THRESHOLD_MS = 1000

The timeout is measured in seconds, and the slow-response threshold is measured in milliseconds.


Usage

Run a monitoring session:

python health_checker.py

The script checks the configured endpoints, displays a summary, and saves the latest results to health_report.json. Continuous monitoring repeats every 60 seconds.

Press Ctrl + C to stop monitoring.

Example Output

Checking: JSONPlaceholder API
Status: UP
HTTP code: 200
Response time: 120.45 ms

SUMMARY
========================================
Total endpoints: 2
Healthy: 1
Slow: 0
Failed: 1

Report saved to health_report.json

Response times and results are illustrative and will vary.

Understanding the Results

Status

Meaning

UP

The endpoint returned a successful HTTP status and responded within the threshold.

SLOW

The endpoint returned a successful HTTP status but exceeded the response-time threshold.

FAIL

The request returned a non-success HTTP status or encountered a request error.

Potential Improvements

Historical CSV logging for trend analysis.

Automated tests for successful responses, HTTP errors, timeouts, and connection failures.

Configurable endpoint lists and monitoring intervals.

Structured logging and alerting integrations.

Response-time statistics and availability summaries.

Disclaimer

Use endpoints that you own or are authorised to monitor. Avoid sending credentials or sensitive information to public repositories.
