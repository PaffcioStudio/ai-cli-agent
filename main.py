import sys
from pathlib import Path
from core.config import load_config
from core.ollama import OllamaClient, OllamaConnectionError
from core.agent import AIAgent
from ui_layer.ui import UI, Colors
from core.conversation_history import ConversationHistory
from ui_layer.commands import (
    cmd_prompt, cmd_logs, cmd_panel, cmd_init, cmd_config,
    cmd_model, cmd_stats, cmd_history, cmd_analyze, cmd_review,
    cmd_audit, cmd_capability, cmd_web_search, cmd_memory,
    cmd_knowledge,
    cmd_export,
    cmd_deps,          # ← DODAJ
    get_panel_url,
)

# WERSJA
__version__ = "1.5.0"


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
    import shutil

    # Jeśli nie TTY (pipe/redirect) — zwykły readline
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        if not line:
            raise EOFError
        return line.rstrip("\n")

    # Szerokość terminala — kluczowa do śledzenia zawijania wierszy
    term_cols = shutil.get_terminal_size().columns

    PROMPT_LEN = 2   # widoczna długość "❯ "
    INDENT_LEN = 2   # wcięcie "  " dla kolejnych linii (Shift+Enter)

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

    def backspace_one():
        """
        Usuń ostatni znak z current[] i cofnij kursor na ekranie.
        Obsługuje przekraczanie granicy wizualnego zawijania linii.
        """
        if not current:
            return

        offset = PROMPT_LEN if not lines else INDENT_LEN
        pos_before = offset + len(current)    # pozycja kursora przed usunięciem
        col_before  = pos_before % term_cols  # kolumna ekranowa przed usunięciem

        current.pop()

        if col_before == 0:
            # Kursor jest na początku wizualnego wiersza (zawinięcie!) —
            # trzeba wskoczyć wiersz wyżej i usunąć znak tam.
            col_after = (pos_before - 1) % term_cols
            # \033[A       — wiersz wyżej
            # \033[{n}G    — przejdź do kolumny n (1-based)
            # spacja        — nadpisz usuwany znak
            # \033[{n}G    — wróć kursor na tę samą pozycję
            sys.stdout.write(f"\033[A\033[{col_after + 1}G \033[{col_after + 1}G")
        else:
            sys.stdout.write("\b \b")

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
                    backspace_one()
                elif lines:
                    # Cofnij do poprzedniej logicznej linii (Shift+Enter)
                    prev = lines.pop()
                    current.extend(list(prev))
                    offset = PROMPT_LEN if not lines else INDENT_LEN
                    # Wróć o jeden wiersz ekranowy i odbuduj linię
                    joined = ''.join(current)
                    sys.stdout.write("\033[A\033[" + str(offset + 1) + "G\033[K" + joined)
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
    """Zwięzła pomoc — bez przykładów."""
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║                  AI CLI v{__version__} - POMOC                       ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}

{Colors.CYAN}PODSTAWOWE UŻYCIE:{Colors.RESET}
  ai <polecenie>              Wykonaj polecenie w języku naturalnym
  ai                          Tryb interaktywny
  ai init                     Zainicjalizuj projekt w bieżącym katalogu

{Colors.CYAN}POLECENIA SYSTEMOWE:{Colors.RESET}
  ai model                    Zarządzaj modelami (czat/embeddingi/fallback/coder/vision)
  ai prompt                   Edytuj prompt systemowy (nano)
  ai analyze                  Przeanalizuj projekt
  ai review                   Przegląd projektu (co poprawić)
  ai audit                    Audit trail (dlaczego AI to zrobiło)
  ai stats                    Statystyki projektu
  ai history                  Historia poleceń projektu
  ai export [plik.md]         Eksportuj sesję do pliku Markdown
                              Flagi: --all (cała historia), --operations (tabela)
  ai logs [clean|rotate]      Zarządzaj logami diagnostycznymi
  ai capability [list|enable|disable|reset]
                              Kontrola dozwolonych akcji per-projekt

{Colors.CYAN}KONFIGURACJA:{Colors.RESET}
  ai config                        Pokaż całą konfigurację
  ai config get <klucz>            Pokaż jedną wartość
  ai config set <klucz> <wartość>  Ustaw wartość (klucze przez kropkę)
  ai config unset <klucz>          Usuń klucz
  ai config list                   Płaska lista wszystkich kluczy
  ai config edit                   Edytuj w nano

{Colors.CYAN}WEB SEARCH:{Colors.RESET}
  ai web-search <zapytanie>        Szukaj w internecie
  ai web-search enable|disable     Włącz/wyłącz
  ai web-search status             Status i zależności
  ai web-search scrape <url>       Pobierz zawartość strony
  ai web-search cache clear        Wyczyść cache
  ai web-search domains add <dom>  Dodaj domenę do whitelist

{Colors.CYAN}WIEDZA (RAG):{Colors.RESET}
  ai --index                  Zaindeksuj / przebuduj bazę wiedzy
  ai knowledge [status|list]  Zarządzaj bazą wiedzy

{Colors.CYAN}HISTORIA ROZMÓW:{Colors.RESET}
  ai config set conversation.save_history true    Włącz zapis historii (domyślnie)
  ai config set conversation.save_history false   Wyłącz zapis historii
  ai config set conversation.resume_prompt false  Wyłącz pytanie o wznowienie
  ai config set conversation.max_saved_messages 40

{Colors.CYAN}PANEL WEB:{Colors.RESET}
  ai panel [status|start|stop|open|log|--help]
                                       Panel administracyjny ({get_panel_url()})

{Colors.CYAN}FLAGI:{Colors.RESET}
  --plan          Tylko plan, bez wykonywania
  --dry-run       Symulacja, bez zmian w plikach
  --yes, -y       Pomiń potwierdzenie (NIEBEZPIECZNE!)
  --global, -g    Tryb globalny (bez projektu)
  --quiet, -q     Cichy tryb
  --verbose, -v   Tryb debug
  --version       Wyświetl wersję

{Colors.CYAN}BEZPIECZEŃSTWO:{Colors.RESET}
  {Colors.RED}✗ DESTRUKCYJNE{Colors.RESET}  (delete, move, rm)              — ZAWSZE potwierdzenie
  {Colors.YELLOW}▶ EXECUTE{Colors.RESET}       (run_command, download, convert) — Potwierdzenie
  {Colors.GREEN}✓ BEZPIECZNE{Colors.RESET}    (read, find, ls, mkdir)          — Bez potwierdzenia

{Colors.GRAY}Aby zobaczyć przykłady użycia wpisz:  ai --help-all{Colors.RESET}
    """)


def show_help_all():
    """Pełna pomoc z przykładami."""
    show_help()
    print(f"""{Colors.CYAN}PRZYKŁADY UŻYCIA:{Colors.RESET}

  {Colors.GRAY}# Projekt{Colors.RESET}
  cd ~/Projekty/moj-app && ai init
  ai co robi ten projekt
  ai review

  {Colors.GRAY}# Pliki{Colors.RESET}
  ai jakie tu są pliki mp4
  ai znajdź wszystkie pliki py w podfolderach
  ai pokaż 5 największych plików

  {Colors.GRAY}# Tworzenie i edycja{Colors.RESET}
  ai stwórz prostą stronę HTML
  ai stwórz TODO app w React
  ai napraw błędy w app.py
  ai dodaj komentarze do funkcji
  ai zamiast Punkty użyj Kulki

  {Colors.GRAY}# Media{Colors.RESET}
  ai pobierz https://youtube.com/...
  ai pobierz i przekonwertuj na mp3 https://...
  ai przekonwertuj video.mp4 na mp3
  ai stwórz favicon z logo.png
  ai przekonwertuj wszystkie PNG na WebP
  ai skompresuj zdjęcia w folderze

  {Colors.GRAY}# Schowek{Colors.RESET}
  ai wyjaśnij kod ze schowka
  ai napraw błąd ze schowka
  ai skopiuj wynik do schowka

  {Colors.GRAY}# Web Search{Colors.RESET}
  ai web-search enable
  ai jaka jest najnowsza wersja pandas
  ai web-search scrape https://pypi.org/project/pandas/

  {Colors.GRAY}# Konfiguracja (klucze przez kropkę){Colors.RESET}
  ai config set nick Paffcio
  ai config set execution.timeout_seconds 60
  ai config set web_search.enabled true
  ai config set conversation.save_history false
  ai config unset web_search.brave_api_key
  ai config get execution.command_output_limit
  ai config list

  {Colors.GRAY}# Diagnostyka{Colors.RESET}
  ai logs
  ai logs clean
  ai audit

  {Colors.CYAN}Wersja: {__version__}{Colors.RESET}
    """)


def main():
    # Obsługa --help i --version przed inicjalizacją agenta
    if "--help-all" in sys.argv or "--examples" in sys.argv:
        show_help_all()
        return

    # Jeśli to 'ai panel --help' - przekaż do cmd_panel, nie globalny help
    _raw = sys.argv[1:]
    if len(_raw) >= 2 and _raw[0] == "panel" and _raw[1] in ("--help", "-h", "help"):
        config = load_config()
        ui = UI(quiet=False, verbose=False, config=config)
        cmd_panel(ui, _raw)
        return

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
        "--help-all", "--examples",
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

    # deps nie potrzebuje agenta
    if args and args[0] == "deps":
        cmd_deps(ui, config)
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

    # =========================================================
    # WZNOWIENIE ROZMOWY
    # =========================================================
    _resume_cfg = config.get("conversation", {})
    _save_history = _resume_cfg.get("save_history", True)
    _resume_prompt = _resume_cfg.get("resume_prompt", True)
    _is_system_cmd = bool(args and args[0] in {
        "logs", "stats", "history", "analyze", "review",
        "audit", "capability", "web-search", "memory", "knowledge", "kb"
    })

    if (
        _save_history
        and _resume_prompt
        and not _is_system_cmd
        and not global_mode
        and agent.conv_history is not None
        and agent.conv_history.exists()
    ):
        _last_ts = agent.conv_history.last_timestamp()
        _preview = agent.conv_history.last_exchange_preview()
        print()
        if ui.use_rich and ui._console:
            from rich.panel import Panel
            from rich.text import Text as RichText
            _info = RichText()
            _info.append("Znaleziono historię rozmowy", style="bold bright_cyan")
            if _last_ts:
                _info.append(f"  ({_last_ts})", style="bright_black")
            if _preview:
                _info.append(f'\nOstatnie: "{_preview}"', style="bright_black")
            _info.append("\n\nCzy wznowić poprzednią rozmowę?  ", style="bright_white")
            _info.append("[T/n]", style="bright_yellow")
            ui._console.print(Panel(_info, border_style="bright_cyan", padding=(0, 1)))
        else:
            ts_str = f" ({_last_ts})" if _last_ts else ""
            print(f"\033[96m► Znaleziono historię rozmowy{ts_str}\033[0m")
            if _preview:
                print(f'  Ostatnie: "{_preview}"')
            print("\033[93mCzy wznowić poprzednią rozmowę? [T/n]\033[0m ", end="", flush=True)

        try:
            _answer = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            _answer = "t"

        if _answer in ("", "t", "tak", "y", "yes"):
            _hist_msgs = agent.conv_history.to_conversation_messages()
            for _m in _hist_msgs:
                if _m["role"] == "user":
                    agent.conversation.add_user_message(_m["content"])
                elif _m["role"] == "assistant":
                    agent.conversation.add_ai_message(_m["content"])
            if not quiet:
                ui.success(f"Wczytano {len(_hist_msgs)} wiadomości z historii")
        else:
            agent.conv_history.clear()
            if not quiet:
                ui.status("Historia wyczyszczona — nowa sesja")
        print()

    
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

    if args and args[0] == "export":
        cmd_export(agent, ui, args)
        return

    if args and args[0] == "web-search":
        cmd_web_search(agent, ui, config, args)
        return

    if args and args[0] == "memory":
        cmd_memory(ui, args[1:])
        return

    # === TRYB INTERAKTYWNY ===

    if not args:
        # ── Textual TUI (domyślny tryb interaktywny) ────────────
        try:
            from ui_layer.tui_app import run_tui
            run_tui(agent, config)
            return
        except ImportError:
            pass  # brak textual – fallback do terminala

        # ── nagłówek powitalny (fallback) ───────────────────────
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
                        "knowledge", "kb", "export", "help",
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
                        elif _sub == "export":
                            cmd_export(agent, ui, _subcmd_args)
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
