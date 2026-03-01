"""
Moduł decyzji semantycznych - rozumienie ZAMIARU zmian.
Odpowiada na pytanie: to jest zmiana lokalna czy globalna konwencja?
"""

from typing import Dict, List, Optional
from datetime import datetime
import json
from pathlib import Path

class SemanticDecision:
    """Pojedyncza decyzja semantyczna"""
    
    def __init__(self, 
                 decision_type: str,  # "terminology", "convention", "architecture"
                 scope: str,          # "global", "module", "file"
                 old_value: str,
                 new_value: str,
                 reason: Optional[str] = None):
        self.type = decision_type
        self.scope = scope
        self.old = old_value
        self.new = new_value
        self.reason = reason
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type,
            "scope": self.scope,
            "old": self.old,
            "new": self.new,
            "reason": self.reason,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SemanticDecision':
        decision = cls(
            data["type"],
            data["scope"],
            data["old"],
            data["new"],
            data.get("reason")
        )
        decision.timestamp = data.get("timestamp", datetime.now().isoformat())
        return decision


class SemanticDecisionManager:
    """
    Zarządza decyzjami semantycznymi projektu.
    Rozumie ZAMIAR zmian, nie tylko ich techniczną realizację.
    """
    
    def __init__(self, project_root: Path):
        self.root = project_root
        self.decisions_file = project_root / ".ai-decisions.json"
        self.decisions: List[SemanticDecision] = []
        self._load()
    
    def _load(self):
        """Wczytaj decyzje z pliku"""
        if not self.decisions_file.exists():
            return
        
        try:
            with open(self.decisions_file, 'r') as f:
                data = json.load(f)
                self.decisions = [
                    SemanticDecision.from_dict(d) 
                    for d in data.get("decisions", [])
                ]
        except Exception:
            pass
    
    def _save(self):
        """Zapisz decyzje do pliku"""
        try:
            data = {
                "decisions": [d.to_dict() for d in self.decisions],
                "updated_at": datetime.now().isoformat()
            }
            with open(self.decisions_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[WARN] Nie udało się zapisać decyzji: {e}")
    
    def add_decision(self, decision: SemanticDecision):
        """Dodaj nową decyzję semantyczną"""
        self.decisions.append(decision)
        self._save()
    
    def detect_semantic_change(self, actions: List[Dict], user_input: str) -> Optional[SemanticDecision]:
        """
        Wykryj czy zmiana jest decyzją semantyczną (nie tylko lokalną edycją).
        
        Sygnały:
        - użytkownik używa słów: "zamiast", "zmień na", "teraz nazywamy"
        - wiele plików dotknięte tą samą zmianą
        - zmiana w UI + README + komentarzach
        """
        lower_input = user_input.lower()
        
        # Terminologia
        terminology_signals = [
            "zamiast", "zmień", "teraz", "nazywaj", "używaj",
            "przejdź na", "zastąp", "od teraz"
        ]
        
        if any(signal in lower_input for signal in terminology_signals):
            # Spróbuj wyciągnąć starą i nową wartość
            old_new = self._extract_terminology_change(user_input)
            if old_new:
                old_term, new_term = old_new
                
                # Sprawdź czy dotyczy wielu plików
                affected_files = [
                    a["path"] for a in actions 
                    if a.get("type") in ["edit_file", "create_file"]
                ]
                
                scope = "global" if len(affected_files) > 2 else "module"
                
                return SemanticDecision(
                    "terminology",
                    scope,
                    old_term,
                    new_term,
                    f"Zmiana w {len(affected_files)} plikach"
                )
        
        # Konwencja nazewnictwa
        if "konwencja" in lower_input or "standard" in lower_input:
            # np. "używaj kebab-case dla CSS"
            return SemanticDecision(
                "convention",
                "global",
                "unspecified",
                "specified in project",
                user_input[:100]
            )
        
        return None
    
    def _extract_terminology_change(self, text: str) -> Optional[tuple]:
        """
        Wyciągnij starą i nową terminologię z tekstu.
        Np: "zamiast Punkty użyj Kulki" → ("Punkty", "Kulki")
        """
        import re
        
        # Wzorce: "zamiast X użyj Y", "X → Y", "zmień X na Y"
        patterns = [
            r"zamiast\s+(\w+).*?(?:użyj|zrób|będzie)\s+(\w+)",
            r"(\w+)\s*→\s*(\w+)",
            r"zmień\s+(\w+)\s+na\s+(\w+)",
            r"zastąp\s+(\w+)\s+przez\s+(\w+)"
        ]
        
        text_lower = text.lower()
        for pattern in patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                # Znajdź oryginalne słowa (z wielkimi literami) w tekście
                old_word = match.group(1)
                new_word = match.group(2)
                
                # Znajdź oryginalne formy w tekście
                original_old = self._find_original_case(text, old_word)
                original_new = self._find_original_case(text, new_word)
                
                return (original_old, original_new)
        
        return None
    
    def _find_original_case(self, text: str, word: str) -> str:
        """Znajdź oryginalne słowo z zachowaniem wielkości liter"""
        match = re.search(r'\b' + re.escape(word) + r'\b', text, re.IGNORECASE)
        if match:
            return match.group(0)
        return word
    
    def get_active_terminology(self) -> Dict[str, str]:
        """
        Zwróć aktywną terminologię projektu.
        Format: {"stary_termin": "nowy_termin"}
        """
        terminology = {}
        
        for decision in self.decisions:
            if decision.type == "terminology" and decision.scope == "global":
                terminology[decision.old] = decision.new
        
        return terminology
    
    def get_conventions(self) -> List[str]:
        """Zwróć listę ustalonych konwencji"""
        conventions = []
        
        for decision in self.decisions:
            if decision.type == "convention":
                conventions.append(f"{decision.new} (od {decision.timestamp[:10]})")
        
        return conventions
    
    def get_context_for_prompt(self) -> str:
        """Wygeneruj kontekst dla AI o ustalonych decyzjach"""
        if not self.decisions:
            return ""
        
        lines = ["\n===================="]
        lines.append("DECYZJE SEMANTYCZNE PROJEKTU")
        lines.append("====================\n")
        
        terminology = self.get_active_terminology()
        if terminology:
            lines.append("Terminologia (ZAWSZE używaj nowych nazw):")
            for old, new in terminology.items():
                lines.append(f"  • {old} → {new}")
            lines.append("")
        
        conventions = self.get_conventions()
        if conventions:
            lines.append("Konwencje:")
            for conv in conventions:
                lines.append(f"  • {conv}")
            lines.append("")
        
        lines.append("WAŻNE: Te decyzje dotyczą CAŁEGO projektu.")
        lines.append("Używaj nowej terminologii w:")
        lines.append("  - nowych plikach")
        lines.append("  - komentarzach")
        lines.append("  - README")
        lines.append("  - komunikatach użytkownika")
        
        return "\n".join(lines)
    
    def suggest_related_changes(self, decision: SemanticDecision) -> List[str]:
        """
        Zasugeruj powiązane zmiany na podstawie decyzji.
        Np: zmiana terminologii → trzeba zaktualizować README, testy, komentarze
        """
        suggestions = []
        
        if decision.type == "terminology" and decision.scope == "global":
            suggestions.extend([
                f"README.md - zaktualizuj opis używając '{decision.new}'",
                f"Komentarze w kodzie - sprawdź czy używają starego '{decision.old}'",
                f"Testy - nazwy testów mogą zawierać '{decision.old}'",
                f"Dokumentacja - jeśli istnieje docs/ zaktualizuj terminologię"
            ])
        
        if decision.type == "convention":
            suggestions.extend([
                "Dodaj konwencję do README.md w sekcji Development",
                "Sprawdź czy istniejące pliki są zgodne z nową konwencją",
                "Rozważ dodanie lintera/formattera dla egzekwowania konwencji"
            ])
        
        return suggestions