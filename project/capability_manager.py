"""
Capability Manager - kontrola dozwolonych akcji w projekcie.

FILOZOFIA:
- Nie każdy projekt pozwala na wszystko
- Użytkownik ustala reguły w .ai-context.json
- Agent MUSI je respektować
- To warstwa ponad ActionValidator

NOWE w tej wersji:
- Lepsze walidacje z komunikatami błędów
- Kontekst dla promptu z przykładami
- Inteligentne sugestie enable
- Wsparcie dla custom capabilities
"""

from typing import Dict, List, Optional
from pathlib import Path
import json

class CapabilityViolation(Exception):
    """Wyjątek rzucany gdy akcja narusza capabilities projektu"""
    pass

class CapabilityManager:
    """
    Zarządza dozwolonymi akcjami w projekcie.
    Prosta, jasna reguła: jeśli capability = false, akcja NIEDOZWOLONA.
    """
    
    # Mapowanie akcji na capabilities
    ACTION_TO_CAPABILITY = {
        "run_command": "allow_execute",
        "open_path": "allow_execute",
        "delete_file": "allow_delete",
        "move_file": "allow_delete",
        "web_search": "allow_network",      # Web Search wymaga allow_network
        "web_scrape": "allow_network",       # Web Scraping też
        # list_files nie wymaga capability (SAFE)
    }
    
    # Domyślne capabilities - bezpieczne wartości
    DEFAULT_CAPABILITIES = {
        "allow_execute": True,      # run_command, open_path
        "allow_delete": True,        # delete_file, move_file
        "allow_git": False,          # git_commit, git_add (future)
        "allow_network": False,      # fetch_url, api_call (future)
    }
    
    # Opisy capabilities dla UI
    CAPABILITY_DESCRIPTIONS = {
        "allow_execute": "Wykonywanie komend systemowych i otwieranie plików",
        "allow_delete": "Usuwanie i przenoszenie plików",
        "allow_git": "Operacje Git (commit, add, push)",
        "allow_network": "Dostęp do sieci – web search i scraping (ai web-search)",
    }
    
    def __init__(self, project_root: Optional[Path], memory_data: Dict, config: Optional[Dict] = None):
        """
        Args:
            project_root: ścieżka do projektu
            memory_data: dane z ProjectMemory (zawiera capabilities)
            config: globalny config (używany do odczytu web_search.enabled)
        """
        if project_root is None:
            raise ValueError("CapabilityManager requires a valid project_root")
        
        self.project_root = Path(project_root)
        self.memory_data = memory_data
        self.config = config or {}
        self.capabilities = self._load_capabilities()
    
    def _load_capabilities(self) -> Dict[str, bool]:
        """Wczytaj capabilities z pamięci projektu.
        
        allow_network jest automatycznie True gdy web_search.enabled=True w config,
        chyba że użytkownik jawnie wyłączył je w .ai-context.json.
        """
        caps = self.memory_data.get("capabilities", {})
        
        # Merge z defaultami
        result = self.DEFAULT_CAPABILITIES.copy()
        
        # Auto: jeśli web_search włączony w config, allow_network domyślnie True
        # (można nadpisać w .ai-context.json ustawiając "allow_network": false)
        if self.config.get("web_search", {}).get("enabled", False):
            result["allow_network"] = True
        
        # Dane z .ai-context.json mają PRIORYTET nad defaultami i auto
        result.update(caps)
        
        return result
    
    def check_action(self, action: Dict) -> Optional[str]:
        """
        Sprawdź czy akcja jest dozwolona.
        
        Returns:
            None jeśli OK
            str (powód) jeśli NIEDOZWOLONA
        """
        action_type = action.get("type")
        
        if not action_type:
            return "Akcja bez typu"
        
        # Sprawdź czy akcja wymaga capability
        required_cap = self.ACTION_TO_CAPABILITY.get(action_type)
        
        if not required_cap:
            # Akcja nie wymaga specjalnego capability
            return None
        
        # Sprawdź czy capability jest włączone
        if not self.capabilities.get(required_cap, True):
            cap_desc = self.CAPABILITY_DESCRIPTIONS.get(required_cap, required_cap)
            return f"Capability '{required_cap}' wyłączone ({cap_desc})"
        
        return None
    
    def validate_actions(self, actions: List[Dict]) -> tuple[bool, List[str]]:
        """
        Waliduj listę akcji pod kątem capabilities.
        
        Returns:
            (czy_ok, lista_błędów)
        """
        errors = []
        
        for i, action in enumerate(actions):
            reason = self.check_action(action)
            if reason:
                action_type = action.get("type", "unknown")
                errors.append(f"Akcja #{i+1} ({action_type}): {reason}")
        
        return (len(errors) == 0, errors)
    
    def get_disabled_actions(self) -> List[str]:
        """Zwróć listę wyłączonych typów akcji"""
        disabled = []
        
        for action_type, cap_name in self.ACTION_TO_CAPABILITY.items():
            if not self.capabilities.get(cap_name, True):
                disabled.append(action_type)
        
        return disabled
    
    def set_capability(self, name: str, value: bool):
        """
        Ustaw capability i zapisz do pamięci.
        
        UWAGA: To modyfikuje memory_data (referencja)
        """
        if name not in self.DEFAULT_CAPABILITIES:
            raise ValueError(f"Nieznane capability: {name}")
        
        if "capabilities" not in self.memory_data:
            self.memory_data["capabilities"] = {}
        
        self.memory_data["capabilities"][name] = value
        self.capabilities[name] = value
    
    def get_context_for_prompt(self) -> str:
        """
        Wygeneruj kontekst dla promptu AI.
        AI MUSI wiedzieć jakie akcje są wyłączone.
        """
        disabled = self.get_disabled_actions()
        
        if not disabled:
            return ""
        
        lines = ["\n===================="]
        lines.append("OGRANICZENIA PROJEKTU")
        lines.append("====================\n")
        lines.append("NASTĘPUJĄCE AKCJE SĄ WYŁĄCZONE:")
        
        for action in disabled:
            cap = self.ACTION_TO_CAPABILITY[action]
            desc = self.CAPABILITY_DESCRIPTIONS.get(cap, cap)
            lines.append(f"  ✗ {action} (capability: {cap} - {desc})")
        
        lines.append("\nNIE WOLNO używać tych akcji w odpowiedzi.")
        lines.append("Jeśli użytkownik poprosi o coś co wymaga wyłączonej akcji:")
        lines.append("  - wyjaśnij że ta akcja jest wyłączona")
        lines.append("  - podaj powód (bezpieczeństwo, ograniczenia projektu)")
        lines.append("  - zaproponuj alternatywę (jeśli istnieje)")
        lines.append("  - wspomnij jak włączyć capability (ai capability enable <nazwa>)")
        
        return "\n".join(lines)
    
    def suggest_enable(self, action_type: str) -> Optional[str]:
        """
        Zasugeruj jak włączyć capability dla danej akcji.
        
        Returns:
            None jeśli akcja już dozwolona
            str z instrukcją jeśli wyłączona
        """
        required_cap = self.ACTION_TO_CAPABILITY.get(action_type)
        
        if not required_cap:
            return None
        
        if self.capabilities.get(required_cap, True):
            return None
        
        cap_desc = self.CAPABILITY_DESCRIPTIONS.get(required_cap, required_cap)
        
        return f"""
Akcja '{action_type}' jest wyłączona.

Capability: {required_cap}
Opis: {cap_desc}

Aby włączyć, dodaj do .ai-context.json:

{{
  "capabilities": {{
    "{required_cap}": true
  }}
}}

Lub użyj komendy:
  ai capability enable {required_cap}

Dlaczego wyłączone:
- Bezpieczeństwo: {action_type} może mieć nieodwracalne skutki
- Kontrola: Świadome włączenie tylko gdy potrzebne
- Best practice: Minimalizuj uprawnienia AI
"""
    
    def get_summary(self) -> str:
        """Zwróć czytelne podsumowanie capabilities"""
        lines = ["Capabilities projektu:"]
        
        for cap, enabled in self.capabilities.items():
            status = "✓ włączone" if enabled else "✗ wyłączone"
            desc = self.CAPABILITY_DESCRIPTIONS.get(cap, "")
            lines.append(f"  {cap}: {status}")
            if desc:
                lines.append(f"    ({desc})")
        
        disabled = self.get_disabled_actions()
        if disabled:
            lines.append("\nWyłączone akcje:")
            for action in disabled:
                lines.append(f"  - {action}")
        else:
            lines.append("\nWszystkie akcje dozwolone.")
        
        return "\n".join(lines)
    
    def export_config(self) -> Dict:
        """
        Eksportuj capabilities do zapisania w .ai-context.json
        
        Returns:
            Dict gotowy do JSONa
        """
        return {
            "capabilities": self.capabilities.copy()
        }
    
    def import_config(self, config: Dict):
        """
        Importuj capabilities z .ai-context.json
        
        Args:
            config: Dict z kluczem "capabilities"
        """
        if "capabilities" in config:
            for cap_name, value in config["capabilities"].items():
                if cap_name in self.DEFAULT_CAPABILITIES:
                    self.set_capability(cap_name, value)
    
    def get_risky_actions_enabled(self) -> List[str]:
        """
        Zwróć listę ryzykownych akcji które są WŁĄCZONE.
        
        Przydatne do ostrzeżeń przy setup projektu.
        """
        risky = []
        
        risky_caps = {
            "allow_execute": "Wykonywanie komend (może uruchomić rm -rf /)",
            "allow_delete": "Usuwanie plików (nieodwracalne)",
        }
        
        for cap, desc in risky_caps.items():
            if self.capabilities.get(cap, False):
                actions = [a for a, c in self.ACTION_TO_CAPABILITY.items() if c == cap]
                risky.append(f"{cap}: {desc} (akcje: {', '.join(actions)})")
        
        return risky