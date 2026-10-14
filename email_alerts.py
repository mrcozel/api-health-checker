
import os
import requests


BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_alert(subject, message):
    api_key = os.getenv("BREVO_API_KEY")

    if not api_key:
        print("ERROR: BREVO_API_KEY is not configured.")
        return False

    payload = {
        "sender": {
            "name": "API Health Checker",
            "email": "ozel1903@gmail.com"
        },
        "to": [
            {
                "email": "ozel1903@gmail.com"
            }
        ],
        "subject": subject,
        "textContent": message
    }

    headers = {
        "api-key": api_key,
        "accept": "application/json",
        "content-type": "application/json"
    }

    try:
        response = requests.post(
            BREVO_API_URL,
            json=payload,
            headers=headers,
            timeout=10
        )

        if response.status_code == 201:
            print("Alert email accepted by Brevo.")
            return True

        print(f"Email failed: HTTP {response.status_code}")
        print(response.text)
        return False

    except requests.RequestException as exc:
        print(f"Email request failed: {exc}")
        return False


if __name__ == "__main__":
    send_alert(
        "API Health Checker - Test Alert",
        "This is a test email from your Python API Health Checker."
    )
