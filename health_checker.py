
import time
import requests
from email_alerts import send_alert
from datetime import datetime
import json
import csv
import os
import logging
from logging.handlers import RotatingFileHandler


# Logging configuration
logger = logging.getLogger()
logger.setLevel(logging.INFO)

if not any(
    isinstance(handler, RotatingFileHandler)
    and handler.baseFilename == os.path.abspath("health_checker.log")
    for handler in logger.handlers
):
    file_handler = RotatingFileHandler(
        "health_checker.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8"
    )

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


# APIs we want to monitor
ENDPOINTS = [
    {
        "name": "JSONPlaceholder API",
        "url": "https://jsonplaceholder.typicode.com/posts/1"
    },
]

TIMEOUT = 5
SLOW_THRESHOLD_MS = 1000
FAILURE_THRESHOLD = 3

# Tracks failure counts and alert state for each endpoint.
# These values reset when the program restarts.
endpoint_states = {}


def check_endpoint(name, url):
    print(f"\nChecking: {name}")
    logging.info("Checking API: %s", name)

    start_time = time.perf_counter()

    try:
        response = requests.get(url, timeout=TIMEOUT)
        elapsed = (time.perf_counter() - start_time) * 1000

        if not 200 <= response.status_code < 300:
            status = "FAIL"
        elif elapsed > SLOW_THRESHOLD_MS:
            status = "SLOW"
        else:
            status = "UP"

        result = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "name": name,
            "url": url,
            "status": status,
            "http_code": response.status_code,
            "response_ms": round(elapsed, 2),
            "error": None
        }

    except requests.exceptions.Timeout:
        logging.error("Request timed out for %s", name)

        result = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "name": name,
            "url": url,
            "status": "FAIL",
            "http_code": None,
            "response_ms": None,
            "error": "Request timed out"
        }

    except requests.exceptions.RequestException as exc:
        logging.exception("Request failed for %s: %s", name, exc)

        result = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "name": name,
            "url": url,
            "status": "FAIL",
            "http_code": None,
            "response_ms": None,
            "error": str(exc)
        }

    print(f"Status: {result['status']}")
    print(f"HTTP code: {result['http_code']}")
    print(f"Response time: {result['response_ms']} ms")

    if result["status"] == "UP":
        logging.info(
            "API healthy: %s | HTTP %s | %.2f ms",
            name,
            result["http_code"],
            result["response_ms"]
        )

    elif result["status"] == "SLOW":
        logging.warning(
            "API responding slowly: %s | HTTP %s | %.2f ms",
            name,
            result["http_code"],
            result["response_ms"]
        )
        print("WARNING: API is responding slowly!")

    else:
        logging.error(
            "API failed: %s | HTTP %s | Error: %s",
            name,
            result["http_code"],
            result["error"] or "Unexpected HTTP status"
        )

    if result["error"]:
        print(f"Error: {result['error']}")

    return result


def update_endpoint_state(result):
    name = result["name"]

    if name not in endpoint_states:
        endpoint_states[name] = {
            "consecutive_failures": 0,
            "alert_sent": False
        }

    state = endpoint_states[name]

    if result["status"] == "FAIL":
        state["consecutive_failures"] += 1

        if (
            state["consecutive_failures"] >= FAILURE_THRESHOLD
            and not state["alert_sent"]
        ):
            alert_sent = send_alert(
                f"API FAILURE: {name}",
                (
                    f"Endpoint: {name}\n"
                    f"URL: {result['url']}\n"
                    f"Consecutive failures: "
                    f"{state['consecutive_failures']}\n"
                    f"HTTP code: {result['http_code']}\n"
                    f"Error: {result['error'] or 'Unexpected HTTP status'}\n"
                    f"Time: {result['timestamp']}"
                )
            )

            if alert_sent:
                state["alert_sent"] = True
                logging.warning(
                    "Failure alert sent for %s", name
                )
            else:
                logging.error(
                    "Failure alert could not be sent for %s", name
                )

    elif result["status"] == "UP":
        if state["alert_sent"]:
            alert_sent = send_alert(
                f"API RECOVERED: {name}",
                (
                    f"Endpoint: {name}\n"
                    f"URL: {result['url']}\n"
                    f"Status: {result['status']}\n"
                    f"The endpoint is responding successfully again.\n"
                    f"Time: {result['timestamp']}"
                )
            )

            if alert_sent:
                logging.info(
                    "Recovery alert sent for %s", name
                )
            else:
                logging.error(
                    "Recovery alert could not be sent for %s", name
                )

        # UP confirms recovery. Reset the failure state.
        state["consecutive_failures"] = 0
        state["alert_sent"] = False

    # SLOW leaves the failure counter and alert state unchanged.


def main():
    results = []

    print("API HEALTH CHECKER")
    print("=" * 40)

    for endpoint in ENDPOINTS:
        result = check_endpoint(
            endpoint["name"],
            endpoint["url"]
        )

        # All failure and recovery alert logic is handled here.
        update_endpoint_state(result)

        # Add each endpoint result exactly once.
        results.append(result)

    healthy = sum(
        result["status"] == "UP"
        for result in results
    )

    slow = sum(
        result["status"] == "SLOW"
        for result in results
    )

    failed = sum(
        result["status"] == "FAIL"
        for result in results
    )

    print("\nSUMMARY")
    print("=" * 40)
    print(f"Total endpoints: {len(results)}")
    print(f"Healthy: {healthy}")
    print(f"Slow: {slow}")
    print(f"Failed: {failed}")

    with open(
        "health_report.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(results, file, indent=4)

    print("\nReport saved to health_report.json")

    file_exists = os.path.exists("health_history.csv")

    with open(
        "health_history.csv",
        "a",
        newline="",
        encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "timestamp",
                "name",
                "url",
                "status",
                "http_code",
                "response_ms",
                "error"
            ]
        )

        if not file_exists:
            writer.writeheader()

        writer.writerows(results)

    print("Historical results saved to health_history.csv")


def test_failure_alert():
    """Test email alerting against a deliberately failing endpoint."""
    endpoint = {
        "name": "HTTP 500 Test",
        "url": "https://httpbin.org/status/500"
    }

    # Make three checks so the normal threshold is exercised.
    for _ in range(FAILURE_THRESHOLD):
        result = check_endpoint(
            endpoint["name"],
            endpoint["url"]
        )

        update_endpoint_state(result)

        if result["status"] != "FAIL":
            print(
                "The test endpoint did not fail as expected. "
                "Check connectivity before testing alerts."
            )
            return


if __name__ == "__main__":
    import sys

    if "--test-alert" in sys.argv:
        test_failure_alert()
    else:
        try:
            while True:
                main()
                time.sleep(60)
        except KeyboardInterrupt:
            logging.info("Health checker stopped by user")
            print("\nHealth checker stopped.")
