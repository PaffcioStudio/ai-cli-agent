"""
conversation_history.py — persystentna historia rozmów per katalog.

PROBLEM:
    ConversationState żyje tylko w RAM. Po Ctrl+C/Q znika.
    Użytkownik pyta "na czym skończyliśmy" — AI nie wie.

ROZWIĄZANIE:
    - Historia zapisywana do .ai-logs/conversation_history.jsonl
    - Przy starcie: wykrycie poprzedniej historii → pytanie T/N
    - T → wczytaj kontekst, N → wyczyść i zacznij od nowa
    - Można wyłączyć przez config: conversation.save_history = false

PLIK HISTORII:
    <project_root>/.ai-logs/conversation_history.jsonl
    Każda linia = jedna wymiana {role, content, timestamp}

USTAWIENIA CONFIG:
    conversation.save_history        (bool, domyślnie true)
    conversation.resume_prompt       (bool, domyślnie true)
        — czy pytać o wznowienie przy starcie
    conversation.max_saved_messages  (int, domyślnie 40)
        — ile ostatnich wiadomości trzymać w pliku
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict


HISTORY_FILENAME = "conversation_history.jsonl"


class ConversationHistory:
    """
    Zarządza persystentną historią rozmów dla danego katalogu projektu.
    Zapis/odczyt .ai-logs/conversation_history.jsonl
    """

    def __init__(self, project_root: Path, config: Optional[Dict] = None):
        self.project_root = project_root
        self.config = config or {}
        self._cfg = self.config.get("conversation", {})

        self.save_history: bool = self._cfg.get("save_history", True)
        self.max_saved: int     = self._cfg.get("max_saved_messages", 40)

        self._log_dir = project_root / ".ai-logs"
        self._history_file = self._log_dir / HISTORY_FILENAME

    # ── Odczyt ────────────────────────────────────────────────────────────────

    def exists(self) -> bool:
        """Czy plik historii istnieje i ma przynajmniej jedną wiadomość."""
        if not self._history_file.exists():
            return False
        try:
            with open(self._history_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        return True
        except Exception:
            pass
        return False

    def load(self) -> List[Dict]:
        """
        Wczytaj historię z pliku.
        Zwraca listę słowników {role, content, timestamp}.
        """
        if not self._history_file.exists():
            return []
        messages = []
        try:
            with open(self._history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception:
            return []
        return messages[-self.max_saved:]

    def last_timestamp(self) -> Optional[str]:
        """Zwraca timestamp ostatniej wiadomości (czytelny string) lub None."""
        messages = self.load()
        if not messages:
            return None
        ts = messages[-1].get("timestamp", "")
        if not ts:
            return None
        # Uprość ISO do czytelnego formatu
        try:
            dt = datetime.fromisoformat(ts)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return ts[:16]

    def last_exchange_preview(self) -> str:
        """
        Zwraca czytelne podsumowanie ostatniej wymiany do wyświetlenia w pytaniu.
        Format: 'User: <pierwsze 80 znaków>' lub pusty string.
        """
        messages = self.load()
        # Znajdź ostatnią wiadomość user
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                preview = content[:80].replace("\n", " ")
                if len(content) > 80:
                    preview += "…"
                return preview
        return ""

    # ── Zapis ─────────────────────────────────────────────────────────────────

    def append(self, role: str, content: str):
        """
        Dopisz jedną wiadomość do pliku historii.
        Nic nie robi gdy save_history=False.
        """
        if not self.save_history:
            return
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            entry = {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            }
            with open(self._history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._trim_if_needed()
        except Exception:
            pass  # Zapis historii nigdy nie powinien crashować agenta

    def _trim_if_needed(self):
        """Przytnie plik do max_saved_messages jeśli jest za długi."""
        try:
            lines = self._history_file.read_text(encoding="utf-8").splitlines()
            valid = [l for l in lines if l.strip()]
            if len(valid) > self.max_saved:
                trimmed = valid[-self.max_saved:]
                self._history_file.write_text(
                    "\n".join(trimmed) + "\n", encoding="utf-8"
                )
        except Exception:
            pass

    # ── Czyszczenie ───────────────────────────────────────────────────────────

    def clear(self):
        """Usuwa plik historii. Nowa sesja zaczyna od zera."""
        try:
            if self._history_file.exists():
                self._history_file.unlink()
        except Exception:
            pass

    # ── Konwersja do formatu ConversationState ────────────────────────────────

    def to_conversation_messages(self) -> List[Dict]:
        """
        Zwraca historię w formacie gotowym do wstrzyknięcia
        do ConversationState.messages (bez pola timestamp).
        """
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.load()
            if m.get("role") in ("user", "assistant")
        ]
