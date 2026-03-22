"""
handlers/sandbox_handler.py – upload plików, sandbox workspace, download.
"""
import io
import json
import mimetypes
import os
import re
import shutil
import zipfile
from pathlib import Path
from urllib.parse import unquote

from .base import (
    MAX_UPLOAD_MB, SESSIONS_DIR,
    sanitize_id, get_session_paths, ensure_session,
    safe_extract_zip, get_workspace_tree,
    log_error,
    JsonMixin,
)


def _parse_multipart(data: bytes, boundary: bytes) -> dict:
    """
    Prosty parser multipart/form-data – zastępstwo za usunięty moduł cgi (Python 3.13+).
    Zwraca słownik {name: (filename_or_None, bytes)}.
    """
    result = {}
    delim = b"--" + boundary
    parts = data.split(delim)
    for part in parts[1:]:  # pomijamy część przed pierwszym separatorem
        # Zakończenie multipart
        if part.lstrip(b"\r\n").startswith(b"--"):
            continue
        # Usuń wiodący CRLF (przeglądarka dodaje \r\n po delimitere)
        if part.startswith(b"\r\n"):
            part = part[2:]
        elif part.startswith(b"\n"):
            part = part[1:]
        # Oddziel nagłówki od ciała
        if b"\r\n\r\n" in part:
            raw_headers, body = part.split(b"\r\n\r\n", 1)
        elif b"\n\n" in part:
            raw_headers, body = part.split(b"\n\n", 1)
        else:
            continue
        # Usuń końcowy CRLF z ciała (separator następnej części)
        if body.endswith(b"\r\n"):
            body = body[:-2]
        # Parsuj Content-Disposition
        headers_str = raw_headers.decode("utf-8", errors="replace")
        cd_match = re.search(r'Content-Disposition:[^\r\n]*(?:^|;|\s)name="([^"]+)"', headers_str, re.IGNORECASE)
        if not cd_match:
            continue
        name = cd_match.group(1)
        fn_match = re.search(r'filename="([^"]*)"', headers_str, re.IGNORECASE)
        filename = fn_match.group(1) if fn_match else None
        result[name] = (filename, body)
    return result


class SandboxHandlerMixin(JsonMixin):

    # ── Upload ────────────────────────────────────────────────────────────────

    def api_upload(self, session_id: str):
        """Odbiera plik multipart, zapisuje do uploads/. Zwraca kontekst dla AI."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_UPLOAD_MB * 1024 * 1024:
                self.send_json_response(
                    {"error": f"Plik za duży (max {MAX_UPLOAD_MB} MB)"}, 413)
                return

            ct = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in ct:
                self.send_json_response({"error": "Wymagany multipart/form-data"}, 400)
                return

            # Wyciągnij boundary z Content-Type
            boundary_match = re.search(r'boundary=([^\s;]+)', ct)
            if not boundary_match:
                self.send_json_response({"error": "Brak boundary w Content-Type"}, 400)
                return
            boundary = boundary_match.group(1).encode("utf-8")

            raw_data = self.rfile.read(content_length)
            fields = _parse_multipart(raw_data, boundary)

            if "file" not in fields:
                self.send_json_response({"error": "Brak pola 'file'"}, 400)
                return

            orig_filename, file_data = fields["file"]
            filename = Path(orig_filename or "upload").name or "upload"
            safe_sid = sanitize_id(session_id)
            paths    = ensure_session(safe_sid)
            dest     = paths["uploads"] / filename
            dest.write_bytes(file_data)

            is_zip     = filename.lower().endswith(".zip")
            size_bytes = dest.stat().st_size
            size_mb    = round(size_bytes / 1024 / 1024, 2)

            self.send_json_response({
                "success":    True,
                "filename":   filename,
                "size_bytes": size_bytes,
                "size_mb":    size_mb,
                "is_zip":     is_zip,
                "session_id": safe_sid,
                "ai_context": self._build_upload_context(
                    safe_sid, filename, size_mb, is_zip, dest, paths),
            })
        except Exception as e:
            log_error("upload", str(e), f"session={session_id}")
            self.send_json_response({"error": str(e)}, 500)

    def _build_upload_context(self, session_id: str, filename: str,
                               size_mb: float, is_zip: bool,
                               upload_path: Path, paths: dict) -> str:
        ws  = paths["workspace"]
        out = paths["outputs"]

        lines = [
            f"Użytkownik wgrał plik: {filename} ({size_mb} MB)",
            f"Workspace: {ws}",
            f"Outputs:   {out}",
            "",
        ]

        if is_zip:
            lines += self._extract_and_read_zip(upload_path, ws, out, session_id)
        else:
            # Pojedynczy plik – skopiuj do workspace i wczytaj jeśli tekstowy
            import shutil
            dest_file = ws / filename
            ws.mkdir(parents=True, exist_ok=True)
            shutil.copy2(upload_path, dest_file)
            lines.append(f"Plik skopiowany do workspace: {dest_file}")
            content = self._try_read_text(dest_file)
            if content is not None:
                lines += ["", f"=== {filename} ===", content, ""]
            else:
                lines.append(f"(Plik binarny – nie można wyświetlić treści)")
            lines += self._download_hint(out, session_id)

        return "\n".join(lines)

    def _extract_and_read_zip(self, zip_path: Path, ws: Path,
                               out: Path, session_id: str) -> list:
        """Rozpakuje ZIP, wczyta strukturę i treść plików tekstowych."""
        import zipfile as zf
        lines = []

        # 1. Rozpakowanie z walidacją path traversal
        ws.mkdir(parents=True, exist_ok=True)
        try:
            with zf.ZipFile(zip_path, "r") as z:
                for member in z.namelist():
                    target = (ws / member).resolve()
                    if not str(target).startswith(str(ws.resolve())):
                        return [f"BŁĄD: Path traversal wykryty w ZIP ({member}) – przerwano."]
                z.extractall(ws)
        except Exception as e:
            return [f"BŁĄD przy rozpakowywaniu: {e}"]

        # 2. Zbierz drzewo plików
        all_files = sorted([p for p in ws.rglob("*") if p.is_file()])
        lines.append("Archiwum rozpakowane. Struktura projektu:")
        lines.append("")
        for f in all_files:
            rel = f.relative_to(ws)
            size = f.stat().st_size
            size_str = self._fmt_bytes(size)
            lines.append(f"  {rel}  ({size_str})")
        lines.append("")

        # 3. Wczytaj zawartość plików tekstowych (z limitem)
        TEXT_EXTS = {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
            ".html", ".htm", ".css", ".scss", ".sass",
            ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
            ".md", ".txt", ".rst", ".sh", ".bash", ".zsh",
            ".c", ".cpp", ".h", ".hpp", ".java", ".go", ".rs",
            ".rb", ".php", ".lua", ".sql", ".xml", ".csv",
            "Makefile", "Dockerfile", ".gitignore", ".editorconfig",
        }
        MAX_FILE_CHARS = 8000   # limit na jeden plik
        MAX_TOTAL_CHARS = 40000 # limit łączny żeby nie wysadzić kontekstu
        total_chars = 0
        shown = 0

        for f in all_files:
            if total_chars >= MAX_TOTAL_CHARS:
                lines.append(f"(… dalsze pliki pominięte – przekroczono limit kontekstu)")
                break
            ext = f.suffix.lower() if f.suffix else f.name
            if ext not in TEXT_EXTS:
                continue
            content = self._try_read_text(f)
            if content is None:
                continue
            if len(content) > MAX_FILE_CHARS:
                content = content[:MAX_FILE_CHARS] + f"\n… (plik ucięty, {len(content)} znaków łącznie)"
            rel = f.relative_to(ws)
            lines += ["", f"=== {rel} ===", content, ""]
            total_chars += len(content)
            shown += 1

        if shown == 0:
            lines.append("(Brak plików tekstowych do wyświetlenia)")

        # 4. Wskazówki dla AI
        lines += [
            "",
            "Przeanalizuj powyższy kod/projekt i odpowiedz czym jest ten projekt.",
            "Jeśli użytkownik poprosi o modyfikacje – edytuj pliki bezpośrednio w workspace.",
            "Gdy skończysz i użytkownik poprosi o pobranie – spakuj workspace do ZIP:",
            f"  import zipfile, pathlib",
            f"  ws  = pathlib.Path(r'{ws}')",
            f"  out = pathlib.Path(r'{out}/projekt_gotowy.zip')",
            f"  with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:",
            f"      for f in ws.rglob('*'):",
            f"          if f.is_file(): z.write(f, f.relative_to(ws))",
            f"  print('ZIP gotowy:', out.name)",
            f"Następnie podaj link: /api/download/{session_id}/projekt_gotowy.zip",
        ]
        return lines

    def _try_read_text(self, path: Path, max_bytes: int = 512 * 1024) -> str | None:
        """Próbuje wczytać plik jako tekst UTF-8. Zwraca None jeśli binarny."""
        try:
            raw = path.read_bytes()
            if b"\x00" in raw[:8192]:  # heurystyka: binarne mają null bytes
                return None
            return raw[:max_bytes].decode("utf-8", errors="replace")
        except Exception:
            return None

    def _fmt_bytes(self, n: int) -> str:
        if n < 1024:            return f"{n} B"
        if n < 1024 ** 2:       return f"{n/1024:.1f} KB"
        if n < 1024 ** 3:       return f"{n/1024**2:.2f} MB"
        return f"{n/1024**3:.2f} GB"

    def _download_hint(self, out: Path, session_id: str) -> list:
        return [
            "",
            "Gdy użytkownik poprosi o pobranie – spakuj workspace do ZIP i podaj link.",
            f"Link do pobrania: /api/download/{session_id}/workspace.zip",
        ]

    # ── Download ──────────────────────────────────────────────────────────────

    def api_download(self, session_id: str, filename: str):
        """Serwuje plik z outputs/. 'workspace.zip' pakuje workspace on-the-fly."""
        try:
            safe_id = sanitize_id(session_id)
            paths   = get_session_paths(safe_id)

            if filename == "workspace.zip":
                self._send_workspace_zip(paths)
                return

            safe_file = Path(unquote(filename)).name
            file_path = paths["outputs"] / safe_file

            # Ochrona path traversal
            try:
                file_path.resolve().relative_to(paths["outputs"].resolve())
            except ValueError:
                self.send_json_response({"error": "Forbidden"}, 403)
                return

            if not file_path.is_file():
                self.send_json_response({"error": "Plik nie istnieje"}, 404)
                return

            data = file_path.read_bytes()
            mime = mimetypes.guess_type(safe_file)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Disposition", f'attachment; filename="{safe_file}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        except Exception as e:
            log_error("download", str(e), f"session={session_id} file={filename}")
            self.send_json_response({"error": str(e)}, 500)

    def _send_workspace_zip(self, paths: dict):
        ws = paths["workspace"]
        if not ws.exists() or not any(ws.rglob("*")):
            self.send_json_response({"error": "Workspace jest pusty"}, 404)
            return
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in ws.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(ws))
        data = buf.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", 'attachment; filename="workspace.zip"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── Tree / uploads list ───────────────────────────────────────────────────

    def api_sandbox_tree(self, session_id: str):
        try:
            paths = get_session_paths(sanitize_id(session_id))
            self.send_json_response({
                "tree":       get_workspace_tree(paths["workspace"]),
                "session_id": sanitize_id(session_id),
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def api_sandbox_uploads(self, session_id: str):
        try:
            paths = get_session_paths(sanitize_id(session_id))
            files = []
            if paths["uploads"].exists():
                for f in sorted(paths["uploads"].iterdir()):
                    if f.is_file():
                        sz = f.stat().st_size
                        files.append({
                            "name":       f.name,
                            "size_bytes": sz,
                            "size_mb":    round(sz / 1024 / 1024, 2),
                            "is_zip":     f.suffix.lower() == ".zip",
                        })
            self.send_json_response({"uploads": files,
                                     "session_id": sanitize_id(session_id)})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def api_delete_session(self, session_id: str):
        """Usuwa tylko sandbox (bez historii chatu)."""
        try:
            sd = SESSIONS_DIR / sanitize_id(session_id)
            if sd.exists():
                shutil.rmtree(sd)
            self.send_json_response({"success": True})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)
