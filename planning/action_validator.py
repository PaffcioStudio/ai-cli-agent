"""
Moduł walidacji i kategoryzacji akcji.
Odpowiada za bezpieczeństwo i kontrolę nad operacjami.
"""

from typing import Dict, List, Tuple, Optional
from enum import Enum

class ActionRisk(Enum):
    """Poziom ryzyka akcji"""
    SAFE = "safe"           # read_file, semantic_search, list_files
    MODIFY = "modify"       # create_file, edit_file
    DESTRUCTIVE = "destructive"  # delete_file, move_file
    EXECUTE = "execute"     # run_command, open_path, download_media, convert_media

class ActionValidator:
    """
    Waliduje akcje przed wykonaniem.
    Kategoryzuje akcje według ryzyka.
    Wymusza confirm dla operacji niebezpiecznych.
    """
    
    # Mapowanie akcji na poziomy ryzyka
    RISK_MAP = {
        "read_file": ActionRisk.SAFE,
        "semantic_search": ActionRisk.SAFE,
        "list_files": ActionRisk.SAFE,
        "clipboard_read": ActionRisk.SAFE,
        "image_info": ActionRisk.SAFE,
        "create_file": ActionRisk.MODIFY,
        "patch_file": ActionRisk.MODIFY,
        "edit_file": ActionRisk.MODIFY,
        "mkdir": ActionRisk.MODIFY,
        "chmod": ActionRisk.MODIFY,
        "delete_file": ActionRisk.DESTRUCTIVE,
        "move_file": ActionRisk.DESTRUCTIVE,
        "run_command": ActionRisk.EXECUTE,
        "open_path": ActionRisk.EXECUTE,
        "download_media": ActionRisk.EXECUTE,
        "convert_media": ActionRisk.EXECUTE,
        "clipboard_write": ActionRisk.MODIFY,
        "process_image": ActionRisk.EXECUTE,
        "batch_images": ActionRisk.EXECUTE,
        "web_search": ActionRisk.EXECUTE,
        "web_scrape": ActionRisk.EXECUTE,
        "use_template": ActionRisk.MODIFY,
        "save_memory": ActionRisk.SAFE,
    }

    # Mapowanie zestawów pól → typ akcji (używane do odgadywania brakującego type)
    _FIELD_TYPE_HINTS: List[Tuple[frozenset, str]] = [
        (frozenset({"path", "content"}),           "create_file"),
        (frozenset({"path", "patches"}),            "patch_file"),
        (frozenset({"path", "match", "replace"}),   "edit_file"),
        (frozenset({"path", "diff"}),               "patch_file"),
        (frozenset({"from", "to"}),                 "move_file"),
        (frozenset({"command"}),                    "run_command"),
        (frozenset({"cmd"}),                        "run_command"),
        (frozenset({"bash"}),                       "run_command"),
        (frozenset({"shell"}),                      "run_command"),
        (frozenset({"query"}),                      "web_search"),
        (frozenset({"url"}),                        "web_scrape"),
        (frozenset({"input_path", "output_format"}), "convert_media"),
        (frozenset({"input_path", "operation"}),    "process_image"),
        (frozenset({"content", "category"}),        "save_memory"),
        (frozenset({"content", "fact"}),            "save_memory"),
        (frozenset({"path", "mode"}),               "chmod"),
        (frozenset({"pattern"}),                    "list_files"),
        (frozenset({"path", "pattern"}),             "list_files"),
        (frozenset({"path"}),                       "read_file"),
    ]

    @classmethod
    def _guess_type(cls, action: Dict) -> Optional[str]:
        """
        Próbuje wydedukować brakujący 'type' na podstawie pól akcji.
        Zwraca odgadnięty typ lub None gdy niemożliwe.
        """
        keys = set(action.keys())
        best_type = None
        best_score = 0
        for required_fields, action_type in cls._FIELD_TYPE_HINTS:
            overlap = len(keys & required_fields)
            if overlap == len(required_fields) and overlap > best_score:
                best_score = overlap
                best_type = action_type
        return best_type
    
    # Aliasy nieznanych typów → znane typy
    # Model czasem wymyśla nazwy których nie ma w RISK_MAP
    _TYPE_ALIASES: dict = {
        "create_shortcut":    "create_file",
        "create-shortcut":    "create_file",
        "create_desktop_file":"create_file",
        "add_to_menu":        "create_file",
        "register_app":       "run_command",
        "install":            "run_command",
        "install_app":        "run_command",
        "pin":                "run_command",
        "make_executable":    "chmod",
        "set_executable":     "chmod",
        "write_file":         "create_file",
        "save_file":          "create_file",
        "append_file":        "edit_file",
        "update_file":        "edit_file",
        "execute":            "run_command",
        "shell":              "run_command",
        "bash":               "run_command",
        "cmd":                "run_command",
        "command":            "run_command",
        "search":             "web_search",
        "copy_file":          "run_command",
        "rename_file":        "move_file",
    }

    @classmethod
    def validate(cls, actions: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Waliduj listę akcji.
        Zwraca: (czy_valid, lista_błędów)
        """
        errors = []
        
        for i, action in enumerate(actions):
            if "type" not in action:
                guessed = cls._guess_type(action)
                if guessed:
                    action["type"] = guessed
                else:
                    errors.append(f"Akcja #{i+1}: brak pola 'type'")
                    continue
            
            action_type = action["type"]
            
            if action_type not in cls.RISK_MAP:
                # Sprawdź alias
                alias = cls._TYPE_ALIASES.get(action_type)
                if alias:
                    action["type"] = alias
                    action_type = alias
                else:
                    # Nieznany typ - spróbuj odgadnąć z pól akcji
                    guessed = cls._guess_type(action)
                    if guessed:
                        action["type"] = guessed
                        action_type = guessed
                    else:
                        errors.append(f"Akcja #{i+1}: nieznany typ '{action_type}'")
                        continue
            
            type_errors = cls._validate_action_type(action)
            errors.extend([f"Akcja #{i+1}: {e}" for e in type_errors])
        
        return (len(errors) == 0, errors)
    
    @classmethod
    def _validate_action_type(cls, action: Dict) -> List[str]:
        """Walidacja specyficzna dla danego typu akcji"""
        errors = []
        action_type = action["type"]
        
        if action_type == "read_file":
            if "path" not in action:
                errors.append("brak wymaganego pola 'path'")
        
        elif action_type == "semantic_search":
            if "query" not in action:
                errors.append("brak wymaganego pola 'query'")
        
        elif action_type == "list_files":
            if "pattern" in action:
                if not isinstance(action["pattern"], str):
                    errors.append("pole 'pattern' musi być stringiem")
                elif not action["pattern"]:
                    errors.append("pole 'pattern' nie może być puste")
            if "path" in action:
                # Usprawnienie 5: pole path jest teraz aktywnie używane przez
                # action_executor do złożenia pełnej ścieżki glob;
                # walidujemy że to string i nie jest pusty
                if not isinstance(action["path"], str):
                    errors.append("pole 'path' w list_files musi być stringiem")
                elif not action["path"].strip():
                    errors.append("pole 'path' w list_files nie może być puste")
            if "recursive" in action:
                if not isinstance(action["recursive"], bool):
                    errors.append("pole 'recursive' musi być boolean")
        
        elif action_type == "create_file":
            if "path" not in action:
                errors.append("brak wymaganego pola 'path'")
            if "content" not in action:
                errors.append("brak wymaganego pola 'content'")
            elif not action["content"]:
                errors.append("pole 'content' jest puste (NIE WOLNO tworzyć pustych plików)")
        
        elif action_type == "edit_file":
            if "path" not in action:
                errors.append("brak wymaganego pola 'path'")
            has_match_replace = "match" in action and "replace" in action
            has_line_edit = all(k in action for k in ["line_start", "line_end", "content"])
            if not (has_match_replace or has_line_edit):
                errors.append("brak wymaganych pól do edycji (match+replace LUB line_start+line_end+content)")
        
        elif action_type == "patch_file":
            if "path" not in action:
                errors.append("brak wymaganego pola 'path'")
            has_patches = "patches" in action and isinstance(action["patches"], list)
            has_diff    = "diff" in action and isinstance(action["diff"], str) and action["diff"].strip()
            if not has_patches and not has_diff:
                errors.append(
                    "patch_file wymaga pola 'patches' (lista bloków) "
                    "lub 'diff' (string z blokami SEARCH/REPLACE)"
                )
            if has_patches:
                for i, p in enumerate(action["patches"], 1):
                    if not isinstance(p, dict):
                        errors.append(f"patches[{i}]: musi być słownikiem")
                    elif "search" not in p or "replace" not in p:
                        errors.append(f"patches[{i}]: wymaga pól 'search' i 'replace'")

        elif action_type == "delete_file":
            if "path" not in action:
                errors.append("brak wymaganego pola 'path'")
        
        elif action_type == "move_file":
            if "from" not in action:
                errors.append("brak wymaganego pola 'from'")
            if "to" not in action:
                errors.append("brak wymaganego pola 'to'")
        
        elif action_type == "mkdir":
            if "path" not in action:
                errors.append("brak wymaganego pola 'path'")
        
        elif action_type == "chmod":
            if "path" not in action:
                errors.append("brak wymaganego pola 'path'")
            if "mode" not in action:
                errors.append("brak wymaganego pola 'mode'")
        
        elif action_type == "run_command":
            if "command" not in action:
                errors.append("brak wymaganego pola 'command'")
        
        elif action_type == "open_path":
            if "path" not in action:
                errors.append("brak wymaganego pola 'path'")
        
        elif action_type == "download_media":
            if "url" not in action:
                errors.append("brak wymaganego pola 'url'")
        
        elif action_type == "convert_media":
            if "input_path" not in action:
                errors.append("brak wymaganego pola 'input_path'")
            if "output_format" not in action:
                errors.append("brak wymaganego pola 'output_format'")

        # === IMAGE ACTIONS ===

        elif action_type == "process_image":
            if "input_path" not in action:
                errors.append("brak wymaganego pola 'input_path'")
            if "operation" not in action:
                errors.append("brak wymaganego pola 'operation' (convert/compress/resize/crop/ico/favicon_set/info/strip_metadata)")
            else:
                op = action["operation"]
                valid_ops = {"convert", "compress", "resize", "crop", "ico", "favicon_set", "info", "strip_metadata"}
                if op not in valid_ops:
                    errors.append(f"nieznana operacja '{op}', dozwolone: {', '.join(sorted(valid_ops))}")
                if op == "resize":
                    if "width" not in action and "height" not in action:
                        errors.append("resize wymaga pola 'width' lub 'height'")
                elif op == "crop":
                    for field in ("x", "y", "width", "height"):
                        if field not in action:
                            errors.append(f"crop wymaga pola '{field}'")
                elif op == "convert":
                    if "output_format" not in action:
                        errors.append("convert wymaga pola 'output_format'")

        elif action_type == "batch_images":
            if "input_paths" not in action and "input_pattern" not in action:
                errors.append("brak wymaganego pola 'input_paths' lub 'input_pattern'")
            if "operation" not in action:
                errors.append("brak wymaganego pola 'operation' (convert/compress)")
            else:
                op = action["operation"]
                if op not in {"convert", "compress"}:
                    errors.append(f"batch_images obsługuje tylko: convert, compress")
                if op == "convert" and "output_format" not in action:
                    errors.append("batch convert wymaga pola 'output_format'")

        elif action_type == "image_info":
            if "path" not in action:
                errors.append("brak wymaganego pola 'path'")

        # === CLIPBOARD ACTIONS ===

        elif action_type == "clipboard_write":
            if "content" not in action:
                errors.append("brak wymaganego pola 'content'")

        # clipboard_read nie wymaga żadnych pól
        
        return errors
    
    @classmethod
    def categorize_by_risk(cls, actions: List[Dict]) -> Dict[ActionRisk, List[Dict]]:
        """
        Kategoryzuj akcje według poziomu ryzyka.
        Zwraca dict: {ActionRisk: [actions]}
        """
        categorized: Dict[ActionRisk, List[Dict]] = {risk: [] for risk in ActionRisk}
        
        for action in actions:
            action_type = action.get("type", "")
            if not action_type:
                continue
            risk = cls.RISK_MAP.get(action_type, ActionRisk.EXECUTE)
            categorized[risk].append(action)
        
        return categorized
    
    @classmethod
    def requires_confirm(cls, actions: List[Dict], config: Optional[Dict] = None) -> bool:
        """
        Sprawdź czy akcje wymagają potwierdzenia użytkownika.
        """
        from classification.command_classifier import CommandClassifier, CommandRisk as CmdRisk
        
        if config is None:
            config = {}
        
        auto_confirm_safe = config.get('execution', {}).get('auto_confirm_safe_commands', True)
        
        categorized = cls.categorize_by_risk(actions)
        
        if categorized[ActionRisk.DESTRUCTIVE]:
            return True
        
        execute_actions = categorized[ActionRisk.EXECUTE]
        
        if execute_actions:
            for action in execute_actions:
                if action.get("type") == "run_command":
                    command = action.get("command", "")
                    risk, _ = CommandClassifier.classify(command)
                    if risk != CmdRisk.READ_ONLY:
                        return True
                elif action.get("type") in ["download_media", "convert_media", "process_image", "batch_images"]:
                    return True
            
            if auto_confirm_safe:
                return False
        
        if len(categorized[ActionRisk.MODIFY]) > 5:
            return True
        
        return False
    
    @classmethod
    def get_risk_summary(cls, actions: List[Dict]) -> str:
        """Zwróć podsumowanie ryzyka dla listy akcji"""
        categorized = cls.categorize_by_risk(actions)
        
        lines = []
        
        if categorized[ActionRisk.SAFE]:
            lines.append(f"✓ Bezpieczne: {len(categorized[ActionRisk.SAFE])} akcji")
        
        if categorized[ActionRisk.MODIFY]:
            lines.append(f"✎ Modyfikacje: {len(categorized[ActionRisk.MODIFY])} akcji")
        
        if categorized[ActionRisk.DESTRUCTIVE]:
            lines.append(f"⚠ DESTRUKCYJNE: {len(categorized[ActionRisk.DESTRUCTIVE])} akcji")
        
        if categorized[ActionRisk.EXECUTE]:
            lines.append(f"▶ WYKONANIE: {len(categorized[ActionRisk.EXECUTE])} akcji")
        
        return "\n".join(lines)