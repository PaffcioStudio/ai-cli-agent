#!/usr/bin/env python3
"""
web/server.py – cienki router HTTP dla AI CLI web panelu.

Logika podzielona na moduły:
  handlers/base.py           – stałe, helpery sandboxa, JsonMixin
  handlers/config_handler.py – config, status, modele, prompt, logi
  handlers/chat_handler.py   – AI proxy (Ollama), memory, historia chatów
  handlers/sandbox_handler.py– upload, download, workspace tree
"""

import http.server
import socketserver
import sys
from pathlib import Path
from urllib.parse import urlparse

# Handlers
sys.path.insert(0, str(Path(__file__).parent))
from handlers.base            import get_local_ip, REQUESTS_AVAILABLE
from handlers.config_handler  import ConfigHandlerMixin
from handlers.chat_handler    import ChatHandlerMixin
from handlers.sandbox_handler import SandboxHandlerMixin

WEB_DIR       = Path(__file__).parent
PORT          = 21650
HOST          = "0.0.0.0"
MAX_UPLOAD_MB = 100


class PanelHandler(ConfigHandlerMixin, ChatHandlerMixin,
                   SandboxHandlerMixin, http.server.SimpleHTTPRequestHandler):
    """Router panelu – łączy wszystkie handlery przez MRO."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    # ── GET ──────────────────────────────────────────────────────────────────

    def do_OPTIONS(self):
        """CORS preflight – wymagany przez przeglądarkę przed POST multipart."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Content-Length")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._route_get(parsed.path)
        else:
            super().do_GET()

    def _route_get(self, path: str):
        if   path == "/api/status":       self.api_status()
        elif path == "/api/config":       self.api_get_config()
        elif path == "/api/prompt":       self.api_get_prompt()
        elif path == "/api/logs":         self.api_get_logs()
        elif path == "/api/models":       self.api_get_models()
        elif path == "/api/memory":       self.api_get_memory()
        elif path == "/api/chats":        self.api_list_chats()
        elif path.startswith("/api/chats/"):
            self.api_get_chat(path[len("/api/chats/"):])
        elif path.startswith("/api/sandbox/") and path.endswith("/tree"):
            self.api_sandbox_tree(path[len("/api/sandbox/"):-len("/tree")])
        elif path.startswith("/api/sandbox/") and path.endswith("/uploads"):
            self.api_sandbox_uploads(path[len("/api/sandbox/"):-len("/uploads")])
        elif path.startswith("/api/download/"):
            rest  = path[len("/api/download/"):]
            parts = rest.split("/", 1)
            if len(parts) == 2:
                self.api_download(*parts)
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    # ── POST ─────────────────────────────────────────────────────────────────

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._route_post(parsed.path)
        else:
            self.send_error(404)

    def _route_post(self, path: str):
        # Upload multipart - nie czytaj jako JSON
        if path.startswith("/api/upload/"):
            self.api_upload(path[len("/api/upload/"):])
            return

        import json
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_json_response({"error": "Invalid JSON"}, 400)
            return

        if   path == "/api/config":         self.api_save_config(data)
        elif path == "/api/prompt":         self.api_save_prompt(data)
        elif path == "/api/logs/clear":     self.api_clear_logs()
        elif path == "/api/chat":           self.api_chat(data)
        elif path == "/api/memory":         self.api_save_memory(data)
        elif path == "/api/memory/delete":  self.api_delete_memory(data)
        elif path == "/api/chats":          self.api_save_chat(data)
        elif path.startswith("/api/chats/") and path.endswith("/delete"):
            self.api_delete_chat(path[len("/api/chats/"):-len("/delete")])
        elif path.startswith("/api/session/") and path.endswith("/delete"):
            self.api_delete_session(path[len("/api/session/"):-len("/delete")])
        else:
            self.send_error(404)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not REQUESTS_AVAILABLE:
        print("⚠ Brak 'requests' – status Ollama niedostępny")
        print("  pip install requests --break-system-packages\n")

    try:
        local_ip = get_local_ip()
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer((HOST, PORT), PanelHandler) as httpd:
            print("╔══════════════════════════════════════════════════════════════╗")
            print("║           AI CLI Agent – Web Panel                           ║")
            print("╚══════════════════════════════════════════════════════════════╝")
            print()
            print(f"  LAN:       http://{local_ip}:{PORT}")
            print(f"  localhost: http://localhost:{PORT}")
            print(f"  Upload:    max {MAX_UPLOAD_MB} MB")
            print()
            print("  Ctrl+C aby zatrzymać")
            print()
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nZatrzymano.")
        sys.exit(0)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"✗ Port {PORT} zajęty")
        else:
            print(f"✗ Błąd: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
