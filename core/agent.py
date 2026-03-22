"""
agent.py – AIAgent (refaktoryzacja).

Główna logika podzielona na mikro-moduły:
  - core/agent_prompts.py    – budowanie promptów
  - core/agent_runner.py     – pętla iteracji run()
  - core/agent_global.py     – obsługa trybu globalnego
  - core/agent_state.py      – stany agenta

Ten plik zawiera: __init__, właściwości lazy, metody pomocnicze,
_execute_with_transaction, _needs_confirm i fasadę delegacji.
"""
import json
import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

from classification.command_classifier import CommandClassifier, CommandRisk as CmdRisk
from classification.intent_classifier import IntentClassifier, Intent
from core.conversation_state import ConversationState
from core.conversation_history import ConversationHistory
from core.json_parser import JSONParser
from core.ollama import OllamaClient, OllamaConnectionError
from planning.action_planner import ActionPlanner
from planning.action_validator import ActionValidator, ActionRisk
from planning.impact_analyzer import ImpactAnalyzer
from project.capability_manager import CapabilityManager
from project.global_memory import GlobalMemory
from project.global_mode import GlobalMode
from project.project_detector import ProjectDetector, NotInProjectError
from project.project_memory import ProjectMemory
from project.project_analyzer import ProjectAnalyzer
from project.semantic_decisions import SemanticDecisionManager
from rag.knowledge_base import KnowledgeBase, find_knowledge_dir, build_rag_context_section
from tasks.image_tasks import ImagePipeline, ImageTaskError
from tasks.media_tasks import MediaPipeline, ToolStatus, MediaTaskError
from tasks.web_search import WebSearchEngine, WebSearchError, RateLimitError
from ui_layer.review_mode import ProjectReviewer
from ui_layer.ui import UI, Colors
from utils.clipboard_utils import ClipboardManager
from utils.diff_editor import DiffEditor
from utils.fs_tools import FileSystemTools
from utils.search_replace import SearchReplacePatcher, SearchReplaceParser
from utils.transaction_manager import TransactionManager, Transaction
from utils.template_manager import get_template_context_for_prompt, apply_template, list_templates
from core.prompt_builder import PromptBuilder
from core.agent_state import (
    AgentState, StepResult, IterationContext, StagnationDetector,
    DoneReason, FailedReason,
)

class AIAgent:
    def __init__(self, client, config, dry_run=False, plan_only=False, quiet=False, verbose=False, auto_confirm=False, global_mode=False):
        self.client = client
        self.config = config
        self.dry_run = dry_run
        self.plan_only = plan_only
        self.auto_confirm = auto_confirm
        self.global_mode = global_mode

        # Stan wykonania (zapobieganie autopilocie)
        self.execution_failed = False
        self.last_failed_command = None
        
        # Conversation state
        self.conversation = ConversationState(max_history=10)
        # Persystentna historia rozmów (zapis na dysk)
        self.conv_history: ConversationHistory | None = None
        
        # Globalna pamięć persystentna
        self.global_memory = GlobalMemory()
        
        # Media Pipeline (NOWE) - inicjalizuj lazy
        self._media_pipeline = None

        self._image_pipeline = None
        self._clipboard = None
        self._web_search_engine = None  # Web Search - lazy init

        # RAG – Knowledge Base (lazy init)
        self._kb: KnowledgeBase | None = None
        self._kb_ready: bool = False
        
        # Wykryj projekt
        try:
            if not global_mode:
                detected_root = ProjectDetector.detect_project_root()
                
                # POPRAWKA: Jeśli nie znaleziono markerów, użyj cwd
                if detected_root is None:
                    self.project_root = Path.cwd()
                    
                    # Ostrzeżenie tylko jeśli cwd == home
                    if self.project_root == Path.home():
                        if not quiet:
                            print(f"{Colors.YELLOW}⚠ Pracujesz w katalogu domowym bez projektu{Colors.RESET}")
                            print(f"{Colors.YELLOW}  Rozważ użycie: ai init{Colors.RESET}\n")
                else:
                    self.project_root = detected_root
            else:
                self.project_root = None
        except NotInProjectError as e:
            if not quiet:
                print(str(e))
            self.project_root = None
            self.global_mode = True
        
        # Jeśli global mode - ograniczona inicjalizacja
        if self.global_mode:
            self.ui = UI(quiet=quiet, verbose=verbose, config=config)
            self.fs = None
            self.editor = None
            self.memory = None
            self.analyzer = None
            self.semantic = None
            self.impact = None
            self.reviewer = None
            self.capabilities = None
            self.tx_manager = None
            # Logger działa nawet bez projektu — zapisuje do cache_dir (~/.cache/ai-cli/logs/)
            from utils.logger import AILogger
            self.logger = AILogger(project_root=None, config=config)
            self.logger.info("AI Agent initialized (mode: global)")

            self.system_prompt = self._build_global_prompt()
            return
        
        # Normalna inicjalizacja (tryb projektowy)
        assert self.project_root is not None, "project_root musi być ustawiony w trybie projektowym"
        
        self.fs = FileSystemTools(dry_run=dry_run, project_root=self.project_root)
        self.editor = DiffEditor()
        self.ui = UI(quiet=quiet, verbose=verbose, config=config)
        self.memory = ProjectMemory(self.project_root, config=config)
        self.analyzer = ProjectAnalyzer(self.fs)
        self.semantic = SemanticDecisionManager(self.project_root)
        self.impact = ImpactAnalyzer(self.fs)
        self.reviewer = ProjectReviewer(self.fs, self.analyzer, self.memory)
        self.capabilities = CapabilityManager(self.project_root, self.memory.data, config=config)
        
        # Transaction Manager
        self.tx_manager = TransactionManager(self.project_root)
        
        # Logger (POPRAWKA: po inicjalizacji project_root)
        from utils.logger import AILogger
        self.logger = AILogger(
            project_root=self.project_root,
            config=config
        )
        
        self.logger.info(f"AI Agent initialized (mode: project)")

        # Persystentna historia rozmów per projekt
        self.conv_history = ConversationHistory(
            project_root=self.project_root,
            config=config
        )

        self.project_analyzed = False
        if config.get('project', {}).get('auto_analyze_on_start', True):
            if self._is_project_reasonable_size():
                self._ensure_project_analyzed()

        BASE_DIR = Path(__file__).resolve().parent.parent  # core/ -> root

        # PromptBuilder: warstwowy prompt – core zawsze + inject per-request
        self._prompt_builder = PromptBuilder(BASE_DIR / "prompts" / "layers")
        base_prompt = self._prompt_builder._load("core.txt")
        if not base_prompt:
            # Fallback do system.txt jeśli brak warstw
            SYSTEM_PROMPT_PATH = BASE_DIR / "prompts" / "system.txt"
            with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
                base_prompt = f.read()

        # NOWE: Załaduj user prompt
        user_prompt = ""
        USER_PROMPT_FILE = Path.home() / ".config" / "ai" / "prompt.txt"

        if USER_PROMPT_FILE.exists():
            try:
                user_prompt_content = USER_PROMPT_FILE.read_text(encoding="utf-8")
                
                # Filtruj komentarze (linie zaczynające się od #)
                lines = [
                    line for line in user_prompt_content.splitlines()
                    if line.strip() and not line.strip().startswith('#')
                ]
                
                if lines:
                    user_prompt = "\n".join(lines)
            except Exception as e:
                # Ignoruj błędy - user prompt jest opcjonalny
                pass

        # Buduj finalny prompt
        project_context = self.memory.get_context_prompt()
        semantic_context = self.semantic.get_context_for_prompt()
        capability_context = self.capabilities.get_context_for_prompt()
        system_context = GlobalMode.format_system_context_for_prompt()

        # Kontekst szablonów
        template_context = get_template_context_for_prompt()

        # Buduj statyczny kontekst (raz przy starcie) – nie zawiera warstw inject
        user_prompt_section = ""
        if user_prompt:
            user_prompt_section = f"""

====================
SYSTEM PROMPT UŻYTKOWNIKA
====================

{user_prompt}

WAŻNE: Te zasady mają PRIORYTET nad domyślnym zachowaniem.
Szanuj preferencje użytkownika.
"""

        self._static_context = user_prompt_section + f"""

====================
KONTEKST UŻYTKOWNIKA
====================

Nick użytkownika: {config.get("nick")}
Katalog roboczy: {self.fs.cwd}
Projekt: {self.project_root}

{project_context}
{semantic_context}
{capability_context}
{system_context}
{template_context}

{self.global_memory.get_context_for_prompt()}
"""
        # system_prompt = core prompt (bez warstw inject, bez kontekstu)
        # Pełny prompt jest budowany per-request w _build_system_prompt(user_input)
        self.system_prompt = base_prompt  # fallback / kompatybilność wsteczna

        # ── Moduły pomocnicze ─────────────────────────────────────────────────
        self._json_parser = JSONParser()
        from core.action_executor import ActionExecutor
        self._executor = ActionExecutor(self)
    
    def _build_system_prompt(self, user_input: str) -> str:
        """
        Buduje pełny system prompt per-request.
        core.txt (zawsze) + warstwy inject (wg triggera) + statyczny kontekst.
        """
        if hasattr(self, '_prompt_builder') and self._prompt_builder:
            core_with_layers = self._prompt_builder.build(user_input)
        else:
            core_with_layers = self.system_prompt  # fallback

        # Dołącz statyczny kontekst (nick, projekt, pamięć)
        static = getattr(self, '_static_context', '')
        return core_with_layers + static

    def _validate_destructive_context(self, command: str) -> tuple:
        """
        KRYTYCZNY BEZPIECZNIK - walidacja kontekstu destrukcyjnej komendy.
        
        ZASADY:
        1. rm -rf / lub rm -rf ~ → BLOKADA ABSOLUTNA
        2. Destrukcyjna komenda bez ścieżki absolutnej:
           - cwd == home + globy (* .) → BLOKADA
           - cwd poza projektem → BLOKADA (wymaga jawnej ścieżki)
        3. Destrukcyjna komenda ze ścieżką absolutną → OK (user wie co robi)
        
        Returns:
            (is_safe, error_message)
        """
        
        # Wykryj czy komenda jest destrukcyjna
        destructive_patterns = [
            r'\brm\b.*-rf',
            r'\brm\b.*-r',
            r'\bdd\b',
            r'\bmkfs\b',
            r'\bshred\b',
            r'>\s*/dev/',
        ]
        
        is_destructive = any(re.search(pattern, command) for pattern in destructive_patterns)
        
        if not is_destructive:
            return (True, None)
        
        # ===== BLOKADA 1: rm -rf / lub rm -rf ~ =====
        if re.search(r'rm\s+.*-rf?\s+(/|~)\s*$', command):
            return (False, 
                f"{Colors.RED}═════════════════════════════════════════════════════\n"
                f"BLOKADA KRYTYCZNA - DATA LOSS PREVENTION\n"
                f"═════════════════════════════════════════════════════{Colors.RESET}\n\n"
                f"Komenda: {command}\n\n"
                f"{Colors.RED}rm -rf / lub rm -rf ~ jest ABSOLUTNIE ZABRONIONE{Colors.RESET}\n\n"
                f"To jest operacja NIEODWRACALNA która usuwa CAŁY SYSTEM.\n"
                f"Agent NIE wykona tej operacji pod ŻADNYM warunkiem.\n")
        
        # Sprawdź czy komenda zawiera ścieżki absolutne
        # Jeśli tak - to user wie co robi (ale pytamy o confirm)
        if re.search(r'/[a-zA-Z0-9_/-]+', command):
            # Ma ścieżkę absolutną - dozwolone (z confirm)
            return (True, None)
        
        # ===== BLOKADA 2: Nie ma ścieżki absolutnej - sprawdź kontekst =====
        cwd = Path.cwd()
        home = Path.home()
        
        # BLOKADA: cwd == home i wzorce globalne
        if cwd == home:
            if re.search(r'[\*\.]', command):
                return (False,
                    f"{Colors.RED}═════════════════════════════════════════════════════\n"
                    f"BLOKADA KRYTYCZNA - DATA LOSS PREVENTION\n"
                    f"═════════════════════════════════════════════════════{Colors.RESET}\n\n"
                    f"Komenda: {command}\n"
                    f"CWD: {cwd}\n\n"
                    f"{Colors.RED}Destrukcyjna komenda z globami w katalogu domowym{Colors.RESET}\n\n"
                    f"To ryzykowna operacja która może usunąć WSZYSTKIE dane użytkownika.\n\n"
                    f"Jeśli NAPRAWDĘ chcesz usunąć pliki z {cwd}:\n"
                    f"1. Podaj JAWNĄ ścieżkę absolutną (np. rm -rf /home/user/plik)\n"
                    f"2. Przejdź do katalogu projektu i uruchom tam\n"
                    f"3. Wykonaj komendę ręcznie w terminalu\n")
        
        # ===== BLOKADA 3: Sprawdź czy jesteśmy w katalogu projektu =====
        if self.project_root:
            # Sprawdź czy cwd jest w project_root
            try:
                cwd.relative_to(self.project_root)
                # Jesteśmy w projekcie - OK
                return (True, None)
            except ValueError:
                # Jesteśmy POZA projektem
                return (False,
                    f"{Colors.RED}═════════════════════════════════════════════════════\n"
                    f"BLOKADA KRYTYCZNA - DATA LOSS PREVENTION\n"
                    f"═════════════════════════════════════════════════════{Colors.RESET}\n\n"
                    f"Komenda: {command}\n"
                    f"CWD: {cwd}\n"
                    f"Projekt: {self.project_root}\n\n"
                    f"{Colors.RED}Destrukcyjna komenda poza katalogiem projektu{Colors.RESET}\n\n"
                    f"Agent NIE wykona destrukcyjnych operacji poza zakresem projektu\n"
                    f"bez jawnej ścieżki absolutnej.\n\n"
                    f"Jeśli to zamierzone:\n"
                    f"1. Podaj JAWNĄ ścieżkę absolutną (np. rm -rf /home/user/plik)\n"
                    f"2. Wykonaj komendę ręcznie w terminalu\n")
        
        # Brak projektu, ale nie jesteśmy w home - dozwolone
        return (True, None)

    @property
    def image_pipeline(self) -> ImagePipeline:
        if self._image_pipeline is None:
            self._image_pipeline = ImagePipeline(logger=self.logger)
        return self._image_pipeline

    @property
    def clipboard(self) -> ClipboardManager:
        if self._clipboard is None:
            self._clipboard = ClipboardManager(logger=self.logger)
        return self._clipboard

    @property
    def media_pipeline(self) -> MediaPipeline:
        """Lazy initialization Media Pipeline"""
        if self._media_pipeline is None:
            self._media_pipeline = MediaPipeline(logger=self.logger)
        return self._media_pipeline

    @property
    def web_search_engine(self) -> WebSearchEngine:
        """Lazy-init silnika web search."""
        if self._web_search_engine is None:
            self._web_search_engine = WebSearchEngine(self.config, logger=self.logger)
        return self._web_search_engine

    @property
    def kb(self) -> KnowledgeBase:
        """Lazy-init Knowledge Base (RAG)."""
        if self._kb is None:
            self._kb = KnowledgeBase(self.config)
            loaded = self._kb.load()
            self._kb_ready = loaded
        return self._kb

    def _get_rag_context(self, user_input: str) -> str:
        """
        Wyszukaj w bazie wiedzy i zwróć sekcję kontekstu dla promptu.
        Wywoływana automatycznie przed każdą odpowiedzią agenta.
        """
        rag_cfg = self.config.get('rag', {})
        if not rag_cfg.get('enabled', True):
            return ''

        # Sprawdź czy jest katalog knowledge
        project_root = self.project_root if not self.global_mode else None
        kdir = find_knowledge_dir(project_root)
        if kdir is None:
            return ''

        try:
            kb = self.kb
            if not kb.is_ready:
                return ''
            top_k        = rag_cfg.get('top_k', 4)
            min_score    = rag_cfg.get('min_score', 0.1)
            max_per_file = rag_cfg.get('max_per_file', 2)
            results      = kb.search(user_input, top_k=top_k, min_score=min_score, max_per_file=max_per_file)
            if not results:
                return ''
            context = build_rag_context_section(results, kb)
            if self.logger:
                sources = [r.file_path for r in results]
                self.logger.debug(f'RAG: {len(results)} wyników dla: {user_input!r} | źródła: {sources}')
            # show_sources – wyświetl źródła w terminalu jeśli włączone w config
            if rag_cfg.get('show_sources', False):
                from ui_layer.ui import Colors
                print(f'\n{Colors.GRAY}  📚 RAG [{len(results)}]: ' +
                      ', '.join(r.file_path.split('knowledge/')[-1] for r in results) +
                      f'{Colors.RESET}')
            return context
        except Exception as e:
            if self.logger:
                self.logger.warning(f'RAG error: {e}')
            return ''

    def _extract_image_paths(self, user_input: str) -> list:
        """
        Wyciągnij ścieżki do obrazów z tekstu użytkownika.
        Rozpoznaje: ss.jpg, /home/user/foto.png, ~/Pobrane/img.webp, ./foto.jpeg itp.
        """
        import re, os
        img_exts = r'\.(?:png|jpg|jpeg|webp|gif|bmp|tiff)'
        # Dopasuj ścieżki: absolutne, ~/, ./, same nazwy plików
        pattern = r'(?:(?:~|\.\.?)?\/[\w\./\-_ ]+|[\w\.\-_]+)' + img_exts + r'(?=\s|$|[,\)])'
        matches = re.findall(pattern, user_input, re.IGNORECASE)
        paths = []
        for m in matches:
            m = m.strip()
            expanded = os.path.expanduser(m)
            # Jeśli nie absolutna – sprawdź w cwd
            if not os.path.isabs(expanded):
                cwd_path = os.path.join(os.getcwd(), expanded)
                if os.path.isfile(cwd_path):
                    paths.append(cwd_path)
                    continue
            if os.path.isfile(expanded):
                paths.append(expanded)
        return paths

    def _json_reminder(self) -> str:
        """
        Zwróć suffix przypominający o formacie JSON.
        Modele thinking (qwen3) i cloud mają tendencję do odpowiadania swobodnym
        tekstem zamiast JSON - muszą dostawać przypomnienie tak samo jak lokalne.
        """
        return (
            "\n\n[WAŻNE: Odpowiedz WYŁĄCZNIE poprawnym JSON. "
            "Żadnego tekstu przed ani po. Żadnego markdown. "
            "Format: {\"actions\": [...]} lub {\"message\": \"...\"}]"
        )

    def _build_global_prompt(self) -> str:
        system_context = GlobalMode.format_system_context_for_prompt()
        
        config_path = Path.home() / ".config" / "ai" / "config.json"
        template_context = get_template_context_for_prompt()
        
        # Web search status
        ws_config = self.config.get("web_search", {})
        ws_enabled = ws_config.get("enabled", False)
        ws_engine  = ws_config.get("engine", "duckduckgo")
        if ws_enabled:
            ws_section = f"""====================
WEB SEARCH
====================

Status web_search: WŁĄCZONY (silnik: {ws_engine})

Używaj akcji web_search do wyszukiwania informacji w internecie:
  {{"actions": [{{"type": "web_search", "query": "zapytanie", "max_results": 5}}]}}

Możesz też użyć run_command z curl jako alternatywy:
  Pogoda: {{"type": "run_command", "command": "curl -s 'wttr.in/Gdansk?format=3&lang=pl'"}}"""
        else:
            ws_section = """====================
WEB SEARCH
====================

Status web_search: WYŁĄCZONY — używaj run_command z curl zamiast tego.

ZAMIAST web_search używaj CURL (zawsze dostępny):
  Pogoda:     curl -s 'wttr.in/MIASTO?format=3&lang=pl'
  Wiadomości: curl -s 'rss.cnn.com/rss/edition.rss' | grep -o '<title>[^<]*</title>' | head -10
  IP:         curl -s ifconfig.me
  PyPI:       curl -s 'https://pypi.org/pypi/PAKIET/json' | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["info"]["version"])'
  DuckDuckGo: curl -s 'https://api.duckduckgo.com/?q=ZAPYTANIE&format=json' | python3 -c 'import sys,json;d=json.load(sys.stdin);[print(r["Text"]) for r in d.get("RelatedTopics",[])[:3] if r.get("Text")]'

ZAWSZE używaj curl zamiast mówić że nie masz dostępu do internetu.
NIE używaj akcji web_search — jest wyłączona, zamiast niej jest curl."""

        return f"""Jesteś AI CLI - asystentem terminalowym działającym bez aktywnego projektu (tryb GLOBAL).

{system_context}

{self.global_memory.get_context_for_prompt()}

====================
CO MOŻESZ ROBIĆ
====================

Jesteś PEŁNOPRAWNYM asystentem. Odpowiadaj na pytania, szukaj informacji, wykonuj komendy.

Masz dostęp do: run_command, list_files, read_file, create_file, edit_file, mkdir, delete_file, move_file.
Możesz TWORZYĆ i MODYFIKOWAĆ pliki — podawaj ścieżki absolutne (np. /home/user/skrypt.sh lub ~/skrypt.sh).

NIGDY nie odmawiaj odpowiedzi jeśli możesz użyć curl lub run_command.

{ws_section}

====================
KOMENDY SYSTEMOWE (run_command)
====================

MOŻESZ używać run_command dla WSZYSTKIEGO co użytkownik pyta:

Pogoda i API:
  curl -s 'wttr.in/MIASTO?format=3&lang=pl'              - aktualna pogoda (3-liniowy format)
  curl -s 'wttr.in/MIASTO?format=j1' | python3 -c '...' - dane JSON pogody
  curl -s 'https://api.open-meteo.com/v1/forecast?...'  - prognoza (darmowe API)

Przeglądanie pliku (BARDZO PRZYDATNE):
  sed -n 'LINIA1,LINIA2p' PLIK            - pokaż linie od LINIA1 do LINIA2 (np. sed -n '10,50p' agent.py)
  grep -n 'wzorzec' PLIK                  - znajdź linie z wzorcem (z numerami linii)
  grep -rn 'wzorzec' .                    - rekurencyjnie w katalogu
  awk 'NR>=10 && NR<=50' PLIK             - linie 10-50 (alternatywa dla sed)
  head -N PLIK                            - pierwsze N linii
  tail -N PLIK                            - ostatnie N linii
  wc -l PLIK                              - liczba linii

Edycja pliku w miejscu:
  sed -i 's/stary/nowy/g' PLIK            - zamień wszystkie wystąpienia
  sed -i 's/stary/nowy/' PLIK             - zamień pierwsze wystąpienie
  sed -i 'Nd' PLIK                        - usuń linię N
  sed -i 'N,Mp' PLIK                      - wydrukuj linie N-M
  awk -i inplace '{{gsub(/stary/,"nowy"); print}}' PLIK  - awk z edycją

Praca z plikami tekstowymi:
  cat PLIK | sort | uniq -c | sort -rn    - sortowanie + unikalne + count
  diff plik1.txt plik2.txt                - różnice między plikami
  comm -13 <(sort f1) <(sort f2)          - linie tylko w f2

Analiza kodu:
  grep -n 'def ' PLIK.py | head -30       - lista funkcji w Pythonie
  grep -n 'function\\|const\\|let\\|var' PLIK.js  - funkcje JS
  wc -l *.py                              - długości plików Python

System:
  df -h                                   - miejsce na dysku
  free -h                                 - pamięć RAM
  top -bn1 | head -20                     - procesy
  ip addr show                            - interfejsy sieciowe
  uname -a                                - informacje o systemie
  lsblk                                   - urządzenia blokowe

Pakiety Python:
  pip show PAKIET                         - info o pakiecie
  pip list --outdated                     - przestarzałe pakiety
  pip install --break-system-packages PAKIET  - instalacja

====================
FORMAT ODPOWIEDZI
====================

Zawsze zwracaj WYŁĄCZNIE poprawny JSON.

{{"message": "odpowiedź tekstowa"}}

lub z akcją:
{{"actions": [{{"type": "run_command", "command": "..."}}]}}

lub akcja + komentarz:
{{"actions": [...], "message": "opcjonalny komentarz"}}

NIE wolno zwracać tekstu poza JSON.
NIE używaj Markdowna (**, __, _, #).

====================
KLUCZOWE ZASADY
====================

1. ZAWSZE próbuj wykonać zadanie - nigdy nie odmawiaj gdy masz narzędzia
2. NIE PYTAJ O POTWIERDZENIE gdy użytkownik wydał jasne polecenie (np. "stwórz skróty" → stwórz je)
3. Jeśli zebrałeś dane w poprzedniej iteracji (np. listę gier), NATYCHMIAST wykonaj żądanie
4. Pogoda, kurs walut, aktualności → curl lub web_search (NIE odmawiaj!)
5. Przeglądanie pliku → sed -n lub grep (szybkie i precyzyjne)
6. Szukanie w kodzie → grep -n (z numerami linii)
7. Duże pliki → sed -n 'N,Mp' zamiast read_file całego pliku
8. Mów po polsku jak użytkownik pisze po polsku

PRZYKŁADY:

Pogoda:
{{"actions": [{{"type": "run_command", "command": "curl -s 'wttr.in/Gdansk?format=3&lang=pl'"}}]}}

Fragment pliku (linie 100-150):
{{"actions": [{{"type": "run_command", "command": "sed -n '100,150p' agent.py"}}]}}

Funkcje w pliku Python:
{{"actions": [{{"type": "run_command", "command": "grep -n 'def ' agent.py"}}]}}

Wersja pakietu na PyPI:
{{"actions": [{{"type": "run_command", "command": "curl -s https://pypi.org/pypi/pandas/json | python3 -c \\"import sys,json;d=json.load(sys.stdin);print(d['info']['name'],d['info']['version'])\\""}}]}}

Schowek:
{{"actions": [{{"type": "clipboard_read"}}]}}

Stwórz plik (podaj ścieżkę absolutną):
{{"actions": [{{"type": "create_file", "path": "/home/user/skrypt.sh", "content": "#!/bin/bash\necho hello"}}]}}

Utwórz katalog:
{{"actions": [{{"type": "mkdir", "path": "~/moj-folder"}}]}}

INFORMACJE O AI CLI:
- Konfiguracja: {config_path}
- Edytuj: ai config edit
- Pomoc: ai help

{template_context}
"""
    
    # ── JSON Parser (delegacja do core/json_parser.py) ─────────────────────────

    def _extract_json(self, raw: str) -> dict:
        """Wyciągnij czysty JSON z odpowiedzi modelu."""
        return self._json_parser.extract_json(raw)

    def _fix_json(self, text: str) -> dict | None:
        """Napraw typowe błędy JSON z lokalnych modeli."""
        return self._json_parser.fix_json(text)

    def _extract_json_or_wrap(self, raw: str) -> dict:
        """Wyciągnij JSON lub owij tekst/kod w odpowiednią strukturę."""
        return self._json_parser.extract_json_or_wrap(
            raw,
            rescue_fn=self._json_parser.rescue_code_from_message
        )

    def _inject_existing_file_if_needed(
        self, user_input: str, message: str, messages: list
    ) -> str | None:
        """
        Wykrywa czy model opisał edycję istniejącego pliku zamiast wykonać akcję.
        Jeśli tak — wczytuje plik i wstrzykuje jego treść do historii messages,
        żeby model mógł w następnej iteracji wykonać patch_file.

        Zwraca ścieżkę pliku jeśli wstrzyknięto, None w przeciwnym razie.
        """
        import re
        from pathlib import Path

        # Zbierz kandydatów na plik: z user_input i z treści message
        candidate_paths = []

        # 1. Ścieżki absolutne z user_input (np. "/home/paffcio/scan.sh")
        for m in re.finditer(r'(/[\w/.\-]+\.(?:sh|py|js|ts|rb|php|go|rs|c|cpp|h|cfg|conf|ini|yaml|yml|toml|json|txt|md))', user_input):
            candidate_paths.append(m.group(1))

        # 2. Sama nazwa pliku z user_input (np. "scan.sh")
        for m in re.finditer(r'([\w.\-]+\.(?:sh|py|js|ts|rb|php|go|rs|c|cpp|h|cfg|conf|ini|yaml|yml|toml|json|txt|md))', user_input):
            name = m.group(1)
            # Szukaj w katalogu projektu i w katalogach absolutnych wspomnianych w user_input
            dir_match = re.search(r'(/[\w/]+)', user_input)
            if dir_match:
                candidate_paths.append(str(Path(dir_match.group(1)) / name))
            if self.project_root:
                candidate_paths.append(str(self.project_root / name))

        # 3. Ścieżki z treści message (model może je wymienić)
        for m in re.finditer(r'`([\w/.\-]+\.(?:sh|py|js|ts|rb|php|go|rs|c|cpp|h))`', message):
            name = m.group(1)
            if '/' not in name and self.project_root:
                candidate_paths.append(str(self.project_root / name))
            elif name.startswith('/'):
                candidate_paths.append(name)

        # Sprawdź które pliki faktycznie istnieją
        existing = []
        seen = set()
        for p in candidate_paths:
            resolved = str(Path(p).expanduser().resolve())
            if resolved not in seen:
                seen.add(resolved)
                if Path(resolved).is_file():
                    existing.append(resolved)

        if not existing:
            return None

        # Weź pierwszy istniejący plik
        file_path = existing[0]
        try:
            file_content = Path(file_path).read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            if self.logger:
                self.logger.warning(f"_inject_existing_file: nie udało się wczytać {file_path}: {e}")
            return None

        # Wstrzyknij treść do messages jako wynik "read_file"
        inject_result = [{
            "type": "file_content",
            "path": file_path,
            "content": file_content[:4000],
            "instruction": (
                f"Masz treść pliku {file_path}. "
                "TERAZ wykonaj żądaną modyfikację używając patch_file z ścieżką absolutną. "
                "NIE twórz nowego pliku — edytuj istniejący."
            )
        }]
        messages.append({
            "role": "user",
            "content": __import__('json').dumps(inject_result, ensure_ascii=False)
        })

        if self.logger:
            self.logger.info(f"_inject_existing_file: wstrzyknięto {file_path} ({len(file_content)} znaków)")

        return file_path

    def _rescue_code_from_message(self, message: str) -> dict | None:
        """Wykryj bloki kodu w tekście i stwórz akcje create_file."""
        return self._json_parser.rescue_code_from_message(message)

    def _is_project_reasonable_size(self) -> bool:
        if not self.project_root:
            return False
        
        try:
            count = 0
            for _ in self.project_root.rglob("*"):
                count += 1
                if count > 500:
                    return False
            return True
        except Exception:
            return False

    def _ensure_project_analyzed(self):
        if self.project_analyzed:
            return
        
        if self.global_mode or self.memory is None or self.analyzer is None:
            return
        
        if not self.memory.data.get("project_type"):
            self.ui.verbose("Analizuję projekt...")
            analysis = self.analyzer.analyze()
            
            if analysis.get("type"):
                self.memory.data["project_type"] = analysis["type"]
                self.memory.data["tech_stack"] = analysis.get("technology", [])
                self.memory._save()
        
        self.project_analyzed = True


    def run(self, user_input: str):
        """Deleguje do AgentRunnerMixin.run()."""
        from core.agent_runner import AgentRunnerMixin
        # Bind mixin methods dynamically (first call injects them)
        if not hasattr(AIAgent, '_runner_injected'):
            for name in dir(AgentRunnerMixin):
                if name.startswith('_') or name == 'run':
                    method = getattr(AgentRunnerMixin, name)
                    if callable(method) and not hasattr(AIAgent, name):
                        setattr(AIAgent, name, method)
            AIAgent._runner_injected = True
        return AgentRunnerMixin.run(self, user_input)

    def _execute_with_transaction(self, actions: List[Dict]) -> List:
        """
        Wykonaj akcje w transakcji z rollbackiem.
        
        Returns:
            Lista wyników akcji
        """
        if not self.tx_manager:
            # Fallback: wykonaj bez transakcji (global mode)
            return [self.execute_action(a) for a in actions]
        
        # Utwórz transakcję
        tx = self.tx_manager.create_transaction()
        tx.begin()
        
        if self.logger:
            self.logger.info(f"Transaction started: {tx.tx_id}")
        
        results = []
        rollback_reason = None
        
        try:
            for i, action in enumerate(actions, 1):
                self.ui.verbose(f"[{i}/{len(actions)}] {action['type']}")
                
                # Backup przed modyfikacją
                if action.get("type") in ["edit_file", "delete_file", "move_file"]:
                    path = action.get("path") or action.get("from")
                    if path:
                        try:
                            tx.stage_backup(Path(path))
                        except Exception as e:
                            self.ui.verbose(f"Backup warning: {e}")
                
                # Wykonaj akcję
                try:
                    result = self.execute_action(action)
                except (UnicodeDecodeError, UnicodeEncodeError) as e:
                    # Binarny plik (np. .pyc w szablonie) — nie rollbackuj, tylko skip
                    self.ui.warning(f"⚠ Akcja #{i} pominięta (plik binarny): {e}")
                    results.append({"type": "skipped_binary", "reason": str(e)})
                    continue
                results.append(result)
                
                # Sprawdź czy nie ma błędu
                if isinstance(result, str) and result.startswith("[BŁĄD]"):
                    rollback_reason = f"Błąd w akcji #{i}: {result}"
                    raise Exception(rollback_reason)
                
                # NOWE: Sprawdź czy to blokada destrukcyjna
                if isinstance(result, dict) and result.get("type") == "blocked_destructive":
                    rollback_reason = f"Blokada destrukcyjna: {result.get('reason')}"
                    raise Exception(rollback_reason)
        
        except Exception as e:
            # Rollback
            self.ui.error(f"Błąd podczas wykonywania: {e}")
            self.ui.warning("Wycofywanie zmian...")
            
            if self.logger:
                self.logger.warning(f"Transaction rollback: {tx.tx_id}, reason: {e}")
            
            rollback_result = tx.rollback(reason=str(e))
            
            self.ui.section("ROLLBACK")
            self.ui.warning(f"Przywrócono {len(rollback_result['restored'])} plików")
            
            if rollback_result['errors']:
                self.ui.error("Błędy podczas rollbacku:")
                for err in rollback_result['errors']:
                    self.ui.error(f"  • {err}")
            
            # Zwróć partial results + info o rollbacku
            results.append({
                "type": "transaction_rolled_back",
                "reason": str(e),
                "restored_files": rollback_result['restored'],
                "errors": rollback_result['errors']
            })
            
            return results
        
        # Sukces - commit
        tx.commit()
        
        if self.logger:
            self.logger.info(f"Transaction committed: {tx.tx_id}")
        
        return results
    
    def _run_global_mode(self, user_input: str):
        self.conversation.add_user_message(user_input)

        # ─── RAG ─────────────────────────────────────────────────────────────
        rag_context = self._get_rag_context(user_input)
        # ─────────────────────────────────────────────────────────────────────

        # ─── Wykryj i wyciągnij ścieżki obrazów z user_input ───────────────
        _img_exts  = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tiff')
        _has_image = any(ext in user_input.lower() for ext in _img_exts)
        _image_paths = self._extract_image_paths(user_input) if _has_image else []
        # ─────────────────────────────────────────────────────────────────────

        # Web Search auto-trigger w trybie globalnym
        web_search_context = ""
        if self.config.get("web_search", {}).get("enabled", False):
            if self.config.get("web_search", {}).get("auto_trigger", True):
                engine = self.web_search_engine
                if engine.detect_trigger(user_input):
                    self.ui.verbose("Wyszukiwanie w internecie...")
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
        
        # Pętla akcji (jak w trybie projektowym) - max 5 iteracji
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
                self.ui.verbose(f"Odpowiedź: {raw[:100]}")
                return
            
            # Wiadomość do wyświetlenia
            if data.get("message") and not data.get("actions"):
                # Krok 1: Sprawdź czy model opisał edycję istniejącego pliku
                _file_injected = self._inject_existing_file_if_needed(
                    user_input, data["message"], messages
                )
                if _file_injected:
                    if self.logger:
                        self.logger.info(
                            f"[global] File injected for edit: {_file_injected} — kontynuuję iterację"
                        )
                    messages.append({"role": "assistant", "content": raw})
                    continue

                # Krok 2: Sprawdź czy message zawiera bloki kodu — zamień na create_file
                rescued = self._rescue_code_from_message(data["message"])
                if rescued:
                    data = rescued
                else:
                    self.ui.ai_message(data["message"])
                    self.conversation.add_ai_message(data["message"])
                    # Auto-wyciągnij fakty z rozmowy (jeśli włączone w config)
                    mem_cfg = self.config.get("memory", {})
                    if mem_cfg.get("auto_extract", True):
                        saved = self.global_memory.auto_extract_and_save(user_input, data["message"])
                        if mem_cfg.get("show_saved", True):
                            for f in saved:
                                self.ui.success(f"💾 Zapamiętano [{f['id']}]: {f['content']}")

            # Jeśli brak akcji - zakończ
            actions = data.get("actions", [])
            if not actions:
                if not data.get("message"):
                    self.ui.warning("Model nie zwrócił odpowiedzi")
                    if self.logger:
                        self.logger.log_model_response(user_input, raw, parsed=data)
                        self.logger.error(
                            f"[global] Model zwrócił pusty JSON. user_input={user_input!r} raw={raw!r}"
                        )
                return
            
            # Wykonaj akcje (tryb globalny ma ograniczone akcje)
            # create_file/edit_file/mkdir/delete_file/move_file dozwolone
            # gdy ścieżka absolutna lub ~/  — user wie co robi
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
                
                # Wyświetl opis akcji
                desc = self._describe_action(action)
                self.ui.status(f"→ {desc}")
                
                # Wykonaj akcję
                if t == "run_command":
                    command = action.get("command", "")
                    if not command:
                        action_results.append("[BŁĄD] run_command bez command")
                        continue
                    
                    # Zatrzymaj spinner (może potrzebować TTY)
                    if self.ui and self.ui.spinner_active:
                        self.ui.spinner_stop()
                    
                    try:
                        import subprocess
                        timeout = self.config.get('execution', {}).get('timeout_seconds', 30)
                        result = subprocess.run(
                            command,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=timeout
                        )
                        output = result.stdout.strip()
                        stderr = result.stderr.strip()
                        
                        if output:
                            print(output)
                        
                        action_results.append({
                            "type": "command_result",
                            "command": command,
                            "exit_code": result.returncode,
                            "stdout": output[:2000],
                            "stderr": stderr[:500] if stderr else ""
                        })
                    except Exception as e:
                        err = f"[BŁĄD] {e}"
                        action_results.append(err)
                
                elif t in ("web_search", "web_scrape"):
                    result = self._execute_global_web_action(action)
                    action_results.append(result)

                    if not isinstance(result, dict):
                        continue

                    rtype = result.get("type", "")

                    # web_search: wyświetl wyniki
                    if rtype == "web_search_results":
                        for r in result.get("results", [])[:5]:
                            if not isinstance(r, dict):
                                continue
                            title   = r.get("title", "")
                            url     = r.get("url", "")
                            snippet = r.get("snippet", "")
                            domain  = r.get("domain", "")
                            print(f"  [{domain}] {title}")
                            if snippet:
                                print(f"  {snippet[:120]}")
                            print(f"  {url}\n")

                    # web_scrape: pokaż tytuł i skrót
                    elif rtype == "web_scrape_result":
                        title   = result.get("title", "")
                        success = result.get("success", False)
                        md_len  = len(result.get("markdown", ""))
                        if success:
                            self.ui.verbose(f"  ✓ Pobrano: {title or action.get('url', '')} ({md_len} znaków)")
                        else:
                            self.ui.warning(f"  ✗ Scraping nieudany: {action.get('url', '')}")

                    # web_scrape_blocked: domena spoza whitelist - powiedz o tym głośno
                    elif rtype == "web_scrape_blocked":
                        domain = result.get("domain", action.get("url", ""))
                        self.ui.warning(
                            f"  ✗ Domena zablokowana: {domain}\n"
                            f"    Dodaj do whitelist: ai web-search domains add {domain}"
                        )
                        # Zastąp wynik czytelnym błędem żeby model mógł odpowiedzieć sensownie
                        action_results[-1] = {
                            "type": "web_scrape_blocked",
                            "domain": domain,
                            "message": (
                                f"Domena '{domain}' jest poza whitelistą i scraping został zablokowany. "
                                f"Użytkownik musi dodać ją komendą: ai web-search domains add {domain}"
                            )
                        }

                    # web_search wyłączony
                    elif rtype == "web_search_disabled":
                        self.ui.warning(f"  ✗ Web search wyłączony. Włącz: ai web-search enable")

                    # brakujące zależności
                    elif rtype == "web_search_missing_deps":
                        missing = result.get("missing", [])
                        self.ui.warning(f"  ✗ Brak zależności: {', '.join(missing)}")
                
                elif t in ("create_file", "edit_file"):
                    from pathlib import Path
                    raw_path = action.get("path", "")
                    if not raw_path:
                        action_results.append("[BŁĄD] create_file/edit_file bez path")
                        continue
                    file_path = Path(raw_path).expanduser()
                    # Tryb globalny: wymagaj ścieżki absolutnej lub ~/
                    if not file_path.is_absolute():
                        action_results.append(
                            f"[BŁĄD] W trybie globalnym podaj ścieżkę absolutną (np. /home/user/plik.sh), "
                            f"nie względną: {raw_path}"
                        )
                        continue
                    content_str = action.get("content", "")
                    try:
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_path.write_text(content_str, encoding="utf-8")
                        verb = "Zaktualizowano" if (t == "edit_file" and file_path.exists()) else "Utworzono"
                        msg = f"{verb}: {file_path}"
                        print(f"  ✓ {msg}")
                        if self.logger:
                            self.logger.info(f"[global] {t}: {file_path}")
                        action_results.append(msg)
                    except Exception as e:
                        action_results.append(f"[BŁĄD] {t} {file_path}: {e}")

                elif t == "mkdir":
                    from pathlib import Path
                    raw_path = action.get("path", "")
                    dir_path = Path(raw_path).expanduser()
                    try:
                        dir_path.mkdir(parents=True, exist_ok=True)
                        msg = f"Utworzono katalog: {dir_path}"
                        print(f"  ✓ {msg}")
                        action_results.append(msg)
                    except Exception as e:
                        action_results.append(f"[BŁĄD] mkdir {dir_path}: {e}")

                elif t == "delete_file":
                    from pathlib import Path
                    raw_path = action.get("path", "")
                    file_path = Path(raw_path).expanduser()
                    if not file_path.is_absolute():
                        action_results.append(f"[BŁĄD] delete_file wymaga ścieżki absolutnej: {raw_path}")
                        continue
                    try:
                        if file_path.exists():
                            file_path.unlink()
                            msg = f"Usunięto: {file_path}"
                        else:
                            msg = f"[BŁĄD] Plik nie istnieje: {file_path}"
                        print(f"  ✓ {msg}")
                        action_results.append(msg)
                    except Exception as e:
                        action_results.append(f"[BŁĄD] delete_file {file_path}: {e}")

                elif t == "move_file":
                    from pathlib import Path
                    src = Path(action.get("from", "")).expanduser()
                    dst = Path(action.get("to", "")).expanduser()
                    try:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        src.rename(dst)
                        msg = f"Przeniesiono: {src} → {dst}"
                        print(f"  ✓ {msg}")
                        action_results.append(msg)
                    except Exception as e:
                        action_results.append(f"[BŁĄD] move_file {src} → {dst}: {e}")

                elif t == "list_files":
                    # W trybie globalnym - używaj absolutnych ścieżek lub cwd
                    pattern = action.get("pattern", "*")
                    recursive = action.get("recursive", False)
                    import glob
                    from pathlib import Path
                    
                    # Rozwiń ~ w pattern
                    pattern_expanded = str(Path(pattern).expanduser())
                    
                    try:
                        if recursive:
                            files = glob.glob(pattern_expanded, recursive=True)
                        else:
                            files = glob.glob(pattern_expanded)
                        
                        if files:
                            for f in sorted(files)[:50]:
                                print(f"  {f}")
                        else:
                            print(f"  (brak plików pasujących do: {pattern})")
                        
                        action_results.append({
                            "type": "file_list",
                            "pattern": pattern,
                            "files": files[:50]
                        })
                    except Exception as e:
                        action_results.append(f"[BŁĄD] list_files: {e}")
                
                elif t == "read_file":
                    from pathlib import Path
                    path = Path(action.get("path", "")).expanduser()
                    try:
                        content = path.read_text(encoding="utf-8", errors="replace")
                        action_results.append({
                            "type": "file_content",
                            "path": str(path),
                            "content": content[:3000]
                        })
                    except Exception as e:
                        action_results.append(f"[BŁĄD] read_file {path}: {e}")

                elif t == "patch_file":
                    from pathlib import Path
                    from utils.search_replace import SearchReplacePatcher, SearchReplaceParser
                    raw_path = action.get("path", "")
                    if not raw_path:
                        action_results.append("[BŁĄD] patch_file bez pola 'path'")
                        continue
                    file_path = Path(raw_path).expanduser()
                    if not file_path.is_absolute():
                        action_results.append(
                            f"[BŁĄD] W trybie globalnym podaj ścieżkę absolutną (np. /home/user/plik.sh): {raw_path}"
                        )
                        continue
                    patches = action.get("patches")
                    diff_text = action.get("diff", "")
                    if not patches and not diff_text:
                        action_results.append("[BŁĄD] patch_file wymaga pola 'patches' lub 'diff'")
                        continue
                    try:
                        # Wczytaj plik bezpośrednio (bez fs)
                        original = file_path.read_text(encoding="utf-8")
                        if patches is not None:
                            blocks = SearchReplaceParser.from_patches_list(patches)
                        else:
                            blocks = SearchReplaceParser.parse(diff_text)
                        new_content = original
                        errors = []
                        for block in blocks:
                            if block.search in new_content:
                                new_content = new_content.replace(block.search, block.replace, 1)
                            else:
                                errors.append(f"Nie znaleziono fragmentu: {block.search[:60]!r}")
                        if errors:
                            for err in errors:
                                action_results.append(f"[BŁĄD] patch_file: {err}")
                        else:
                            file_path.write_text(new_content, encoding="utf-8")
                            msg = f"Zaktualizowano: {file_path}"
                            print(f"  ✓ {msg}")
                            if self.logger:
                                self.logger.info(f"[global] patch_file: {file_path}")
                            action_results.append(msg)
                    except Exception as e:
                        action_results.append(f"[BŁĄD] patch_file {file_path}: {e}")

                elif t in ("clipboard_read", "clipboard_write"):
                    result = self.execute_action(action)
                    action_results.append(result)
                
                elif t == "open_path":
                    import subprocess
                    path = action.get("path", "")
                    try:
                        subprocess.Popen(["xdg-open", path],
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
                        action_results.append(f"Otworzono {path}")
                    except Exception as e:
                        action_results.append(f"[BŁĄD] {e}")

                elif t == "use_template":
                    template_name = action.get("template", "")
                    dest = action.get("dest", ".")
                    dest_path = Path(dest).expanduser().resolve()
                    variables = dict(action.get("variables", {}))
                    variables.setdefault("AUTHOR", self.config.get("nick", "user"))
                    try:
                        result = apply_template(template_name, dest_path, variables, overwrite=action.get("overwrite", False))
                    except (UnicodeDecodeError, UnicodeEncodeError) as e:
                        # Binarny plik w szablonie (np. .pyc) - pomiń bez rollbacku
                        result = {"success": True, "created": [], "skipped": [], "error": None}
                    if result["success"]:
                        summary = f"Szablon '{template_name}' zastosowany w {dest_path} ({len(result['created'])} plików)"
                        print(f"  ✓ {summary}")
                        action_results.append({"type": "template_applied", **result})
                    else:
                        action_results.append(f"[BŁĄD] use_template: {result['error']}")

                else:
                    action_results.append(f"[INFO] Nieznana akcja: {t}")
            
            # Wstrzyknij wyniki do kolejnej iteracji
            messages.append({
                "role": "user",
                "content": json.dumps(action_results, ensure_ascii=False)
            })
        
        # Koniec pętli - jeśli coś poszło nie tak
        self.ui.verbose("Osiągnięto limit iteracji")

    def _execute_global_web_action(self, action: dict):
        """Wykonaj web_search lub web_scrape w trybie globalnym."""
        t = action.get("type")
        engine = self.web_search_engine
        
        if t == "web_search":
            query = action.get("query", "")
            if not engine.is_enabled:
                return {
                    "type": "web_search_disabled",
                    "message": "Web search wyłączony. Włącz: ai web-search enable"
                }
            missing = engine.ensure_dependencies()
            if missing:
                return {"type": "web_search_missing_deps", "missing": missing}
            try:
                results = engine.search(query, max_results=action.get("max_results", 5))
                return {
                    "type": "web_search_results",
                    "query": query,
                    "results": [r.to_dict() for r in results],
                    "count": len(results)
                }
            except (WebSearchError, RateLimitError) as e:
                return {"type": "web_search_error", "message": str(e)}
        
        elif t == "web_scrape":
            url = action.get("url", "")
            user_provided = action.get("user_provided_url", False)
            if not user_provided and not engine.is_domain_allowed(url):
                import urllib.parse
                domain = urllib.parse.urlparse(url).netloc
                return {
                    "type": "web_scrape_blocked",
                    "domain": domain,
                    "message": (
                        f"Domena '{domain}' nie jest na whitelist. "
                        f"Dodaj: ai web-search domains add {domain}"
                    )
                }
            sr = engine.scrape(url)
            return {
                "type": "web_scrape_result",
                "url": url,
                "title": sr.title,
                "markdown": sr.markdown[:3000],
                "success": sr.success
            }
        
        return {"type": "error", "message": f"Nieznana akcja web: {t}"}
    
    def _execute_pending_actions(self, actions: List[Dict]):
        self.ui.section("Wykonywanie akcji")
        
        results = self._execute_with_transaction(actions)
        
        had_rollback = any(
            isinstance(r, dict) and r.get("type") == "transaction_rolled_back"
            for r in results
        )
        
        if had_rollback:
            self.ui.section("BŁĄD — Rollback")
            self.ui.warning("⚠ Operacja nie powiodła się — zmiany zostały wycofane.")
        else:
            self.ui.section("Gotowe")
        self._summarize_results(actions, results)

    def _needs_confirm(self, actions):
        """
        Sprawdź czy akcje wymagają potwierdzenia.

        ZASADA:
        - DESTRUCTIVE (delete_file, move_file) → ZAWSZE confirm
        - download_media, convert_media → ZAWSZE confirm (duże operacje)
        - run_command z destrukcyjną komendą (rm, dd, shred...) → ZAWSZE confirm
        - Reszta (SAFE + MODIFY + read-only/modify run_command) → BEZ confirm
          (list_files, read_file, create_file, chmod, mkdir, curl, find itp.)
        """
        categorized = ActionValidator.categorize_by_risk(actions)
        
        # DESTRUCTIVE (delete_file, move_file) zawsze wymaga confirm
        if categorized[ActionRisk.DESTRUCTIVE]:
            return True
        
        # EXECUTE - tylko naprawdę niebezpieczne wymagają confirm
        for action in categorized[ActionRisk.EXECUTE]:
            action_type = action.get("type")
            
            # Media tasks (download_media, convert_media) - duże operacje, confirm
            if action_type in ["download_media", "convert_media", "process_image", "batch_images"]:
                return True
            
            # run_command - tylko destrukcyjne komendy wymagają confirm
            if action_type == "run_command":
                command = action.get("command", "")
                risk, _ = CommandClassifier.classify(command)
                if risk == CmdRisk.DESTRUCTIVE:
                    return True
                # READ_ONLY i MODIFY (mkdir, curl, chmod, cp itp.) = bez confirm
        
        # Bardzo dużo modyfikacji plików - zapytaj (bezpiecznik)
        modify_threshold = self.config.get('execution', {}).get('auto_confirm_modify_under', 10)
        if len(categorized[ActionRisk.MODIFY]) >= modify_threshold:
            return True
        
        return False

    def _extract_intent_from_data(self, data, user_input, actions):
        if data.get("intent"):
            return data["intent"]
        
        if self.memory:
            return self.memory._extract_intent(user_input, actions)
        
        return "other"

    def _is_project_question(self, user_input: str) -> bool:
        lower = user_input.lower()
        
        project_keywords = [
            "co robi ten projekt",
            "o czym jest ten projekt",
            "czym jest ten projekt",
            "co to za projekt",
            "opisz projekt",
            "jaki jest ten projekt",
            "jak działa ten projekt",
            "co jest w tym projekcie",
            "co robi to repo",
            "o czym jest to repo"
        ]
        
        return any(keyword in lower for keyword in project_keywords)

    def _handle_project_question(self):
        if not self.analyzer:
            self.ui.error("Analiza projektu dostępna tylko w trybie projektowym")
            self.ui.verbose("Przejdź do katalogu z projektem")
            return
        
        self.ui.spinner_start("Analizuję projekt...")
        
        try:
            summary = self.analyzer.get_summary()
            self.ui.spinner_stop()
            self.ui.section("Analiza projektu")
            print(summary)
        except Exception as e:
            self.ui.spinner_stop()
            self.ui.error(f"Nie udało się przeanalizować projektu: {e}")

    # ── Action Executor (delegacja do core/action_executor.py) ─────────────────

    def _describe_action(self, action) -> str:
        """Opis akcji do wyświetlenia użytkownikowi przed wykonaniem."""
        return self._executor.describe_action(action)

    def _summarize_results(self, actions, results):
        """Podsumuj wyniki wykonanych akcji."""
        return self._executor.summarize_results(actions, results)

    def _pre_edit_reread(self, action: dict) -> str | None:
        """Przed edycją odczytaj aktualny plik i zwaliduj parametry."""
        return self._executor.pre_edit_reread(action)

    def execute_action(self, action) -> object:
        """Wykonaj pojedynczą akcję zwróconą przez model LLM."""
        return self._executor.execute_action(action)
