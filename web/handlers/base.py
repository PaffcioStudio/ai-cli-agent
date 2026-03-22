"""
handlers/base.py – stałe, helpery sandboxa i mixin JSON dla web panelu.
"""
import json
import os
import re
import shutil
import socket
import zipfile
import io
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ── Ścieżki ──────────────────────────────────────────────────────────────────
CONFIG_DIR     = Path.home() / ".config" / "ai"
CONFIG_FILE    = CONFIG_DIR / "config.json"
PROMPT_FILE    = CONFIG_DIR / "prompt.txt"
PROMPT_WEB_FILE = CONFIG_DIR / "prompt-web.txt"
MEMORY_FILE    = CONFIG_DIR / "memory.json"
KNOWLEDGE_DIR  = CONFIG_DIR / "knowledge"
WEB_DATA_DIR   = CONFIG_DIR / "web"
CHATS_DIR      = WEB_DATA_DIR / "chats"
SESSIONS_DIR   = WEB_DATA_DIR / "sessions"
LOGS_DIR       = WEB_DATA_DIR / "logs"
LOG_FILE       = LOGS_DIR / "web.log"

MAX_UPLOAD_MB = 100


def log_error(source: str, error: str, extra: str = ""):
    """Zapisuje błąd do pliku web.log w formacie JSON-lines."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "src":    source,
            "error":  str(error),
        }
        if extra:
            entry["extra"] = extra
        import json as _json
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # log failure musi być cicha

# ── Sieć ─────────────────────────────────────────────────────────────────────

def get_local_ip() -> str:
    """Zwraca lokalne IP w sieci LAN."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# ── Helpery sandboxa ─────────────────────────────────────────────────────────

def sanitize_id(raw: str) -> str:
    """Zostawia tylko znaki bezpieczne w nazwie katalogu/pliku."""
    return "".join(c for c in raw if c.isalnum() or c in "-_")

def get_session_paths(session_id: str) -> dict:
    """Zwraca słownik ścieżek sandboxa dla danej sesji."""
    safe = sanitize_id(session_id)
    base = SESSIONS_DIR / safe
    return {
        "base":      base,
        "uploads":   base / "uploads",
        "workspace": base / "workspace",
        "outputs":   base / "outputs",
    }

def ensure_session(session_id: str) -> dict:
    """Tworzy strukturę katalogów sandboxa jeśli nie istnieje."""
    paths = get_session_paths(session_id)
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths

def safe_extract_zip(zip_path: Path, dest: Path):
    """
    Bezpieczne wypakowanie ZIP z walidacją path traversal.
    Rzuca ValueError jeśli wykryje próbę wyjścia poza dest.
    """
    dest = dest.resolve()
    dest_str = str(dest)
    with zipfile.ZipFile(zip_path, 'r') as z:
        for member in z.namelist():
            target = (dest / member).resolve()
            if not (str(target) == dest_str or
                    str(target).startswith(dest_str + os.sep)):
                raise ValueError(f"Path traversal wykryty: {member}")
        z.extractall(dest)

def get_workspace_tree(workspace: Path, max_depth: int = 4) -> list:
    """Zwraca drzewo plików workspace jako lista słowników."""
    result = []
    if not workspace.exists():
        return result
    try:
        for item in sorted(workspace.rglob("*")):
            rel   = item.relative_to(workspace)
            depth = len(rel.parts) - 1
            if depth >= max_depth:
                continue
            result.append({
                "path":   str(rel),
                "name":   item.name,
                "depth":  depth,
                "is_dir": item.is_dir(),
                "size":   item.stat().st_size if item.is_file() else 0,
            })
    except Exception:
        pass
    return result

# ── Mixin dla PanelHandler ────────────────────────────────────────────────────

class JsonMixin:
    """Mixin dodający send_json_response do http.server.BaseHTTPRequestHandler."""

    def send_json_response(self, data, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # wycisz domyślny access log
