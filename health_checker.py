import json
import time
import requests
from datetime import datetime

# APIs we want to monitor
ENDPOINTS = [
    {
        "name": "JSONPlaceholder API",
        "url": "https://jsonplaceholder.typicode.com/posts/1"
    },
    {
        "name": "HTTP 500 Test",
        "url": "https://httpbin.org/status/500"
    },
]

TIMEOUT = 5
SLOW_THRESHOLD_MS = 1000


def check_endpoint(name, url):
    print(f"\nChecking: {name}")

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
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
            "name": name,
            "url": url,
            "status": status,
            "http_code": response.status_code,
            "response_ms": round(elapsed, 2),
            "error": None
        }

    except requests.exceptions.Timeout:
        result = {
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
            "name": name,
            "url": url,
            "status": "FAIL",
            "http_code": None,
            "response_ms": None,
            "error": "Request timed out"
        }

    except requests.exceptions.RequestException as exc:
        result = {
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
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

    if result["status"] == "SLOW":
    	print("WARNING: API is responding slowly!")	
    if result["error"]:
        print(f"Error: {result['error']}")

    return result


def main():
    results = []

    print("API HEALTH CHECKER")
    print("=" * 40)

    for endpoint in ENDPOINTS:
        result = check_endpoint(
            endpoint["name"],
            endpoint["url"]
        )
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


    with open("health_report.json", "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4)

    print("\nReport saved to health_report.json")




if __name__ == "__main__":
    try:
        while True:
            main()
            print("\nNext check in 60 seconds...")
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")

