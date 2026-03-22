"""
agent_global.py – obsługa trybu globalnego (bez aktywnego projektu).

Wydzielony z agent.py (refaktoryzacja: agent.py > 2000 linii).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from core.agent import AIAgent


class AgentGlobalMixin:
    """Mixin obsługujący tryb globalny (global_mode=True)."""

    def _run_global_mode(self: "AIAgent", user_input: str):
        from tasks.web_search import WebSearchError, RateLimitError
        from utils.template_manager import apply_template

        self.conversation.add_user_message(user_input)
        rag_context = self._get_rag_context(user_input)

        _img_exts = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tiff')
        _has_image = any(ext in user_input.lower() for ext in _img_exts)
        _image_paths = self._extract_image_paths(user_input) if _has_image else []

        web_search_context = ""
        if self.config.get("web_search", {}).get("enabled", False):
            if self.config.get("web_search", {}).get("auto_trigger", True):
                engine = self.web_search_engine
                if engine.detect_trigger(user_input):
                    self.ui.verbose("🌐 Wykryto frazę wyszukiwania – szukam...")
                    try:
                        results = engine.search(user_input, max_results=5)
                        if results:
                            web_search_context = (
                                "\n\n=== WYNIKI WYSZUKIWANIA ===\n"
                                + engine.format_results_for_prompt(results)
                                + "\n=== KONIEC WYNIKÓW ===\n"
                            )
                    except (WebSearchError, RateLimitError) as e:
                        self.ui.verbose(f"⚠ Web search: {e}")
                    except Exception:
                        pass

        conversation_context = self.conversation.format_context_for_prompt()
        messages = [
            {"role": "system", "content": self._build_system_prompt(user_input) + conversation_context + web_search_context + rag_context},
            {"role": "user", "content": user_input + self._json_reminder()}
        ]

        for iteration in range(5):
            self.ui.spinner_start("Myślę...")
            try:
                raw = self.client.chat(messages, user_input=user_input, has_image=_has_image, image_paths=_image_paths)
            except Exception as e:
                self.ui.spinner_stop()
                self.ui.error(f"Błąd: {e}")
                return
            finally:
                self.ui.spinner_stop()

            if not raw or not raw.strip():
                self.ui.error("Model zwrócił pustą odpowiedź")
                return

            try:
                data = self._extract_json_or_wrap(raw)
            except Exception as e:
                self.ui.error(f"Błąd parsowania odpowiedzi: {e}")
                return

            if data.get("message") and not data.get("actions"):
                _file_injected = self._inject_existing_file_if_needed(user_input, data["message"], messages)
                if _file_injected:
                    messages.append({"role": "assistant", "content": raw})
                    continue

                rescued = self._rescue_code_from_message(data["message"])
                if rescued:
                    data = rescued
                else:
                    self.ui.ai_message(data["message"])
                    self.conversation.add_ai_message(data["message"])
                    mem_cfg = self.config.get("memory", {})
                    if mem_cfg.get("auto_extract", True):
                        saved = self.global_memory.auto_extract_and_save(user_input, data["message"])
                        if mem_cfg.get("show_saved", True):
                            for f in saved:
                                self.ui.success(f"💾 Zapamiętano [{f['id']}]: {f['content']}")
                    return

            actions = data.get("actions", [])
            if not actions:
                if not data.get("message"):
                    self.ui.warning("Model nie zwrócił odpowiedzi")
                    if self.logger:
                        self.logger.log_model_response(user_input, raw, parsed=data)
                return

            GLOBAL_ALLOWED = {
                "run_command", "list_files", "read_file",
                "create_file", "edit_file", "patch_file", "mkdir",
                "delete_file", "move_file",
                "web_search", "web_scrape",
                "clipboard_read", "clipboard_write",
                "open_path", "use_template"
            }

            action_results = []
            messages.append({"role": "assistant", "content": raw})

            for action in actions:
                t = action.get("type", "")
                if t not in GLOBAL_ALLOWED:
                    result = f"[INFO] Akcja '{t}' niedostępna w trybie global (brak projektu)"
                    self.ui.verbose(result)
                    action_results.append(result)
                    continue

                desc = self._describe_action(action)
                self.ui.status(f"→ {desc}")

                if t == "run_command":
                    result = self._global_run_command(action)
                    action_results.append(result)
                elif t in ("web_search", "web_scrape"):
                    result = self._execute_global_web_action(action)
                    action_results.append(result)
                    self._print_web_result(result, action)
                elif t in ("create_file", "edit_file"):
                    result = self._global_write_file(action, t)
                    action_results.append(result)
                elif t == "mkdir":
                    result = self._global_mkdir(action)
                    action_results.append(result)
                elif t == "delete_file":
                    result = self._global_delete_file(action)
                    action_results.append(result)
                elif t == "move_file":
                    result = self._global_move_file(action)
                    action_results.append(result)
                elif t == "list_files":
                    result = self._global_list_files(action)
                    action_results.append(result)
                elif t == "read_file":
                    result = self._global_read_file(action)
                    action_results.append(result)
                elif t == "patch_file":
                    result = self._global_patch_file(action)
                    action_results.append(result)
                elif t in ("clipboard_read", "clipboard_write"):
                    result = self.execute_action(action)
                    action_results.append(result)
                elif t == "open_path":
                    path = action.get("path", "")
                    try:
                        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        action_results.append(f"Otworzono {path}")
                    except Exception as e:
                        action_results.append(f"[BŁĄD] {e}")
                elif t == "use_template":
                    result = self._global_use_template(action, apply_template)
                    action_results.append(result)
                else:
                    action_results.append(f"[INFO] Nieznana akcja: {t}")

            messages.append({
                "role": "user",
                "content": json.dumps(action_results, ensure_ascii=False)
            })

        self.ui.verbose("(max iteracji osiągnięto)")

    # ── Akcje globalne ─────────────────────────────────────────────────────────

    def _global_run_command(self: "AIAgent", action: dict) -> dict | str:
        command = action.get("command", "")
        if not command:
            return "[BŁĄD] run_command bez command"
        if self.ui and self.ui.spinner_active:
            self.ui.spinner_stop()
        try:
            timeout = self.config.get('execution', {}).get('timeout_seconds', 30)
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            output = result.stdout.strip()
            stderr = result.stderr.strip()
            if output:
                print(output)
            return {
                "type": "command_result",
                "command": command,
                "exit_code": result.returncode,
                "stdout": output[:2000],
                "stderr": stderr[:500] if stderr else ""
            }
        except Exception as e:
            return f"[BŁĄD] {e}"

    def _global_write_file(self: "AIAgent", action: dict, t: str) -> str:
        raw_path = action.get("path", "")
        if not raw_path:
            return f"[BŁĄD] {t} bez path"
        file_path = Path(raw_path).expanduser()
        if not file_path.is_absolute():
            return f"[BŁĄD] W trybie globalnym podaj ścieżkę absolutną: {raw_path}"
        content_str = action.get("content", "")
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content_str, encoding="utf-8")
            verb = "Zaktualizowano" if (t == "edit_file" and file_path.exists()) else "Utworzono"
            msg = f"{verb}: {file_path}"
            print(f"  ✓ {msg}")
            if self.logger:
                self.logger.info(f"[global] {t}: {file_path}")
            return msg
        except Exception as e:
            return f"[BŁĄD] {t} {file_path}: {e}"

    def _global_mkdir(self: "AIAgent", action: dict) -> str:
        raw_path = action.get("path", "")
        dir_path = Path(raw_path).expanduser()
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            msg = f"Utworzono katalog: {dir_path}"
            print(f"  ✓ {msg}")
            return msg
        except Exception as e:
            return f"[BŁĄD] mkdir {dir_path}: {e}"

    def _global_delete_file(self: "AIAgent", action: dict) -> str:
        raw_path = action.get("path", "")
        file_path = Path(raw_path).expanduser()
        if not file_path.is_absolute():
            return f"[BŁĄD] delete_file wymaga ścieżki absolutnej: {raw_path}"
        try:
            if file_path.exists():
                file_path.unlink()
                msg = f"Usunięto: {file_path}"
            else:
                msg = f"[BŁĄD] Plik nie istnieje: {file_path}"
            print(f"  ✓ {msg}")
            return msg
        except Exception as e:
            return f"[BŁĄD] delete_file {file_path}: {e}"

    def _global_move_file(self: "AIAgent", action: dict) -> str:
        src = Path(action.get("from", "")).expanduser()
        dst = Path(action.get("to", "")).expanduser()
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            msg = f"Przeniesiono: {src} → {dst}"
            print(f"  ✓ {msg}")
            return msg
        except Exception as e:
            return f"[BŁĄD] move_file {src} → {dst}: {e}"

    def _global_list_files(self: "AIAgent", action: dict) -> dict | str:
        import glob
        pattern = action.get("pattern", "*")
        recursive = action.get("recursive", False)
        pattern_expanded = str(Path(pattern).expanduser())
        try:
            files = glob.glob(pattern_expanded, recursive=recursive)
            for f in sorted(files)[:50]:
                print(f"  {f}")
            return {"type": "file_list", "pattern": pattern, "files": files[:50]}
        except Exception as e:
            return f"[BŁĄD] list_files: {e}"

    def _global_read_file(self: "AIAgent", action: dict) -> dict | str:
        path = Path(action.get("path", "")).expanduser()
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return {"type": "file_content", "path": str(path), "content": content[:3000]}
        except Exception as e:
            return f"[BŁĄD] read_file {path}: {e}"

    def _global_patch_file(self: "AIAgent", action: dict) -> str:
        from utils.search_replace import SearchReplacePatcher, SearchReplaceParser

        raw_path = action.get("path", "")
        if not raw_path:
            return "[BŁĄD] patch_file bez pola 'path'"
        file_path = Path(raw_path).expanduser()
        if not file_path.is_absolute():
            return f"[BŁĄD] W trybie globalnym podaj ścieżkę absolutną: {raw_path}"
        patches = action.get("patches")
        diff_text = action.get("diff", "")
        if not patches and not diff_text:
            return "[BŁĄD] patch_file wymaga pola 'patches' lub 'diff'"
        try:
            original = file_path.read_text(encoding="utf-8")
            blocks = SearchReplaceParser.from_patches_list(patches) if patches is not None else SearchReplaceParser.parse(diff_text)
            new_content = original
            errors = []
            for block in blocks:
                if block.search in new_content:
                    new_content = new_content.replace(block.search, block.replace, 1)
                else:
                    errors.append(f"Nie znaleziono fragmentu: {block.search[:60]!r}")
            if errors:
                return "\n".join(f"[BŁĄD] patch_file: {err}" for err in errors)
            file_path.write_text(new_content, encoding="utf-8")
            msg = f"Zaktualizowano: {file_path}"
            print(f"  ✓ {msg}")
            return msg
        except Exception as e:
            return f"[BŁĄD] patch_file {file_path}: {e}"

    def _global_use_template(self: "AIAgent", action: dict, apply_template) -> dict | str:
        template_name = action.get("template", "")
        dest = action.get("dest", ".")
        dest_path = Path(dest).expanduser().resolve()
        variables = dict(action.get("variables", {}))
        variables.setdefault("AUTHOR", self.config.get("nick", "user"))
        try:
            result = apply_template(template_name, dest_path, variables, overwrite=action.get("overwrite", False))
        except (UnicodeDecodeError, UnicodeEncodeError):
            result = {"success": True, "created": [], "skipped": [], "error": None}
        if result["success"]:
            summary = f"Szablon '{template_name}' zastosowany w {dest_path} ({len(result['created'])} plików)"
            print(f"  ✓ {summary}")
            return {"type": "template_applied", **result}
        return f"[BŁĄD] use_template: {result['error']}"

    def _print_web_result(self: "AIAgent", result: dict | str, action: dict):
        """Wyświetl wyniki web akcji w trybie globalnym."""
        if not isinstance(result, dict):
            return
        rtype = result.get("type", "")
        if rtype == "web_search_results":
            for r in result.get("results", [])[:5]:
                if not isinstance(r, dict):
                    continue
                print(f"  [{r.get('domain', '')}] {r.get('title', '')}")
                if r.get('snippet'):
                    print(f"  {r['snippet'][:120]}")
                print(f"  {r.get('url', '')}\n")
        elif rtype == "web_scrape_result":
            title = result.get("title", "")
            success = result.get("success", False)
            md_len = len(result.get("markdown", ""))
            if success:
                self.ui.verbose(f"  ✓ Pobrano: {title or action.get('url', '')} ({md_len} znaków)")
            else:
                self.ui.warning(f"  ✗ Scraping nieudany: {action.get('url', '')}")
        elif rtype == "web_scrape_blocked":
            domain = result.get("domain", action.get("url", ""))
            self.ui.warning(f"  ✗ Domena zablokowana: {domain}\n    Dodaj: ai web-search domains add {domain}")
        elif rtype == "web_search_disabled":
            self.ui.warning("  ✗ Web search wyłączony. Włącz: ai web-search enable")
        elif rtype == "web_search_missing_deps":
            self.ui.warning(f"  ✗ Brak zależności: {', '.join(result.get('missing', []))}")

    def _execute_global_web_action(self: "AIAgent", action: dict) -> dict:
        from tasks.web_search import WebSearchError, RateLimitError

        t = action.get("type")
        engine = self.web_search_engine

        if t == "web_search":
            query = action.get("query", "")
            if not engine.is_enabled:
                return {"type": "web_search_disabled", "message": "Web search wyłączony. Włącz: ai web-search enable"}
            missing = engine.ensure_dependencies()
            if missing:
                return {"type": "web_search_missing_deps", "missing": missing}
            try:
                results = engine.search(query, max_results=action.get("max_results", 5))
                return {"type": "web_search_results", "query": query, "results": [r.to_dict() for r in results], "count": len(results)}
            except (WebSearchError, RateLimitError) as e:
                return {"type": "web_search_error", "message": str(e)}

        elif t == "web_scrape":
            import urllib.parse
            url = action.get("url", "")
            user_provided = action.get("user_provided_url", False)
            if not user_provided and not engine.is_domain_allowed(url):
                domain = urllib.parse.urlparse(url).netloc
                return {
                    "type": "web_scrape_blocked",
                    "domain": domain,
                    "message": f"Domena '{domain}' nie jest na whitelist. Dodaj: ai web-search domains add {domain}"
                }
            sr = engine.scrape(url)
            return {"type": "web_scrape_result", "url": url, "title": sr.title, "markdown": sr.markdown[:3000], "success": sr.success}

        return {"type": "error", "message": f"Nieznana akcja web: {t}"}
