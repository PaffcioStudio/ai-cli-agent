"""
Clipboard Utils - integracja ze schowkiem systemowym.

OBSŁUGUJE:
- Odczyt ze schowka (xclip, xsel, wl-clipboard, pyperclip fallback)
- Zapis do schowka
- Wykrywanie środowiska (X11, Wayland, macOS, Windows)
- ai explain → wyjaśnia kod ze schowka
- ai fix → analizuje błąd ze schowka i sugeruje fix
- ai copy → kopiuje output do schowka

ZALEŻNOŚCI ZEWNĘTRZNE (opcjonalne, w kolejności preferencji):
- xclip (X11) - sudo apt install xclip
- xsel (X11) - sudo apt install xsel
- wl-clipboard (Wayland) - sudo apt install wl-clipboard
- pyperclip (fallback) - pip install pyperclip
"""

import subprocess
import shutil
import os
import sys
from typing import Optional, Dict, Tuple
from enum import Enum


class ClipboardBackend(Enum):
    XCLIP = "xclip"
    XSEL = "xsel"
    WLCLIPBOARD = "wl-clipboard"
    PYPERCLIP = "pyperclip"
    PBCOPY = "pbcopy"        # macOS
    POWERSHELL = "powershell"  # Windows
    NONE = "none"


class ClipboardError(Exception):
    pass


class ClipboardManager:
    """
    Zarządza dostępem do schowka systemowego.
    
    Automatycznie wykrywa dostępne narzędzie i używa go.
    Działa na X11, Wayland, macOS, Windows.
    """

    def __init__(self, logger=None):
        self.logger = logger
        self._backend: Optional[ClipboardBackend] = None
        self._backend_detected = False

    # =====================================================================
    # BACKEND DETECTION
    # =====================================================================

    def detect_backend(self) -> ClipboardBackend:
        """
        Wykryj dostępne narzędzie do obsługi schowka.
        
        Kolejność preferencji:
        1. Wayland (wl-copy/wl-paste)
        2. X11 xclip
        3. X11 xsel
        4. macOS pbcopy/pbpaste
        5. Windows PowerShell
        6. pyperclip (cross-platform Python)
        7. None
        
        Returns:
            ClipboardBackend - wykryty backend
        """
        if self._backend_detected:
            return self._backend if self._backend is not None else ClipboardBackend.NONE

        # Wayland
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
            self._backend = ClipboardBackend.WLCLIPBOARD

        # X11 - xclip
        elif (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and shutil.which("xclip"):
            self._backend = ClipboardBackend.XCLIP

        # X11 - xsel
        elif (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and shutil.which("xsel"):
            self._backend = ClipboardBackend.XSEL

        # macOS
        elif sys.platform == "darwin" and shutil.which("pbcopy"):
            self._backend = ClipboardBackend.PBCOPY

        # Windows
        elif sys.platform == "win32":
            self._backend = ClipboardBackend.POWERSHELL

        # pyperclip fallback
        else:
            try:
                import pyperclip
                self._backend = ClipboardBackend.PYPERCLIP
            except ImportError:
                self._backend = ClipboardBackend.NONE

        self._backend_detected = True

        if self.logger:
            self.logger.debug(f"Clipboard backend: {self._backend.value}")

        return self._backend

    def get_available_backends(self) -> Dict[str, bool]:
        """Sprawdź które backendy są dostępne"""
        result = {}

        result["xclip"] = bool(shutil.which("xclip"))
        result["xsel"] = bool(shutil.which("xsel"))
        result["wl-copy"] = bool(shutil.which("wl-copy"))
        result["pbcopy"] = bool(shutil.which("pbcopy"))

        try:
            import pyperclip
            result["pyperclip"] = True
        except ImportError:
            result["pyperclip"] = False

        result["wayland"] = bool(os.environ.get("WAYLAND_DISPLAY"))
        result["x11"] = bool(os.environ.get("DISPLAY"))
        result["platform"] = sys.platform

        return result

    def ensure_backend(self) -> Dict:
        """
        Upewnij się że jakiś backend jest dostępny.
        Instaluje xclip jeśli możliwe.
        
        Returns:
            {"success": bool, "backend": str, "message": str}
        """
        backend = self.detect_backend()

        if backend != ClipboardBackend.NONE:
            return {
                "success": True,
                "backend": backend.value,
                "message": f"Using {backend.value}"
            }

        # Spróbuj zainstalować xclip
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            try:
                result = subprocess.run(
                    ["sudo", "apt", "install", "-y", "xclip"],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    self._backend = ClipboardBackend.XCLIP
                    self._backend_detected = True
                    return {"success": True, "backend": "xclip", "message": "Installed xclip via apt"}
            except Exception:
                pass

        # Spróbuj pyperclip
        try:
            result = subprocess.run(
                ["pip", "install", "--break-system-packages", "pyperclip"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                self._backend = ClipboardBackend.PYPERCLIP
                self._backend_detected = True
                return {"success": True, "backend": "pyperclip", "message": "Installed pyperclip via pip"}
        except Exception:
            pass

        return {
            "success": False,
            "backend": "none",
            "message": (
                "Brak obsługi schowka.\n"
                "Zainstaluj: sudo apt install xclip\n"
                "Lub: pip install pyperclip"
            )
        }

    # =====================================================================
    # READ / WRITE
    # =====================================================================

    def read(self) -> Tuple[bool, Optional[str]]:
        """
        Odczytaj zawartość schowka.
        
        Returns:
            (success: bool, content: Optional[str])
        """
        backend = self.detect_backend()

        if backend == ClipboardBackend.NONE:
            return (False, None)

        try:
            if backend == ClipboardBackend.XCLIP:
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return (True, result.stdout)
                return (False, None)

            elif backend == ClipboardBackend.XSEL:
                result = subprocess.run(
                    ["xsel", "--clipboard", "--output"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return (True, result.stdout)
                return (False, None)

            elif backend == ClipboardBackend.WLCLIPBOARD:
                result = subprocess.run(
                    ["wl-paste"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return (True, result.stdout)
                return (False, None)

            elif backend == ClipboardBackend.PBCOPY:
                result = subprocess.run(
                    ["pbpaste"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return (True, result.stdout)
                return (False, None)

            elif backend == ClipboardBackend.POWERSHELL:
                result = subprocess.run(
                    ["powershell", "-command", "Get-Clipboard"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return (True, result.stdout)
                return (False, None)

            elif backend == ClipboardBackend.PYPERCLIP:
                import pyperclip
                content = pyperclip.paste()
                return (True, content)

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Clipboard read error: {e}")
            return (False, None)

        return (False, None)

    def write(self, content: str) -> Tuple[bool, Optional[str]]:
        """
        Zapisz tekst do schowka.
        
        Args:
            content: tekst do zapisania
        
        Returns:
            (success: bool, error: Optional[str])
        """
        backend = self.detect_backend()

        if backend == ClipboardBackend.NONE:
            return (False, "Brak obsługi schowka")

        try:
            encoded = content.encode("utf-8")

            if backend == ClipboardBackend.XCLIP:
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=encoded, capture_output=True, timeout=5
                )
                return (result.returncode == 0, result.stderr.decode() if result.returncode != 0 else None)

            elif backend == ClipboardBackend.XSEL:
                result = subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=encoded, capture_output=True, timeout=5
                )
                return (result.returncode == 0, result.stderr.decode() if result.returncode != 0 else None)

            elif backend == ClipboardBackend.WLCLIPBOARD:
                result = subprocess.run(
                    ["wl-copy"],
                    input=encoded, capture_output=True, timeout=5
                )
                return (result.returncode == 0, result.stderr.decode() if result.returncode != 0 else None)

            elif backend == ClipboardBackend.PBCOPY:
                result = subprocess.run(
                    ["pbcopy"],
                    input=encoded, capture_output=True, timeout=5
                )
                return (result.returncode == 0, None)

            elif backend == ClipboardBackend.POWERSHELL:
                result = subprocess.run(
                    ["powershell", "-command", f"Set-Clipboard -Value '{content}'"],
                    capture_output=True, text=True, timeout=5
                )
                return (result.returncode == 0, None)

            elif backend == ClipboardBackend.PYPERCLIP:
                import pyperclip
                pyperclip.copy(content)
                return (True, None)

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Clipboard write error: {e}")
            return (False, str(e))

        return (False, "Unknown backend")

    # =====================================================================
    # HIGH-LEVEL OPERATIONS
    # =====================================================================

    def get_content(self, strip: bool = True) -> Optional[str]:
        """
        Pobierz zawartość schowka jako string.
        
        Args:
            strip: usuń białe znaki z początku/końca
        
        Returns:
            Zawartość schowka lub None jeśli błąd
        """
        success, content = self.read()
        if not success or not content:
            return None
        return content.strip() if strip else content

    def set_content(self, text: str) -> bool:
        """
        Ustaw zawartość schowka.
        
        Returns:
            True jeśli sukces
        """
        success, _ = self.write(text)
        return success

    def append_content(self, text: str, separator: str = "\n\n") -> bool:
        """
        Dodaj tekst do istniejącej zawartości schowka.
        
        Returns:
            True jeśli sukces
        """
        current = self.get_content()
        if current:
            new_content = current + separator + text
        else:
            new_content = text
        return self.set_content(new_content)

    def is_available(self) -> bool:
        """Czy schowek jest dostępny?"""
        return self.detect_backend() != ClipboardBackend.NONE

    def get_status(self) -> Dict:
        """
        Zwróć status schowka i środowiska.
        
        Returns:
            {"available": bool, "backend": str, "environment": Dict}
        """
        backend = self.detect_backend()
        backends = self.get_available_backends()

        # Sprawdź czy można odczytać schowek
        can_read = False
        content_preview = None

        if backend != ClipboardBackend.NONE:
            success, content = self.read()
            can_read = success
            if success and content:
                preview_len = 80
                content_preview = content[:preview_len] + ("..." if len(content) > preview_len else "")

        return {
            "available": backend != ClipboardBackend.NONE,
            "backend": backend.value,
            "can_read": can_read,
            "content_preview": content_preview,
            "environment": {
                "wayland": backends.get("wayland", False),
                "x11": backends.get("x11", False),
                "platform": backends.get("platform"),
            },
            "available_tools": {k: v for k, v in backends.items() if k not in ("wayland", "x11", "platform")}
        }

    # =====================================================================
    # SMART OPERATIONS (dla AI agenta)
    # =====================================================================

    def prepare_for_explain(self) -> Dict:
        """
        Przygotuj zawartość schowka do wyjaśnienia przez AI.
        
        Wykrywa typ zawartości (kod, błąd, tekst) i formatuje do promptu.
        
        Returns:
            {
                "success": bool,
                "content": str,
                "detected_type": str,  # "code", "error", "text", "empty"
                "language": Optional[str],
                "prompt_hint": str,
                "length": int
            }
        """
        content = self.get_content()

        if not content:
            return {
                "success": False,
                "content": "",
                "detected_type": "empty",
                "language": None,
                "prompt_hint": "",
                "length": 0,
                "error": "Schowek jest pusty"
            }

        content_type, language = self._detect_content_type(content)

        prompt_hints = {
            "code": f"Wyjaśnij co robi ten kod{f' ({language})' if language else ''}:",
            "error": "Wyjaśnij ten błąd i zaproponuj rozwiązanie:",
            "traceback": "Zanalizuj ten traceback i wskaż przyczynę błędu:",
            "text": "Wyjaśnij poniższy tekst:",
            "url": "Co to za adres URL? Co można o nim powiedzieć?",
            "json": "Wyjaśnij strukturę tego JSONa:",
            "command": "Wyjaśnij co robi ta komenda:",
        }

        return {
            "success": True,
            "content": content,
            "detected_type": content_type,
            "language": language,
            "prompt_hint": prompt_hints.get(content_type, "Wyjaśnij:"),
            "length": len(content)
        }

    def prepare_for_fix(self) -> Dict:
        """
        Przygotuj zawartość schowka do naprawy przez AI.
        
        Returns:
            {
                "success": bool,
                "content": str,
                "detected_type": str,
                "fix_prompt": str
            }
        """
        content = self.get_content()

        if not content:
            return {
                "success": False,
                "content": "",
                "detected_type": "empty",
                "fix_prompt": "",
                "error": "Schowek jest pusty"
            }

        content_type, language = self._detect_content_type(content)

        fix_prompts = {
            "code": f"Znajdź i napraw błędy w tym kodzie{f' ({language})' if language else ''}:",
            "error": "Zaproponuj fix dla tego błędu:",
            "traceback": "Zaproponuj fix dla tego tracebacku:",
            "text": "Popraw błędy w tym tekście:",
            "command": "Napraw tę komendę:",
        }

        return {
            "success": True,
            "content": content,
            "detected_type": content_type,
            "fix_prompt": fix_prompts.get(content_type, "Napraw:"),
            "language": language
        }

    def copy_output(self, text: str, notify: bool = True) -> Dict:
        """
        Skopiuj output do schowka.
        
        Args:
            text: tekst do skopiowania
            notify: czy powiadomić o sukcesie
        
        Returns:
            {"success": bool, "message": str, "length": int}
        """
        success = self.set_content(text)

        if success:
            return {
                "success": True,
                "message": f"✓ Skopiowano {len(text)} znaków do schowka",
                "length": len(text)
            }
        else:
            return {
                "success": False,
                "message": "✗ Nie udało się skopiować do schowka",
                "length": 0
            }

    # =====================================================================
    # CONTENT DETECTION
    # =====================================================================

    def _detect_content_type(self, content: str) -> Tuple[str, Optional[str]]:
        """
        Wykryj typ zawartości schowka.
        
        Returns:
            (type: str, language: Optional[str])
        """
        stripped = content.strip()

        if not stripped:
            return ("empty", None)

        # Traceback / Error
        if any(marker in stripped for marker in [
            "Traceback (most recent call last)",
            "Error:", "Exception:", "WARNING:", "CRITICAL:",
            "at line", "SyntaxError", "TypeError", "ValueError",
            "RuntimeError", "NameError", "AttributeError"
        ]):
            return ("traceback" if "Traceback" in stripped else "error", None)

        # URL
        if stripped.startswith(("http://", "https://", "ftp://")) and "\n" not in stripped:
            return ("url", None)

        # JSON
        if (stripped.startswith("{") and stripped.endswith("}")) or \
           (stripped.startswith("[") and stripped.endswith("]")):
            try:
                import json
                json.loads(stripped)
                return ("json", None)
            except Exception:
                pass

        # Shell command (single line, starts with common commands)
        if "\n" not in stripped:
            shell_starters = [
                "sudo", "apt", "pip", "npm", "git", "docker",
                "ls", "cd", "cp", "mv", "rm", "mkdir", "cat",
                "grep", "find", "curl", "wget", "python", "python3",
                "./", "../", "bash", "sh", "zsh"
            ]
            first_word = stripped.split()[0] if stripped.split() else ""
            if any(stripped.startswith(s) for s in shell_starters):
                return ("command", "bash")

        # Wykryj język programowania
        language = self._detect_language(stripped)
        if language:
            return ("code", language)

        return ("text", None)

    def _detect_language(self, content: str) -> Optional[str]:
        """
        Wykryj język programowania z zawartości.
        
        Returns:
            Nazwa języka lub None
        """
        # Python
        python_signals = [
            "def ", "import ", "from ", "class ", "if __name__",
            "print(", "return ", "elif ", "except:", "lambda ",
            "self.", "async def", "await ", "@"
        ]
        python_score = sum(1 for sig in python_signals if sig in content)

        # JavaScript/TypeScript
        js_signals = [
            "const ", "let ", "var ", "function ", "=>",
            "console.log", "require(", "module.exports",
            "async/await", "Promise", "import {", "export default",
            "useState", "useEffect"
        ]
        js_score = sum(1 for sig in js_signals if sig in content)

        # TypeScript specific
        ts_signals = [": string", ": number", ": boolean", "interface ", "type ", "<T>", "readonly "]
        ts_score = sum(1 for sig in ts_signals if sig in content)

        # HTML
        html_signals = ["<html", "<div", "<p>", "<head>", "<body", "<!DOCTYPE", "</"]
        html_score = sum(1 for sig in html_signals if sig in content)

        # CSS
        css_signals = ["{", "}", ":", ";", "px", "em", "rem", ".class", "#id", "@media"]
        css_score = 0
        if "{" in content and "}" in content and ":" in content:
            css_score = sum(1 for sig in css_signals if sig in content)
            # Odejmij jeśli jest za dużo Python sygnałów
            if python_score > 3:
                css_score = 0

        # SQL
        sql_signals = ["SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE", "JOIN", "GROUP BY", "ORDER BY"]
        sql_score = sum(1 for sig in sql_signals if sig.lower() in content.lower())

        # Bash
        bash_signals = ["#!/bin/bash", "#!/bin/sh", "echo ", "export ", "source ", "$", "&&", "||", "fi\n", "done\n"]
        bash_score = sum(1 for sig in bash_signals if sig in content)

        scores = {
            "python": python_score,
            "typescript": ts_score + js_score if ts_score > 1 else 0,
            "javascript": js_score,
            "html": html_score,
            "css": css_score,
            "sql": sql_score,
            "bash": bash_score
        }

        best = max(scores, key=lambda k: scores[k])
        if scores[best] >= 2:
            return best

        return None

    def format_status_report(self) -> str:
        """Sformatuj raport statusu schowka"""
        status = self.get_status()
        lines = []

        if status["available"]:
            lines.append(f"✓ Schowek dostępny (backend: {status['backend']})")
        else:
            lines.append("✗ Schowek niedostępny")
            lines.append("  Zainstaluj: sudo apt install xclip")
            return "\n".join(lines)

        env = status["environment"]
        if env.get("wayland"):
            lines.append("  Środowisko: Wayland")
        elif env.get("x11"):
            lines.append("  Środowisko: X11")
        else:
            lines.append(f"  Platforma: {env.get('platform', 'unknown')}")

        if status["content_preview"]:
            lines.append(f"\nZawartość schowka:")
            lines.append(f"  {status['content_preview']}")

        tools = status["available_tools"]
        available = [k for k, v in tools.items() if v]
        if available:
            lines.append(f"\nDostępne narzędzia: {', '.join(available)}")

        return "\n".join(lines)


# =====================================================================
# MODULE-LEVEL SINGLETON
# =====================================================================

_default_clipboard = None


def get_clipboard(logger=None) -> ClipboardManager:
    """Zwróć globalną instancję ClipboardManager"""
    global _default_clipboard
    if _default_clipboard is None:
        _default_clipboard = ClipboardManager(logger=logger)
    return _default_clipboard