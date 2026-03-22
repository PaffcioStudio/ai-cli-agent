"""
{{PROJECT_NAME}} — {{DESCRIPTION}}
Autor: {{AUTHOR}}, {{YEAR}}
"""
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import json


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"status": "ok"}).encode()
        else:
            body = json.dumps({"project": "{{PROJECT_NAME}}", "version": "0.1.0"}).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"[{{PROJECT_NAME}}] Startuje na porcie {port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
