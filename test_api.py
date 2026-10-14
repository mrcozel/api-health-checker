import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

# Bind to localhost only: this test server is not intended to be exposed publicly.
HOST = "127.0.0.1"
PORT = 8001

# Demo-only fallback values. Override these with environment variables for local tests.
BEARER_TOKEN = os.getenv("TEST_API_BEARER_TOKEN", "demo-bearer-123")
API_KEY = os.getenv("TEST_API_KEY", "demo-api-key-456")


class TestAPIHandler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self.send_json(200, {"status": "ok"})

        if self.path == "/bearer":
            supplied = self.headers.get("Authorization", "")
            expected = f"Bearer {BEARER_TOKEN}"
            if not hmac.compare_digest(supplied, expected):
                return self.send_json(401, {"error": "Invalid bearer token"})
            return self.send_json(
                200, {"message": "Bearer authentication successful"}
            )

        if self.path == "/api-key":
            supplied = self.headers.get("X-API-Key", "")
            if not hmac.compare_digest(supplied, API_KEY):
                return self.send_json(401, {"error": "Invalid API key"})
            return self.send_json(
                200, {"message": "API key authentication successful"}
            )

        return self.send_json(404, {"error": "Endpoint not found"})

    def log_message(self, format, *args):
        print(f"{self.client_address[0]} - {format % args}")


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), TestAPIHandler)
    print(f"Test API running at http://{HOST}:{PORT}")
    print("Endpoints: /health, /bearer, /api-key")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTest API stopped.")
    finally:
        server.server_close()
