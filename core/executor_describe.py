"""
executor_describe.py – metody describe_action i summarize_results.

Wydzielone z action_executor.py (refaktoryzacja: > 1100 linii).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from utils.search_replace import SearchReplaceParser
from classification.command_classifier import CommandClassifier, CommandRisk as CmdRisk
from ui_layer.ui import Colors

if TYPE_CHECKING:
    pass


    def describe_action(self, action):
        t = action["type"]
        
        if t == "create_file":
            lines = len(action.get("content", "").splitlines())
            return f"create_file: {action['path']} ({lines} linii)"
        
        if t == "edit_file":
            if "match" in action:
                return f"edit_file: {action['path']} (replace text)"
            else:
                return f"edit_file: {action['path']} (lines {action.get('line_start')}-{action.get('line_end')})"

        if t == "patch_file":
            try:
                # Obsługa obu formatów: patches (lista) lub diff (string)
                if action.get("patches"):
                    n = len(action["patches"])
                elif action.get("diff"):
                    blocks = SearchReplaceParser.parse(action["diff"])
                    n = len(blocks)
                else:
                    n = 0
            except Exception:
                n = "?"
            return f"🔧 patch_file: {action.get('path', '?')} ({n} blok(ów) SEARCH/REPLACE)"
        
        if t == "delete_file":
            return f"❌ delete_file: {action['path']}"
        
        if t == "move_file":
            return f"move_file: {action['from']} → {action['to']}"
        
        if t == "mkdir":
            return f"mkdir: {action['path']}"
        
        if t == "chmod":
            return f"chmod {action['mode']}: {action['path']}"
        
        if t == "open_path":
            return f"▶ open: {action['path']}"
        
        if t == "run_command":
            # NOWE: Pokaż poziom ryzyka
            command = action['command']
            risk, _ = CommandClassifier.classify(command)
            
            risk_emoji = {
                CmdRisk.READ_ONLY: "✓",
                CmdRisk.MODIFY: "⚠",
                CmdRisk.DESTRUCTIVE: "🔴"
            }
            
            emoji = risk_emoji.get(risk, "▶")
            return f"{emoji} run: {command}"
        
        if t == "read_file":
            return f"read: {action['path']}"
        
        if t == "semantic_search":
            return f"search: \"{action['query']}\""
        
        if t == "list_files":
            pattern = action.get('pattern', '*')
            return f"list: {pattern}"
        
        # Web Search actions
        if t == "web_search":
            return f"🌐 web-search: \"{action.get('query', '?')}\""
        
        if t == "web_scrape":
            return f"🌐 web-scrape: {action.get('url', '?')}"
        
        # NOWE: Media actions
        if t == "download_media":
            url_short = action['url'][:50] + "..." if len(action['url']) > 50 else action['url']
            convert = f" → {action.get('convert_to', '')}" if action.get('convert_to') else ""
            return f"🎬 download_media: {url_short}{convert}"
        
        if t == "convert_media":
            return f"🎵 convert: {action.get('input_path', '')} → {action.get('output_format', '')}"
        
        # Image actions
        if t == "process_image":
            op = action.get("operation", "?")
            inp = action.get("input_path", "?")
            op_emojis = {
                "convert": "🔄", "compress": "📦", "resize": "↔",
                "crop": "✂", "ico": "🖼", "favicon_set": "🌐",
                "info": "ℹ", "strip_metadata": "🧹"
            }
            emoji = op_emojis.get(op, "🖼")
            extra = ""
            if op == "convert":
                extra = f" → {action.get('output_format', '?')}"
            elif op == "resize":
                w = action.get("width", "auto")
                h = action.get("height", "auto")
                extra = f" {w}x{h}"
            elif op == "compress":
                q = action.get("quality", 80)
                extra = f" q={q}"
            return f"{emoji} {op}: {Path(inp).name}{extra}"

        if t == "batch_images":
            op = action.get("operation", "?")
            n = len(action.get("input_paths", [])) or "glob"
            fmt = action.get("output_format", "")
            fmt_str = f" → {fmt}" if fmt else ""
            return f"📦 batch {op} ({n} plików){fmt_str}"

        if t == "image_info":
            return f"ℹ image_info: {action.get('path', '?')}"

        if t == "clipboard_read":
            return "📋 clipboard: odczytaj schowek"

        if t == "clipboard_write":
            preview = action.get("content", "")[:40]
            return f"📋 clipboard: zapisz do schowka ({len(action.get('content', ''))} znaków)"
        
        return f"{t}: {action}"

    def summarize_results(self, actions, results):
        created = []
        edited = []
        deleted = []
        opened = []
        executed = []
        downloaded = []  # NOWE
        converted = []   # NOWE
        
        for action, result in zip(actions, results):
            t = action["type"]
            
            if t == "create_file" and "Utworzono" in str(result):
                created.append(action["path"])
            elif t == "edit_file" and "Zaktualizowano" in str(result):
                edited.append(action["path"])
            elif t == "delete_file" and "Usunięto" in str(result):
                deleted.append(action["path"])
            elif t == "open_path" and "Otworzono" in str(result):
                opened.append(action["path"])
            elif t == "run_command":
                executed.append(action["command"])
            # NOWE: Media operations
            elif t == "download_media" and isinstance(result, dict) and result.get("type") == "media_downloaded":
                downloaded.append(result.get("report", "Media downloaded"))
            elif t == "convert_media" and isinstance(result, dict) and result.get("success"):
                converted.append(f"{action.get('input_path', '')} → {action.get('output_format', '')}")
        
        if created:
            self.ui.success(f"✓ Utworzono {len(created)} plik(ów)")
            for f in created:
                self.ui.verbose(f"  • {f}")
        
        if edited:
            self.ui.success(f"✓ Zmodyfikowano {len(edited)} plik(ów)")
            for f in edited:
                self.ui.verbose(f"  • {f}")
        
        if deleted:
            self.ui.warning(f"✗ Usunięto {len(deleted)} plik(ów)")
            for f in deleted:
                self.ui.verbose(f"  • {f}")
        
        if opened:
            self.ui.success(f"↗ Otwarto {len(opened)} plik(ów)")
            for f in opened:
                self.ui.verbose(f"  • {f}")
        
        if executed:
            self.ui.success(f"▶ Wykonano {len(executed)} komend(ę)")
            for cmd in executed:
                self.ui.verbose(f"  • {cmd}")
        
        # NOWE: Media operations summary
        if downloaded:
            print()
            for report in downloaded:
                print(report)
        
        if converted:
            self.ui.success(f"🎵 Skonwertowano {len(converted)} plik(ów)")
            for c in converted:
                self.ui.verbose(f"  • {c}")

        images_processed = []
        batch_results = []
        clipboard_ops = []

        for action, result in zip(actions, results):
            t = action["type"]
            if t == "process_image" and isinstance(result, dict) and result.get("type") == "image_processed":
                images_processed.append(result)
            elif t == "batch_images" and isinstance(result, dict) and result.get("type") == "batch_images_done":
                batch_results.append(result)
            elif t in ("clipboard_read", "clipboard_write") and isinstance(result, dict):
                clipboard_ops.append(result)

        if images_processed:
            self.ui.success(f"🖼 Przetworzono {len(images_processed)} obraz(y)")
            for r in images_processed:
                op = r.get("operation", "")
                res = r.get("result", {})
                fp = res.get("filepath", "?")
                size_kb = res.get("size_kb", "?")
                reduction = res.get("reduction_pct")
                dims = res.get("dimensions")
                info_parts = []
                if size_kb != "?":
                    info_parts.append(f"{size_kb} KB")
                if reduction:
                    info_parts.append(f"-{reduction}%")
                if dims:
                    info_parts.append(f"{dims}")
                extra = f" ({', '.join(info_parts)})" if info_parts else ""
                self.ui.verbose(f"  • {op}: {Path(str(fp)).name}{extra}")

        if batch_results:
            for r in batch_results:
                op = r.get("operation", "batch")
                processed = r.get("processed", 0)
                failed = r.get("failed", 0)
                saved = r.get("total_saved_kb")
                msg = f"📦 Batch {op}: {processed} OK"
                if failed:
                    msg += f", {failed} błędów"
                if saved:
                    msg += f", zaoszczędzono {saved} KB"
                self.ui.success(msg)
                summary = r.get("results_summary")
                if summary:
                    print()
                    print(summary)

        if clipboard_ops:
            for r in clipboard_ops:
                if r.get("type") == "clipboard_written" and r.get("success"):
                    self.ui.success(r.get("message", "✓ Skopiowano do schowka"))
                elif r.get("type") == "clipboard_content":
                    length = r.get("length", 0)
                    lang = r.get("language", "")
                    ctype = r.get("detected_type", "text")
                    self.ui.success(f"📋 Odczytano ze schowka: {length} znaków ({ctype}{', ' + lang if lang else ''})")

        # Template results display
        for action, result in zip(actions, results):
            if action.get("type") == "use_template" and isinstance(result, dict):
                if result.get("type") == "template_applied":
                    created = result.get("created", [])
                    skipped = result.get("skipped", [])
                    tpl_name = result.get("template", "")
                    dest = result.get("dest", ".")
                    self.ui.success(f"📁 Szablon '{tpl_name}' → {dest}")
                    if created:
                        self.ui.success(f"  ✓ Utworzono {len(created)} plików")
                        for f in created:
                            self.ui.verbose(f"    • {f}")
                    if skipped:
                        self.ui.verbose(f"  ↷ Pominięto {len(skipped)} (już istnieją)")

        # Web search results display
        for action, result in zip(actions, results):
            t = action.get("type")
            if t == "web_search" and isinstance(result, dict):
                if result.get("type") == "web_search_results":
                    query = result.get("query", "")
                    count = result.get("count", 0)
                    self.ui.success(f"🌐 Wyniki web search dla: {query!r} ({count} wyników)")
                elif result.get("type") == "web_search_disabled":
                    self.ui.warning(f"🌐 {result.get('message', 'Web search wyłączony')}")
                elif result.get("type") == "web_search_rate_limit":
                    self.ui.warning(f"🌐 Rate limit: {result.get('message', '')}")
                elif result.get("type") == "web_search_error":
                    self.ui.error(f"🌐 {result.get('message', 'Błąd web search')}")
            elif t == "web_scrape" and isinstance(result, dict):
                if result.get("type") == "web_scrape_result" and result.get("success"):
                    title = result.get("title", result.get("url", ""))
                    words = result.get("word_count", 0)
                    self.ui.success(f"🌐 Pobrano stronę: {title} ({words} słów)")

    def pre_edit_reread(self, action: dict) -> str | None:
        """
        Przed edycją zawsze odczytaj aktualny plik.
        Zwraca błąd (str) lub None jeśli OK.
        """
        path = action.get("path", "")
        if not path:
            return "[BŁĄD] edit_file bez pola 'path'"

        if not self.fs:
            return "[BŁĄD] FileSystem niedostępny (tryb global)"

        try:
            content = self.fs._safe_path(path).read_text(encoding="utf-8")
            lines = content.splitlines()
            line_count = len(lines)
        except FileNotFoundError:
            return f"[BŁĄD] Plik {path} nie istnieje — użyj create_file zamiast edit_file"
        except Exception as e:
            return f"[BŁĄD] Nie można odczytać {path}: {e}"

        # Jeśli model podał line_end > rzeczywista liczba linii — napraw
        if "line_end" in action and isinstance(action["line_end"], int):
            if action["line_end"] > line_count:
                # Przytnij zamiast blokować (błąd off-by-one)
                action["line_end"] = line_count

        return None

