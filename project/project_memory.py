import json
from pathlib import Path
from datetime import datetime
from collections import Counter
from typing import Optional

class ProjectMemory:
    """Pamięć kontekstu projektu - zapamiętuje decyzje, strukturę i konwencje"""
    
    def __init__(self, project_root: Optional[Path], config=None):
        if project_root is None:
            raise ValueError("ProjectMemory requires a valid project_root")
        
        self.project_root = Path(project_root)
        self.memory_file = self.project_root / ".ai-context.json"
        self.config = config or {}
        self.data = self._load()
    
    def _load(self):
        """Wczytaj pamięć projektu"""
        if not self.memory_file.exists():
            return self._default_memory()
        
        try:
            with open(self.memory_file, 'r') as f:
                return json.load(f)
        except Exception:
            return self._default_memory()
    
    def _default_memory(self):
        """Domyślna struktura pamięci"""
        return {
            "project_type": None,
            "tech_stack": [],
            "conventions": {},
            "structure": {},
            "decisions": [],
            "file_edits": {},
            "suggested_files": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    
    def _save(self):
        """Zapisz pamięć do pliku"""
        self.data["updated_at"] = datetime.now().isoformat()
        
        # Ogranicz historię według configu
        max_history = self.config.get('project', {}).get('max_history', 20)
        if len(self.data["decisions"]) > max_history:
            self.data["decisions"] = self.data["decisions"][-max_history:]
        
        try:
            with open(self.memory_file, 'w') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[WARN] Nie udało się zapisać pamięci projektu: {e}")
    
    def update_from_actions(self, actions, user_input, intent=None):
        """
        Zaktualizuj pamięć na podstawie wykonanych akcji.
        
        Args:
            actions: lista wykonanych akcji
            user_input: polecenie użytkownika
            intent: NOWE - zrozumiany zamiar (opcjonalny)
        """
        if not actions:
            return
        
        # Wykryj typ projektu
        self._detect_project_type(actions)
        
        # Zapisz historię edycji
        for action in actions:
            if action["type"] in ["create_file", "edit_file"]:
                path = action.get("path", "")
                self.data["file_edits"][path] = self.data["file_edits"].get(path, 0) + 1
        
        # Zapisz decyzję z INTENCJĄ
        if user_input:
            decision = {
                "timestamp": datetime.now().isoformat(),
                "command": user_input,
                "actions_count": len(actions),
            }
            
            # Zapisz intent jeśli został wykryty
            if intent:
                decision["intent"] = intent
            elif self.config.get('project', {}).get('remember_intents', True):
                # Spróbuj wykryć automatycznie
                decision["intent"] = self._extract_intent(user_input, actions)
            
            self.data["decisions"].append(decision)
        
        self._save()
    
    def _extract_intent(self, user_input: str, actions: list) -> str:
        """
        Automatyczna ekstrakcja intencji z polecenia.
        HEURYSTYKA - nie AI.
        """
        lower = user_input.lower()
        
        # Utworzenie
        if any(w in lower for w in ["stwórz", "zrób", "utwórz", "dodaj"]):
            action_types = set(a["type"] for a in actions)
            if "create_file" in action_types:
                return "create_files"
        
        # Modyfikacja
        if any(w in lower for w in ["napraw", "popraw", "zmień", "edytuj"]):
            return "modify_code"
        
        # Refaktoryzacja
        if any(w in lower for w in ["zamiast", "przejdź na", "zastąp"]):
            return "refactor"
        
        # Eksploracja
        if any(w in lower for w in ["gdzie", "pokaż", "znajdź", "szukaj"]):
            return "explore"
        
        # Wykonanie
        if any(w in lower for w in ["uruchom", "otwórz", "wykonaj"]):
            return "execute"
        
        return "other"
    
    def _detect_project_type(self, actions):
        """Wykryj typ projektu na podstawie tworzonych plików"""
        files_created = [
            action["path"] for action in actions 
            if action["type"] == "create_file"
        ]
        
        # HTML/CSS/JS = projekt web
        if any(f.endswith('.html') for f in files_created):
            self.data["project_type"] = "web"
            if any(f.endswith('.css') for f in files_created):
                if "css" not in self.data["tech_stack"]:
                    self.data["tech_stack"].append("css")
            if any(f.endswith('.js') for f in files_created):
                if "javascript" not in self.data["tech_stack"]:
                    self.data["tech_stack"].append("javascript")
        
        # package.json = Node
        if "package.json" in files_created:
            self.data["project_type"] = "node"
            if "node" not in self.data["tech_stack"]:
                self.data["tech_stack"].append("node")
        
        # requirements.txt = Python
        if "requirements.txt" in files_created:
            self.data["project_type"] = "python"
            if "python" not in self.data["tech_stack"]:
                self.data["tech_stack"].append("python")
    
    def get_context_prompt(self):
        """Wygeneruj prompt kontekstowy dla AI"""
        if not self.data["project_type"]:
            return ""
        
        prompt = f"""
====================
PAMIĘĆ PROJEKTU
====================

Typ projektu: {self.data["project_type"]}
Technologie: {', '.join(self.data["tech_stack"]) or 'brak'}
"""
        
        if self.data["conventions"]:
            prompt += f"\nKonwencje:\n"
            for key, val in self.data["conventions"].items():
                prompt += f"  - {key}: {val}\n"
        
        if self.data["structure"]:
            prompt += f"\nStruktura:\n"
            for key, val in self.data["structure"].items():
                prompt += f"  - {key}: {val}\n"
        
        # Często edytowane pliki
        frequently_edited = self.get_frequently_edited(limit=5)
        if frequently_edited:
            prompt += f"\nCzęsto edytowane pliki:\n"
            for f in frequently_edited:
                prompt += f"  - {f}\n"
        
        # Pokaż ostatnie intencje
        recent_intents = [
            d.get("intent") for d in self.data["decisions"][-3:]
            if d.get("intent")
        ]
        if recent_intents:
            prompt += f"\nOstatnie intencje:\n"
            for intent in recent_intents:
                prompt += f"  - {intent}\n"
        
        # Sugerowane pliki
        if self.data["suggested_files"]:
            prompt += f"\nSugerowane pliki (mogą być przydatne):\n"
            for f in self.data["suggested_files"]:
                prompt += f"  - {f}\n"
        
        return prompt
    
    def get_frequently_edited(self, limit=10):
        """Zwróć listę najczęściej edytowanych plików"""
        edits = self.data["file_edits"]
        sorted_files = sorted(edits.items(), key=lambda x: x[1], reverse=True)
        return [f for f, _ in sorted_files[:limit]]
    
    def suggest_files(self, files):
        """Dodaj sugestie plików do utworzenia"""
        for f in files:
            if f not in self.data["suggested_files"]:
                self.data["suggested_files"].append(f)
        self._save()
    
    def set_convention(self, key, value):
        """Ustaw konwencję projektu"""
        self.data["conventions"][key] = value
        self._save()
    
    def set_structure(self, key, value):
        """Ustaw strukturę projektu"""
        self.data["structure"][key] = value
        self._save()
    
    def get_stats(self):
        """Statystyki projektu"""
        return {
            "project_type": self.data["project_type"],
            "tech_stack": self.data["tech_stack"],
            "total_edits": sum(self.data["file_edits"].values()),
            "files_touched": len(self.data["file_edits"]),
            "decisions_count": len(self.data["decisions"]),
            "age_days": (
                datetime.now() - datetime.fromisoformat(self.data["created_at"])
            ).days
        }