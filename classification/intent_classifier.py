"""
Intent Classifier - rozpoznawanie ZAMIARU użytkownika.

PROBLEM:
- model skacze od razu do akcji
- brak spójnej wizji
- chaotyczne wykonanie

ROZWIĄZANIE:
- najpierw ZROZUM zamiar
- potem ZAPLANUJ
- dopiero WYKONAJ

INTENTY:
- explore: "co robi", "gdzie jest", "pokaż"
- create: "stwórz", "zrób", "dodaj"
- modify: "napraw", "zmień", "popraw"
- refactor: "zamiast X użyj Y", "reorganizuj"
- execute: "uruchom", "otwórz", "zainstaluj"
- delete: "usuń", "wyczyść"
- question: pytania bez akcji
"""

from typing import Dict, List, Optional, Tuple
from enum import Enum
import re

class Intent(Enum):
    """Typy intencji użytkownika"""
    EXPLORE = "explore"           # Eksploracja projektu
    CREATE = "create"             # Tworzenie nowych plików
    MODIFY = "modify"             # Modyfikacja istniejących
    REFACTOR = "refactor"         # Refaktoryzacja/reorganizacja
    EXECUTE = "execute"           # Uruchomienie/otwarcie
    DELETE = "delete"             # Usuwanie
    QUESTION = "question"         # Pytanie bez akcji
    REVIEW = "review"             # Przegląd/analiza
    DEBUG = "debug"               # Debugging/naprawa błędów

class IntentConfidence(Enum):
    """Pewność rozpoznania intencji"""
    HIGH = "high"       # > 0.8
    MEDIUM = "medium"   # 0.5 - 0.8
    LOW = "low"         # < 0.5

class IntentResult:
    """Wynik klasyfikacji intencji"""
    
    def __init__(self, 
                 intent: Intent,
                 confidence: IntentConfidence,
                 reasoning: str,
                 keywords: List[str],
                 scope: str = "unknown"):  # "file", "module", "project"
        self.intent = intent
        self.confidence = confidence
        self.reasoning = reasoning
        self.keywords = keywords
        self.scope = scope
    
    def to_dict(self) -> Dict:
        return {
            "intent": self.intent.value,
            "confidence": self.confidence.value,
            "reasoning": self.reasoning,
            "keywords": self.keywords,
            "scope": self.scope
        }

class IntentClassifier:
    """
    Klasyfikator intencji użytkownika.
    
    HEURYSTYKA (nie ML) - szybka i deterministyczna.
    """
    
    # Wzorce dla każdego intentu
    PATTERNS = {
        Intent.EXPLORE: {
            "keywords": [
                "co robi", "gdzie jest", "pokaż", "znajdź", "szukaj",
                "jakie", "który", "które", "lista", "wyświetl",
                "sprawdź", "zobacz", "przejrzyj"
            ],
            "verbs": ["pokaż", "znajdź", "szukaj", "wyświetl", "lista"]
        },
        
        Intent.CREATE: {
            "keywords": [
                "stwórz", "utwórz", "zrób", "dodaj", "wygeneruj",
                "napisz", "przygotuj", "sklonuj", "zbuduj"
            ],
            "verbs": ["stwórz", "utwórz", "zrób", "dodaj"]
        },
        
        Intent.MODIFY: {
            "keywords": [
                "napraw", "popraw", "zmień", "edytuj", "zaktualizuj",
                "uaktualnij", "dostosuj", "zmodyfikuj", "ulepsz"
            ],
            "verbs": ["napraw", "popraw", "zmień", "edytuj"]
        },
        
        Intent.REFACTOR: {
            "keywords": [
                "zamiast", "przejdź na", "zastąp", "reorganizuj",
                "przenieś", "przemianuj", "refaktor", "czyściej",
                "od teraz"
            ],
            "verbs": ["zastąp", "reorganizuj", "przenieś"]
        },
        
        Intent.EXECUTE: {
            "keywords": [
                "uruchom", "wykonaj", "otwórz", "zainstaluj",
                "wystartuj", "odpal", "wdróż", "deploy"
            ],
            "verbs": ["uruchom", "wykonaj", "otwórz", "zainstaluj"]
        },
        
        Intent.DELETE: {
            "keywords": [
                "usuń", "skasuj", "wyczyść", "wywal", "pozbyj się",
                "delete", "remove"
            ],
            "verbs": ["usuń", "skasuj", "wyczyść"]
        },
        
        Intent.QUESTION: {
            "keywords": [
                "jak", "dlaczego", "kiedy", "czy", "co to",
                "wyjaśnij", "opisz", "jaka", "który", "co oznacza"
            ],
            "question_marks": True
        },
        
        Intent.REVIEW: {
            "keywords": [
                "przeanalizuj", "oceń", "review", "audit",
                "sprawdź jakość", "co można poprawić", "code review"
            ],
            "verbs": ["przeanalizuj", "oceń"]
        },
        
        Intent.DEBUG: {
            "keywords": [
                "błąd", "error", "nie działa", "crashuje",
                "debug", "napraw bug", "problem z", "exception"
            ],
            "verbs": ["debuguj", "napraw"]
        }
    }
    
    @classmethod
    def classify(cls, user_input: str, context: Optional[Dict] = None) -> IntentResult:
        """
        Klasyfikuj intencję użytkownika.
        
        Args:
            user_input: polecenie użytkownika
            context: dodatkowy kontekst (pamięć projektu, ostatnie akcje)
        
        Returns:
            IntentResult z rozpoznanym zamiarem
        """
        lower = user_input.lower().strip()
        
        # Scoring dla każdego intentu
        scores: Dict[Intent, float] = {intent: 0.0 for intent in Intent}
        matched_keywords: Dict[Intent, List[str]] = {intent: [] for intent in Intent}
        
        # Sprawdź każdy intent
        for intent, patterns in cls.PATTERNS.items():
            keywords = patterns.get("keywords", [])
            verbs = patterns.get("verbs", [])
            
            # Sprawdź keywords
            for keyword in keywords:
                if keyword in lower:
                    scores[intent] += 1.0
                    matched_keywords[intent].append(keyword)
            
            # Bonus za czasowniki na początku
            for verb in verbs:
                if lower.startswith(verb):
                    scores[intent] += 2.0
                    matched_keywords[intent].append(f"START:{verb}")
            
            # Question marks dla QUESTION
            if patterns.get("question_marks") and "?" in user_input:
                scores[intent] += 1.5
        
        # Normalizuj scores (0-1)
        max_score = max(scores.values()) if scores.values() else 0
        if max_score > 0:
            scores = {k: v / max_score for k, v in scores.items()}
        
        # Wybierz najlepszy intent - NAPRAWKA
        best_intent = max(scores.keys(), key=lambda k: scores[k])
        best_score = scores[best_intent]
        
        # Określ confidence
        if best_score >= 0.8:
            confidence = IntentConfidence.HIGH
        elif best_score >= 0.5:
            confidence = IntentConfidence.MEDIUM
        else:
            confidence = IntentConfidence.LOW
        
        # Określ scope
        scope = cls._detect_scope(lower)
        
        # Reasoning
        reasoning = cls._generate_reasoning(
            best_intent, 
            matched_keywords[best_intent],
            best_score
        )
        
        return IntentResult(
            intent=best_intent,
            confidence=confidence,
            reasoning=reasoning,
            keywords=matched_keywords[best_intent],
            scope=scope
        )
    
    @classmethod
    def _detect_scope(cls, text: str) -> str:
        """
        Wykryj zakres operacji.
        
        Returns:
            "file", "module", "project", "unknown"
        """
        # Plik
        if any(word in text for word in ["plik", "file", "w pliku"]):
            return "file"
        
        # Moduł/komponent
        if any(word in text for word in ["moduł", "komponent", "klasę", "funkcję"]):
            return "module"
        
        # Cały projekt
        if any(word in text for word in ["projekt", "wszędzie", "wszystkie", "całość", "globalnie"]):
            return "project"
        
        return "unknown"
    
    @classmethod
    def _generate_reasoning(cls, intent: Intent, keywords: List[str], score: float) -> str:
        """Wygeneruj uzasadnienie dla klasyfikacji"""
        if not keywords:
            return f"Niska pewność ({score:.2f}) - brak wyraźnych sygnałów"
        
        kw_str = ", ".join(keywords[:3])
        return f"Wykryto intent {intent.value} (score: {score:.2f}) na podstawie: {kw_str}"
    
    @classmethod
    def is_safe_intent(cls, intent: Intent) -> bool:
        """Czy intent jest bezpieczny (nie modyfikuje plików)?"""
        safe_intents = {Intent.EXPLORE, Intent.QUESTION, Intent.REVIEW}
        return intent in safe_intents
    
    @classmethod
    def requires_confirmation(cls, intent: Intent) -> bool:
        """Czy intent wymaga potwierdzenia użytkownika?"""
        risky_intents = {Intent.DELETE, Intent.EXECUTE, Intent.REFACTOR}
        return intent in risky_intents
    
    @classmethod
    def get_suggested_actions(cls, intent: Intent, scope: str) -> List[str]:
        """
        Zasugeruj typowe akcje dla danego intentu.
        
        To pomaga w planowaniu.
        """
        suggestions = {
            Intent.EXPLORE: {
                "file": ["read_file", "semantic_search"],
                "module": ["list_files", "read_file"],
                "project": ["analyze_structure", "list_files"]
            },
            
            Intent.CREATE: {
                "file": ["create_file"],
                "module": ["create_file", "mkdir"],
                "project": ["create_file", "mkdir", "create_file"]
            },
            
            Intent.MODIFY: {
                "file": ["read_file", "edit_file"],
                "module": ["semantic_search", "edit_file"],
                "project": ["semantic_search", "edit_file"]
            },
            
            Intent.REFACTOR: {
                "file": ["read_file", "edit_file"],
                "module": ["semantic_search", "edit_file", "move_file"],
                "project": ["semantic_search", "edit_file", "move_file"]
            },
            
            Intent.EXECUTE: {
                "file": ["open_path"],
                "module": ["run_command"],
                "project": ["run_command"]
            },
            
            Intent.DELETE: {
                "file": ["delete_file"],
                "module": ["delete_file"],
                "project": ["semantic_search", "delete_file"]
            },
            
            Intent.QUESTION: {
                "file": ["read_file"],
                "module": ["semantic_search"],
                "project": ["analyze_structure"]
            }
        }
        
        return suggestions.get(intent, {}).get(scope, [])