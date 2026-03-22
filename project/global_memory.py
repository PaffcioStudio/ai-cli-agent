"""
Globalna pamięć persystentna AI CLI.

Przechowuje fakty o użytkowniku, preferencje i konfigurację
niezależnie od projektu. Plik: ~/.config/ai/memory.json
"""
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional


MEMORY_FILE = Path.home() / ".config" / "ai" / "memory.json"


class GlobalMemory:
    """Persystentna pamięć globalna — fakty o użytkowniku i preferencje."""

    def __init__(self):
        self.memory_file = MEMORY_FILE
        self.data = self._load()

    def _load(self) -> dict:
        if not self.memory_file.exists():
            return self._default()
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return self._default()

    def _default(self) -> dict:
        return {
            "facts": [],        # [{id, content, category, created_at}]
            "version": 1
        }

    def _save(self):
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[WARN] Nie udało się zapisać pamięci globalnej: {e}")

    def _next_id(self) -> int:
        if not self.data["facts"]:
            return 1
        return max(f.get("id", 0) for f in self.data["facts"]) + 1

    # ── Public API ─────────────────────────────────────────────────────────

    def add(self, content: str, category: str = "general") -> dict:
        """Dodaj nowy fakt do pamięci. Zwraca dodany fakt."""
        fact = {
            "id": self._next_id(),
            "content": content.strip(),
            "category": category,
            "created_at": datetime.now().isoformat()
        }
        self.data["facts"].append(fact)
        self._save()
        return fact

    def remove(self, fact_id: int) -> bool:
        """Usuń fakt o podanym ID. Zwraca True jeśli usunięto."""
        before = len(self.data["facts"])
        self.data["facts"] = [f for f in self.data["facts"] if f.get("id") != fact_id]
        if len(self.data["facts"]) < before:
            self._save()
            return True
        return False

    def list_facts(self, category: Optional[str] = None) -> list:
        """Zwróć listę faktów, opcjonalnie filtrowaną po kategorii."""
        facts = self.data["facts"]
        if category:
            facts = [f for f in facts if f.get("category") == category]
        return facts

    def clear(self):
        """Wyczyść całą pamięć."""
        self.data["facts"] = []
        self._save()

    def get_context_for_prompt(self) -> str:
        """Zwróć sformatowany kontekst do system promptu."""
        facts = self.data.get("facts", [])
        if not facts:
            return ""

        lines = ["====================",
                 "PAMIĘĆ GLOBALNA (fakty o użytkowniku)",
                 "====================",
                 ""]
        for f in facts:
            cat = f.get("category", "general")
            content = f.get("content", "")
            lines.append(f"[{cat}] {content}")

        lines += [
            "",
            "Używaj tych informacji w odpowiedziach gdy są istotne.",
            "NIE pytaj ponownie o rzeczy które już wiesz.",
            ""
        ]
        return "\n".join(lines)

    def try_extract_explicit_save(self, user_input: str) -> str | None:
        """
        Wykryj jawne żądanie zapamiętania faktu w wiadomości użytkownika.
        Zwraca treść faktu do zapisania lub None jeśli brak żądania.

        Przykłady które wykrywa:
          "zapamiętaj że używam mygit zamiast git"
          "zapisz że preferuję dark mode"
          "zapamiętaj: jestem z Gdańska"
          "zapamietaj ze mam psa"

        NIE wykrywa (zwraca None — to zadania dla AI, nie fakty):
          "zapamiętaj jakie mam preferencje"
          "potrzebuje do memory notatkę na temat moich preferencji"
          "zapisz do pamięci moje preferencje z rozmowy"
        """
        patterns = [
            r"(?:zapamiętaj|zapamietaj|zapisz|zanotuj|note that|remember)[,:\s]+(?:że|ze|to|that)?\s+(.+)",
            r"(?:zapamiętaj|zapamietaj|zapisz|zanotuj)[,:\s]+(.+)",
        ]

        # Frazy wskazujące że to polecenie dla AI (żądanie podsumowania/wygenerowania),
        # a nie konkretny fakt do zapisania
        AI_TASK_INDICATORS = [
            r"^(jakie|co|które|jak|ile|czego|skąd|kiedy|gdzie)\b",  # pytania zaimkowe
            r"\b(z rozmowy|z chatu|z kontekstu|z tej rozmowy)\b",
            r"\b(moje preferencje|moich preferencji|na temat mnie|o mnie)\b",
            r"\b(notatkę|notatki|podsumowanie|streszczenie)\b",
            r"\b(napisz|stwórz|przygotuj|wygeneruj|zrób)\b",
        ]

        text = user_input.strip()
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                fact = m.group(1).strip().rstrip(".")
                if len(fact) <= 3:
                    continue
                # Sprawdź czy to polecenie do AI zamiast konkretny fakt
                for indicator in AI_TASK_INDICATORS:
                    if re.search(indicator, fact, re.IGNORECASE):
                        return None  # To zadanie dla AI, nie fakt
                return fact
        return None

    def auto_extract_and_save(self, user_input: str, ai_response: str) -> list:
        """
        Automatycznie wyciągnij i zapisz istotne fakty z rozmowy.
        1. Najpierw sprawdza jawne żądanie zapamiętania (priorytet).
        2. Potem heurystyka na wzorcach.
        Zwraca listę nowo dodanych faktów.
        """
        added = []
        existing_contents = {f["content"].lower() for f in self.data["facts"]}

        # 1. Jawne żądanie zapamiętania
        explicit = self.try_extract_explicit_save(user_input)
        if explicit and explicit.lower() not in existing_contents:
            # Wykryj kategorię
            lower = explicit.lower()
            if any(w in lower for w in ["używam", "zamiast", "narzędzie", "tool"]):
                cat = "tool"
            elif any(w in lower for w in ["python", "javascript", "rust", "java", "język"]):
                cat = "language"
            elif any(w in lower for w in ["kde", "gnome", "ubuntu", "arch", "edytor", "ide"]):
                cat = "environment"
            elif any(w in lower for w in ["jestem", "nazywam", "nick", "imię", "mieszkam", "z gdańska"]):
                cat = "identity"
            else:
                cat = "general"
            fact = self.add(explicit, cat)
            added.append(fact)
            existing_contents.add(explicit.lower())
            return added  # Jawne żądanie = zakończ, nie kontynuuj heurystyki

        # 2. Heurystyka na wzorcach w całej rozmowie
        combined = (user_input + " " + ai_response).lower()

        patterns = [
            (r"(?:używam|korzystam z|mam własne?(?:go)?)\s+([a-z][a-zA-Z0-9_-]+)\s+(?:zamiast|jako|do)\s+(\w+)", "tool"),
            (r"([a-z][a-zA-Z0-9_-]+)\s+(?:to|jest)\s+(?:mój|własny|autorski)\s+(\w+)", "tool"),
            (r"(?:używam|piszę w|programuję w|preferuję)\s+(python|javascript|typescript|rust|go|java|kotlin)", "language"),
            (r"(?:używam|mam|korzystam z)\s+(kde|gnome|wayland|x11|ubuntu|arch|fedora|debian|manjaro)", "environment"),
        ]

        for pattern, category in patterns:
            for match in re.finditer(pattern, combined):
                groups = [g for g in match.groups() if g]
                if len(groups) >= 2:
                    fact_text = f"Używa '{groups[0]}' jako {groups[1]}"
                else:
                    fact_text = f"Preferuje {groups[0]}"

                if fact_text.lower() not in existing_contents:
                    fact = self.add(fact_text, category)
                    added.append(fact)
                    existing_contents.add(fact_text.lower())

        return added

    def __len__(self):
        return len(self.data.get("facts", []))

    def __bool__(self):
        return len(self) > 0
