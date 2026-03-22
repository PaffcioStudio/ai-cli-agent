"""
CLI Commands - komendy systemowe AI CLI Agent.

Wydzielone z main.py dla czytelności.
"""

import sys
import json
import socket
import subprocess
import webbrowser
from pathlib import Path
from ui_layer.ui import UI, Colors
from core.config import CONFIG_FILE, save_config

PANEL_PORT = 21650


def get_panel_url() -> str:
    """Zwraca URL panelu z lokalnym IP zamiast 127.0.0.1."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return f"http://{ip}:{PANEL_PORT}"


def cmd_prompt(config):
    """ai prompt - edycja system promptu w nano"""
    ui = UI(quiet=False, verbose=False, config=config)
    
    PROMPT_FILE = Path.home() / ".config" / "ai" / "prompt.txt"
    PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if not PROMPT_FILE.exists():
        PROMPT_FILE.write_text("""# System Prompt dla AI CLI Agent
#
# Ten plik wpływa na zachowanie AI:
# - styl odpowiedzi
# - preferencje technologiczne
# - ton rozmowy
# - zasady i zakazy
#
# NIE omija to zabezpieczeń ani capabilities.
# NIE jest to prompt injection.
#
# Przykłady:
# - Zawsze używaj polskich nazw zmiennych
# - Preferuj TypeScript zamiast JavaScript
# - Dodawaj obszerne komentarze do kodu
# - Unikaj skrótów w nazwach funkcji
#
# Zacznij pisać poniżej:

""")
    
    try:
        subprocess.run(["nano", str(PROMPT_FILE)])
        ui.success("System prompt zapisany")
        ui.verbose(f"Lokalizacja: {PROMPT_FILE}")
    except FileNotFoundError:
        ui.error("Edytor 'nano' nie jest zainstalowany")
        ui.verbose("Zainstaluj nano: sudo apt install nano (lub yum/pacman)")
    except KeyboardInterrupt:
        print()
        ui.status("Anulowano edycję")


def cmd_logs(agent, ui, args):
    """ai logs [clean|rotate] - zarządzanie logami"""
    if not agent.logger:
        ui.error("Logger niedostępny")
        ui.verbose("Logi dostępne tylko w trybie projektowym")
        return
    
    if len(args) > 1 and args[1] == "clean":
        removed = agent.logger.cleanup_old_logs(days=30)
        ui.success(f"Usunięto {len(removed)} starych logów")
        return
    
    if len(args) > 1 and args[1] == "rotate":
        agent.logger.rotate_logs(max_size_mb=10)
        ui.success("Rotacja logów zakończona")
        return
    
    # Podsumowanie
    summary = agent.logger.get_logs_summary()
    
    ui.section("Podsumowanie logów")
    ui.success(f"Cache: {summary['cache_dir']}")
    
    if summary['diagnostic_logs']:
        print()
        ui.verbose("Logi diagnostyczne:")
        for log in summary['diagnostic_logs']:
            ui.verbose(f"  • {log['name']}: {log['size_mb']} MB (ostatnia modyfikacja: {log['modified'][:10]})")
    
    ui.success(f"\nCałkowity rozmiar: {summary['total_size_mb']} MB")
    
    if summary.get('project_logs_dir'):
        print()
        ui.success(f"Audit trail projektu: {summary['project_logs_dir']}")
        if summary.get('project_operations_count'):
            ui.verbose(f"  Operacji zalogowanych: {summary['project_operations_count']}")
    
    print()
    ui.verbose("Komendy:")
    ui.verbose("  ai logs clean  - usuń stare logi (>30 dni)")
    ui.verbose("  ai logs rotate - rotacja dużych logów")


def cmd_panel(ui, args):
    """ai panel [status|start|stop|open|log|--help] - panel webowy"""
    sub = args[1] if len(args) > 1 else "status"

    SERVICE_NAME = "ai-panel.service"
    SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
    SERVICE_FILE = SYSTEMD_USER_DIR / SERVICE_NAME

    if sub in ("--help", "-h", "help"):
        lines = [
            "",
            f"  {Colors.CYAN}ai panel{Colors.RESET} – zarządzanie web panelem AI CLI (port 21650)",
            "",
            f"  {Colors.BOLD}Komendy:{Colors.RESET}",
            f"    {Colors.GREEN}status{Colors.RESET}   Pokaż stan serwisu systemd (domyślna)",
            f"    {Colors.GREEN}start{Colors.RESET}    Uruchom panel",
            f"    {Colors.GREEN}stop{Colors.RESET}     Zatrzymaj panel",
            f"    {Colors.GREEN}open{Colors.RESET}     Otwórz panel w przeglądarce",
            f"    {Colors.GREEN}log{Colors.RESET}      Pokaż ostatnie logi panelu",
            f"    {Colors.GREEN}--help{Colors.RESET}   Ta pomoc",
            "",
            f"  {Colors.BOLD}Przykłady:{Colors.RESET}",
            f"    ai panel             # sprawdź status",
            f"    ai panel start       # uruchom",
            f"    ai panel log         # ostatnie 30 linii logów",
            f"    ai panel log 50      # ostatnie 50 linii logów",
            "",
            f"  {Colors.BOLD}URL:{Colors.RESET}  {get_panel_url()}",
            "",
        ]
        print("\n".join(lines))
        return

    if sub == "status":
        if not SERVICE_FILE.exists():
            ui.warning("Systemd service nie jest zainstalowany")
            ui.verbose("Panel nie został skonfigurowany jako service")
            ui.verbose("")
            ui.verbose("Aby uruchomić panel ręcznie:")
            ui.verbose("  python3 ~/.local/share/ai-cli-agent/web/server.py")
            ui.verbose("")
            ui.verbose("Aby zainstalować service:")
            ui.verbose("  Uruchom ponownie instalator: ~/.local/share/ai-cli-agent/install-cli.sh")
            return

        try:
            subprocess.run(
                ["systemctl", "--user", "status", SERVICE_NAME],
                check=False
            )
        except KeyboardInterrupt:
            print()
            return
        except FileNotFoundError:
            ui.error("systemctl nie jest dostępne")
        return

    if sub == "start":
        if not SERVICE_FILE.exists():
            ui.error("Systemd service nie jest zainstalowany")
            ui.verbose("Uruchom panel ręcznie:")
            ui.verbose("  python3 ~/.local/share/ai-cli-agent/web/server.py")
            return

        try:
            result = subprocess.run(
                ["systemctl", "--user", "start", SERVICE_NAME],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                ui.success("✓ Panel uruchomiony")
                ui.verbose(f"URL: {get_panel_url()}")
            else:
                ui.error(f"Nie udało się uruchomić: {result.stderr}")
        except FileNotFoundError:
            ui.error("systemctl nie jest dostępne")
        return

    if sub == "stop":
        if not SERVICE_FILE.exists():
            ui.warning("Systemd service nie jest zainstalowany")
            return

        try:
            result = subprocess.run(
                ["systemctl", "--user", "stop", SERVICE_NAME],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                ui.success("✓ Panel zatrzymany")
            else:
                ui.error(f"Nie udało się zatrzymać: {result.stderr}")
        except FileNotFoundError:
            ui.error("systemctl nie jest dostępne")
        return

    if sub == "open":
        webbrowser.open(get_panel_url())
        ui.success("✓ Otwarto panel w przeglądarce")
        return

    if sub == "log":
        _cmd_panel_log(ui, args)
        return

    ui.error(f"Nieznana subkomenda: {sub}")
    ui.verbose("Użycie: ai panel [status|start|stop|open|log|--help]")


def _cmd_panel_log(ui, args):
    """Wyświetla logi panelu - z fallbackiem dla systemów bez journalctl."""
    # Opcjonalna liczba linii jako drugi argument, np. ai panel log 50
    try:
        n = int(args[2]) if len(args) > 2 else 30
        n = max(1, min(n, 1000))
    except (ValueError, IndexError):
        n = 30

    SERVICE_NAME = "ai-panel.service"

    # Strategia 1: journalctl (systemd, Linux)
    if _has_cmd("journalctl"):
        try:
            subprocess.run(
                ["journalctl", "--user", "-u", SERVICE_NAME,
                 "-n", str(n), "--no-pager"],
                check=False
            )
            return
        except (FileNotFoundError, KeyboardInterrupt):
            pass

    # Strategia 2: plik web.log z web panelu (~/.config/ai/web/logs/web.log)
    web_log = Path.home() / ".config" / "ai" / "web" / "logs" / "web.log"
    if web_log.exists():
        ui.verbose(f"journalctl niedostępny – czytam {web_log}")
        try:
            lines = web_log.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines[-n:]:
                print(line)
            return
        except Exception as e:
            ui.error(f"Błąd odczytu web.log: {e}")

    # Strategia 3: systemd journal bezpośrednio przez plik (macOS/brak journalctl)
    journal_paths = [
        Path("/var/log/syslog"),          # Ubuntu/Debian bez journald
        Path("/var/log/messages"),        # RHEL/CentOS/openSUSE
        Path("/var/log/system.log"),      # macOS
        Path.home() / ".local" / "share" / "systemd" / "coredump",
    ]
    for log_path in journal_paths:
        if log_path.exists() and log_path.is_file():
            ui.verbose(f"journalctl niedostępny – szukam wpisów w {log_path}")
            try:
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                # Filtruj tylko linie zawierające nazwę serwisu
                relevant = [l for l in lines if "ai-panel" in l or "ai_panel" in l or "server.py" in l]
                if relevant:
                    for line in relevant[-n:]:
                        print(line)
                    return
            except PermissionError:
                pass  # Brak dostępu - próbuj dalej

    # Nic nie znaleziono
    ui.warning("Brak logów – journalctl niedostępny i nie znaleziono pliku web.log")
    ui.verbose("")
    ui.verbose("Logi web panelu będą dostępne po restarcie serwisu w:")
    ui.verbose(f"  {web_log}")
    ui.verbose("")
    ui.verbose("Możesz też uruchomić panel ręcznie żeby zobaczyć output:")
    ui.verbose("  python3 ~/.local/share/ai-cli-agent/web/server.py")


def _has_cmd(name: str) -> bool:
    """Sprawdza czy komenda jest dostępna w PATH."""
    import shutil as _shutil
    return _shutil.which(name) is not None


def cmd_init(ui, config):
    """ai init - inicjalizacja projektu"""
    import os
    from project.project_memory import ProjectMemory
    
    cwd = Path.cwd()
    home = Path.home()
    
    if cwd == home:
        ui.error("⚠ Nie można inicjalizować projektu w katalogu domowym")
        ui.verbose("Przejdź do katalogu projektu i spróbuj ponownie")
        ui.verbose("Przykład:")
        ui.verbose("  cd ~/Projekty/moj-projekt")
        ui.verbose("  ai init")
        return
    
    context_file = cwd / ".ai-context.json"
    
    if context_file.exists():
        ui.warning("Projekt już zainicjalizowany")
        ui.verbose(f"Plik istnieje: {context_file}")
        
        try:
            response = input(f"\n{Colors.YELLOW}Nadpisać istniejącą konfigurację? [t/N]: {Colors.RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            ui.status("Anulowano")
            return
        
        if response not in ['t', 'tak', 'y', 'yes']:
            ui.status("Anulowano")
            return
    
    memory = ProjectMemory(cwd, config=config)
    memory.data["project_root"] = str(cwd)
    memory._save()
    
    ui.success("✓ Projekt zainicjalizowany")
    ui.verbose(f"📁 Katalog projektu: {cwd}")
    ui.verbose(f"📄 Utworzono: {context_file}")
    
    print()
    ui.verbose("Następne kroki:")
    ui.verbose("  ai analyze          # przeanalizuj strukturę projektu")
    ui.verbose("  ai prompt           # ustaw personalizację AI")
    ui.verbose("  ai capability list  # sprawdź dozwolone akcje")


def _config_get_nested(cfg: dict, key_path: str):
    """Pobierz wartość z zagnieżdżonego klucza, np. 'execution.timeout_seconds'"""
    parts = key_path.split(".")
    node = cfg
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return None, False
        node = node[part]
    return node, True


def _config_set_nested(cfg: dict, key_path: str, value) -> bool:
    """Ustaw wartość w zagnieżdżonym kluczu. Tworzy pośrednie słowniki."""
    parts = key_path.split(".")
    node = cfg
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value
    return True


def _config_unset_nested(cfg: dict, key_path: str) -> bool:
    """Usuń klucz z zagnieżdżonego słownika. Zwraca True jeśli usunięto."""
    parts = key_path.split(".")
    node = cfg
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    if parts[-1] in node:
        del node[parts[-1]]
        return True
    return False


def _parse_config_value(raw: str):
    """Próbuje zamienić string na właściwy typ Pythona."""
    if raw.lower() == "true":  return True
    if raw.lower() == "false": return False
    if raw.lower() in ("null", "none"): return None
    try: return int(raw)
    except ValueError: pass
    try: return float(raw)
    except ValueError: pass
    # Tablica JSON: ["a","b"]
    if raw.startswith("["):
        import json as _j
        try: return _j.loads(raw)
        except Exception: pass
    return raw  # zostaw jako string


def _config_list_keys(cfg: dict, prefix: str = "") -> list:
    """Zwróć płaską listę wszystkich kluczy w formacie 'a.b.c'."""
    keys = []
    for k, v in cfg.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.extend(_config_list_keys(v, full))
        else:
            keys.append((full, v))
    return keys


def cmd_config(ui, config, args):
    """
    ai config                        — pokaż całą konfigurację
    ai config get <klucz>            — pokaż jedną wartość
    ai config set <klucz> <wartość>  — ustaw wartość (tworzy zagnieżdżone klucze)
    ai config unset <klucz>          — usuń klucz
    ai config list                   — płaska lista wszystkich kluczy i wartości
    ai config edit                   — otwórz w nano (jak poprzednio)

    Klucze zagnieżdżone: execution.timeout_seconds, web_search.enabled itp.
    Typy: true/false, liczby, null, ["tablica","json"] — auto-konwersja.

    Przykłady:
      ai config set nick Paffcio
      ai config set execution.timeout_seconds 60
      ai config set web_search.enabled true
      ai config set execution.command_output_limit 8000
      ai config unset web_search.brave_api_key
      ai config get execution.timeout_seconds
    """
    sub = args[1] if len(args) > 1 else None

    # --- SHOW (domyślne) ---
    if sub is None:
        print(json.dumps(config, indent=2, ensure_ascii=False))
        return

    # --- EDIT ---
    if sub == "edit":
        subprocess.run(["nano", str(CONFIG_FILE)])
        return

    # --- LIST ---
    if sub == "list":
        pairs = _config_list_keys(config)
        width = max((len(k) for k, _ in pairs), default=0)
        for k, v in pairs:
            ui.success(f"{k:<{width}}  =  {json.dumps(v, ensure_ascii=False)}")
        return

    # --- GET ---
    if sub == "get":
        if len(args) < 3:
            ui.error("Użycie: ai config get <klucz>")
            ui.verbose("Przykład: ai config get execution.timeout_seconds")
            return
        key = args[2]
        val, found = _config_get_nested(config, key)
        if not found:
            ui.error(f"Klucz '{key}' nie istnieje w konfiguracji")
            return
        print(json.dumps(val, indent=2, ensure_ascii=False))
        return

    # --- SET ---
    if sub == "set":
        if len(args) < 4:
            ui.error("Użycie: ai config set <klucz> <wartość>")
            ui.verbose("Przykłady:")
            ui.verbose("  ai config set nick Paffcio")
            ui.verbose("  ai config set execution.timeout_seconds 60")
            ui.verbose("  ai config set web_search.enabled true")
            return
        key   = args[2]
        value = _parse_config_value(args[3])
        old_val, existed = _config_get_nested(config, key)
        _config_set_nested(config, key, value)
        save_config(config)
        if existed:
            ui.success(f"Zaktualizowano: {key}")
            ui.verbose(f"  {json.dumps(old_val, ensure_ascii=False)}  →  {json.dumps(value, ensure_ascii=False)}")
        else:
            ui.success(f"Dodano: {key} = {json.dumps(value, ensure_ascii=False)}")
        return

    # --- UNSET ---
    if sub == "unset":
        if len(args) < 3:
            ui.error("Użycie: ai config unset <klucz>")
            return
        key = args[2]
        removed = _config_unset_nested(config, key)
        if removed:
            save_config(config)
            ui.success(f"Usunięto klucz: {key}")
        else:
            ui.error(f"Klucz '{key}' nie istnieje — nic nie zmieniono")
        return

    # --- NIEZNANA KOMENDA ---
    ui.error(f"Nieznana subkomenda: '{sub}'")
    ui.verbose("Dostępne: get, set, unset, list, edit")
    ui.verbose("Lub samo 'ai config' żeby zobaczyć całą konfigurację")


def cmd_model(config):
    """ai model - wybór modelu Ollama"""
    from core.model_manager import interactive_model_selection
    interactive_model_selection(config)


def cmd_stats(agent, ui):
    """ai stats - statystyki projektu"""
    if agent.memory is None:
        ui.error("Polecenie 'stats' dostępne tylko w trybie projektowym")
        ui.verbose("Przejdź do katalogu z projektem")
        return
    
    stats = agent.memory.get_stats()
    
    ui.section("Statystyki projektu")
    ui.success(f"Typ: {stats['project_type'] or 'nieznany'}")
    ui.success(f"Technologie: {', '.join(stats['tech_stack']) or 'brak'}")
    ui.success(f"Edycji plików: {stats['total_edits']}")
    ui.success(f"Plików dotknięto: {stats['files_touched']}")
    ui.success(f"Decyzji podjęto: {stats['decisions_count']}")
    ui.success(f"Wiek projektu: {stats['age_days']} dni")


def cmd_history(agent, ui):
    """ai history - historia poleceń"""
    if agent.memory is None:
        ui.error("Polecenie 'history' dostępne tylko w trybie projektowym")
        ui.verbose("Przejdź do katalogu z projektem")
        return
    
    ui.section("Historia poleceń")
    decisions = agent.memory.data.get("decisions", [])
    
    if not decisions:
        ui.warning("Brak historii poleceń dla tego projektu")
        return
    
    for i, decision in enumerate(decisions[-10:], 1):
        timestamp = decision["timestamp"][:19]
        ui.success(f"{i}. [{timestamp}] {decision['command']}")
        
        if decision.get("intent"):
            ui.verbose(f"   Intent: {decision['intent']}")
        
        ui.verbose(f"   Akcji: {decision['actions_count']}")


def cmd_analyze(agent, ui):
    """ai analyze - analiza projektu"""
    if agent.analyzer is None:
        ui.error("Polecenie 'analyze' dostępne tylko w trybie projektowym")
        ui.verbose("Przejdź do katalogu z projektem")
        return
    
    ui.spinner_start("Analizuję projekt...")
    try:
        summary = agent.analyzer.get_summary()
        ui.spinner_stop()
        ui.section("Analiza projektu")
        print(summary)
    except Exception as e:
        ui.spinner_stop()
        ui.error(f"Nie udało się przeanalizować projektu: {e}")


def cmd_review(agent, ui):
    """ai review - przegląd projektu"""
    if agent.reviewer is None:
        ui.error("Polecenie 'review' dostępne tylko w trybie projektowym")
        ui.verbose("Przejdź do katalogu z projektem")
        return
    
    ui.spinner_start("Przeprowadzam przegląd...")
    try:
        review = agent.reviewer.review()
        ui.spinner_stop()
        ui.section("Przegląd projektu")
        print(agent.reviewer.format_review(review))
    except Exception as e:
        ui.spinner_stop()
        ui.error(f"Nie udało się przeprowadzić przeglądu: {e}")


def cmd_audit(agent, ui):
    """ai audit - audit trail"""
    if agent.memory is None:
        ui.error("Polecenie 'audit' dostępne tylko w trybie projektowym")
        ui.verbose("Przejdź do katalogu z projektem")
        return
    
    ui.section("Audit Trail - Ostatnie decyzje AI")
    decisions = agent.memory.data.get("decisions", [])[-5:]
    
    if not decisions:
        ui.warning("Brak historii decyzji")
        return
    
    for i, decision in enumerate(decisions, 1):
        timestamp = decision["timestamp"][:19]
        command = decision["command"]
        intent = decision.get("intent", "nieznany")
        actions = decision.get("actions_count", 0)
        
        print()
        ui.success(f"{i}. [{timestamp}]")
        ui.verbose(f"   Polecenie: {command}")
        ui.verbose(f"   Rozpoznany zamiar: {intent}")
        ui.verbose(f"   Akcji wykonano: {actions}")
    
    # Statystyki intencji
    intents = [d.get("intent") for d in agent.memory.data.get("decisions", []) if d.get("intent")]
    if intents:
        from collections import Counter
        intent_counts = Counter(intents)
        
        print()
        ui.section("Rozkład intencji")
        for intent, count in intent_counts.most_common(5):
            ui.verbose(f"  {intent}: {count} razy")


def cmd_capability(agent, ui, args):
    """ai capability [list|enable|disable|reset] - zarządzanie capabilities"""
    if agent.capabilities is None or agent.memory is None:
        ui.error("Polecenie 'capability' dostępne tylko w trybie projektowym")
        ui.verbose("Przejdź do katalogu z projektem")
        return
    
    if len(args) == 1:
        ui.section("Capabilities projektu")
        print(agent.capabilities.get_summary())
        
        risky = agent.capabilities.get_risky_actions_enabled()
        if risky:
            print()
            ui.warning("Ryzykowne akcje WŁĄCZONE:")
            for r in risky:
                ui.verbose(f"  ⚠ {r}")
            print()
            ui.verbose("Rozważ wyłączenie jeśli nie są potrzebne:")
            ui.verbose("  ai capability disable allow_execute")
            ui.verbose("  ai capability disable allow_delete")
        
        return
    
    subcmd = args[1]
    
    if subcmd == "list":
        print(agent.capabilities.get_summary())
    
    elif subcmd == "enable" and len(args) > 2:
        cap_name = args[2]
        try:
            agent.capabilities.set_capability(cap_name, True)
            agent.memory._save()
            ui.success(f"✓ Włączono capability: {cap_name}")
            
            desc = agent.capabilities.CAPABILITY_DESCRIPTIONS.get(cap_name)
            if desc:
                ui.verbose(f"  {desc}")
            
            if cap_name in ["allow_execute", "allow_delete"]:
                ui.warning("To ryzykowne capability - używaj ostrożnie!")
        except ValueError as e:
            ui.error(str(e))
    
    elif subcmd == "disable" and len(args) > 2:
        cap_name = args[2]
        try:
            agent.capabilities.set_capability(cap_name, False)
            agent.memory._save()
            ui.warning(f"✗ Wyłączono capability: {cap_name}")
            
            disabled = agent.capabilities.get_disabled_actions()
            if disabled:
                ui.verbose("Wyłączone akcje:")
                for action in disabled:
                    ui.verbose(f"  - {action}")
        except ValueError as e:
            ui.error(str(e))
    
    elif subcmd == "reset":
        ui.warning("Resetowanie do domyślnych capabilities...")
        agent.memory.data["capabilities"] = agent.capabilities.DEFAULT_CAPABILITIES.copy()
        agent.memory._save()
        agent.capabilities.capabilities = agent.capabilities.DEFAULT_CAPABILITIES.copy()
        ui.success("✓ Reset do domyślnych wartości")
    
    else:
        ui.error("Użycie: ai capability [list|enable|disable|reset] <nazwa>")

def cmd_web_search(agent, ui, config, args):
    """
    ai web-search <zapytanie>         - Wyszukaj w internecie
    ai web-search enable              - Włącz web search
    ai web-search disable             - Wyłącz web search
    ai web-search status              - Status silnika
    ai web-search cache clear         - Wyczyść cache
    ai web-search domains             - Pokaż/edytuj whitelist domen
    ai web-search scrape <url>        - Pobierz i wyświetl treść strony
    """
    from tasks.web_search import WebSearchEngine, WebSearchError, RateLimitError, DomainBlockedError

    sub = args[1] if len(args) > 1 else None

    # ── enable / disable ───────────────────────────────────────────────────────
    if sub == "enable":
        config.setdefault("web_search", {})["enabled"] = True
        save_config(config)
        ui.success("✓ Web search włączony")
        ui.verbose("Uruchom: ai web-search status  aby sprawdzić stan")
        ui.verbose("")
        ui.verbose("Przykłady:")
        ui.verbose("  ai jaka jest najnowsza wersja pandas")
        ui.verbose("  ai web-search co nowego w Python 3.13")
        return

    if sub == "disable":
        config.setdefault("web_search", {})["enabled"] = False
        save_config(config)
        ui.warning("✗ Web search wyłączony")
        return

    # ── status ─────────────────────────────────────────────────────────────────
    if sub == "status":
        engine = WebSearchEngine(config)
        status = engine.get_status()

        ui.section("Web Search – Status")

        enabled_str = f"{Colors.GREEN}✓ WŁĄCZONY{Colors.RESET}" if status["enabled"] else f"{Colors.RED}✗ WYŁĄCZONY{Colors.RESET}"
        print(f"  Status:       {enabled_str}")
        print(f"  Silnik:       {status['engine']}")
        print(f"  Max wyników:  {status['max_results']}")
        print(f"  Cache TTL:    {status['cache_ttl_hours']}h")
        print(f"  Potwierdzenie dla nieznanych domen: {'tak' if status['require_confirmation'] else 'nie'}")

        print()
        print(f"  Rate limit:   {status['rate_limiter']['remaining']}/{status['rate_limiter']['max_per_minute']} zapytań pozostało")
        cache = status["cache"]
        print(f"  Cache:        {cache['entries']} wpisów ({cache['size_kb']} KB) → {cache['cache_dir']}")

        print()
        deps = status["dependencies"]
        print(f"  Zależności:")
        for pkg, ok in deps.items():
            icon = f"{Colors.GREEN}✓{Colors.RESET}" if ok else f"{Colors.RED}✗{Colors.RESET}"
            print(f"    {icon} {pkg}")

        missing = engine.ensure_dependencies()
        if missing:
            print()
            ui.warning(f"Brakujące pakiety: {', '.join(missing)}")
            ui.verbose(f"Zainstaluj: pip install {' '.join(missing)}")

        print()
        print(f"  Whitelist domen ({len(status['allowed_domains'])}):")
        for domain in status["allowed_domains"]:
            print(f"    • {domain}")

        if not status["enabled"]:
            print()
            ui.verbose("Aby włączyć: ai web-search enable")
        return

    # ── cache clear ────────────────────────────────────────────────────────────
    if sub == "cache":
        action = args[2] if len(args) > 2 else None
        if action == "clear":
            engine = WebSearchEngine(config)
            engine.cache.clear()
            ui.success("✓ Cache wyczyszczony")
        else:
            engine = WebSearchEngine(config)
            stats = engine.cache.stats()
            ui.section("Cache statystyki")
            print(f"  Wpisów:   {stats['entries']}")
            print(f"  Rozmiar:  {stats['size_kb']} KB")
            print(f"  Lokalizacja: {stats['cache_dir']}")
            ui.verbose("Wyczyść: ai web-search cache clear")
        return

    # ── domains ────────────────────────────────────────────────────────────────
    if sub == "domains":
        ws = config.get("web_search", {})
        domains = ws.get("allowed_domains", WebSearchEngine.DEFAULT_ALLOWED_DOMAINS)

        if len(args) > 2:
            action = args[2]
            domain = args[3] if len(args) > 3 else None

            if action == "add" and domain:
                if domain not in domains:
                    domains.append(domain)
                    config.setdefault("web_search", {})["allowed_domains"] = domains
                    save_config(config)
                    ui.success(f"✓ Dodano domenę: {domain}")
                else:
                    ui.warning(f"Domena już na liście: {domain}")
                return

            if action == "remove" and domain:
                if domain in domains:
                    domains.remove(domain)
                    config.setdefault("web_search", {})["allowed_domains"] = domains
                    save_config(config)
                    ui.warning(f"✗ Usunięto domenę: {domain}")
                else:
                    ui.error(f"Nie znaleziono domeny: {domain}")
                return

        ui.section("Whitelist domen")
        for i, d in enumerate(domains, 1):
            print(f"  {i:2}. {d}")
        print()
        ui.verbose("Dodaj domenę:  ai web-search domains add <domena>")
        ui.verbose("Usuń domenę:   ai web-search domains remove <domena>")
        return

    # ── scrape <url> ───────────────────────────────────────────────────────────
    if sub == "scrape":
        url = args[2] if len(args) > 2 else None
        if not url:
            ui.error("Użycie: ai web-search scrape <url>")
            return

        engine = WebSearchEngine(config)
        missing = engine.ensure_dependencies()
        if missing:
            ui.error(f"Brakujące pakiety: pip install {' '.join(missing)}")
            return

        # Sprawdź whitelist (lub pytaj)
        if not engine.is_domain_allowed(url):
            import urllib.parse
            domain = urllib.parse.urlparse(url).netloc
            if engine.require_confirmation:
                try:
                    response = input(
                        f"\n{Colors.YELLOW}⚠ Domena '{domain}' nie jest na whitelist.\n"
                        f"  Czy chcesz pobrać tę stronę? [t/N]: {Colors.RESET}"
                    ).strip().lower()
                except (KeyboardInterrupt, EOFError):
                    print()
                    ui.warning("Anulowano")
                    return
                if response not in ["t", "tak", "y", "yes"]:
                    ui.warning("Anulowano")
                    return
            force = True
        else:
            force = False

        ui.spinner_start(f"Pobieranie {url}...")
        try:
            result = engine.scraper.scrape(url) if force else engine.scrape(url)
        finally:
            ui.spinner_stop()

        if not result.success:
            ui.error(f"Błąd scrapowania: {result.error}")
            return

        ui.section(f"Treść: {result.title or url}")
        print(f"  Słów: {result.word_count}")
        print(f"  URL:  {result.url}")
        print()
        print(result.markdown)
        return

    # ── wyszukiwanie (domyślne) ────────────────────────────────────────────────
    # Jeśli brak sub lub sub to część zapytania (nie jest komendą systemową)
    SYSTEM_SUBS = {"enable", "disable", "status", "cache", "domains", "scrape"}
    if sub and sub in SYSTEM_SUBS:
        ui.error(f"Nieznana subkomenda: {sub}")
        ui.verbose("Użycie: ai web-search [enable|disable|status|cache|domains|scrape|<zapytanie>]")
        return

    # Zbuduj zapytanie ze wszystkich argumentów po 'web-search'
    query = " ".join(args[1:]) if len(args) > 1 else None

    if not query:
        ui.section("Web Search – Pomoc")
        print("""  Komendy:
  ai web-search <zapytanie>         Wyszukaj w internecie
  ai web-search enable              Włącz web search
  ai web-search disable             Wyłącz web search
  ai web-search status              Status silnika i dependencies
  ai web-search scrape <url>        Pobierz treść strony
  ai web-search cache               Pokaż statystyki cache
  ai web-search cache clear         Wyczyść cache
  ai web-search domains             Pokaż whitelist domen
  ai web-search domains add <d>     Dodaj domenę do whitelist
  ai web-search domains remove <d>  Usuń domenę z whitelist

  Przykłady:
  ai web-search najnowsza wersja pandas
  ai web-search co nowego w Python 3.13
  ai web-search scrape https://pypi.org/project/requests/
        """)
        return

    # Sprawdź włączenie
    engine = WebSearchEngine(config)
    if not engine.is_enabled:
        ui.error("Web search jest wyłączony")
        ui.verbose("Włącz: ai web-search enable")
        return

    # Sprawdź zależności
    missing = engine.ensure_dependencies()
    if missing:
        ui.warning(f"Brakujące pakiety: {', '.join(missing)}")
        try:
            response = input(
                f"\n{Colors.YELLOW}Czy zainstalować automatycznie? [T/n]: {Colors.RESET}"
            ).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            ui.warning("Anulowano")
            return
        if response not in ["n", "nie", "no"]:
            import subprocess as sp
            sp.run(
                ["pip", "install", "--break-system-packages", "--quiet"] + missing,
                check=False
            )
            ui.success("✓ Pakiety zainstalowane. Spróbuj ponownie.")
        return

    # Wykonaj wyszukiwanie
    ui.spinner_start(f"Szukam: {query!r}...")
    try:
        results = engine.search(query)
    except RateLimitError as e:
        ui.spinner_stop()
        ui.error(str(e))
        return
    except WebSearchError as e:
        ui.spinner_stop()
        ui.error(str(e))
        return
    except Exception as e:
        ui.spinner_stop()
        ui.error(f"Nieoczekiwany błąd: {e}")
        return
    finally:
        ui.spinner_stop()

    if not results:
        ui.warning("Brak wyników dla tego zapytania")
        ui.verbose("Spróbuj innych słów kluczowych")
        return

    ui.section(f"Wyniki wyszukiwania: {query!r}")
    print()

    for i, r in enumerate(results, 1):
        date_str = f"  [{r.date}]" if r.date else ""
        domain_str = f"{Colors.GRAY}({r.domain}){Colors.RESET}" if r.domain else ""
        print(f"{Colors.CYAN}[{i}]{Colors.RESET} {Colors.WHITE}{r.title}{Colors.RESET} {domain_str}{date_str}")
        if r.snippet:
            print(f"     {r.snippet}")
        print(f"     {Colors.GRAY}{r.url}{Colors.RESET}")
        print()

    print(f"{Colors.GRAY}  Rate limit: {engine.rate_limiter.remaining}/10 zapytań pozostało w tej minucie{Colors.RESET}")
    print()
    ui.verbose("Tip: ai web-search scrape <url>  — pobierz pełną treść strony")


def cmd_memory(ui, args):
    """
    Zarządzanie globalną pamięcią AI.
    
    Użycie:
      ai memory               — lista wszystkich faktów
      ai memory list          — lista faktów
      ai memory add <treść>   — dodaj fakt ręcznie
      ai memory rm <id>       — usuń fakt po ID
      ai memory clear         — wyczyść całą pamięć
      ai memory show          — pokaż kontekst dla promptu
    """
    from project.global_memory import GlobalMemory
    mem = GlobalMemory()

    subcmd = args[0] if args else "list"

    if subcmd in ("list", "ls", "show") and subcmd != "show":
        facts = mem.list_facts()
        if not facts:
            ui.warning("Pamięć globalna jest pusta.")
            print()
            print("  Dodaj fakty: ai memory add <treść>")
            print("  Np.: ai memory add 'Używam mygit zamiast git do wersjonowania'")
            return
        ui.section(f"Pamięć globalna ({len(facts)} faktów)")
        print()
        for f in facts:
            cat = f.get("category", "general")
            fid = f.get("id", "?")
            content = f.get("content", "")
            created = f.get("created_at", "")[:10]
            print(f"  [{fid}] ({cat})  {content}  {Colors.GRAY}({created}){Colors.RESET}")
        print()
        print(f"  {Colors.GRAY}ai memory add <treść>{Colors.RESET}  — dodaj fakt")
        print(f"  {Colors.GRAY}ai memory rm <id>{Colors.RESET}      — usuń fakt")
        print(f"  {Colors.GRAY}ai memory clear{Colors.RESET}        — wyczyść wszystko")

    elif subcmd == "show":
        ctx = mem.get_context_for_prompt()
        if ctx:
            print(ctx)
        else:
            ui.warning("Pamięć jest pusta — brak kontekstu dla promptu.")

    elif subcmd == "add":
        content = " ".join(args[1:]).strip()
        if not content:
            ui.error("Podaj treść faktu: ai memory add <treść>")
            return
        # Wykryj kategorię
        lower = content.lower()
        if any(w in lower for w in ["używam", "zamiast", "narzędzie", "tool", "skrypt"]):
            cat = "tool"
        elif any(w in lower for w in ["python", "javascript", "rust", "java", "język"]):
            cat = "language"
        elif any(w in lower for w in ["kde", "gnome", "ubuntu", "arch", "edytor", "ide", "terminal"]):
            cat = "environment"
        elif any(w in lower for w in ["nick", "nazywam", "imię", "jestem"]):
            cat = "identity"
        else:
            cat = "general"

        fact = mem.add(content, cat)
        ui.success(f"✓ Dodano fakt [{fact['id']}] ({cat}): {content}")

    elif subcmd in ("rm", "remove", "del", "delete"):
        if not args[1:]:
            ui.error("Podaj ID faktu: ai memory rm <id>")
            return
        try:
            fid = int(args[1])
        except ValueError:
            ui.error(f"ID musi być liczbą, nie: {args[1]}")
            return
        if mem.remove(fid):
            ui.success(f"✓ Usunięto fakt [{fid}]")
        else:
            ui.error(f"Nie znaleziono faktu o ID={fid}")

    elif subcmd == "clear":
        try:
            confirm = input(f"{Colors.YELLOW}Czy na pewno wyczyścić całą pamięć? [t/N]: {Colors.RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            ui.warning("Anulowano.")
            return
        if confirm in ("t", "tak", "y", "yes"):
            mem.clear()
            ui.success("✓ Pamięć globalna wyczyszczona.")
        else:
            ui.warning("Anulowano.")

    else:
        # Nieznana podkomenda — pokaż pomoc
        print(f"  {Colors.CYAN}ai memory{Colors.RESET}               — lista faktów")
        print(f"  {Colors.CYAN}ai memory add <treść>{Colors.RESET}   — dodaj fakt")
        print(f"  {Colors.CYAN}ai memory rm <id>{Colors.RESET}       — usuń fakt po ID")
        print(f"  {Colors.CYAN}ai memory clear{Colors.RESET}         — wyczyść pamięć")
        print(f"  {Colors.CYAN}ai memory show{Colors.RESET}          — pokaż kontekst promptu")


def cmd_knowledge(ui, config: dict, args: list, do_index: bool = False):
    """
    ai --index / ai --reindex / ai knowledge [status|list]

    Zarządzanie bazą wiedzy RAG.
    """
    from rag.knowledge_base import KnowledgeBase, find_knowledge_dir, GLOBAL_KNOWLEDGE_DIR
    from pathlib import Path

    # Wyznacz katalog knowledge
    # Jeśli jesteśmy w projekcie – szukaj lokalnie, potem globalnie
    try:
        from project.project_detector import ProjectDetector
        project_root = ProjectDetector.detect_project_root()
    except Exception:
        project_root = None

    # Subkomenda
    is_index   = do_index or "--index" in args or "--reindex" in args
    subcmd     = args[1] if len(args) > 1 and args[0] in ("knowledge", "kb") else None

    kb = KnowledgeBase(config)

    # ── STATUS ──────────────────────────────────────────────────────────────
    if subcmd in ("status", None) and not is_index:
        ui.section("Baza wiedzy (RAG)")
        loaded = kb.load()
        kdir   = find_knowledge_dir(project_root)

        if loaded:
            ui.success(f"Status:         załadowana ({kb.chunk_count} chunków)")
        else:
            ui.warning("Status:         nie zaindeksowana (uruchom: ai --index)")

        if kdir:
            ui.success(f"Katalog wiedzy: {kdir}")
            # Policz pliki
            md_files  = list(kdir.rglob("*.md"))
            txt_files = list(kdir.rglob("*.txt"))
            ui.success(f"Pliki:          {len(md_files)} .md, {len(txt_files)} .txt")
        else:
            ui.warning(f"Brak katalogu knowledge/")
            ui.verbose(f"Utwórz jeden z katalogów i dodaj pliki .md / .txt:")
            ui.verbose(f"  {GLOBAL_KNOWLEDGE_DIR}  ← globalny")
            if project_root:
                ui.verbose(f"  {project_root / 'knowledge'}  ← lokalny (projekt)")

        info = kb.get_info()
        ui.verbose(f"Model embed:    {info['embed_model']}")
        ui.verbose(f"Cache:          {info['db_path']}.*")
        print()
        print(f"  {Colors.CYAN}ai --index{Colors.RESET}           — zaindeksuj / odbuduj bazę")
        print(f"  {Colors.CYAN}ai knowledge list{Colors.RESET}    — lista plików wiedzy")
        print(f"  {Colors.CYAN}ai knowledge status{Colors.RESET}  — ten ekran")
        return

    # ── LIST ─────────────────────────────────────────────────────────────────
    if subcmd == "list":
        kdir = find_knowledge_dir(project_root)
        if not kdir:
            ui.error("Brak katalogu knowledge/")
            return
        ui.section(f"Pliki wiedzy: {kdir}")
        prev_cat = None
        total    = 0
        for path in sorted(kdir.rglob("*.md")) + sorted(kdir.rglob("*.txt")):
            rel = path.relative_to(kdir)
            cat = str(rel.parent)
            if cat != prev_cat:
                print(f"\n  {Colors.BOLD}{cat}/{Colors.RESET}")
                prev_cat = cat
            size = path.stat().st_size
            print(f"    {rel.name:<50} {size:>7} B")
            total += 1
        print(f"\n  Łącznie: {total} plików")
        return

    # ── INDEX ─────────────────────────────────────────────────────────────────
    if is_index or subcmd in ("index", "reindex"):
        kdir = find_knowledge_dir(project_root)
        if not kdir:
            ui.error("Brak katalogu knowledge/!")
            ui.verbose(f"Utwórz katalog i dodaj pliki .md:")
            ui.verbose(f"  mkdir -p {GLOBAL_KNOWLEDGE_DIR}")
            ui.verbose(f"  # lub <projekt>/knowledge/")
            return

        ui.section("Indeksowanie bazy wiedzy")
        print(f"  Katalog:     {kdir}")
        print(f"  Model embed: {kb.embed_model}")
        print()

        try:
            count = kb.index(kdir, verbose=True)
            print()
            if count > 0:
                ui.success(f"Zaindeksowano {count} chunków!")
                ui.verbose(f"Cache: ~/.cache/ai/rag/knowledge_vectors.*")
            else:
                ui.warning("Brak plików do zaindeksowania")
        except FileNotFoundError as e:
            ui.error(str(e))
        except Exception as e:
            ui.error(f"Błąd indeksowania: {e}")
            if ui.verbose:
                import traceback
                traceback.print_exc()
        return

    # Nieznana subkomenda
    print(f"  {Colors.CYAN}ai knowledge status{Colors.RESET}  — stan bazy wiedzy")
    print(f"  {Colors.CYAN}ai knowledge list{Colors.RESET}    — lista plików")
    print(f"  {Colors.CYAN}ai --index{Colors.RESET}           — zaindeksuj bazę")


def cmd_export(agent, ui, args):
    """
    ai export [opcje] — eksportuj historię sesji do pliku Markdown

    ai export                    eksportuj bieżącą sesję do ai-session-YYYY-MM-DD.md
    ai export <plik.md>          eksportuj do podanego pliku
    ai export --all              eksportuj całe .ai-logs/session.log
    ai export --operations       eksportuj operations.jsonl jako tabelę
    """
    import json
    from datetime import datetime
    from pathlib import Path

    if agent.project_root is None:
        log_dir = Path.home() / ".cache" / "ai-cli" / "logs"
    else:
        log_dir = agent.project_root / ".ai-logs"

    # Ustal plik docelowy
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_file = None
    export_all = "--all" in args
    export_ops = "--operations" in args

    for a in args[1:]:
        if not a.startswith("--"):
            out_file = Path(a)
            break

    if out_file is None:
        out_file = Path.cwd() / f"ai-session-{date_str}.md"

    lines = []
    lines.append(f"# Sesja AI CLI — {date_str}\n")

    # --- session.log ---
    session_log = log_dir / "session.log"
    if session_log.exists():
        lines.append("## Historia rozmów\n")
        raw = session_log.read_text(encoding="utf-8", errors="replace")
        if not export_all:
            # Tylko dzisiejsze wpisy
            today = date_str
            raw_lines = [l for l in raw.splitlines() if l.startswith(f"[{today}")]
        else:
            raw_lines = raw.splitlines()

        if not raw_lines:
            lines.append("_Brak wpisów z dzisiaj. Użyj `--all` aby zobaczyć całą historię._\n")
        else:
            for l in raw_lines:
                if "USER:" in l:
                    msg = l.split("USER:", 1)[-1].strip().strip("'")
                    lines.append(f"**User:** {msg}\n")
                elif "AI:" in l:
                    msg = l.split("AI:", 1)[-1].strip()
                    lines.append(f"**AI:** {msg}\n")
                elif "ACTIONS:" in l:
                    msg = l.split("ACTIONS:", 1)[-1].strip()
                    lines.append(f"> `{msg}`\n")
    else:
        lines.append("_Brak pliku session.log_\n")

    # --- operations.jsonl (opcjonalnie) ---
    if export_ops:
        ops_file = log_dir / "operations.jsonl"
        if ops_file.exists():
            lines.append("\n## Operacje\n")
            lines.append("| Czas | Polecenie | Akcji | Sukces |\n")
            lines.append("|------|-----------|-------|--------|\n")
            with open(ops_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        op = json.loads(line)
                        ts = op.get("timestamp", "")[:16]
                        cmd = op.get("command", "")[:60].replace("|", "\\|")
                        cnt = op.get("actions_count", 0)
                        ok = "✓" if op.get("overall_success") else "✗"
                        lines.append(f"| {ts} | {cmd} | {cnt} | {ok} |\n")
                    except Exception:
                        pass

    # Zapisz
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines), encoding="utf-8")
    ui.success(f"Eksport zapisany: {out_file}")
    ui.verbose(f"  Wiersze: {len(lines)}")


def cmd_deps(ui, config):
    """
    ai deps — sprawdź stan zależności Python w venv agenta.
    """
    import sys
    import importlib.util
    import re
    from pathlib import Path

    install_dir = Path.home() / ".local" / "share" / "ai-cli-agent"
    venv_python = install_dir / "venv" / "bin" / "python3"
    req_file    = install_dir / "requirements.txt"

    ui.section("Zależności Python")

    current_python = sys.executable
    using_venv = "venv" in current_python
    if using_venv:
        ui.success(f"Python: {current_python}  (venv ✓)")
    else:
        ui.warning(f"Python: {current_python}  (systemowy — nie venv)")
        ui.verbose(f"Oczekiwany venv: {venv_python}")

    if not req_file.exists():
        ui.error(f"Brak pliku requirements.txt w {install_dir}")
        return

    packages = []
    with open(req_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^([A-Za-z0-9_\-]+)', line)
            if m:
                packages.append((m.group(1), line))

    print()
    ok = 0
    missing = []
    for pkg_name, req_line in packages:
        import_aliases = {
            "pillow":        "PIL",
            "beautifulsoup4":"bs4",
        }
        import_name = import_aliases.get(pkg_name.lower(),
                        pkg_name.replace("-", "_").lower())

        spec = importlib.util.find_spec(import_name)
        if spec is not None:
            try:
                import importlib.metadata
                ver = importlib.metadata.version(pkg_name)
                ui.success(f"  ✓  {pkg_name:<22} {ver}")
            except Exception:
                ui.success(f"  ✓  {pkg_name}")
            ok += 1
        else:
            ui.error(f"  ✕  {pkg_name:<22} BRAK  ({req_line})")
            missing.append(pkg_name)

    print()
    ui.success(f"Zainstalowane: {ok}/{len(packages)}")

    if missing:
        print()
        ui.warning(f"Brakujące: {', '.join(missing)}")
        print()
        if using_venv:
            ui.verbose(f"Napraw:  {venv_python} -m pip install {' '.join(missing)}")
        else:
            ui.verbose(f"Napraw:  {venv_python} -m pip install {' '.join(missing)}")
            ui.verbose(f"System:  pip install {' '.join(missing)} --break-system-packages")
