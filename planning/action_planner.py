"""
Action Planner - planowanie akcji na podstawie intentu.

PROBLEM:
- model generuje akcje bez przemyślenia
- brak walidacji spójności
- konfliktujące operacje

ROZWIĄZANIE:
- intent → plan → walidacja → akcje
- wykrywanie konfliktów
- optymalizacja kolejności
"""

from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from classification.intent_classifier import Intent, IntentResult

class PlanIssue(Enum):
    """Typy problemów w planie"""
    FILE_CONFLICT = "file_conflict"           # Konflikt plików (edit + delete)
    MISSING_DEPENDENCY = "missing_dependency" # Brak wymaganego pliku
    ORDER_VIOLATION = "order_violation"       # Zła kolejność (edit przed read)
    EXCESSIVE_SCOPE = "excessive_scope"       # Zbyt dużo akcji
    DANGEROUS_COMBO = "dangerous_combo"       # Niebezpieczna kombinacja

class ActionPlan:
    """
    Plan akcji do wykonania.
    
    Zawiera:
    - intent
    - lista akcji
    - walidacja
    - metadata
    """
    
    def __init__(self, intent: IntentResult, actions: List[Dict]):
        self.intent = intent
        self.actions = actions
        self.issues: List[Tuple[PlanIssue, str]] = []
        self.metadata = {
            "created_at": None,
            "validated": False,
            "risk_level": "unknown"
        }
    
    def add_issue(self, issue_type: PlanIssue, description: str):
        """Dodaj problem do planu"""
        self.issues.append((issue_type, description))
    
    def is_valid(self) -> bool:
        """Czy plan jest poprawny?"""
        # Plan jest valid jeśli nie ma critical issues
        critical_issues = {
            PlanIssue.FILE_CONFLICT,
            PlanIssue.MISSING_DEPENDENCY,
            PlanIssue.DANGEROUS_COMBO
        }
        
        return not any(
            issue_type in critical_issues 
            for issue_type, _ in self.issues
        )
    
    def get_affected_files(self) -> Set[str]:
        """Zwróć pliki które będą zmienione"""
        files = set()
        
        for action in self.actions:
            if action.get("type") in ["create_file", "edit_file", "delete_file"]:
                files.add(action.get("path", ""))
            elif action.get("type") == "move_file":
                files.add(action.get("from", ""))
                files.add(action.get("to", ""))
        
        return files
    
    def to_dict(self) -> Dict:
        """Eksportuj plan do dict"""
        return {
            "intent": self.intent.to_dict(),
            "actions": self.actions,
            "issues": [
                {"type": issue.value, "description": desc}
                for issue, desc in self.issues
            ],
            "metadata": self.metadata,
            "is_valid": self.is_valid()
        }

class ActionPlanner:
    """
    Planuje akcje na podstawie intentu.
    Waliduje spójność planu.
    Optymalizuje kolejność.
    """
    
    @classmethod
    def create_plan(cls, intent: IntentResult, actions: List[Dict]) -> ActionPlan:
        """
        Utwórz plan akcji na podstawie intentu.
        
        Args:
            intent: rozpoznany zamiar
            actions: surowe akcje z modelu
        
        Returns:
            ActionPlan z walidacją
        """
        plan = ActionPlan(intent, actions)
        
        # Walidacja
        cls._validate_file_conflicts(plan)
        cls._validate_dependencies(plan)
        cls._validate_order(plan)
        cls._validate_scope(plan)
        cls._validate_dangerous_combos(plan)
        
        # Metadata
        plan.metadata["validated"] = True
        plan.metadata["risk_level"] = cls._calculate_risk_level(plan)
        
        return plan
    
    @classmethod
    def _validate_file_conflicts(cls, plan: ActionPlan):
        """
        Sprawdź konflikty plików.
        
        Konflikty:
        - edit + delete tego samego pliku
        - create + create tego samego pliku
        - move + edit tego samego pliku
        """
        file_operations: Dict[str, List[str]] = {}
        
        for action in plan.actions:
            action_type = action.get("type")
            
            if action_type in ["create_file", "edit_file", "delete_file"]:
                path = action.get("path", "")
                if path not in file_operations:
                    file_operations[path] = []
                file_operations[path].append(action_type)
            
            elif action_type == "move_file":
                src = action.get("from", "")
                dst = action.get("to", "")
                
                if src not in file_operations:
                    file_operations[src] = []
                file_operations[src].append("move_from")
                
                if dst not in file_operations:
                    file_operations[dst] = []
                file_operations[dst].append("move_to")
        
        # Wykryj konflikty
        for path, ops in file_operations.items():
            # edit + delete
            if "edit_file" in ops and "delete_file" in ops:
                plan.add_issue(
                    PlanIssue.FILE_CONFLICT,
                    f"Konflikt: edit i delete dla {path}"
                )
            
            # create + create
            if ops.count("create_file") > 1:
                plan.add_issue(
                    PlanIssue.FILE_CONFLICT,
                    f"Konflikt: wielokrotne create dla {path}"
                )
            
            # move + edit
            if "move_from" in ops and "edit_file" in ops:
                plan.add_issue(
                    PlanIssue.FILE_CONFLICT,
                    f"Konflikt: move i edit dla {path}"
                )
    
    @classmethod
    def _validate_dependencies(cls, plan: ActionPlan):
        """
        Sprawdź czy wszystkie wymagane pliki istnieją.
        
        Np: edit_file wymaga że plik istnieje
        """
        created_files = set()
        
        for action in plan.actions:
            action_type = action.get("type")
            
            if action_type == "create_file":
                created_files.add(action.get("path", ""))
            
            elif action_type == "edit_file":
                path = action.get("path", "")
                
                # Jeśli nie był utworzony wcześniej w tym planie
                # to musi istnieć w projekcie (ale tego nie sprawdzamy tutaj)
                # To jest zadanie fs_tools przy wykonaniu
                pass
    
    @classmethod
    def _validate_order(cls, plan: ActionPlan):
        """
        Sprawdź czy kolejność akcji ma sens.
        
        Zasady:
        - read przed edit (jeśli ten sam plik)
        - create przed edit (jeśli ten sam plik)
        - mkdir przed create (jeśli w tym folderze)
        """
        seen_reads: Set[str] = set()
        seen_creates: Set[str] = set()
        
        for i, action in enumerate(plan.actions):
            action_type = action.get("type")
            
            if action_type == "read_file":
                seen_reads.add(action.get("path", ""))
            
            elif action_type == "create_file":
                seen_creates.add(action.get("path", ""))
            
            elif action_type == "edit_file":
                path = action.get("path", "")
                
                # Sprawdź czy był read wcześniej (DOBRA praktyka, nie błąd)
                if path not in seen_reads and path not in seen_creates:
                    # To nie jest błąd, ale warto zarekomendować read
                    pass
    
    @classmethod
    def _validate_scope(cls, plan: ActionPlan):
        """
        Sprawdź czy zakres akcji nie jest zbyt duży.
        
        Limity:
        - max 20 akcji w jednym planie
        - max 10 plików modyfikowanych
        - max 5 usunięć w jednym planie
        """
        action_count = len(plan.actions)
        affected_files = plan.get_affected_files()
        
        deletes = [a for a in plan.actions if a.get("type") == "delete_file"]
        
        if action_count > 20:
            plan.add_issue(
                PlanIssue.EXCESSIVE_SCOPE,
                f"Zbyt dużo akcji ({action_count}) - rozważ podział na mniejsze kroki"
            )
        
        if len(affected_files) > 10:
            plan.add_issue(
                PlanIssue.EXCESSIVE_SCOPE,
                f"Zbyt dużo plików ({len(affected_files)}) - ryzyko błędów"
            )
        
        if len(deletes) > 5:
            plan.add_issue(
                PlanIssue.EXCESSIVE_SCOPE,
                f"Zbyt dużo usunięć ({len(deletes)}) - bardzo ryzykowne"
            )
    
    @classmethod
    def _validate_dangerous_combos(cls, plan: ActionPlan):
        """
        Sprawdź niebezpieczne kombinacje akcji.
        
        Niebezpieczne:
        - delete + run_command (może usunąć coś potrzebnego)
        - move + run_command (może zepsuć ścieżki)
        - edit config + run_command (może crashnąć)
        """
        has_delete = any(a.get("type") == "delete_file" for a in plan.actions)
        has_move = any(a.get("type") == "move_file" for a in plan.actions)
        has_run = any(a.get("type") == "run_command" for a in plan.actions)
        
        if has_delete and has_run:
            plan.add_issue(
                PlanIssue.DANGEROUS_COMBO,
                "Usuwanie plików + uruchomienie komendy - może spowodować błędy runtime"
            )
        
        if has_move and has_run:
            plan.add_issue(
                PlanIssue.DANGEROUS_COMBO,
                "Przenoszenie plików + uruchomienie komendy - może zepsuć ścieżki"
            )
    
    @classmethod
    def _calculate_risk_level(cls, plan: ActionPlan) -> str:
        """
        Oblicz poziom ryzyka planu.
        
        Returns:
            "low", "medium", "high", "critical"
        """
        # Zlicz akcje według ryzyka
        safe = ["read_file", "semantic_search", "list_files"]
        modify = ["create_file", "edit_file", "mkdir", "chmod"]
        destructive = ["delete_file", "move_file"]
        execute = ["run_command", "open_path"]
        
        safe_count = sum(1 for a in plan.actions if a.get("type") in safe)
        modify_count = sum(1 for a in plan.actions if a.get("type") in modify)
        destructive_count = sum(1 for a in plan.actions if a.get("type") in destructive)
        execute_count = sum(1 for a in plan.actions if a.get("type") in execute)
        
        # Critical issues = critical
        if any(
            issue in {PlanIssue.FILE_CONFLICT, PlanIssue.DANGEROUS_COMBO}
            for issue, _ in plan.issues
        ):
            return "critical"
        
        # Destructive lub execute = high
        if destructive_count > 0 or execute_count > 0:
            return "high"
        
        # Dużo modyfikacji = medium
        if modify_count > 5:
            return "medium"
        
        # Tylko safe = low
        if safe_count > 0 and modify_count == 0:
            return "low"
        
        return "medium"
    
    @classmethod
    def optimize_order(cls, actions: List[Dict]) -> List[Dict]:
        """
        Optymalizuj kolejność akcji.
        
        Zasady:
        1. mkdir przed create_file (w tym folderze)
        2. read_file przed edit_file (tego samego pliku)
        3. create_file przed edit_file (tego samego pliku)
        4. wszystkie read przed wszystkimi modify
        """
        # Kategorie
        mkdirs = []
        reads = []
        creates = []
        edits = []
        others = []
        
        for action in actions:
            action_type = action.get("type")
            
            if action_type == "mkdir":
                mkdirs.append(action)
            elif action_type == "read_file":
                reads.append(action)
            elif action_type == "create_file":
                creates.append(action)
            elif action_type == "edit_file":
                edits.append(action)
            else:
                others.append(action)
        
        # Optymalna kolejność
        optimized = []
        
        # 1. mkdir najpierw
        optimized.extend(mkdirs)
        
        # 2. read
        optimized.extend(reads)
        
        # 3. create
        optimized.extend(creates)
        
        # 4. edit
        optimized.extend(edits)
        
        # 5. reszta (delete, move, run)
        optimized.extend(others)
        
        return optimized
    
    @classmethod
    def format_plan_summary(cls, plan: ActionPlan) -> str:
        """Sformatuj podsumowanie planu dla użytkownika"""
        lines = []
        
        # Intent
        lines.append(f"Intent: {plan.intent.intent.value} ({plan.intent.confidence.value})")
        lines.append(f"Zakres: {plan.intent.scope}")
        lines.append("")
        
        # Akcje
        lines.append(f"Akcji: {len(plan.actions)}")
        lines.append(f"Plików dotkniętych: {len(plan.get_affected_files())}")
        lines.append(f"Poziom ryzyka: {plan.metadata['risk_level']}")
        lines.append("")
        
        # Issues
        if plan.issues:
            lines.append("PROBLEMY:")
            for issue_type, desc in plan.issues:
                lines.append(f"  • {issue_type.value}: {desc}")
            lines.append("")
        
        # Status
        if plan.is_valid():
            lines.append("✓ Plan poprawny - można wykonać")
        else:
            lines.append("✗ Plan ma błędy krytyczne - ZATRZYMANO")
        
        return "\n".join(lines)