"""
handlers/chat_handler.py – proxy AI (Ollama), pamięć, historia konwersacji.
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path

from .base import (
    CHATS_DIR, KNOWLEDGE_DIR, MEMORY_FILE, PROMPT_FILE, PROMPT_WEB_FILE,
    SESSIONS_DIR, REQUESTS_AVAILABLE, sanitize_id,
    get_session_paths, get_workspace_tree,
    log_error,
    JsonMixin,
)

try:
    import requests
except ImportError:
    requests = None




class ChatHandlerMixin(JsonMixin):

    # ── AI chat proxy ─────────────────────────────────────────────────────────

    def api_chat(self, data: dict):
        """Proxy do Ollamy – streaming, memory, knowledge w system prompcie."""
        try:
            if not REQUESTS_AVAILABLE:
                self.send_json_response({"error": "requests nie jest zainstalowany"}, 500)
                return

            config   = self.load_config()
            host     = config.get("ollama_host", "127.0.0.1")
            port     = config.get("ollama_port", 11434)
            model    = data.get("model") or config.get("chat_model", "")
            messages = data.get("messages", [])
            session_id = data.get("session_id", "")

            if not model:
                self.send_json_response({"error": "Brak wybranego modelu"}, 400)
                return
            if not messages:
                self.send_json_response({"error": "Brak wiadomości"}, 400)
                return

            system = self._build_system_prompt(session_id)
            ollama_messages = []
            if system:
                ollama_messages.append({"role": "system", "content": system})
            for m in messages:
                if m.get("role") in ("user", "assistant"):
                    ollama_messages.append({"role": m["role"], "content": m.get("content", "")})

            reply_parts = []
            with requests.post(
                f"http://{host}:{port}/api/chat",
                json={"model": model, "messages": ollama_messages, "stream": True},
                stream=True, timeout=(10, 300),
            ) as r:
                if r.status_code != 200:
                    self.send_json_response(
                        {"error": f"Ollama error {r.status_code}: {r.text[:200]}"}, 502)
                    return
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        reply_parts.append(token)
                    if chunk.get("done"):
                        break

            reply = "".join(reply_parts)
            last_user = next((m["content"] for m in reversed(messages)
                              if m.get("role") == "user"), "")
            if last_user:
                self._auto_save_memory(last_user, reply)

            self.send_json_response({"message": reply, "model": model})

        except requests.exceptions.ConnectionError:
            log_error("chat", "Brak połączenia z Ollamą")
            self.send_json_response(
                {"error": "Brak połączenia z Ollamą. Sprawdź czy ollama serve działa."}, 503)
        except requests.exceptions.Timeout:
            log_error("chat", "Timeout – model nie odpowiedział w 300s")
            self.send_json_response(
                {"error": "Timeout – model nie odpowiedział w 300s."}, 504)
        except Exception as e:
            log_error("chat", str(e))
            self.send_json_response({"error": str(e)}, 500)

    def _build_system_prompt(self, session_id: str = "") -> str:
        parts = []
        # 1. prompt - ściśle zależnie od trybu web_prompt_mode
        #    Brak pliku config = tryb "disabled" (bezpieczny fallback - nie zasysamy nic)
        mode = self._get_prompt_mode()
        try:
            if mode == "cli":
                # Tylko prompt.txt CLI - świadomie wybrany przez użytkownika
                if PROMPT_FILE.exists():
                    pt = PROMPT_FILE.read_text(encoding="utf-8").strip()
                    if pt:
                        parts.append(pt)
            elif mode == "web":
                # Tylko prompt-web.txt - nigdy nie sięga do prompt.txt
                if PROMPT_WEB_FILE.exists():
                    pt = PROMPT_WEB_FILE.read_text(encoding="utf-8").strip()
                    if pt:
                        parts.append(pt)
            # mode == "disabled" lub cokolwiek innego = brak promptu systemowego
        except Exception:
            pass  # błąd odczytu pliku - nie dołączamy nic (fail-safe)
        # 2. memory (pamięć użytkownika - niezależna od trybu promptu)
        mem = self._load_memory_context()
        if mem:
            parts.append(mem)
        # 3. knowledge (baza wiedzy - niezależna od trybu promptu)
        know = self._load_knowledge_context()
        if know:
            parts.append(know)
        # 4. sandbox context jeśli sesja ma pliki
        if session_id:
            sb = self._load_sandbox_context(session_id)
            if sb:
                parts.append(sb)
        return "\n\n".join(parts)

    def _get_prompt_mode(self) -> str:
        """
        Wczytuje web_prompt_mode z config.json.
        Fallback: "disabled" - bezpieczny, nie zasysamy prompt.txt bez wiedzy użytkownika.
        Tryb "cli" jest tylko gdy użytkownik go świadomie wybrał w ustawieniach.
        """
        try:
            from .base import CONFIG_FILE
            import json as _j
            if CONFIG_FILE.exists():
                mode = _j.loads(CONFIG_FILE.read_text(encoding="utf-8")).get("web_prompt_mode")
                if mode in ("cli", "web", "disabled"):
                    return mode
                # Klucz nie istnieje (stara instalacja bez ustawienia) = disabled
                return "disabled"
        except Exception:
            pass
        return "disabled"

    def _load_sandbox_context(self, session_id: str) -> str:
        from .base import get_session_paths, get_workspace_tree
        paths = get_session_paths(session_id)
        ws    = paths["workspace"]
        if not ws.exists() or not any(ws.rglob("*")):
            return ""
        tree = get_workspace_tree(ws, max_depth=3)
        files = [f"  {'  ' * item['depth']}{'📁' if item['is_dir'] else '📄'} {item['name']}"
                 for item in tree[:30]]
        lines = [
            "====================",
            "SANDBOX SESJI",
            "====================",
            f"Workspace: {ws}",
            f"Uploads:   {paths['uploads']}",
            f"Outputs:   {paths['outputs']}",
            "",
            "Struktura workspace:",
        ] + files + [
            "",
            "Operuj WYŁĄCZNIE w tym katalogu. Nie wychodź poza workspace.",
            "Używaj run_command z Pythonem do operacji na plikach.",
            "Do eksportu spakuj workspace do outputs/ i podaj link /api/download/<id>/nazwa.zip",
        ]
        return "\n".join(lines)

    # ── Memory helpers ────────────────────────────────────────────────────────

    def _load_memory_data(self) -> dict:
        if not MEMORY_FILE.exists():
            return {"facts": [], "version": 1}
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"facts": [], "version": 1}

    def _save_memory_data(self, data: dict):
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_memory_context(self) -> str:
        facts = self._load_memory_data().get("facts", [])
        if not facts:
            return ""
        lines = ["====================", "PAMIĘĆ", "====================", ""]
        for f in facts:
            lines.append(f"[{f.get('category','general')}] {f.get('content','')}")
        lines += ["", "Używaj tych informacji gdy są istotne.", ""]
        return "\n".join(lines)

    def _load_knowledge_context(self) -> str:
        if not KNOWLEDGE_DIR.exists():
            return ""
        parts = []
        for ext in ("*.md", "*.txt"):
            for f in sorted(KNOWLEDGE_DIR.glob(ext)):
                if len(parts) >= 3:
                    break
                try:
                    text = f.read_text(encoding="utf-8").strip()[:1200]
                    parts.append(f"--- Wiedza: {f.name} ---\n{text}")
                except Exception:
                    pass
        return "\n\n".join(parts)

    def _auto_save_memory(self, user_input: str, _ai_response: str):
        patterns = [
            r"(?:zapamiętaj|zapamietaj|zapisz|zanotuj|remember)[,:\s]+(?:że|ze|to|that)?\s+(.+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, user_input.strip(), re.IGNORECASE)
            if m:
                fact = m.group(1).strip().rstrip(".")
                if len(fact) > 3:
                    self._memory_add(fact, "general")
                return

    def _memory_next_id(self, facts: list) -> int:
        return max((f.get("id", 0) for f in facts), default=0) + 1

    def _memory_add(self, content: str, category: str = "general") -> dict:
        data     = self._load_memory_data()
        existing = {f["content"].lower() for f in data["facts"]}
        if content.lower() in existing:
            return {}
        fact = {"id": self._memory_next_id(data["facts"]),
                "content": content.strip(), "category": category,
                "created_at": datetime.now().isoformat()}
        data["facts"].append(fact)
        self._save_memory_data(data)
        return fact

    def api_get_memory(self):
        try:
            self.send_json_response({"facts": self._load_memory_data().get("facts", [])})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def api_save_memory(self, data: dict):
        try:
            content  = data.get("content", "").strip()
            category = data.get("category", "general")
            if not content:
                self.send_json_response({"error": "Brak treści"}, 400)
                return
            fact = self._memory_add(content, category)
            if not fact:
                self.send_json_response({"success": False, "message": "Fakt już istnieje"})
            else:
                self.send_json_response({"success": True, "fact": fact})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def api_delete_memory(self, data: dict):
        try:
            fact_id = int(data.get("id", -1))
            mem     = self._load_memory_data()
            before  = len(mem["facts"])
            mem["facts"] = [f for f in mem["facts"] if f.get("id") != fact_id]
            if len(mem["facts"]) < before:
                self._save_memory_data(mem)
                self.send_json_response({"success": True})
            else:
                self.send_json_response({"success": False, "message": "Nie znaleziono"})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    # ── Chats storage ─────────────────────────────────────────────────────────

    def api_list_chats(self):
        try:
            CHATS_DIR.mkdir(parents=True, exist_ok=True)
            chats = []
            for f in sorted(CHATS_DIR.glob("*.json"),
                            key=lambda x: x.stat().st_mtime, reverse=True):
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                    chats.append({
                        "id":        d.get("id", f.stem),
                        "title":     d.get("title", ""),
                        "model":     d.get("model", ""),
                        "created":   d.get("created", 0),
                        "updated":   d.get("updated", 0),
                        "msg_count": len(d.get("messages", [])),
                        "has_sandbox": (SESSIONS_DIR / sanitize_id(d.get("id", f.stem))).exists(),
                    })
                except Exception:
                    pass
            self.send_json_response({"chats": chats})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def api_get_chat(self, chat_id: str):
        try:
            safe = sanitize_id(chat_id)
            if not safe:
                self.send_json_response({"error": "invalid id"}, 400)
                return
            f = CHATS_DIR / f"{safe}.json"
            if not f.exists():
                self.send_json_response({"error": "not found"}, 404)
                return
            self.send_json_response({"chat": json.loads(f.read_text(encoding="utf-8"))})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def api_save_chat(self, data: dict):
        try:
            CHATS_DIR.mkdir(parents=True, exist_ok=True)
            chat    = data.get("chat", data)
            chat_id = chat.get("id", "")
            safe    = sanitize_id(chat_id)
            if not safe:
                self.send_json_response({"error": "missing/invalid id"}, 400)
                return
            chat["updated"] = int(time.time() * 1000)
            chat.setdefault("created", chat["updated"])
            (CHATS_DIR / f"{safe}.json").write_text(
                json.dumps(chat, ensure_ascii=False, indent=2), encoding="utf-8")
            self.send_json_response({"success": True, "id": safe})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def api_delete_chat(self, chat_id: str):
        """Usuwa historię chatu ORAZ sandbox sesji."""
        try:
            import shutil
            safe = sanitize_id(chat_id)
            if not safe:
                self.send_json_response({"error": "invalid id"}, 400)
                return
            f = CHATS_DIR / f"{safe}.json"
            if f.exists():
                f.unlink()
            sd = SESSIONS_DIR / safe
            if sd.exists():
                shutil.rmtree(sd)
            self.send_json_response({"success": True})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)
