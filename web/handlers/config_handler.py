"""
handlers/config_handler.py – obsługa konfiguracji, statusu, modeli i logów.
"""
import json
import re
from datetime import datetime
from pathlib import Path

from .base import (
    CONFIG_DIR, CONFIG_FILE, PROMPT_FILE, PROMPT_WEB_FILE,
    LOGS_DIR, LOG_FILE, REQUESTS_AVAILABLE,
    JsonMixin,
)

try:
    import requests
except ImportError:
    requests = None


class ConfigHandlerMixin(JsonMixin):

    # ── Config ────────────────────────────────────────────────────────────────

    def load_config(self) -> dict:
        if not CONFIG_FILE.exists():
            return self.get_default_config()
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return self.get_default_config()

    def get_default_config(self) -> dict:
        return {
            "nick": "user",
            "ollama_host": "127.0.0.1",
            "ollama_port": 11434,
            "chat_model": "qwen3-coder:480b-cloud",
            "embed_model": "nomic-embed-text-v2-moe:latest",
            "behavior": {}, "semantic": {}, "ui": {},
            "execution": {}, "project": {}, "debug": {},
        }

    def deep_merge(self, base: dict, override: dict) -> dict:
        result = base.copy()
        for key, val in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = self.deep_merge(result[key], val)
            else:
                result[key] = val
        return result

    def api_get_config(self):
        try:
            self.send_json_response({"config": self.load_config()})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def api_save_config(self, data: dict):
        try:
            config = data.get("config", {})
            if not isinstance(config, dict):
                self.send_json_response({"error": "Config must be object"}, 400)
                return
            required = ["nick", "ollama_host", "ollama_port", "chat_model", "embed_model"]
            missing  = [k for k in required if not config.get(k)]
            if missing:
                self.send_json_response({"error": f"Brak pól: {', '.join(missing)}"}, 400)
                return
            try:
                config["ollama_port"] = int(config["ollama_port"])
            except (ValueError, TypeError):
                self.send_json_response({"error": "ollama_port musi być liczbą"}, 400)
                return
            merged = self.deep_merge(self.get_default_config(), config)
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
            self.send_json_response({"success": True})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    # ── Prompt ────────────────────────────────────────────────────────────────

    def api_get_prompt(self):
        try:
            mode = self._load_prompt_mode()

            cli_content = ""
            if PROMPT_FILE.exists():
                raw = PROMPT_FILE.read_text(encoding="utf-8")
                lines = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith("#")]
                cli_content = "\n".join(lines)

            web_content = ""
            if PROMPT_WEB_FILE.exists():
                web_content = PROMPT_WEB_FILE.read_text(encoding="utf-8")

            content = web_content if mode == "web" else cli_content

            self.send_json_response({
                "mode":        mode,
                "content":     content,
                "cli_content": cli_content,
                "web_content": web_content,
                "exists":      PROMPT_FILE.exists(),
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def _load_prompt_mode(self) -> str:
        try:
            mode = self.load_config().get("web_prompt_mode")
            if mode in ("cli", "web", "disabled"):
                return mode
            return "disabled"  # stara instalacja bez klucza = disabled
        except Exception:
            return "disabled"

    def api_save_prompt(self, data: dict):
        try:
            mode    = data.get("mode", "cli")
            content = data.get("content", "")

            if mode not in ("cli", "web", "disabled"):
                self.send_json_response({"error": "Nieprawidłowy tryb promptu"}, 400)
                return

            CONFIG_DIR.mkdir(parents=True, exist_ok=True)

            cfg = self.load_config()
            cfg["web_prompt_mode"] = mode
            CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

            if mode == "web":
                if content:
                    PROMPT_WEB_FILE.write_text(content, encoding="utf-8")
                elif PROMPT_WEB_FILE.exists():
                    PROMPT_WEB_FILE.unlink()

            self.send_json_response({"success": True})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    # ── Status ────────────────────────────────────────────────────────────────

    def api_status(self):
        try:
            config          = self.load_config()
            ollama_ok       = self.check_ollama(config) if REQUESTS_AVAILABLE else False
            self.send_json_response({
                "version":           self.get_version(),
                "mode":              "project",
                "chat_model":        config.get("chat_model", "unknown"),
                "embed_model":       config.get("embed_model", "unknown"),
                "ollama_host":       config.get("ollama_host", "127.0.0.1"),
                "ollama_port":       config.get("ollama_port", 11434),
                "ollama_available":  ollama_ok,
                "capabilities":      self.load_capabilities(),
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def check_ollama(self, config: dict) -> bool:
        if not REQUESTS_AVAILABLE:
            return False
        try:
            host = config.get("ollama_host", "127.0.0.1")
            port = config.get("ollama_port", 11434)
            r = requests.get(f"http://{host}:{port}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def load_capabilities(self) -> dict:
        ctx = Path.cwd() / ".ai-context.json"
        if not ctx.exists():
            return {"allow_execute": True, "allow_delete": True,
                    "allow_git": False, "allow_network": False}
        try:
            return json.loads(ctx.read_text(encoding="utf-8")).get("capabilities", {})
        except Exception:
            return {}

    def get_version(self) -> str:
        try:
            main = Path.home() / ".local" / "share" / "ai-cli-agent" / "main.py"
            if main.exists():
                m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', main.read_text())
                if m:
                    return m.group(1)
        except Exception:
            pass
        return "unknown"

    # ── Modele ────────────────────────────────────────────────────────────────

    def api_get_models(self):
        try:
            config = self.load_config()
            if not REQUESTS_AVAILABLE:
                self.send_json_response({"models": [], "error": "requests not available"})
                return
            host = config.get("ollama_host", "127.0.0.1")
            port = config.get("ollama_port", 11434)
            r    = requests.get(f"http://{host}:{port}/api/tags", timeout=4)
            r.raise_for_status()
            models = [{"name": m["name"], "size": m.get("size", 0)}
                      for m in r.json().get("models", [])]
            self.send_json_response({"models": models})
        except Exception as e:
            self.send_json_response({"models": [], "error": str(e)})

    # ── Logi ──────────────────────────────────────────────────────────────────

    def api_get_logs(self):
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            if not LOG_FILE.exists():
                self.send_json_response({"logs": "(brak logów)"})
                return
            lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
            # Ostatnie 300 linii
            self.send_json_response({"logs": "\n".join(lines[-300:])})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def api_clear_logs(self):
        try:
            if LOG_FILE.exists():
                LOG_FILE.unlink()
            self.send_json_response({"success": True})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)
