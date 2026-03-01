import sys
from pathlib import Path
from core.config import load_config
from core.ollama import OllamaClient, OllamaConnectionError
from core.agent import AIAgent
from ui_layer.ui import UI, Colors
from ui_layer.commands import (
    cmd_prompt, cmd_logs, cmd_panel, cmd_init, cmd_config,
    cmd_model, cmd_stats, cmd_history, cmd_analyze, cmd_review,
    cmd_audit, cmd_capability, cmd_web_search, cmd_memory,
    cmd_knowledge
)

# WERSJA
__version__ = "1.4.6"


def _multiline_input() -> str:
    """
    Wczytaj input użytkownika z obsługą multiline.
    Shift+Enter = nowa linia
    Enter       = wyślij

    Czyta terminal bajt po bajcie w trybie raw.
    Shift+Enter wysyła sekwencję ESC O M  (\x1b\x4f\x4d) lub ESC [ O M.
    """
    import os
    import tty
    import termios
    import select

    # Jeśli nie TTY (pipe/redirect) — zwykły readline
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        if not line:
            raise EOFError
        return line.rstrip("\n")

    sys.stdout.write("\033[92m❯\033[0m ")
    sys.stdout.flush()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    lines: list[str] = []
    current: list[str] = []

    def read_byte() -> bytes:
        """Czytaj jeden bajt (blokująco)."""
        return os.read(fd, 1)

    def peek_bytes(n: int, timeout: float = 0.08) -> bytes:
        """Czytaj do n bajtów nieblokująco (z timeoutem)."""
        result = b""
        for _ in range(n):
            r, _, _ = select.select([fd], [], [], timeout)
            if not r:
                break
            result += os.read(fd, 1)
        return result

    def new_line():
        """Dodaj nową linię (Shift+Enter)."""
        lines.append("".join(current))
        current.clear()
        sys.stdout.write("\n\r  ")
        sys.stdout.flush()

    try:
        tty.setraw(fd)

        while True:
            b = read_byte()

            # Ctrl+C
            if b == b"\x03":
                sys.stdout.write("\n")
                sys.stdout.flush()
                raise KeyboardInterrupt

            # Ctrl+D
            if b == b"\x04":
                sys.stdout.write("\n")
                sys.stdout.flush()
                raise EOFError

            # Enter (\r lub \n) — wyślij
            if b in (b"\r", b"\n"):
                break

            # ESC — czytaj sekwencję
            if b == b"\x1b":
                rest = peek_bytes(4, timeout=0.08)

                # \x1b O M  lub  \x1b [ O M  — Shift+Enter
                if rest in (b"OM", b"[OM"):
                    new_line()
                    continue

                # Strzałki i inne sekwencje CSI — ignoruj cicho
                # (np. \x1b[A, \x1b[B, \x1b[C, \x1b[D)
                continue

            # Backspace
            if b in (b"\x7f", b"\x08"):
                if current:
                    current.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                elif lines:
                    # Cofnij do poprzedniej linii
                    prev = lines.pop()
                    current.extend(list(prev))
                    sys.stdout.write(f"\033[A\033[2K\r  {prev}")
                    sys.stdout.flush()
                continue

            # Zwykły znak (dekoduj UTF-8 wielobajtowo jeśli trzeba)
            try:
                ch = b.decode("utf-8")
            except UnicodeDecodeError:
                # Pierwszy bajt wielobajtowego UTF-8 — czytaj resztę
                if b[0] & 0xE0 == 0xC0:
                    extra = peek_bytes(1)
                elif b[0] & 0xF0 == 0xE0:
                    extra = peek_bytes(2)
                elif b[0] & 0xF8 == 0xF0:
                    extra = peek_bytes(3)
                else:
                    continue
                try:
                    ch = (b + extra).decode("utf-8")
                except UnicodeDecodeError:
                    continue

            current.append(ch)
            sys.stdout.write(ch)
            sys.stdout.flush()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    sys.stdout.write("\n")
    sys.stdout.flush()

    return "\n".join(lines + ["".join(current)])

def show_help():
    """Pokaż pomoc (bez inicjalizacji agenta)"""
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║                    AI CLI - POMOC                            ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}

{Colors.CYAN}PODSTAWOWE UŻYCIE:{Colors.RESET}
  ai <polecenie>              Wykonaj polecenie w języku naturalnym
  ai                          Tryb interaktywny
  ai init                     Zainicjalizuj projekt (utwórz .ai-context.json)

{Colors.CYAN}POLECENIA SYSTEMOWE:{Colors.RESET}
  ai panel [status|start|stop|open]
                              Panel administracyjny (web)
                              - status: sprawdź czy działa
                              - start: uruchom panel (systemd)
                              - stop: zatrzymaj panel
                              - open: otwórz w przeglądarce
                              URL: http://127.0.0.1:21650
  
  ai model                    Zarządzaj modelami (czat/embeddingi/fallback/coder/vision)
  ai prompt                   Edytuj prompt systemowy (nano)
  ai analyze                  Przeanalizuj projekt (co to jest)
  ai review                   Przegląd projektu (co poprawić)
  ai audit                    Audit trail (dlaczego AI to zrobiło)
  ai logs [...]               Zarządzaj logami diagnostycznymi
                              Subkomendy: clean, rotate
  
  ai capability [...]         Zarządzaj dozwolonymi akcjami
                              Subkomendy: list, enable, disable, reset
  
  ai web-search <zapytanie>   Szukaj w internecie ("Okno na świat")
                              Subkomendy: enable, disable, status, scrape,
                              cache, domains
  ai --index                  Zaindeksuj / przebuduj bazę wiedzy (RAG)
  ai knowledge [status|list]  Zarządzaj bazą wiedzy
                              - status: stan bazy i pliki
                              - list:   lista plików w knowledge/
  
  ai config                   Pokaż konfigurację
  ai config edit              Edytuj konfigurację (nano)
  ai stats                    Statystyki projektu
  ai history                  Historia poleceń
  ai help / --help            Ta pomoc

{Colors.CYAN}FLAGI:{Colors.RESET}
  --plan                      Tylko plan, bez wykonywania
  --dry-run                   Symulacja, bez zmian w plikach
  --yes, -y                   Pomiń potwierdzenie (NIEBEZPIECZNE!)
  --global, -g                Tryb globalny (bez projektu)
  --quiet, -q                 Cichy tryb (bez output)
  --verbose, -v               Gadliwy tryb (debug info)
  --version                   Wyświetla aktualną wersję AI CLI Agent

{Colors.CYAN}BEZPIECZEŃSTWO:{Colors.RESET}
  {Colors.RED}✗ DESTRUKCYJNE{Colors.RESET}  (delete, move, rm)           - ZAWSZE potwierdzenie
  {Colors.YELLOW}▶ MEDIA{Colors.RESET}         (download_media, convert_media) - Potwierdzenie
  {Colors.GREEN}✓ BEZPIECZNE{Colors.RESET}    (read, find, ls, curl, mkdir)   - Bez potwierdzenia

{Colors.CYAN}CAPABILITIES (kontrola per-projekt):{Colors.RESET}
  allow_execute               Wykonywanie komend systemowych
  allow_delete                Usuwanie i przenoszenie plików
  allow_git                   Operacje Git (future)
  allow_network               Dostęp do sieci (future)

{Colors.CYAN}PRZYKŁADY UŻYCIA:{Colors.RESET}

  {Colors.GRAY}# Inicjalizacja projektu{Colors.RESET}
  cd ~/Projekty/moj-app
  ai init                     # zainicjalizuj projekt w tym katalogu

  {Colors.GRAY}# Analiza projektu{Colors.RESET}
  ai prompt                   # ustaw personalizację AI
  ai co robi ten projekt      # szybka analiza
  ai review                   # głęboki przegląd

  {Colors.GRAY}# Eksploracja plików{Colors.RESET}
  ai jakie tu są pliki mp4
  ai jakie mam pliki w /media/dysk
  ai znajdź wszystkie pliki py w podfolderach

  {Colors.GRAY}# Tworzenie plików{Colors.RESET}
  ai stwórz prostą stronę HTML
  ai zrób landing page o kotach
  ai stwórz TODO app w React

  {Colors.GRAY}# Edycja{Colors.RESET}
  ai napraw błędy w app.py
  ai dodaj komentarze do funkcji
  ai zamiast Punkty użyj Kulki

  {Colors.GRAY}# Media (YouTube, audio, wideo){Colors.RESET}
  ai pobierz https://youtube.com/...
  ai pobierz i przekonwertuj na mp3 https://...
  ai przekonwertuj video.mp4 na mp3

  {Colors.GRAY}# Obrazy (konwersja, kompresja, favicon){Colors.RESET}
  ai stwórz favicon z logo.png
  ai przekonwertuj wszystkie PNG na WebP
  ai skompresuj zdjęcia w folderze
  ai zmień rozmiar obrazka na 800px szerokości
  ai pokaż info o photo.jpg

  {Colors.GRAY}# Schowek{Colors.RESET}
  ai wyjaśnij kod ze schowka
  ai napraw błąd ze schowka
  ai skopiuj wynik do schowka

  {Colors.GRAY}# Wykonywanie (bezpieczne komendy bez confirm){Colors.RESET}
  ai znajdź pliki większe niż 1MB
  ai pokaż 5 największych plików py
  ai ile linii ma każdy plik

  {Colors.GRAY}# Diagnostyka{Colors.RESET}
  ai logs                     # podsumowanie logów
  ai logs clean               # usuń stare logi (>30 dni)
  ai logs rotate              # rotacja dużych logów

  {Colors.GRAY}# Web Search ("Okno na świat"){Colors.RESET}
  ai web-search enable                    # włącz web search
  ai web-search status                    # sprawdź status i zależności
  ai web-search najnowsza wersja pandas   # szukaj bezpośrednio
  ai web-search scrape https://pypi.org/project/pandas/
  ai web-search cache clear               # wyczyść cache
  ai web-search domains add example.com  # dodaj domenę do whitelist
  {Colors.GRAY}# Auto-trigger (gdy web_search.enabled=true){Colors.RESET}
  ai jaka jest najnowsza wersja pandas   # wykryje trigger phrase → szuka

  {Colors.CYAN}Wersja: {__version__}{Colors.RESET}
    """)

def main():
    # Obsługa --help i --version przed inicjalizacją agenta
    if "--help" in sys.argv or "-h" in sys.argv:
        show_help()
        return

    if "--version" in sys.argv or "-V" in sys.argv:
        print(f"AI CLI Agent v{__version__}")
        return

    config = load_config()

    args = sys.argv[1:]

    # Flagi
    dry_run = "--dry-run" in args
    plan_only = "--plan" in args
    quiet = "--quiet" in args or "-q" in args
    verbose = "--verbose" in args or "-v" in args
    auto_confirm = "--yes" in args or "-y" in args
    global_mode = "--global" in args or "-g" in args

    # Usuń flagi z argumentów
    flags = [
        "--dry-run", "--plan",
        "--quiet", "-q",
        "--verbose", "-v",
        "--yes", "-y",
        "--global", "-g",
        "--help", "-h",
        "--version", "-V",
        "--index",
        "--reindex",
    ]
    args = [a for a in args if a not in flags]

    # UI (lekki, nie wymaga agenta)
    ui = UI(quiet=quiet, verbose=verbose, config=config)

    # =========================================================
    # POLECENIA LEKKIE - nie wymagają inicjalizacji agenta
    # (brak połączenia z Ollama, brak wykrywania projektu)
    # =========================================================

    if args and args[0] == "help":
        show_help()
        return

    if args and args[0] == "prompt":
        cmd_prompt(config)
        return

    if args and args[0] == "panel":
        cmd_panel(ui, args)
        return

    if args and args[0] == "init":
        cmd_init(ui, config)
        return

    if args and args[0] == "config":
        cmd_config(ui, config, args)
        return

    if args and args[0] == "model":
        cmd_model(config)
        return

    # web-search enable/disable/status/cache/domains nie potrzebują agenta
    if args and args[0] == "web-search":
        non_agent_subs = {"enable", "disable", "status", "cache", "domains"}
        sub = args[1] if len(args) > 1 else None
        if sub in non_agent_subs or sub is None:
            cmd_web_search(None, ui, config, args)
            return

    # memory nie potrzebuje agenta
    if args and args[0] == "memory":
        cmd_memory(ui, args[1:])
        return

    # Komendy RAG (nie wymagają agenta do pracy)
    _do_index = "--index" in sys.argv or "--reindex" in sys.argv
    if _do_index or (args and args[0] in ("knowledge", "kb")):
        cmd_knowledge(ui, config, args, do_index=_do_index)
        return

    # =========================================================
    # INICJALIZACJA AGENTA - tylko gdy naprawdę potrzebna
    # =========================================================

    client = OllamaClient(config)

    agent = AIAgent(
        client,
        config,
        dry_run=dry_run,
        plan_only=plan_only,
        quiet=quiet,
        verbose=verbose,
        auto_confirm=auto_confirm,
        global_mode=global_mode
    )

    # Przekaż logger do OllamaClient
    if agent.logger:
        client.logger = agent.logger
    
    if args and args[0] == "logs":
        cmd_logs(agent, ui, args)
        return

    if args and args[0] == "stats":
        cmd_stats(agent, ui)
        return
    
    if args and args[0] == "history":
        cmd_history(agent, ui)
        return
    
    if args and args[0] == "analyze":
        cmd_analyze(agent, ui)
        return
    
    if args and args[0] == "review":
        cmd_review(agent, ui)
        return
    
    if args and args[0] == "audit":
        cmd_audit(agent, ui)
        return
    
    if args and args[0] == "capability":
        cmd_capability(agent, ui, args)
        return

    if args and args[0] == "web-search":
        cmd_web_search(agent, ui, config, args)
        return

    if args and args[0] == "memory":
        cmd_memory(ui, args[1:])
        return

    # === TRYB INTERAKTYWNY ===

    if not args:
        # ── nagłówek powitalny ──────────────────────────────────
        if ui.use_rich and ui._console:
            from rich.panel import Panel
            from rich.text import Text
            header = Text.assemble(
                ("AI CLI ", "bold bright_cyan"),
                ("· tryb interaktywny", "bright_black"),
            )
            hints = Text.assemble(
                ("Tip: ", "bright_black"),
                ("'exit'", "bright_white"),
                (" aby wyjść  ·  spróbuj: ", "bright_black"),
                ("'jakie są tu pliki mp4'", "bright_white"),
                (" lub ", "bright_black"),
                ("'która godzina'", "bright_white"),
            )
            ui._console.print(
                Panel(hints, title=header, border_style="bright_cyan", padding=(0, 1))
            )
            ui._console.print()
        else:
            ui.section("AI CLI - Tryb interaktywny")
            print(f"{Colors.GRAY}Wpisz polecenie lub 'exit' aby wyjść{Colors.RESET}")
            print(f"{Colors.GRAY}Tip: spróbuj 'help', 'jakie są tu pliki mp4' lub 'która godzina'{Colors.RESET}\n")

        idle_time = 0

        try:
            while True:
                try:
                    if ui.use_rich and ui._console:
                        # Użyj multiline input z obsługą Shift+Enter
                        user_prompt = _multiline_input().strip()
                    else:
                        user_prompt = _multiline_input().strip()
                    idle_time = 0
                except EOFError:
                    print()
                    break

                if not user_prompt:
                    idle_time += 1
                    if idle_time == 3:
                        ui.verbose("Tip: wpisz 'help' aby zobaczyć dostępne komendy")
                    continue

                if user_prompt.lower() in ['exit', 'quit', 'q']:
                    if ui.use_rich and ui._console:
                        ui._console.print("[bright_black]  Do zobaczenia! 👋[/]")
                    else:
                        ui.status("Do zobaczenia!")
                    break
                
                # === EARLY INTERCEPT: zapamiętaj/zapisz że ... ===
                # Przechwytujemy PRZED wysłaniem do LLM
                _mem_fact = agent.global_memory.try_extract_explicit_save(user_prompt)
                if _mem_fact:
                    from project.global_memory import GlobalMemory
                    _cat = "general"
                    _lw = _mem_fact.lower()
                    if any(w in _lw for w in ["używam", "zamiast", "narzędzie", "tool"]):
                        _cat = "tool"
                    elif any(w in _lw for w in ["python", "javascript", "rust", "java"]):
                        _cat = "language"
                    elif any(w in _lw for w in ["kde", "gnome", "ubuntu", "arch", "edytor"]):
                        _cat = "environment"
                    elif any(w in _lw for w in ["jestem", "nazywam", "nick", "mieszkam"]):
                        _cat = "identity"
                    _saved = agent.global_memory.add(_mem_fact, _cat)
                    ui.success(f"💾 Zapamiętano [{_saved['id']}]: {_mem_fact}")
                    print()
                    continue

                # Obsłuż przypadkowy prefiks "ai " w trybie interaktywnym
                # Jeśli użytkownik wpisał "ai logs", "ai logs clean" itp. — obsłuż jako subkomendę
                if user_prompt.lower().startswith("ai "):
                    _subcmd_args = user_prompt.split()[1:]  # pomiń "ai"
                    _known_subcmds = {
                        "logs", "stats", "history", "analyze", "review",
                        "audit", "capability", "web-search", "memory",
                        "knowledge", "kb", "help",
                    }
                    if _subcmd_args and _subcmd_args[0].lower() in _known_subcmds:
                        _sub = _subcmd_args[0].lower()
                        if _sub == "logs":
                            cmd_logs(agent, ui, ["ai"] + _subcmd_args)
                        elif _sub == "stats":
                            cmd_stats(agent, ui)
                        elif _sub == "history":
                            cmd_history(agent, ui)
                        elif _sub == "analyze":
                            cmd_analyze(agent, ui)
                        elif _sub == "review":
                            cmd_review(agent, ui)
                        elif _sub == "audit":
                            cmd_audit(agent, ui)
                        elif _sub == "capability":
                            cmd_capability(agent, ui, ["ai"] + _subcmd_args)
                        elif _sub == "web-search":
                            cmd_web_search(agent, ui, config, ["ai"] + _subcmd_args)
                        elif _sub == "memory":
                            cmd_memory(ui, _subcmd_args[1:])
                        elif _sub in ("knowledge", "kb"):
                            cmd_knowledge(ui, config, ["ai"] + _subcmd_args, do_index=False)
                        elif _sub == "help":
                            show_help()
                        else:
                            ui.warning(f"Komenda '{_sub}' dostępna tylko poza trybem interaktywnym")
                        continue
                    else:
                        # Nie jest subkomendą — strippuj prefiks i wyślij do modelu
                        user_prompt = user_prompt[3:].lstrip()

                try:
                    agent.run(user_prompt)
                
                except OllamaConnectionError as e:
                    print()
                    ui.error("Nie można połączyć się z Ollamą!")
                    ui.verbose(f"Serwer: {e.host}:{e.port}")
                    print()
                    print(e.reason)
                    print()
                    ui.verbose("Sprawdź konfigurację:")
                    ui.verbose("  ai config")
                    ui.verbose("  ai config edit")
                
                except KeyboardInterrupt:
                    print()
                    ui.warning("Przerwano")
                    continue
                
                except Exception as e:
                    ui.error(f"Wystąpił błąd: {e}")
                    if verbose:
                        import traceback
                        traceback.print_exc()
                
                print()
                
        except KeyboardInterrupt:
            print()
            ui.status("Przerwano")
        return

    # === POJEDYNCZE POLECENIE ===
    
    user_prompt = " ".join(args)
    
    try:
        agent.run(user_prompt)
    
    except OllamaConnectionError as e:
        print()
        ui.error("Nie można połączyć się z Ollamą!")
        ui.verbose(f"Serwer: {e.host}:{e.port}")
        print()
        print(e.reason)
        print()
        ui.verbose("Sprawdź konfigurację:")
        ui.verbose("  ai config")
        ui.verbose("  ai config edit")
        sys.exit(1)
    
    except KeyboardInterrupt:
        print()
        ui.warning("Przerwano przez użytkownika")
        sys.exit(130)
    
    except Exception as e:
        ui.error(f"Wystąpił błąd: {e}")
        if verbose:
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()