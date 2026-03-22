"""
ActionExecutor – wykonywanie akcji agenta (fs, shell, media, web, clipboard, images).
Wyekstrahowany z core/agent.py dla lepszej czytelności.
"""
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from utils.search_replace import SearchReplacePatcher, SearchReplaceParser
from classification.command_classifier import CommandClassifier, CommandRisk as CmdRisk

if TYPE_CHECKING:
    from core.agent import AIAgent


class ActionExecutor:
    """
    Wykonuje pojedyncze akcje zwrócone przez model LLM.
    Trzyma referencję do agenta (agent.fs, agent.ui, agent.config itp.)
    zamiast kopiować stan.
    """

    def __init__(self, agent: "AIAgent"):
        self.agent = agent

    # ── Skróty do często używanych atrybutów agenta ──────────────────────────
    @property
    def fs(self):       return self.agent.fs
    @property
    def ui(self):       return self.agent.ui
    @property
    def config(self):   return self.agent.config
    @property
    def dry_run(self):  return self.agent.dry_run
    @property
    def logger(self):   return self.agent.logger
    @property
    def memory(self):   return self.agent.memory
    @property
    def editor(self):   return self.agent.editor

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

    def execute_action(self, action):
        t = action["type"]
        
        if not self.fs:
            return f"[BŁĄD] Operacje na plikach niedostępne w trybie global"

        if t == "read_file":
            return {
                "type": "file_content",
                "path": action["path"],
                "content": self.fs.read_file(action["path"])
            }

        if t == "list_files":
            pattern = action.get("pattern", "*")
            recursive = action.get("recursive", False)
            explicit_path = action.get("path")

            # Poprawka: jeśli model podał osobne pole "path" (katalog),
            # połącz go z pattern żeby fs.list_files dostał pełną ścieżkę glob.
            # Bez tego model pisał {"path": "/home/paffcio/Pobrane", "pattern": "*.mp4"}
            # a executor ignorował path i szukał *.mp4 w cwd projektu.
            if explicit_path:
                import os as _os
                ep = str(explicit_path).rstrip("/")
                # Jeśli pattern to "*" lub nie zawiera separatora — złącz z path
                if pattern == "*" or _os.sep not in pattern:
                    pattern = ep + "/" + pattern
                # Jeśli pattern już jest ścieżką bezwzględną — zostaw jak jest
                # (model mógł podać pełny glob w pattern zamiast w path)

            # Zabezpieczenie: jeśli pattern to konkretna nazwa pliku (bez wildcard),
            # przekieruj do read_file zamiast list_files (częsty błąd modelu)
            if "*" not in pattern and "?" not in pattern and not os.path.isdir(pattern) and not os.path.isdir(
                os.path.join(str(self.fs.cwd), pattern)
            ):
                # Wygląda jak konkretny plik, nie glob pattern
                potential_path = pattern if os.path.isabs(pattern) else os.path.join(str(self.fs.cwd), pattern)
                if os.path.isfile(potential_path):
                    try:
                        content = self.fs.read_file(potential_path)
                        return {
                            "type": "file_content",
                            "path": potential_path,
                            "content": content
                        }
                    except Exception as e:
                        return f"[BŁĄD] Nie udało się odczytać pliku {potential_path}: {e}"

            try:
                files = self.fs.list_files(pattern, recursive)
                return {
                    "type": "file_list",
                    "pattern": pattern,
                    "files": files
                }
            except Exception as e:
                return f"[BŁĄD] Nie udało się wylistować plików: {e}"

        if t == "semantic_search":
            if self.config.get('debug', {}).get('log_semantic_queries', False):
                print(f"[DEBUG] semantic_search: {action['query']}")
                if self.logger:
                    self.logger.debug(f"Semantic search: {action['query']}")
            
            docs = self.fs.iter_source_files()
            ranked = self.agent.client.semantic_search(action["query"], docs)
            
            frequently_edited = []
            if self.memory:
                frequently_edited = self.memory.get_frequently_edited()
            
            if self.config.get('semantic', {}).get('prefer_frequently_edited', True):
                weighted = []
                for path in ranked:
                    score = 1.0
                    if path in frequently_edited:
                        score = 1.5
                    
                    boost_paths = self.config.get('semantic', {}).get('boost_paths', [])
                    if any(p in path for p in boost_paths):
                        score *= 1.2
                    
                    weighted.append((score, path))
                
                weighted.sort(reverse=True)
                ranked = [path for _, path in weighted]
            
            return {
                "type": "semantic_result",
                "files": ranked[:5]
            }

        if t == "create_file":
            if "content" not in action:
                return f"[BŁĄD] create_file bez content dla {action['path']}"
            
            return self.fs.create_file(action["path"], action["content"])

        if t == "edit_file":
            if not self.editor:
                return f"[BŁĄD] Editor niedostępny"

            # Zawsze re-read przed edycją (naprawia błędy line_end i brakujących plików)
            err = self.pre_edit_reread(action)
            if err:
                return err

            return self.editor.edit(
                action["path"],
                self.fs,
                action.get("match"),
                action.get("replace"),
                action.get("line_start"),
                action.get("line_end"),
                action.get("content")
            )

        if t == "patch_file":
            # Obsługuje dwa formaty:
            # - "patches": lista {"search": [...], "replace": [...]}  ← PREFEROWANY
            # - "diff": string z blokami SEARCH/REPLACE                 ← czytelny alternatywny
            path = action.get("path", "")
            if not path:
                return "[BŁĄD] patch_file bez pola 'path'"

            patches   = action.get("patches")    # Format A (lista)
            diff_text = action.get("diff", "")  # Format B (string)

            # Pustą listę traktuj jak brak danych
            if isinstance(patches, list) and len(patches) == 0:
                patches = None

            if not patches and not diff_text:
                return (
                    "[BŁĄD] patch_file wymaga pola 'patches' (lista bloków) "
                    "lub 'diff' (string z blokami SEARCH/REPLACE)\n"
                    "Przykład: {\"patches\": [{\"search\": [\"stary tekst\"], \"replace\": [\"nowy tekst\"]}]}"
                )

            dry_run = action.get("dry_run", self.dry_run)

            result = SearchReplacePatcher.apply_to_file(
                path=path,
                diff_text=diff_text if diff_text else None,
                patches=patches,
                fs=self.fs,
                dry_run=dry_run
            )
            formatted = SearchReplacePatcher.format_result(result)

            if result.success:
                return formatted
            else:
                return f"[BŁĄD] {formatted}"

        if t == "mkdir":
            return self.fs.mkdir(action["path"])

        if t == "chmod":
            return self.fs.chmod(action["path"], action["mode"])

        if t == "delete_file":
            return self.fs.delete_file(action["path"])

        if t == "move_file":
            return self.fs.move_file(action["from"], action["to"])

        if t == "open_path":
            path = action["path"]
            try:
                subprocess.Popen(
                    ["xdg-open", path], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
                return f"Otworzono {path}"
            except Exception as e:
                return f"[BŁĄD] Nie udało się otworzyć {path}: {e}"
        
        if t == "run_command":
            command = action["command"]

            # =========================
            # BEZPIECZNIK DESTRUKCYJNY
            # =========================
            is_safe, error = self.agent._validate_destructive_context(command)

            if not is_safe:
                if self.logger:
                    self.logger.error(
                        f"Blocked destructive command: {command}, reason: {error}"
                    )

                return {
                    "type": "blocked_destructive",
                    "reason": error,
                    "command": command
                }

            # =========================
            # KLASYFIKACJA KOMENDY
            # =========================
            risk, risk_reason = CommandClassifier.classify(command)

            if self.logger:
                self.logger.debug(
                    f"Command classified: {command} -> {risk.value} ({risk_reason})"
                )

            # =========================
            # BLOKADA PO WCZEŚNIEJSZYM BŁĘDZIE
            # =========================
            if self.agent.execution_failed:
                if self.logger:
                    self.logger.warning(
                        f"Blocked run_command due to previous failure: {command}"
                    )

                return {
                    "type": "blocked",
                    "reason": (
                        "Poprzednia komenda zakończyła się błędem. "
                        "Nie wykonuję kolejnych bez decyzji użytkownika."
                    ),
                    "last_failed": self.agent.last_failed_command,
                    "blocked_command": command
                }

            # =========================
            # DRY-RUN
            # =========================
            if self.dry_run:
                return {
                    "type": "dry_run",
                    "command": command,
                    "risk": risk.value
                }

            timeout = self.config.get('execution', {}).get('timeout_seconds', 30)

            # =========================
            # ZATRZYMAJ SPINNER (sudo/tty)
            # =========================
            if self.ui and self.ui.spinner_active:
                self.ui.spinner_stop()

            # =========================
            # WYKONANIE KOMENDY
            # =========================
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

                # Limit wyjścia — konfigurowalne (domyślnie 4000).
                # 500 ucinało wyniki find/snap/df, model dostawał niekompletne dane.
                _out_limit = self.config.get("execution", {}).get("command_output_limit", 4000)
                _stdout = result.stdout
                _stderr = result.stderr
                output = {
                    "type": "command_result",
                    "command": command,
                    "returncode": result.returncode,
                    "stdout": _stdout[:_out_limit] + (" …[ucięto]") * (len(_stdout) > _out_limit),
                    "stderr": _stderr[:_out_limit] + (" …[ucięto]") * (len(_stderr) > _out_limit),
                    "risk": risk.value,
                    "risk_reason": risk_reason
                }

                # =========================
                # BŁĄD WYKONANIA
                # =========================
                if result.returncode != 0:
                    self.agent.execution_failed = True
                    self.agent.last_failed_command = command

                    if self.logger:
                        self.logger.warning(
                            f"Command failed (exit {result.returncode}): {command}"
                        )

                return output

            except subprocess.TimeoutExpired:
                if self.logger:
                    self.logger.warning(f"Command timeout: {command}")

                return {
                    "type": "command_timeout",
                    "command": command,
                    "timeout_seconds": timeout,
                    "risk": risk.value,
                    "message": (
                        f"Komenda przekroczyła limit czasu ({timeout}s). "
                        "Stan systemu może być nieznany."
                    )
                }

            except Exception as e:
                self.agent.execution_failed = True
                self.agent.last_failed_command = command

                if self.logger:
                    self.logger.error(
                        f"Command execution error: {command}, {e}",
                        exc_info=True
                    )

                return {
                    "type": "command_error",
                    "command": command,
                    "error": str(e)
                }

        
        # ===== NOWE: MEDIA PIPELINE ACTIONS =====
        
        if t == "download_media":
            try:
                pipeline = self.agent.media_pipeline
                
                # Check/ensure yt-dlp
                yt_status, yt_version = pipeline.check_tool("yt-dlp")
                if yt_status not in [ToolStatus.AVAILABLE, ToolStatus.OUTDATED]:
                    self.ui.verbose("yt-dlp nie jest dostępne, instaluję...")
                    ensure_result = pipeline.ensure_tool("yt-dlp")
                    
                    if not ensure_result["success"]:
                        return {
                            "type": "error",
                            "error": f"Nie udało się zainstalować yt-dlp: {ensure_result['message']}"
                        }
                    
                    self.ui.success(f"✓ {ensure_result['message']}")
                
                # Download
                download_result = pipeline.download_media(
                    url=action["url"],
                    output_format=action.get("format", "best"),
                    audio_only=action.get("audio_only", False)
                )
                
                if not download_result["success"]:
                    return {
                        "type": "error",
                        "error": download_result.get("error", "Download failed")
                    }
                
                # Convert if requested
                convert_result = None
                final_path = download_result["filepath"]
                
                if action.get("convert_to"):
                    # Check/ensure ffmpeg
                    ffmpeg_status, _ = pipeline.check_tool("ffmpeg")
                    if ffmpeg_status not in [ToolStatus.AVAILABLE, ToolStatus.OUTDATED]:
                        self.ui.verbose("ffmpeg nie jest dostępne, instaluję...")
                        ensure_result = pipeline.ensure_tool("ffmpeg")
                        
                        if not ensure_result["success"]:
                            return {
                                "type": "error",
                                "error": f"Nie udało się zainstalować ffmpeg: {ensure_result['message']}"
                            }
                        
                        self.ui.success(f"✓ {ensure_result['message']}")
                    
                    # Convert
                    convert_result = pipeline.convert_to_audio(
                        video_path=download_result["filepath"],
                        audio_format=action.get("convert_to"),
                        bitrate=action.get("bitrate", "192k")
                    )
                    
                    if not convert_result["success"]:
                        return {
                            "type": "error",
                            "error": convert_result.get("error", "Conversion failed")
                        }
                    
                    # Cleanup original
                    pipeline.cleanup([download_result["filepath"]])
                    final_path = convert_result["filepath"]
                
                # Move to destination if specified
                if action.get("dest_dir"):
                    dest_dir = Path(action["dest_dir"])
                    final_path = pipeline.move_to_destination(
                        final_path,
                        dest_dir,
                        action.get("new_name")
                    )
                
                # Format report
                report = pipeline.format_report(
                    download_result,
                    convert_result,
                    final_path
                )
                
                return {
                    "type": "media_downloaded",
                    "report": report,
                    "filepath": str(final_path)
                }
            
            except MediaTaskError as e:
                return {
                    "type": "error",
                    "error": str(e)
                }
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Media download error: {e}", exc_info=True)
                return {
                    "type": "error",
                    "error": f"Błąd podczas pobierania mediów: {e}"
                }
        
        if t == "convert_media":
            try:
                pipeline = self.agent.media_pipeline
                
                # Check/ensure ffmpeg
                ffmpeg_status, _ = pipeline.check_tool("ffmpeg")
                if ffmpeg_status not in [ToolStatus.AVAILABLE, ToolStatus.OUTDATED]:
                    self.ui.verbose("ffmpeg nie jest dostępne, instaluję...")
                    ensure_result = pipeline.ensure_tool("ffmpeg")
                    
                    if not ensure_result["success"]:
                        return {
                            "type": "error",
                            "error": f"Nie udało się zainstalować ffmpeg: {ensure_result['message']}"
                        }
                    
                    self.ui.success(f"✓ {ensure_result['message']}")
                
                # Convert
                result = pipeline.convert_to_audio(
                    video_path=Path(action["input_path"]),
                    audio_format=action["output_format"],
                    bitrate=action.get("bitrate", "192k")
                )
                
                if not result["success"]:
                    return {
                        "type": "error",
                        "error": result.get("error", "Conversion failed")
                    }
                
                return {
                    "type": "media_converted",
                    "filepath": str(result["filepath"]),
                    "size_mb": result["size_mb"]
                }
            
            except MediaTaskError as e:
                return {
                    "type": "error",
                    "error": str(e)
                }
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Media conversion error: {e}", exc_info=True)
                return {
                    "type": "error",
                    "error": f"Błąd podczas konwersji: {e}"
                }

        # ===== IMAGE PIPELINE ACTIONS =====

        if t == "process_image":
            try:
                pipeline = self.agent.image_pipeline

                # Ensure Pillow
                from tasks.image_tasks import ImageToolStatus
                pil_status, pil_ver = pipeline.check_pillow()
                if pil_status != ImageToolStatus.AVAILABLE:
                    self.ui.verbose("Pillow nie jest dostępne, instaluję...")
                    ensure_result = pipeline.ensure_pillow()
                    if not ensure_result["success"]:
                        return {"type": "error", "error": f"Nie udało się zainstalować Pillow: {ensure_result['message']}"}
                    self.ui.success(f"✓ {ensure_result['message']}")

                input_path = Path(action["input_path"])
                operation = action["operation"]
                output_path = Path(action["output_path"]) if action.get("output_path") else None

                if operation == "convert":
                    result = pipeline.convert_format(
                        input_path,
                        output_format=action["output_format"],
                        output_path=output_path,
                        quality=action.get("quality", 85),
                        lossless=action.get("lossless", False)
                    )

                elif operation == "compress":
                    result = pipeline.compress_image(
                        input_path,
                        output_path=output_path,
                        quality=action.get("quality", 80),
                        max_width=action.get("max_width"),
                        max_height=action.get("max_height")
                    )

                elif operation == "resize":
                    result = pipeline.resize_image(
                        input_path,
                        width=action.get("width"),
                        height=action.get("height"),
                        output_path=output_path,
                        keep_aspect=action.get("keep_aspect", True),
                        resample=action.get("resample", "lanczos")
                    )

                elif operation == "crop":
                    result = pipeline.crop_image(
                        input_path,
                        x=action["x"],
                        y=action["y"],
                        width=action["width"],
                        height=action["height"],
                        output_path=output_path
                    )

                elif operation == "ico":
                    result = pipeline.convert_to_ico(
                        input_path,
                        output_path=output_path,
                        sizes=action.get("sizes")
                    )

                elif operation == "favicon_set":
                    out_dir = Path(action["output_dir"]) if action.get("output_dir") else None
                    result = pipeline.generate_favicon_set(input_path, output_dir=out_dir)

                elif operation == "info":
                    result = pipeline.get_info(input_path)

                elif operation == "strip_metadata":
                    result = pipeline.strip_metadata(input_path, output_path=output_path)

                else:
                    return {"type": "error", "error": f"Nieznana operacja: {operation}"}

                if not result.get("success"):
                    return {"type": "error", "error": result.get("error", "Unknown error")}

                return {
                    "type": "image_processed",
                    "operation": operation,
                    "result": {k: str(v) if hasattr(v, "__fspath__") else v for k, v in result.items()}
                }

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Image processing error: {e}", exc_info=True)
                return {"type": "error", "error": f"Błąd przetwarzania obrazu: {e}"}

        if t == "batch_images":
            try:
                import glob
                pipeline = self.agent.image_pipeline

                # Resolve input paths
                if action.get("input_paths"):
                    input_paths = [Path(p) for p in action["input_paths"]]
                elif action.get("input_pattern"):
                    input_paths = [Path(p) for p in glob.glob(action["input_pattern"])]
                else:
                    return {"type": "error", "error": "Brak input_paths lub input_pattern"}

                if not input_paths:
                    return {"type": "error", "error": "Nie znaleziono plików pasujących do wzorca"}

                output_dir = Path(action["output_dir"]) if action.get("output_dir") else None
                operation = action["operation"]

                if operation == "convert":
                    result = pipeline.batch_convert(
                        input_paths,
                        output_format=action["output_format"],
                        output_dir=output_dir,
                        quality=action.get("quality", 85)
                    )
                elif operation == "compress":
                    result = pipeline.batch_compress(
                        input_paths,
                        output_dir=output_dir,
                        quality=action.get("quality", 80),
                        max_width=action.get("max_width"),
                        max_height=action.get("max_height")
                    )
                else:
                    return {"type": "error", "error": f"Nieznana operacja batch: {operation}"}

                return {
                    "type": "batch_images_done",
                    "operation": operation,
                    "processed": result["processed"],
                    "failed": result["failed"],
                    "total": result["total"],
                    "total_saved_kb": result.get("total_saved_kb"),
                    "results_summary": pipeline.format_report(
                        result["results"], f"batch {operation}"
                    )
                }

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Batch image error: {e}", exc_info=True)
                return {"type": "error", "error": f"Błąd batch przetwarzania: {e}"}

        if t == "image_info":
            try:
                pipeline = self.agent.image_pipeline
                result = pipeline.get_info(Path(action["path"]))
                return {"type": "image_info_result", "info": result}
            except Exception as e:
                return {"type": "error", "error": f"Błąd odczytu info obrazu: {e}"}

            
        # ===== CLIPBOARD ACTIONS =====

        if t == "clipboard_read":
            cb = self.agent.clipboard
            if not cb.is_available():
                ensure = cb.ensure_backend()
                if not ensure["success"]:
                    return {
                        "type": "clipboard_unavailable",
                        "message": ensure["message"]
                    }

            content = cb.get_content()
            if content is None:
                return {
                    "type": "clipboard_empty",
                    "message": "Schowek jest pusty"
                }

            # Wykryj typ zawartości
            prepared = cb.prepare_for_explain()
            return {
                "type": "clipboard_content",
                "content": content,
                "detected_type": prepared.get("detected_type", "text"),
                "language": prepared.get("language"),
                "length": len(content)
            }

        if t == "clipboard_write":
            cb = self.agent.clipboard
            if not cb.is_available():
                ensure = cb.ensure_backend()
                if not ensure["success"]:
                    return {
                        "type": "clipboard_unavailable",
                        "message": ensure["message"]
                    }

            content = action["content"]
            result = cb.copy_output(content, notify=True)
            return {
                "type": "clipboard_written",
                "success": result["success"],
                "message": result["message"],
                "length": result["length"]
            }

        # ===== WEB SEARCH ACTIONS =====

        if t == "web_search":
            query = action.get("query", "")
            if not query:
                return "[BŁĄD] web_search bez 'query'"

            engine = self.agent.web_search_engine

            if not engine.is_enabled:
                return {
                    "type": "web_search_disabled",
                    "message": (
                        "Web search jest wyłączony. "
                        "Włącz komendą: ai web-search enable"
                    )
                }

            # Sprawdź zależności
            missing = engine.ensure_dependencies()
            if missing:
                return {
                    "type": "web_search_missing_deps",
                    "missing": missing,
                    "message": f"Brakujące pakiety: {', '.join(missing)}. "
                               f"Zainstaluj: pip install {' '.join(missing)}"
                }

            try:
                max_results = action.get("max_results", 5)
                results = engine.search(query, max_results=max_results)

                # Opcjonalnie: scrapuj pierwsze wyniki (jeśli scrape=true w akcji)
                scraped = []
                if action.get("scrape", False):
                    for r in results[:action.get("max_pages", 3)]:
                        if engine.is_domain_allowed(r.url):
                            sr = engine.scraper.scrape(r.url)
                            if sr.success:
                                scraped.append({
                                    "url": r.url,
                                    "title": sr.title or r.title,
                                    "content": sr.markdown[:3000],
                                    "word_count": sr.word_count
                                })

                return {
                    "type": "web_search_results",
                    "query": query,
                    "results": [r.to_dict() for r in results],
                    "scraped": scraped,
                    "count": len(results)
                }

            except RateLimitError as e:
                return {"type": "web_search_rate_limit", "message": str(e)}
            except WebSearchError as e:
                return {"type": "web_search_error", "message": str(e)}
            except Exception as e:
                return f"[BŁĄD] Web search: {e}"

        if t == "web_scrape":
            url = action.get("url", "")
            if not url:
                return "[BŁĄD] web_scrape bez 'url'"

            engine = self.agent.web_search_engine

            # URL podany wprost przez usera w zapytaniu = implicit zgoda, pomijamy whitelist
            user_provided = action.get("user_provided_url", False)

            if not user_provided and not engine.is_domain_allowed(url):
                import urllib.parse
                domain = urllib.parse.urlparse(url).netloc
                return {
                    "type": "web_scrape_blocked",
                    "url": url,
                    "domain": domain,
                    "message": (
                        f"Domena '{domain}' nie jest na whitelist. "
                        f"Dodaj: ai web-search domains add {domain}"
                    )
                }

            missing = engine.ensure_dependencies()
            if missing:
                return {
                    "type": "web_search_missing_deps",
                    "message": f"Brakujące pakiety: {', '.join(missing)}"
                }

            sr = engine.scrape(url)
            return {
                "type": "web_scrape_result",
                "url": url,
                "title": sr.title,
                "markdown": sr.markdown,
                "word_count": sr.word_count,
                "success": sr.success,
                "error": sr.error
            }

        # ===== USE_TEMPLATE =====

        if t == "use_template":
            from utils.template_manager import apply_template, list_templates

            template_name = action.get("template", "")
            if not template_name:
                return "[BŁĄD] use_template wymaga pola 'template'"

            dest = action.get("dest", ".")
            dest_path = Path(dest).expanduser()
            if not dest_path.is_absolute():
                dest_path = (self.fs.cwd if self.fs else Path.cwd()) / dest_path

            variables = dict(action.get("variables", {}))

            # Uzupełnij autora z konfiguracji jeśli nie podano
            if "AUTHOR" not in variables:
                variables["AUTHOR"] = self.config.get("nick", "user")

            overwrite = action.get("overwrite", False)

            try:
                result = apply_template(template_name, dest_path, variables, overwrite=overwrite)
            except (UnicodeDecodeError, UnicodeEncodeError) as e:
                # Binarny plik w szablonie (np. .pyc) - ignoruj i kontynuuj
                return {
                    "type": "template_applied",
                    "template": template_name,
                    "dest": str(dest_path),
                    "created": [],
                    "skipped": [],
                    "message": f"Szablon '{template_name}' pominięty (plik binarny): {e}",
                }

            if not result["success"]:
                return f"[BŁĄD] use_template: {result['error']}"

            summary_parts = []
            if result["created"]:
                summary_parts.append(f"Utworzono {len(result['created'])} plików: {', '.join(result['created'])}")
            if result["skipped"]:
                summary_parts.append(f"Pominięto {len(result['skipped'])} (już istnieją): {', '.join(result['skipped'])}")

            return {
                "type": "template_applied",
                "template": template_name,
                "dest": str(dest_path),
                "created": result["created"],
                "skipped": result["skipped"],
                "message": " | ".join(summary_parts) if summary_parts else "Szablon zastosowany",
            }

        if t == "save_memory":
            # Akcja zapisu faktu do pamięci globalnej
            content = (
                action.get("content")
                or action.get("fact")
                or action.get("note")
                or action.get("text")
                or ""
            ).strip()
            if not content:
                return "[BŁĄD] save_memory wymaga pola 'content' z treścią faktu"

            category = action.get("category", "general")
            gm = getattr(self.agent, "global_memory", None)
            if gm is None:
                return "[BŁĄD] Pamięć globalna niedostępna"

            fact = gm.add(content, category)
            self.ui.success(f"💾 Zapamiętano [{fact['id']}]: {fact['content']}")
            return {"type": "memory_saved", "id": fact["id"], "content": fact["content"]}

