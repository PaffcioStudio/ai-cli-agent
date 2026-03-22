"""
agent_prompts.py – budowanie system promptów dla AIAgent.

Wydzielony z agent.py (refaktoryzacja: agent.py > 2000 linii).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import AIAgent


class AgentPromptMixin:
    """Mixin odpowiedzialny za budowanie promptów."""

    def _build_system_prompt(self: "AIAgent", user_input: str) -> str:
        """
        Buduje pełny system prompt per-request.
        core.txt (zawsze) + warstwy inject (wg triggera) + statyczny kontekst.
        """
        if hasattr(self, '_prompt_builder') and self._prompt_builder:
            core_with_layers = self._prompt_builder.build(user_input)
        else:
            core_with_layers = self.system_prompt  # fallback

        static = getattr(self, '_static_context', '')
        return core_with_layers + static

    def _json_reminder(self: "AIAgent") -> str:
        """
        Zwróć suffix przypominający o formacie JSON.
        Modele thinking (qwen3) i cloud mają tendencję do odpowiadania swobodnym
        tekstem zamiast JSON.
        """
        return (
            "\n\n[WAŻNE: Odpowiedz WYŁĄCZNIE poprawnym JSON. "
            "Żadnego tekstu przed ani po. Żadnego markdown. "
            "Format: {\"actions\": [...]} lub {\"message\": \"...\"}]"
        )

    def _build_global_prompt(self: "AIAgent") -> str:
        from project.global_mode import GlobalMode
        from utils.template_manager import get_template_context_for_prompt

        system_context = GlobalMode.format_system_context_for_prompt()
        config_path = Path.home() / ".config" / "ai" / "config.json"
        template_context = get_template_context_for_prompt()

        ws_config = self.config.get("web_search", {})
        ws_enabled = ws_config.get("enabled", False)
        ws_engine = ws_config.get("engine", "duckduckgo")

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
FORMAT ODPOWIEDZI
====================

Zawsze zwracaj WYŁĄCZNIE poprawny JSON.

{{"message": "odpowiedź tekstowa"}}

lub z akcją:
{{"actions": [{{"type": "run_command", "command": "..."}}]}}

NIE wolno zwracać tekstu poza JSON.
NIE używaj Markdowna (**, __, _, #).

====================
KLUCZOWE ZASADY
====================

1. ZAWSZE próbuj wykonać zadanie - nigdy nie odmawiaj gdy masz narzędzia
2. NIE PYTAJ O POTWIERDZENIE gdy użytkownik wydał jasne polecenie
3. Pogoda, kurs walut, aktualności → curl lub web_search (NIE odmawiaj!)
4. Przeglądanie pliku → sed -n lub grep (szybkie i precyzyjne)
5. Szukanie w kodzie → grep -n (z numerami linii)
6. Duże pliki → sed -n 'N,Mp' zamiast read_file całego pliku
7. Mów po polsku jak użytkownik pisze po polsku

INFORMACJE O AI CLI:
- Konfiguracja: {config_path}
- Edytuj: ai config edit
- Pomoc: ai help

{template_context}
"""
