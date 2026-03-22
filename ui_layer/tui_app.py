"""
tui_app.py – Textual TUI dla AI CLI Agent.
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Footer, Header, Input, Label,
    ListView, ListItem,
    Select, Static, Switch, TabbedContent, TabPane,
)

HELP_TEXT = """\
PODSTAWOWE UŻYCIE
  ai <polecenie>     Wykonaj polecenie w języku naturalnym
  ai                 Tryb interaktywny (TUI)
  ai init            Zainicjalizuj projekt (.ai-context.json)

POLECENIA SYSTEMOWE
  ai model           Zarządzaj modelami (czat/embed/fallback/coder/vision)
  ai prompt          Edytuj prompt systemowy
  ai analyze         Przeanalizuj projekt
  ai review          Przegląd projektu (co poprawić)
  ai audit           Audit trail
  ai logs [...]      Logi (subkomendy: clean, rotate)
  ai capability [...] Akcje dozwolone (list, enable, disable, reset)
  ai web-search ...  Wyszukiwanie (enable, disable, status, scrape, domains)
  ai --index         Przebuduj bazę wiedzy (RAG)
  ai knowledge [...]  Baza wiedzy (status, list)
  ai config          Pokaż konfigurację
  ai config edit     Edytuj konfigurację (nano)
  ai stats           Statystyki projektu
  ai history         Historia poleceń
  ai help / --help   Ta pomoc

FLAGI
  --plan             Tylko plan, bez wykonywania
  --dry-run          Symulacja, bez zmian w plikach
  --yes, -y          Pomiń potwierdzenie (NIEBEZPIECZNE!)
  --global, -g       Tryb globalny (bez projektu)
  --quiet, -q        Cichy tryb
  --verbose, -v      Gadatliwy tryb (debug)
  --version          Wersja AI CLI Agent

BEZPIECZEŃSTWO
  DESTRUKCYJNE (delete, move, rm)        – zawsze potwierdzenie
  MEDIA (download_media, convert_media)  – potwierdzenie
  BEZPIECZNE (read, find, ls, curl)      – bez potwierdzenia

CAPABILITIES (kontrola per-projekt)
  allow_execute      Wykonywanie komend systemowych
  allow_delete       Usuwanie i przenoszenie plików
  allow_git          Operacje Git
  allow_network      Dostęp do sieci

PRZYKŁADY
  ai co robi ten projekt
  ai review
  ai stwórz prostą stronę HTML
  ai jakie tu są pliki mp4
  ai pobierz https://youtube.com/...
  ai przekonwertuj video.mp4 na mp3
  ai web-search enable
  ai jaka jest najnowsza wersja pandas

SKRÓTY KLAWISZOWE (TUI)
  Ctrl+C   Wyjście
  Ctrl+L   Wyczyść chat
  Ctrl+S   Panel ustawień
  Ctrl+M   Wybór modelu
  F1       Pomoc (to okno)
  Escape   Fokus na pole wpisywania
"""

# ─── Modal: Potwierdzenie akcji ───────────────────────────────────────────────

class ConfirmDialog(ModalScreen):
    """Modal z przyciskami Akceptuj / Odrzuć – blokuje wątek agenta przez Event."""

    BINDINGS = [
        ("escape", "reject", "Odrzuć"),
        ("enter",  "accept", "Akceptuj"),
    ]
    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }
    ConfirmDialog > Vertical {
        background: #0d0d0d;
        border: double #00cc44;
        padding: 2 4;
        width: 72;
        height: auto;
    }
    ConfirmDialog #confirm-title {
        color: #ffaa00;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    ConfirmDialog .confirm-action-item {
        color: #ff6666;
        margin-bottom: 0;
    }
    ConfirmDialog #confirm-desc {
        color: #cccccc;
        text-align: center;
        margin-bottom: 2;
        margin-top: 1;
    }
    ConfirmDialog #confirm-buttons {
        align: center middle;
        height: auto;
    }
    ConfirmDialog #btn-accept {
        background: #007722;
        color: #ffffff;
        border: tall #00cc44;
        margin-right: 2;
        min-width: 16;
    }
    ConfirmDialog #btn-accept:hover {
        background: #00aa33;
    }
    ConfirmDialog #btn-reject {
        background: #770000;
        color: #ffffff;
        border: tall #cc0000;
        min-width: 16;
    }
    ConfirmDialog #btn-reject:hover {
        background: #aa0000;
    }
    """

    def __init__(self, event: threading.Event, result: list,
                 actions_desc: list | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event = event
        self._result = result  # result[0] = True/False
        self._actions_desc = actions_desc or []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("⚠  Potwierdzenie wymagane", id="confirm-title")
            if self._actions_desc:
                for desc in self._actions_desc:
                    yield Label(f"  🔴 {desc}", classes="confirm-action-item")
            else:
                yield Label(
                    "Agent chce wykonać powyższe akcje.",
                    id="confirm-desc",
                )
            yield Label("Czy zezwolić na wykonanie?", id="confirm-desc")
            with Horizontal(id="confirm-buttons"):
                yield Button("✔  Akceptuj", id="btn-accept", variant="success")
                yield Button("✘  Odrzuć",   id="btn-reject", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-accept":
            self.action_accept()
        else:
            self.action_reject()

    def action_accept(self) -> None:
        self._result[0] = True
        self._event.set()
        self.dismiss(True)

    def action_reject(self) -> None:
        self._result[0] = False
        self._event.set()
        self.dismiss(False)


# ─── Modal: Pomoc ─────────────────────────────────────────────────────────────

class HelpScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Zamknij"), ("f1", "dismiss", "Zamknij")]
    DEFAULT_CSS = """
    HelpScreen { align: center middle; }
    HelpScreen > Vertical {
        width: 90; height: 40;
        background: #111; border: solid #00cc44; padding: 1 2;
    }
    HelpScreen #help-title { text-style: bold; color: #00cc44; margin-bottom: 1; }
    HelpScreen ScrollableContainer { height: 1fr; }
    HelpScreen #help-content { color: #ccc; }
    HelpScreen Button { margin-top: 1; width: 100%; }
    """
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("AI CLI – POMOC  (Escape = zamknij)", id="help-title")
            with ScrollableContainer():
                yield Static(HELP_TEXT, id="help-content")
            yield Button("Zamknij [Escape]", variant="default", id="btn-close-help")
    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


# ─── Modal: Ustawienia ────────────────────────────────────────────────────────

class SettingsScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Zamknij")]
    DEFAULT_CSS = """
    SettingsScreen { align: center middle; }
    SettingsScreen > Vertical {
        width: 96; height: 46;
        background: #111; border: solid #4a90e2; padding: 1 2;
    }
    SettingsScreen #settings-title { text-style: bold; color: #4a90e2; margin-bottom: 1; }
    SettingsScreen TabbedContent { height: 1fr; }
    SettingsScreen .field-row  { height: 3; layout: horizontal; margin-bottom: 1; }
    SettingsScreen .field-label { width: 34; color: #aaa; padding-top: 1; }
    SettingsScreen .field-input { width: 1fr; }
    SettingsScreen .section-hdr { color: #4a90e2; text-style: bold; margin-top: 1; margin-bottom: 0; }
    SettingsScreen .switch-row  { height: 3; layout: horizontal; margin-bottom: 1; }
    SettingsScreen .switch-label { width: 1fr; color: #ccc; padding-top: 1; }
    SettingsScreen #btn-row { height: 4; layout: horizontal; margin-top: 1; }
    SettingsScreen Button { margin-right: 1; }
    """

    def __init__(self, config: dict, save_fn):
        super().__init__()
        self.cfg = config
        self.save_fn = save_fn

    def compose(self) -> ComposeResult:
        ws   = self.cfg.get("web_search", {})
        mem  = self.cfg.get("memory", {})
        dbg  = self.cfg.get("debug", {})
        exc  = self.cfg.get("execution", {})
        beh  = self.cfg.get("behavior", {})
        rag  = self.cfg.get("rag", {})
        conv = self.cfg.get("conversation", {})

        with Vertical():
            yield Label("Ustawienia AI CLI  (Escape = zamknij bez zapisywania)", id="settings-title")
            with TabbedContent():

                # ── Ogólne ──────────────────────────────────────────────────
                with TabPane("Ogólne", id="tab-general"):
                    with Vertical():
                        yield Label("Podstawowe", classes="section-hdr")
                        with Horizontal(classes="field-row"):
                            yield Label("Nick użytkownika:", classes="field-label")
                            yield Input(value=str(self.cfg.get("nick","user")), id="s-nick", classes="field-input")
                        with Horizontal(classes="field-row"):
                            yield Label("Ollama host:", classes="field-label")
                            yield Input(value=str(self.cfg.get("ollama_host","127.0.0.1")), id="s-host", classes="field-input")
                        with Horizontal(classes="field-row"):
                            yield Label("Ollama port:", classes="field-label")
                            yield Input(value=str(self.cfg.get("ollama_port",11434)), id="s-port", classes="field-input")

                # ── Zachowanie ───────────────────────────────────────────────
                with TabPane("Zachowanie", id="tab-behavior"):
                    with Vertical():
                        yield Label("Wykonanie", classes="section-hdr")
                        with Horizontal(classes="field-row"):
                            yield Label("Timeout komend (sekundy):", classes="field-label")
                            yield Input(value=str(exc.get("timeout_seconds",120)), id="s-timeout", classes="field-input")
                        with Horizontal(classes="field-row"):
                            yield Label("Max znaków output komendy:", classes="field-label")
                            yield Input(value=str(exc.get("command_output_limit",4000)), id="s-out-limit", classes="field-input")
                        with Horizontal(classes="field-row"):
                            yield Label("Max akcji per run:", classes="field-label")
                            yield Input(value=str(beh.get("max_actions_per_run",10)), id="s-max-actions", classes="field-input")
                        yield Label("Przełączniki", classes="section-hdr")
                        with Horizontal(classes="switch-row"):
                            yield Label("Auto-confirm bezpiecznych akcji:", classes="switch-label")
                            yield Switch(value=exc.get("auto_confirm_safe",True), id="s-auto-confirm")
                        with Horizontal(classes="switch-row"):
                            yield Label("Powiadomienie systemowe przy confirmie:", classes="switch-label")
                            yield Switch(value=exc.get("notify_on_confirm",True), id="s-notify-confirm")
                        with Horizontal(classes="switch-row"):
                            yield Label("Czytaj plik przed edycją:", classes="switch-label")
                            yield Switch(value=beh.get("prefer_read_before_edit",True), id="s-read-before-edit")
                        with Horizontal(classes="switch-row"):
                            yield Label("Wieloetapowe rozumowanie:", classes="switch-label")
                            yield Switch(value=beh.get("allow_multi_step_reasoning",True), id="s-multi-step")

                # ── Pamięć & RAG ─────────────────────────────────────────────
                with TabPane("Pamięć & RAG", id="tab-memory"):
                    with Vertical():
                        yield Label("Pamięć globalna", classes="section-hdr")
                        with Horizontal(classes="switch-row"):
                            yield Label("Auto-ekstrakcja faktów z rozmów:", classes="switch-label")
                            yield Switch(value=mem.get("auto_extract",True), id="s-mem-auto-extract")
                        with Horizontal(classes="switch-row"):
                            yield Label("Pokaż zapisane fakty (💾):", classes="switch-label")
                            yield Switch(value=mem.get("show_saved",True), id="s-mem-show-saved")
                        yield Label("RAG (baza wiedzy)", classes="section-hdr")
                        with Horizontal(classes="switch-row"):
                            yield Label("RAG włączony:", classes="switch-label")
                            yield Switch(value=rag.get("enabled",True), id="s-rag-enabled")
                        with Horizontal(classes="field-row"):
                            yield Label("Top-K fragmentów:", classes="field-label")
                            yield Input(value=str(rag.get("top_k",8)), id="s-rag-topk", classes="field-input")
                        with Horizontal(classes="field-row"):
                            yield Label("Min. podobieństwo (0.0-1.0):", classes="field-label")
                            yield Input(value=str(rag.get("min_score",0.1)), id="s-rag-minscore", classes="field-input")
                        with Horizontal(classes="field-row"):
                            yield Label("Max fragmentów z pliku:", classes="field-label")
                            yield Input(value=str(rag.get("max_per_file",2)), id="s-rag-maxperfile", classes="field-input")
                        with Horizontal(classes="switch-row"):
                            yield Label("Pokaż źródła RAG:", classes="switch-label")
                            yield Switch(value=rag.get("show_sources",True), id="s-rag-show-sources")

                # ── Rozmowa ──────────────────────────────────────────────────
                with TabPane("Rozmowa", id="tab-conversation"):
                    with Vertical():
                        yield Label("Historia rozmów", classes="section-hdr")
                        with Horizontal(classes="switch-row"):
                            yield Label("Zapisuj historię do pliku:", classes="switch-label")
                            yield Switch(value=conv.get("save_history",True), id="s-conv-save")
                        with Horizontal(classes="switch-row"):
                            yield Label("Pytaj o wznowienie przy starcie:", classes="switch-label")
                            yield Switch(value=conv.get("resume_prompt",True), id="s-conv-resume")
                        with Horizontal(classes="field-row"):
                            yield Label("Max zapisanych wiadomości:", classes="field-label")
                            yield Input(value=str(conv.get("max_saved_messages",40)), id="s-conv-maxmsg", classes="field-input")
                        yield Label("Plik historii: .ai-logs/conversation_history.jsonl", classes="section-hdr")
                        yield Label("T/Enter przy starcie = wznów  |  N = wyczyść i zacznij od nowa", classes="switch-label")

                # ── Web Search ───────────────────────────────────────────────
                with TabPane("Web Search", id="tab-websearch"):
                    with Vertical():
                        with Horizontal(classes="switch-row"):
                            yield Label("Web search włączony:", classes="switch-label")
                            yield Switch(value=ws.get("enabled",False), id="s-ws-enabled")
                        with Horizontal(classes="field-row"):
                            yield Label("Silnik:", classes="field-label")
                            yield Select(
                                options=[("DuckDuckGo (bezpłatny)","duckduckgo"),
                                         ("Brave Search (wymaga klucza)","brave"),
                                         ("Google (wymaga klucza + CX)","google")],
                                value=ws.get("engine","duckduckgo"),
                                id="s-ws-engine", classes="field-input"
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("Max wyników:", classes="field-label")
                            yield Input(value=str(ws.get("max_results",5)), id="s-ws-max", classes="field-input")
                        with Horizontal(classes="field-row"):
                            yield Label("Cache TTL (godziny):", classes="field-label")
                            yield Input(value=str(ws.get("cache_ttl_hours",1)), id="s-ws-cache", classes="field-input")
                        with Horizontal(classes="switch-row"):
                            yield Label("Auto-trigger (wykryj frazy):", classes="switch-label")
                            yield Switch(value=ws.get("auto_trigger",True), id="s-ws-autotrigger")
                        with Horizontal(classes="switch-row"):
                            yield Label("Pytaj przed nieznanymi domenami:", classes="switch-label")
                            yield Switch(value=ws.get("require_confirmation",False), id="s-ws-confirm")
                        with Horizontal(classes="field-row"):
                            yield Label("Brave API key:", classes="field-label")
                            yield Input(value=ws.get("brave_api_key",""), password=True, id="s-ws-brave-key", classes="field-input")

                # ── Debug ────────────────────────────────────────────────────
                with TabPane("Debug", id="tab-debug"):
                    with Vertical():
                        with Horizontal(classes="field-row"):
                            yield Label("Poziom logów:", classes="field-label")
                            yield Select(
                                options=[("debug","debug"),("info","info"),
                                         ("warning","warning"),("error","error")],
                                value=dbg.get("log_level","info"),
                                id="s-log-level", classes="field-input"
                            )
                        with Horizontal(classes="switch-row"):
                            yield Label("Loguj zapytania semantyczne:", classes="switch-label")
                            yield Switch(value=dbg.get("log_semantic_queries",False), id="s-log-semantic")
                        with Horizontal(classes="switch-row"):
                            yield Label("Loguj surowy output modelu:", classes="switch-label")
                            yield Switch(value=dbg.get("log_model_raw_output",False), id="s-log-raw")
                        with Horizontal(classes="switch-row"):
                            yield Label("Zapisuj błędne odpowiedzi:", classes="switch-label")
                            yield Switch(value=dbg.get("save_failed_responses",True), id="s-log-failed")

            with Horizontal(id="btn-row"):
                yield Button("Zapisz", variant="success", id="btn-save-settings")
                yield Button("Anuluj", variant="default", id="btn-cancel-settings")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-settings":
            self.dismiss(None); return
        if event.button.id == "btn-save-settings":
            self._collect_and_save()

    def _v(self, id_):
        try: return self.query_one(f"#{id_}", Input).value
        except: return ""

    def _sw(self, id_):
        try: return self.query_one(f"#{id_}", Switch).value
        except: return False

    def _sel(self, id_):
        try: return self.query_one(f"#{id_}", Select).value
        except: return None

    def _collect_and_save(self):
        self.cfg["nick"]        = self._v("s-nick") or "user"
        self.cfg["ollama_host"] = self._v("s-host") or "127.0.0.1"
        try: self.cfg["ollama_port"] = int(self._v("s-port"))
        except: pass

        if "execution" not in self.cfg: self.cfg["execution"] = {}
        try: self.cfg["execution"]["timeout_seconds"]      = int(self._v("s-timeout"))
        except: pass
        try: self.cfg["execution"]["command_output_limit"] = int(self._v("s-out-limit"))
        except: pass
        self.cfg["execution"]["auto_confirm_safe"] = self._sw("s-auto-confirm")
        self.cfg["execution"]["notify_on_confirm"]  = self._sw("s-notify-confirm")

        if "behavior" not in self.cfg: self.cfg["behavior"] = {}
        try: self.cfg["behavior"]["max_actions_per_run"] = int(self._v("s-max-actions"))
        except: pass
        self.cfg["behavior"]["prefer_read_before_edit"]    = self._sw("s-read-before-edit")
        self.cfg["behavior"]["allow_multi_step_reasoning"] = self._sw("s-multi-step")

        if "memory" not in self.cfg: self.cfg["memory"] = {}
        self.cfg["memory"]["auto_extract"] = self._sw("s-mem-auto-extract")
        self.cfg["memory"]["show_saved"]   = self._sw("s-mem-show-saved")

        if "rag" not in self.cfg: self.cfg["rag"] = {}
        self.cfg["rag"]["enabled"]      = self._sw("s-rag-enabled")
        try: self.cfg["rag"]["top_k"]   = int(self._v("s-rag-topk"))
        except: pass
        try: self.cfg["rag"]["min_score"]    = float(self._v("s-rag-minscore"))
        except: pass
        try: self.cfg["rag"]["max_per_file"] = int(self._v("s-rag-maxperfile"))
        except: pass
        self.cfg["rag"]["show_sources"] = self._sw("s-rag-show-sources")

        if "conversation" not in self.cfg: self.cfg["conversation"] = {}
        self.cfg["conversation"]["save_history"]  = self._sw("s-conv-save")
        self.cfg["conversation"]["resume_prompt"] = self._sw("s-conv-resume")
        try: self.cfg["conversation"]["max_saved_messages"] = int(self._v("s-conv-maxmsg"))
        except: pass

        if "web_search" not in self.cfg: self.cfg["web_search"] = {}
        self.cfg["web_search"]["enabled"]     = self._sw("s-ws-enabled")
        engine_val = self._sel("s-ws-engine")
        if engine_val and engine_val != Select.BLANK:
            self.cfg["web_search"]["engine"] = engine_val
        try: self.cfg["web_search"]["max_results"]     = int(self._v("s-ws-max"))
        except: pass
        try: self.cfg["web_search"]["cache_ttl_hours"] = int(self._v("s-ws-cache"))
        except: pass
        self.cfg["web_search"]["auto_trigger"]         = self._sw("s-ws-autotrigger")
        self.cfg["web_search"]["require_confirmation"] = self._sw("s-ws-confirm")
        bk = self._v("s-ws-brave-key")
        if bk: self.cfg["web_search"]["brave_api_key"] = bk

        if "debug" not in self.cfg: self.cfg["debug"] = {}
        log_val = self._sel("s-log-level")
        if log_val and log_val != Select.BLANK:
            self.cfg["debug"]["log_level"] = log_val
        self.cfg["debug"]["log_semantic_queries"] = self._sw("s-log-semantic")
        self.cfg["debug"]["log_model_raw_output"] = self._sw("s-log-raw")
        self.cfg["debug"]["save_failed_responses"]= self._sw("s-log-failed")

        self.save_fn(self.cfg)
        self.dismiss("saved")


# ─── Modal: Pamięć ───────────────────────────────────────────────────────────

class MemoryScreen(ModalScreen):
    """Panel pamięci globalnej — przeglądanie, dodawanie i usuwanie faktów."""

    BINDINGS = [("escape", "dismiss", "Zamknij"), ("ctrl+r", "dismiss", "Zamknij")]
    DEFAULT_CSS = """
    MemoryScreen { align: center middle; }
    MemoryScreen > Vertical {
        width: 96; height: 46;
        background: #111; border: solid #00cc88; padding: 1 2;
    }
    MemoryScreen #mem-title    { text-style: bold; color: #00cc88; margin-bottom: 1; }
    MemoryScreen #mem-add-row  { height: 3; layout: horizontal; margin-bottom: 1; }
    MemoryScreen #mem-add-input { width: 1fr; }
    MemoryScreen #mem-add-btn  { width: 14; margin-left: 1; }
    MemoryScreen #mem-cat-row  { height: 3; layout: horizontal; margin-bottom: 1; }
    MemoryScreen #mem-cat-label { width: 22; color: #aaa; padding-top: 1; }
    MemoryScreen #mem-cat-input { width: 18; }
    MemoryScreen #mem-count    { color: #555; margin-bottom: 1; }
    MemoryScreen #mem-scroll   { height: 1fr; border: solid #1e1e1e; padding: 0 1; }
    MemoryScreen .mem-entry    { height: 3; layout: horizontal; padding: 0 0 0 1; }
    MemoryScreen .mem-entry:hover { background: #1a1a1a; }
    MemoryScreen .mem-entry-text { width: 1fr; color: #ccc; padding-top: 1; }
    MemoryScreen .mem-entry-cat  { width: 14; color: #555; padding-top: 1; }
    MemoryScreen .mem-del-btn    { width: 6; min-width: 6; margin-left: 1; }
    MemoryScreen .mem-empty    { color: #444; padding: 2 1; }
    MemoryScreen #mem-hint     { color: #444; margin-top: 1; height: auto; width: 1fr; }
    MemoryScreen #btn-row      { height: 4; layout: horizontal; margin-top: 1; }
    MemoryScreen Button        { margin-right: 1; }
    """

    def __init__(self, agent=None):
        super().__init__()
        self._agent = agent
        self._gm = None
        if agent and hasattr(agent, 'global_memory') and agent.global_memory:
            self._gm = agent.global_memory

    def _load_facts(self) -> list:
        if self._gm:
            try:
                return self._gm.list_facts()
            except Exception:
                pass
        # Fallback — czytaj plik bezpośrednio
        try:
            import json
            mem_file = Path.home() / ".config" / "ai" / "memory.json"
            if mem_file.exists():
                data = json.loads(mem_file.read_text(encoding="utf-8"))
                return data.get("facts", [])
        except Exception:
            pass
        return []

    def _add_fact(self, content: str, category: str = "general") -> bool:
        if not content.strip():
            return False
        if self._gm:
            try:
                self._gm.add_fact(content.strip(), category.strip() or "general")
                return True
            except Exception:
                pass
        # Fallback — zapis bezpośredni do pliku
        try:
            import json, time
            mem_file = Path.home() / ".config" / "ai" / "memory.json"
            mem_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if mem_file.exists():
                data = json.loads(mem_file.read_text(encoding="utf-8"))
            facts = data.get("facts", [])
            new_id = max((f.get("id", 0) for f in facts), default=0) + 1
            facts.append({
                "id": new_id,
                "content": content.strip(),
                "category": category.strip() or "general",
                "created_at": datetime.now().isoformat(),
            })
            data["facts"] = facts
            mem_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def _delete_fact(self, fact_id: int) -> bool:
        if self._gm:
            try:
                self._gm.remove_fact(fact_id)
                return True
            except Exception:
                pass
        # Fallback — zapis bezpośredni
        try:
            import json
            mem_file = Path.home() / ".config" / "ai" / "memory.json"
            if not mem_file.exists():
                return False
            data = json.loads(mem_file.read_text(encoding="utf-8"))
            before = len(data.get("facts", []))
            data["facts"] = [f for f in data.get("facts", []) if f.get("id") != fact_id]
            if len(data["facts"]) < before:
                mem_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                return True
        except Exception:
            pass
        return False

    def compose(self) -> ComposeResult:
        facts = self._load_facts()
        with Vertical():
            yield Label(
                f"Pamięć globalna  [{len(facts)} faktów]  (Escape = zamknij)",
                id="mem-title"
            )
            # Wiersz dodawania
            with Horizontal(id="mem-cat-row"):
                yield Label("Kategoria (opcjonalna):", id="mem-cat-label")
                yield Input(placeholder="general", id="mem-cat-input", value="general")
            with Horizontal(id="mem-add-row"):
                yield Input(placeholder="Wpisz fakt do zapamiętania…", id="mem-add-input")
                yield Button("➕ Dodaj", id="mem-add-btn", variant="success")
            # Lista faktów
            with ScrollableContainer(id="mem-scroll"):
                if not facts:
                    yield Label(
                        "Brak zapamiętanych faktów.\n"
                        "Napisz \"zapamiętaj że...\" w czacie lub dodaj ręcznie powyżej.",
                        classes="mem-empty"
                    )
                else:
                    for f in reversed(facts):  # najnowsze na górze
                        fid      = f.get("id", 0)
                        content  = f.get("content", "")
                        category = f.get("category", "general")
                        ts       = f.get("created_at", "")[:10]
                        with Horizontal(classes="mem-entry", id=f"mem-row-{fid}"):
                            yield Label(
                                f"[dim]{ts}[/]  {content}",
                                classes="mem-entry-text"
                            )
                            yield Label(category, classes="mem-entry-cat")
                            yield Button(
                                "✕", id=f"mem-del-{fid}",
                                classes="mem-del-btn", variant="error"
                            )
            yield Static(
                "Fakty są wczytywane jako kontekst do każdej rozmowy.\n"
                'Napisz "zapamiętaj że…" w czacie — AI doda fakt automatycznie.',
                id="mem-hint"
            )
            with Horizontal(id="btn-row"):
                yield Button("Zamknij  [Escape]", variant="default", id="btn-mem-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "btn-mem-close":
            self.dismiss(None)
            return

        if btn_id == "mem-add-btn":
            try:
                content  = self.query_one("#mem-add-input",  Input).value.strip()
                category = self.query_one("#mem-cat-input",  Input).value.strip() or "general"
            except NoMatches:
                return
            if not content:
                return
            if self._add_fact(content, category):
                # Wyczyść pole input i odśwież listę in-place
                try:
                    self.query_one("#mem-add-input", Input).value = ""
                except NoMatches:
                    pass
                self._refresh_list()
            return

        if btn_id.startswith("mem-del-"):
            try:
                fid = int(btn_id.split("-")[-1])
            except ValueError:
                return
            if self._delete_fact(fid):
                # Usuń wiersz in-place — bez zamykania i ponownego otwierania modala
                try:
                    row = self.query_one(f"#mem-row-{fid}")
                    row.remove()
                except NoMatches:
                    pass
                # Zaktualizuj licznik w tytule
                self._update_title()
            return

    def _refresh_list(self) -> None:
        """Przeładuj całą listę faktów in-place (po dodaniu)."""
        from textual.widgets import ScrollableContainer
        try:
            scroll = self.query_one("#mem-scroll", ScrollableContainer)
            scroll.remove_children()
            facts = self._load_facts()
            if not facts:
                scroll.mount(Label(
                    "Brak zapamiętanych faktów.\n"
                    'Napisz "zapamiętaj że..." w czacie lub dodaj ręcznie powyżej.',
                    classes="mem-empty"
                ))
            else:
                for f in reversed(facts):
                    fid      = f.get("id", 0)
                    content  = f.get("content", "")
                    category = f.get("category", "general")
                    ts       = f.get("created_at", "")[:10]
                    row = Horizontal(classes="mem-entry", id=f"mem-row-{fid}")
                    row.mount(Label(f"[dim]{ts}[/]  {content}", classes="mem-entry-text"))
                    row.mount(Label(category, classes="mem-entry-cat"))
                    row.mount(Button("✕", id=f"mem-del-{fid}", classes="mem-del-btn", variant="error"))
                    scroll.mount(row)
        except NoMatches:
            pass
        self._update_title()

    def _update_title(self) -> None:
        """Zaktualizuj licznik faktów w tytule modala."""
        try:
            facts = self._load_facts()
            self.query_one("#mem-title", Label).update(
                f"Pamięć globalna  [{len(facts)} faktów]  (Escape = zamknij)"
            )
        except (NoMatches, Exception):
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter w polu dodawania = kliknij Dodaj."""
        if event.input.id in ("mem-add-input", "mem-cat-input"):
            try:
                self.query_one("#mem-add-btn", Button).press()
            except NoMatches:
                pass


# ─── Modal: Modele ────────────────────────────────────────────────────────────

class ModelScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Zamknij")]
    DEFAULT_CSS = """
    ModelScreen { align: center middle; }
    ModelScreen > Vertical {
        width: 90; height: 42;
        background: #111; border: solid #ffaa00; padding: 1 2;
    }
    ModelScreen #model-title  { text-style: bold; color: #ffaa00; margin-bottom: 1; }
    ModelScreen .field-row    { height: 3; layout: horizontal; margin-bottom: 1; }
    ModelScreen .field-label  { width: 28; color: #aaa; padding-top: 1; }
    ModelScreen .field-select { width: 1fr; }
    ModelScreen .hint         { color: #555; margin-bottom: 0; }
    ModelScreen .model-desc   { color: #444; margin-bottom: 1; height: 2; }
    ModelScreen #btn-row      { height: 4; layout: horizontal; margin-top: 1; }
    ModelScreen Button        { margin-right: 1; }
    """

    def __init__(self, config: dict, save_fn, available_models: list[str] | None = None):
        super().__init__()
        self.cfg = config
        self.save_fn = save_fn
        self.available_models = available_models or []

    def _model_options(self, current: str) -> list:
        """
        Buduje listę opcji Select z dostępnych modeli Ollama.
        Aktualnie wybrany model jest zawsze na liście (nawet jeśli offline).
        """
        seen = set()
        opts = []
        for m in self.available_models:
            if m and m not in seen:
                seen.add(m)
                opts.append((m, m))
        # Upewnij się że aktualny model jest na liście
        if current and current not in seen:
            opts.insert(0, (f"{current}  (aktualny)", current))
        if not opts:
            opts = [("(Ollama offline — wpisz nazwę ręcznie)", "")]
        return opts

    def compose(self) -> ComposeResult:
        chat    = self.cfg.get("chat_model", "")
        embed   = self.cfg.get("embed_model", "")
        fallbk  = self.cfg.get("fallback_model", "")
        coder   = self.cfg.get("coder_model", "")
        vision  = self.cfg.get("vision_model", "")

        with Vertical():
            yield Label("Wybór modeli  (Escape = zamknij bez zapisywania)", id="model-title")
            yield Label(
                "Modele pobrane z Ollama. Wybierz z listy lub wpisz nazwę modelu ręcznie poniżej.",
                classes="hint"
            )
            yield Label(
                "Tip: chat = główny model czatu  |  embed = RAG  |  coder/vision = smart routing",
                classes="model-desc"
            )

            with Horizontal(classes="field-row"):
                yield Label("Model czatu (główny):", classes="field-label")
                yield Select(
                    options=self._model_options(chat),
                    value=chat if chat else Select.BLANK,
                    id="m-chat", classes="field-select"
                )
            with Horizontal(classes="field-row"):
                yield Label("Model embeddingów (RAG):", classes="field-label")
                yield Select(
                    options=self._model_options(embed),
                    value=embed if embed else Select.BLANK,
                    id="m-embed", classes="field-select"
                )
            with Horizontal(classes="field-row"):
                yield Label("Model fallback (429/timeout):", classes="field-label")
                yield Select(
                    options=self._model_options(fallbk),
                    value=fallbk if fallbk else Select.BLANK,
                    id="m-fallback", classes="field-select"
                )
            with Horizontal(classes="field-row"):
                yield Label("Model coder (smart routing):", classes="field-label")
                yield Select(
                    options=self._model_options(coder),
                    value=coder if coder else Select.BLANK,
                    id="m-coder", classes="field-select"
                )
            with Horizontal(classes="field-row"):
                yield Label("Model vision (smart routing):", classes="field-label")
                yield Select(
                    options=self._model_options(vision),
                    value=vision if vision else Select.BLANK,
                    id="m-vision", classes="field-select"
                )

            with Horizontal(id="btn-row"):
                yield Button("Zapisz", variant="success", id="btn-save-model")
                yield Button("Anuluj", variant="default", id="btn-cancel-model")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-model":
            self.dismiss(None); return
        if event.button.id == "btn-save-model":
            self._collect_and_save()

    def _sel(self, id_: str) -> str:
        try:
            v = self.query_one(f"#{id_}", Select).value
            return "" if v == Select.BLANK else str(v)
        except:
            return ""

    def _collect_and_save(self):
        self.cfg["chat_model"]     = self._sel("m-chat")
        self.cfg["embed_model"]    = self._sel("m-embed")
        self.cfg["fallback_model"] = self._sel("m-fallback")
        self.cfg["coder_model"]    = self._sel("m-coder")
        self.cfg["vision_model"]   = self._sel("m-vision")
        self.save_fn(self.cfg)
        self.dismiss("saved")

# ─── Chat widgets ─────────────────────────────────────────────────────────────

class ChatMessage(Static):
    DEFAULT_CSS = """
    ChatMessage { margin: 0 0 1 0; }
    ChatMessage .user-msg    { border-left: thick #00cc44; background: #0e1f0e; padding: 1 2; }
    ChatMessage .ai-msg      { border-left: thick #4a90e2; background: #0a1525; padding: 1 2; }
    ChatMessage .system-msg  { border-left: thick #555;    background: #141414; padding: 1 2; }
    ChatMessage .error-msg   { border-left: thick #ff4444; background: #1f0a0a; padding: 1 2; }
    ChatMessage .success-msg { border-left: thick #44cc44; background: #0a1f0a; padding: 1 2; }
    ChatMessage .msg-meta    { color: #444; text-style: dim; }
    ChatMessage .msg-text    { color: #ddd; }
    ChatMessage .ai-text     { color: #a8c8f0; }
    ChatMessage .error-text  { color: #ff8080; }
    ChatMessage .success-text{ color: #80ff80; }
    ChatMessage .system-text { color: #888; }
    """
    def __init__(self, sender: str, text: str, role: str = "user"):
        super().__init__()
        self.sender = sender
        self.msg_text = text
        self.role = role
        self.ts = datetime.now().strftime("%H:%M:%S")

    def compose(self) -> ComposeResult:
        css_text = f"{self.role}-text" if self.role in ("ai","error","success","system") else ""
        with Vertical(classes=f"{self.role}-msg"):
            yield Label(f"{self.sender}  {self.ts}", classes="msg-meta")
            yield Static(self.msg_text, classes=f"msg-text {css_text}")


class AuditEntry(Static):
    """
    Pojedynczy wpis audit trail z reaktywnym statusem.
    Można zmienić status po zamontowaniu przez set_status().
    """
    DEFAULT_CSS = """
    AuditEntry { height: 1; padding: 0 1; }
    AuditEntry .audit-pending  { color: #cc8800; }
    AuditEntry .audit-done     { color: #44cc44; }
    AuditEntry .audit-error    { color: #ff5555; }
    AuditEntry .audit-info     { color: #5588bb; }
    AuditEntry .audit-thinking { color: #8866aa; }
    """
    # Ikony: czysty Unicode BMP, dziala w kazdym terminalu UTF-8
    # bez potrzeby Nerd Fonts / emoji
    ICONS = {
        "pending":  "▷",   # right triangle — akcja w toku
        "done":     "✓",   # check mark     — sukces
        "error":    "✕",   # heavy cross    — blad
        "info":     "─",   # dash           — info/etap
        "thinking": "…",   # ellipsis       — AI mysli
    }

    # Tłumaczenia typów akcji na polskie etykiety
    TYPE_LABELS = {
        "QUERY":   "Zapytanie",
        "ACTION":  "Akcja",
        "DONE":    "Koniec",
        "AI":      "Model",
        "ETAP":    "Etap",
        "INFO":    "Info",
        "ITER":    "Iteracja",
        "ZAMIAR":  "Zamiar",
        "POWÓD":   "Powód",
        "KROK":    "Krok",
        "WEB":     "Web",
        "UWAGA":   "Uwaga",
        "LIMIT":   "Limit",
    }

    def __init__(self, action_type: str, detail: str, status: str = "pending",
                 entry_id: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.action_type = action_type
        self.detail = detail
        self.status = status
        self.entry_id = entry_id
        self.ts = datetime.now().strftime("%H:%M:%S")
        self._label: Label | None = None

    def _format(self) -> str:
        icon  = self.ICONS.get(self.status, "•")
        label = self.TYPE_LABELS.get(self.action_type.upper(), self.action_type)
        # Etykieta tylko gdy nie jest to ITER (ma wlasny format)
        if self.action_type.upper() == "ITER":
            return f"  {self.detail}"
        return f"{icon}  {self.ts}  {label}: {self.detail}"

    def compose(self) -> ComposeResult:
        self._label = Label(
            self._format(),
            classes=f"audit-{self.status}"
        )
        yield self._label

    def set_status(self, status: str, detail: str | None = None) -> None:
        """Zaktualizuj status i opcjonalnie tekst wpisu (bez remount)."""
        self.status = status
        if detail is not None:
            self.detail = detail
        try:
            lbl = self.query_one(Label)
            lbl.update(self._format())
            for cls in list(lbl.classes):
                if cls.startswith("audit-"):
                    lbl.remove_class(cls)
            lbl.add_class(f"audit-{status}")
        except Exception:
            pass


class AuditTrail(Vertical):
    """
    Pasek audit trail na dole TUI.
    Obsługuje: dodawanie wpisów, aktualizację statusu istniejących, counter iteracji.
    """
    DEFAULT_CSS = """
    AuditTrail {
        height: 9; background: #060606;
        border-top: solid #222; padding: 0 1;
    }
    AuditTrail .audit-hdr {
        color: #2a2a2a; text-style: bold; height: 1;
        background: #0a0a0a;
    }
    AuditTrail #audit-scroll { height: 7; }
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._entries: list = []
        self._entry_map: dict[str, AuditEntry] = {}  # entry_id -> widget
        self._iter_count: int = 0
        self._action_counter: int = 0  # numeruje akcje w bieżącej sesji

    def compose(self) -> ComposeResult:
        yield Label("AUDIT TRAIL", classes="audit-hdr")
        yield ScrollableContainer(id="audit-scroll")

    def add_entry(self, action_type: str, detail: str, status: str = "pending",
                  entry_id: str = "") -> str:
        """
        Dodaj wpis. Zwraca entry_id który można potem użyć do update_entry().
        Jeśli entry_id puste, generowany jest automatycznie.
        """
        if not entry_id:
            self._action_counter += 1
            entry_id = f"ae-{self._action_counter}"

        self._entries.append((action_type, detail, status))
        if len(self._entries) > 50:
            self._entries = self._entries[-50:]
        try:
            scroll = self.query_one("#audit-scroll")
            widget = AuditEntry(action_type, detail, status, entry_id=entry_id)
            self._entry_map[entry_id] = widget
            scroll.mount(widget)
            scroll.scroll_end(animate=False)
        except NoMatches:
            pass
        return entry_id

    def update_entry(self, entry_id: str, status: str, detail: str | None = None) -> None:
        """Zaktualizuj status istniejącego wpisu po jego entry_id."""
        widget = self._entry_map.get(entry_id)
        if widget:
            widget.set_status(status, detail)
        try:
            self.query_one("#audit-scroll").scroll_end(animate=False)
        except NoMatches:
            pass

    def new_iteration(self, iteration: int, max_iter: int) -> None:
        """Dodaj separator iteracji (np. '── iter 2/8 ──')."""
        self._iter_count = iteration
        sep = f"── iter {iteration}/{max_iter} ──────────────────"
        self.add_entry("ITER", sep, "info")

    def clear_entries(self) -> None:
        """Wyczyść historię wpisów (np. przy nowym zapytaniu)."""
        self._entries.clear()
        self._entry_map.clear()
        self._action_counter = 0
        self._iter_count = 0
        try:
            scroll = self.query_one("#audit-scroll")
            scroll.remove_children()
        except NoMatches:
            pass


class Sidebar(Vertical):
    DEFAULT_CSS = """
    Sidebar {
        width: 32; background: #0a0a0a;
        border-right: solid #1e1e1e; padding: 1;
    }
    Sidebar .section-hdr { text-style: bold; color: #00cc44; margin-top: 1; }
    Sidebar .info-row    { color: #555; }
    Sidebar .info-val    { color: #bbb; margin-bottom: 1; }
    Sidebar .divider     { color: #1e1e1e; }
    Sidebar .hint-key    { color: #444; }
    """
    def __init__(self, config: dict | None = None, project_root: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cfg = config or {}
        self.project_root = project_root or "~"

    def compose(self) -> ComposeResult:
        yield Label("AI CLI AGENT", classes="section-hdr")
        yield Label("─" * 26, classes="divider")
        yield Label("PROJEKT", classes="section-hdr")
        root = str(self.project_root)
        yield Label(("…"+root[-22:]) if len(root)>24 else root, classes="info-val")
        yield Label("─" * 26, classes="divider")
        yield Label("MODEL", classes="section-hdr")
        yield Label(self.cfg.get("chat_model","?"), classes="info-val", id="sb-model")
        yield Label(f"{self.cfg.get('ollama_host','127.0.0.1')}:{self.cfg.get('ollama_port',11434)}", classes="info-row")
        yield Label("─" * 26, classes="divider")
        yield Label("UPRAWNIENIA", classes="section-hdr")
        yield Label("[green]Execute:[/] TAK", classes="info-row")
        yield Label("[red]Delete:[/]  NIE",  classes="info-row")
        yield Label("─" * 26, classes="divider")
        yield Label("SESJA", classes="section-hdr")
        yield Label("Transakcje: 0", classes="info-row", id="sb-tx")
        yield Label("Tokeny: 0",     classes="info-row", id="sb-tokens")
        yield Label("─" * 26, classes="divider")
        yield Label("Ctrl+S  Ustawienia", classes="hint-key")
        yield Label("Ctrl+M  Modele",     classes="hint-key")
        yield Label("Ctrl+R  Pamięć",     classes="hint-key")
        yield Label("F1      Pomoc",      classes="hint-key")

    def update_session(self, tx: int, tokens: int):
        try:
            self.query_one("#sb-tx",     Label).update(f"Transakcje: {tx}")
            self.query_one("#sb-tokens", Label).update(f"Tokeny: ~{tokens}")
        except NoMatches:
            pass

    def update_model(self, model: str):
        try:
            self.query_one("#sb-model", Label).update(model or "?")
        except NoMatches:
            pass


# ─── Główna aplikacja ─────────────────────────────────────────────────────────

class AICLIApp(App):
    TITLE = "AI CLI Agent"
    CSS = """
    Screen { background: #0d0d0d; layout: vertical; }
    Header { background: #0a0a0a; color: #00cc44; }
    Footer { background: #0a0a0a; color: #333; }
    #main-layout { layout: horizontal; height: 1fr; }
    #chat-area   { layout: vertical; width: 1fr; }
    #chat-scroll { height: 1fr; padding: 1 2; }
    #input-area  { height: auto; padding: 0 2 1 2; background: #0d0d0d; }
    #input-hint  { color: #bbb; height: 1; padding: 0 1; }
    #user-input  { border: tall #333; background: #111; color: #eee; width: 1fr; }
    #user-input:focus    { border: tall #00cc44; }
    #user-input:disabled { border: tall #444; color: #555; }
    """
    BINDINGS = [
        Binding("ctrl+c", "quit",          "Wyjście"),
        Binding("ctrl+l", "clear_chat",    "Wyczyść"),
        Binding("ctrl+s", "open_settings", "Ustawienia"),
        Binding("ctrl+m", "open_models",   "Modele"),
        Binding("ctrl+r", "open_memory",   "Pamięć"),
        Binding("f1",     "open_help",     "Pomoc"),
        Binding("escape", "focus_input",   "Fokus"),
    ]

    is_processing: reactive[bool] = reactive(False)

    def __init__(self, agent=None, config: dict | None = None):
        super().__init__()
        self.agent = agent
        self.cfg = config or {}
        self._project_root = None
        self._tx_count = 0
        self._token_count = 0
        self._available_models: list[str] = []
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._poll_timer = None

        if agent and hasattr(agent, 'project_root') and agent.project_root:
            self._project_root = str(agent.project_root)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            yield Sidebar(config=self.cfg, project_root=self._project_root, id="sidebar")
            with Vertical(id="chat-area"):
                yield ScrollableContainer(id="chat-scroll")
                yield AuditTrail(id="audit-trail")
                with Vertical(id="input-area"):
                    yield Label(
                        "Ctrl+S ustawienia  •  Ctrl+M modele  •  Ctrl+R pamięć  •  F1 pomoc  •  Ctrl+L wyczyść  •  Ctrl+C wyjście",
                        id="input-hint"
                    )
                    yield Input(
                        placeholder="W czym mogę pomóc? (np. 'stwórz model użytkownika')",
                        id="user-input"
                    )
        yield Footer()

    def on_mount(self) -> None:
        self._add_message("AI CLI", "Gotowy. Projekt wczytany, kontekst aktywny.", role="ai")
        self.query_one("#user-input").focus()
        threading.Thread(target=self._fetch_models, daemon=True).start()

    def _fetch_models(self):
        try:
            import requests as req
            host = self.cfg.get("ollama_host","127.0.0.1")
            port = self.cfg.get("ollama_port", 11434)
            r = req.get(f"http://{host}:{port}/api/tags", timeout=3)
            self._available_models = [m["name"] for m in r.json().get("models",[])]
        except Exception:
            self._available_models = []

    # ── Input ─────────────────────────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return
        self.query_one("#user-input", Input).value = ""
        if self.is_processing:
            self._add_message("System","Poczekaj – poprzednie zapytanie w toku.", role="error")
            return
        self._add_message("Ty", user_text, role="user")
        self.is_processing = True
        # Wyczyść poprzednie wpisy i zacznij świeżo dla nowego zapytania
        audit = self._get_audit()
        audit.clear_entries()
        audit.add_entry("QUERY", user_text[:60], "pending")
        self._pending_action_ids = {}
        self._thinking_entry_id = None
        threading.Thread(target=self._run_agent_sync, args=(user_text,), daemon=True).start()
        self._poll_timer = self.set_interval(0.1, self._poll_responses)

    def _run_agent_sync(self, user_input: str):
        if self.agent is None:
            self._response_queue.put_nowait({"type":"message","text":"[Tryb demo – brak agenta]","role":"ai"})
            self._response_queue.put_nowait({"type":"done","tokens":0})
            return

        q = self._response_queue
        original = {}

        def _patch(attr, role):
            orig = getattr(self.agent.ui, attr, None)
            if orig:
                original[attr] = orig
                def fn(text, _r=role):
                    q.put_nowait({"type":"message","text":text,"role":_r})
                setattr(self.agent.ui, attr, fn)

        # Patchuj wiadomości czatu
        _patch("ai_message", "ai")
        _patch("success",    "success")
        _patch("error",      "error")
        _patch("warning",    "error")

        # Patchuj status() — krótkie komunikaty systemowe -> audit info
        if hasattr(self.agent.ui, 'status'):
            original["status"] = self.agent.ui.status
            def tui_status(text):
                q.put_nowait({"type":"audit","action":"INFO","detail":text[:70],"status":"info"})
            self.agent.ui.status = tui_status

        # Patchuj section() — nagłówki etapów -> audit info
        if hasattr(self.agent.ui, 'section'):
            original["section"] = self.agent.ui.section
            def tui_section(title):
                q.put_nowait({"type":"audit","action":"ETAP","detail":title[:70],"status":"info"})
            self.agent.ui.section = tui_section

        # Patchuj spinner_start -> wpis "Myślę..." w audit
        if hasattr(self.agent.ui, 'spinner_start'):
            original["spinner_start"] = self.agent.ui.spinner_start
            def tui_spinner_start(msg="Analizuję..."):
                q.put_nowait({"type":"audit_thinking","msg":msg[:60]})
            self.agent.ui.spinner_start = tui_spinner_start

        # Patchuj spinner_stop -> zaktualizuj wpis "Myślę..." na done
        if hasattr(self.agent.ui, 'spinner_stop'):
            original["spinner_stop"] = self.agent.ui.spinner_stop
            def tui_spinner_stop():
                q.put_nowait({"type":"audit_thinking_done"})
            self.agent.ui.spinner_stop = tui_spinner_stop

        # Patchuj action_preview -> wpis pending z entry_id do późniejszej aktualizacji
        # Zbieraj też opisy akcji do przekazania w confirm_request
        _pending_descs: list = []
        if hasattr(self.agent.ui, 'action_preview'):
            original["action_preview"] = self.agent.ui.action_preview
            def tui_action(i, desc, _descs=_pending_descs):
                _descs.append(desc)
                q.put_nowait({"type":"audit_action_start","index":i,"detail":desc})
            self.agent.ui.action_preview = tui_action

        # Patchuj execute_action -> po wykonaniu wyślij wynik do audit
        if hasattr(self.agent, 'execute_action'):
            original["execute_action"] = self.agent.execute_action
            _action_index = [0]
            def tui_execute_action(action, _orig=self.agent.execute_action):
                _action_index[0] += 1
                idx = _action_index[0]
                result = _orig(action)
                # Skonstruuj krótki opis wyniku
                atype = action.get("type","?")
                error = False
                detail = None
                if isinstance(result, str) and result.startswith("[BŁĄD]"):
                    error = True
                    detail = result[7:60]
                elif isinstance(result, dict):
                    rtype = result.get("type","")
                    rc = result.get("returncode")
                    if rtype == "command_result":
                        stdout = result.get("stdout","").strip()[:50]
                        if rc is not None and rc != 0:
                            error = True
                            detail = f"exit {rc}" + (f": {stdout}" if stdout else "")
                        elif stdout:
                            detail = stdout.replace("\n"," ")[:60]
                    elif rtype in ("file_content","file_list"):
                        files = result.get("files",[])
                        detail = f"{len(files)} plików" if files else None
                    elif rtype == "command_timeout":
                        error = True
                        detail = "timeout"
                q.put_nowait({
                    "type": "audit_action_done",
                    "index": idx,
                    "detail": detail,
                    "error": error,
                })
                return result
            self.agent.execute_action = tui_execute_action

        # Patchuj verbose -> audit — filtruj i przypisz typ na podstawie treści
        if hasattr(self.agent.ui, 'verbose'):
            original["verbose"] = self.agent.ui.verbose
            def tui_verbose(text):
                if not text or len(text.strip()) < 3:
                    return
                t = text.strip()
                # Zamiar i uzasadnienie — wyróżniony typ
                if t.startswith("Zamiar:"):
                    q.put_nowait({"type":"audit","action":"ZAMIAR","detail":t[7:].strip()[:70],"status":"info"})
                elif t.startswith("Uzasadnienie:"):
                    q.put_nowait({"type":"audit","action":"POWÓD","detail":t[13:].strip()[:70],"status":"info"})
                # Postęp iteracji w transakcji [1/3] run_command
                elif t.startswith("[") and "]" in t:
                    q.put_nowait({"type":"audit","action":"KROK","detail":t[:70],"status":"info"})
                # Web search
                elif "internecie" in t or "yszukiwan" in t:
                    q.put_nowait({"type":"audit","action":"WEB","detail":t[:70],"status":"info"})
                # Ostrzeżenia z verbose
                elif t.startswith("⚠") or "błąd" in t.lower() or "error" in t.lower():
                    q.put_nowait({"type":"audit","action":"UWAGA","detail":t.lstrip("⚠ ")[:70],"status":"error"})
                # Limity i stagnacja
                elif "iteracj" in t.lower() or "limit" in t.lower() or "pętl" in t.lower():
                    q.put_nowait({"type":"audit","action":"LIMIT","detail":t[:70],"status":"error"})
                # Reszta — pokaż tylko gdy zawiera coś sensownego (nie sama spacja/kreska)
                elif len(t) > 5 and not t.startswith("─") and not t.startswith("•  "):
                    q.put_nowait({"type":"audit","action":"INFO","detail":t[:70],"status":"info"})
            self.agent.ui.verbose = tui_verbose

        # Potwierdzenia
        if hasattr(self.agent.ui, 'confirm_actions'):
            original["confirm_actions"] = self.agent.ui.confirm_actions
            _confirm_event = threading.Event()
            _confirm_result = [False]
            def tui_confirm(_ev=_confirm_event, _res=_confirm_result, _descs=_pending_descs):
                _ev.clear()
                _res[0] = False
                q.put_nowait({"type":"confirm_request","event":_ev,"result":_res,
                              "actions_desc": list(_descs)})
                _ev.wait()
                _descs.clear()  # Wyczyść po potwierdzeniu dla kolejnych akcji
                return _res[0]
            self.agent.ui.confirm_actions = tui_confirm

        try:
            self.agent.run(user_input)
            tokens = 0
            if hasattr(self.agent, 'conversation'):
                hist = getattr(self.agent.conversation, '_history', []) or \
                       getattr(self.agent.conversation, 'history', [])
                tokens = sum(len(str(m)) // 4 for m in hist)
            q.put_nowait({"type":"done","tokens":tokens})
        except Exception as e:
            q.put_nowait({"type":"message","text":f"[BŁĄD]: {e}","role":"error"})
            q.put_nowait({"type":"done","tokens":0})
        finally:
            for attr, orig in original.items():
                if attr == "execute_action":
                    self.agent.execute_action = orig
                else:
                    setattr(self.agent.ui, attr, orig)

    def _poll_responses(self) -> None:
        done = False
        audit = self._get_audit()
        for _ in range(30):
            try:
                msg = self._response_queue.get_nowait()
            except Exception:
                break
            mtype = msg.get("type")

            if mtype == "message":
                self._add_message("AI CLI", msg["text"], role=msg.get("role","ai"))

            elif mtype == "audit":
                audit.add_entry(
                    msg.get("action","?"),
                    msg.get("detail",""),
                    msg.get("status","pending")
                )

            elif mtype == "audit_action_start":
                # Akcja zaczyna się jako pending — zapisz entry_id do aktualizacji
                eid = audit.add_entry(
                    "ACTION",
                    msg.get("detail",""),
                    "pending"
                )
                # Zapamiętaj entry_id pod indeksem akcji żeby móc go zaktualizować
                if not hasattr(self, '_pending_action_ids'):
                    self._pending_action_ids = {}
                self._pending_action_ids[msg.get("index", 0)] = eid

            elif mtype == "audit_action_done":
                # Akcja zakończona — zaktualizuj status
                eid = getattr(self, '_pending_action_ids', {}).pop(msg.get("index", 0), None)
                if eid:
                    detail = msg.get("detail", None)
                    status = "done" if not msg.get("error") else "error"
                    audit.update_entry(eid, status, detail)

            elif mtype == "audit_thinking":
                # Spinner start -> wpis "Myślę..."
                eid = audit.add_entry("AI", msg.get("msg", "Analizuję..."), "thinking")
                self._thinking_entry_id = eid

            elif mtype == "audit_thinking_done":
                # Spinner stop -> zaktualizuj wpis "Myślę..." na done
                eid = getattr(self, '_thinking_entry_id', None)
                if eid:
                    audit.update_entry(eid, "done")
                    self._thinking_entry_id = None

            elif mtype == "confirm_request":
                # Wyślij powiadomienie systemowe jeśli włączone w ustawieniach
                notify_enabled = self.cfg.get("execution", {}).get("notify_on_confirm", True)
                if notify_enabled:
                    try:
                        import subprocess
                        actions_summary = "; ".join(msg.get("actions_desc", [])[:3]) or "wymagane potwierdzenie"
                        subprocess.Popen(
                            ["notify-send", "-u", "critical", "-t", "0",
                             "AI CLI – czeka na Ciebie", actions_summary],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    except Exception:
                        pass
                self.push_screen(
                    ConfirmDialog(
                        event=msg["event"],
                        result=msg["result"],
                        actions_desc=msg.get("actions_desc", []),
                    )
                )

            elif mtype == "done":
                self._tx_count += 1
                self._token_count += msg.get("tokens", 0)
                audit.add_entry("DONE", "Zakończono", "done")
                # Wyczyść pending actions
                if hasattr(self, '_pending_action_ids'):
                    self._pending_action_ids.clear()
                self._thinking_entry_id = None
                try:
                    self.query_one("#sidebar", Sidebar).update_session(self._tx_count, self._token_count)
                except NoMatches:
                    pass
                self.is_processing = False
                done = True
                break

        if done and self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None

    # ── Akcje ─────────────────────────────────────────────────────────────────

    def action_clear_chat(self) -> None:
        try:
            self.query_one("#chat-scroll").remove_children()
            self._add_message("System","Chat wyczyszczony.", role="system")
        except NoMatches:
            pass

    def action_focus_input(self) -> None:
        try: self.query_one("#user-input").focus()
        except NoMatches: pass

    def action_open_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_open_settings(self) -> None:
        def on_close(result):
            if result == "saved":
                self._add_message("System","Ustawienia zapisane.", role="success")
                try: self.query_one("#sidebar", Sidebar).update_model(self.cfg.get("chat_model","?"))
                except NoMatches: pass
        self.push_screen(SettingsScreen(self.cfg, self._save_config), on_close)

    def action_open_memory(self) -> None:
        def on_close(result):
            if result == "reload":
                # Odśwież — otwórz panel ponownie żeby pokazał aktualną listę
                self.call_after_refresh(self.action_open_memory)
        self.push_screen(MemoryScreen(agent=self.agent), on_close)

    def action_open_models(self) -> None:
        def on_close(result):
            if result == "saved":
                model = self.cfg.get("chat_model","?")
                self._add_message("System", f"Model zapisany: {model}", role="success")
                try: self.query_one("#sidebar", Sidebar).update_model(model)
                except NoMatches: pass
        self.push_screen(ModelScreen(self.cfg, self._save_config, self._available_models), on_close)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _save_config(self, cfg: dict):
        try:
            from core.config import save_config
            save_config(cfg)
        except Exception as e:
            self._add_message("System", f"Błąd zapisu: {e}", role="error")

    def _add_message(self, sender: str, text: str, role: str = "user"):
        try:
            scroll = self.query_one("#chat-scroll")
            scroll.mount(ChatMessage(sender, text, role))
            scroll.scroll_end(animate=False)
        except NoMatches:
            pass

    def _get_audit(self) -> AuditTrail:
        try: return self.query_one("#audit-trail", AuditTrail)
        except NoMatches: return AuditTrail()

    def watch_is_processing(self, processing: bool) -> None:
        try:
            inp = self.query_one("#user-input", Input)
            inp.placeholder = "Przetwarzam..." if processing else "W czym mogę pomóc?"
            inp.disabled = processing
            if not processing: inp.focus()
        except NoMatches:
            pass


# ─── Entry points ─────────────────────────────────────────────────────────────

def run_tui(agent, config: dict):
    AICLIApp(agent=agent, config=config).run()

def run_tui_demo():
    AICLIApp(agent=None, config={
        "chat_model": "qwen3-coder:480b-cloud",
        "ollama_host": "127.0.0.1",
        "ollama_port": 11434,
    }).run()

if __name__ == "__main__":
    run_tui_demo()
