"""
System logowania dla AI CLI Agent.

LOKALIZACJE:
- ~/.cache/ai-cli/logs/ - logi diagnostyczne (debug, errors)
- <projekt>/.ai-logs/ - audit trail projektu (operacje, decyzje)
"""

import logging
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import os

class AILogger:
    """
    Centralny system logowania.
    
    Dwie kategorie logów:
    1. Diagnostic logs (cache) - dla developera/debugowania
    2. Audit trail (projekt) - dla zespołu/historii
    """
    
    def __init__(self, project_root: Optional[Path] = None, config: Optional[Dict] = None):
        self.config = config or {}
        self.project_root = project_root
        # run_id tracking: mapuje (user_input) → (run_id, iteration_count)
        self._run_registry: Dict[str, list] = {}  # key → [run_id, iter]
        
        # Cache directory dla logów diagnostycznych
        self.cache_dir = Path.home() / ".cache" / "ai-cli" / "logs"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Project logs (jeśli jesteśmy w projekcie)
        if project_root:
            self.project_logs_dir = project_root / ".ai-logs"
            self.project_logs_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.project_logs_dir = None
        
        # Setup loggers
        self._setup_loggers()
    
    def _setup_loggers(self):
        """Konfiguruj loggery"""
        
        # Poziom logowania z configu
        log_level = self.config.get('debug', {}).get('log_level', 'info').upper()
        
        # === DEBUG LOGGER (cache) ===
        self.debug_logger = logging.getLogger('ai_debug')
        self.debug_logger.setLevel(getattr(logging, log_level))
        
        # Usuń poprzednie handlery
        self.debug_logger.handlers = []
        
        # File handler
        debug_file = self.cache_dir / "debug.log"
        debug_handler = logging.FileHandler(debug_file)
        debug_handler.setLevel(logging.DEBUG)
        debug_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        debug_handler.setFormatter(debug_formatter)
        self.debug_logger.addHandler(debug_handler)
        
        # === ERROR LOGGER (cache) ===
        self.error_logger = logging.getLogger('ai_errors')
        self.error_logger.setLevel(logging.ERROR)
        self.error_logger.handlers = []
        
        error_file = self.cache_dir / "errors.log"
        error_handler = logging.FileHandler(error_file)
        error_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s\n%(pathname)s:%(lineno)d\n',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_formatter)
        self.error_logger.addHandler(error_handler)
        
        # === API LOGGER (cache, opcjonalny) ===
        if self.config.get('debug', {}).get('log_model_raw_output', False):
            self.api_logger = logging.getLogger('ai_api')
            self.api_logger.setLevel(logging.DEBUG)
            self.api_logger.handlers = []
            
            api_file = self.cache_dir / "api-calls.log"
            api_handler = logging.FileHandler(api_file)
            api_formatter = logging.Formatter(
                '%(asctime)s\n%(message)s\n' + '-'*80 + '\n',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            api_handler.setFormatter(api_formatter)
            self.api_logger.addHandler(api_handler)
        else:
            self.api_logger = None
    
    # === DIAGNOSTIC LOGS ===
    
    def _get_run_context(self, user_input: str) -> Tuple[str, int]:
        """
        Zwraca (run_id, iteration) dla danego polecenia użytkownika.
        Pierwsze wywołanie dla danego input → nowy UUID, iteration=1.
        Kolejne → ten sam UUID, iteration rośnie.
        run_id jest resetowany po wywołaniu reset_run() lub przy nowym zapytaniu
        nie zarejestrowanym wcześniej.
        """
        if user_input not in self._run_registry:
            self._run_registry[user_input] = [str(uuid.uuid4())[:8], 0]
        self._run_registry[user_input][1] += 1
        run_id, iteration = self._run_registry[user_input]
        return run_id, iteration

    def reset_run(self, user_input: str):
        """Wyczyść run_id dla danego polecenia (wywołaj po zakończeniu rundy)."""
        self._run_registry.pop(user_input, None)


    def debug(self, message: str):
        """Log debug message"""
        self.debug_logger.debug(message)
    
    def info(self, message: str):
        """Log info message"""
        self.debug_logger.info(message)
    
    def warning(self, message: str):
        """Log warning"""
        self.debug_logger.warning(message)
    
    def error(self, message: str, exc_info=False):
        """Log error"""
        self.debug_logger.error(message, exc_info=exc_info)
        self.error_logger.error(message, exc_info=exc_info)
    
    def log_api_call(self, request: Dict, response: str):
        """Log API call (Ollama)"""
        if not self.api_logger:
            return
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "request": request,
            "response_preview": response[:500]
        }
        
        self.api_logger.debug(json.dumps(log_entry, indent=2, ensure_ascii=False))

    def log_model_response(self, user_input: str, raw: str, parsed: Optional[Dict] = None,
                           error: Optional[str] = None, rescued: bool = False):
        """
        Zapisz surową odpowiedź modelu do .ai-logs/responses.jsonl
        
        Poprawki vs oryginał:
        - raw_response zapisywane po strippowaniu markdown fences (```json...```)
          żeby nie zaśmiecać logu; oryginał dostępny w raw_original gdy inny
        - run_id z tego samego kontekstu co log_operation
        """
        log_dir = self.project_logs_dir if self.project_logs_dir else self.cache_dir

        run_id, _ = self._get_run_context(user_input)

        # Strip markdown code fences jeśli model owinął JSON w ```
        import re as _re
        _fence_re = _re.compile(r'^```(?:json)?\s*\n(.*?)\n```\s*$', _re.DOTALL)
        cleaned_raw = raw.strip()
        fence_match = _fence_re.match(cleaned_raw)
        had_fence = bool(fence_match)
        if had_fence:
            cleaned_raw = fence_match.group(1).strip()

        entry = {
            "timestamp": datetime.now().isoformat(),
            "run_id": run_id,
            "user_input": user_input,
            "raw_response": cleaned_raw,
            "raw_len": len(cleaned_raw),
            # Zachowaj oryginalny raw tylko gdy był zaśmiecony fences
            **({"raw_original_had_fence": True} if had_fence else {}),
            "error": error,
            "rescued_from_message": rescued,
            "parsed_type": (
                "actions" if parsed and parsed.get("actions") else
                "message" if parsed and parsed.get("message") else
                "unknown"
            ) if parsed else None,
            "actions": [a.get("type") for a in (parsed or {}).get("actions", [])] if parsed else None,
        }

        responses_file = log_dir / "responses.jsonl"
        try:
            with open(responses_file, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            self.error(f"Nie udało się zapisać log_model_response: {e}")

    def log_session_turn(self, user_input: str, ai_summary: str, actions: Optional[List] = None):
        """
        Czytelny log sesji do .ai-logs/session.log (lub cache gdy brak projektu).
        Format: timestamp | user: ... | ai: ... | actions: [...]
        """
        log_dir = self.project_logs_dir if self.project_logs_dir else self.cache_dir
        session_file = log_dir / "session.log"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        actions_str = ", ".join(
            f"{a.get('type')}:{a.get('path', a.get('command', '?'))}"
            for a in (actions or [])
        )
        line = f"[{ts}] USER: {user_input!r}\n"
        line += f"[{ts}]   AI: {ai_summary[:200]}\n"
        if actions_str:
            line += f"[{ts}]   ACTIONS: {actions_str}\n"
        line += "\n"

        try:
            with open(session_file, "a") as f:
                f.write(line)
        except Exception as e:
            self.error(f"Nie udało się zapisać session.log: {e}")


    
    # === AUDIT TRAIL (projekt) ===
    
    def log_operation(self, user_input: str, actions: List[Dict], results: List, intent: Optional[str] = None):
        """
        Zaloguj operację w projekcie (audit trail, lub cache gdy brak projektu).
        
        Poprawki vs oryginał:
        - run_id: UUID grupujący wszystkie iteracje tego samego polecenia użytkownika
        - iteration: numer rundy w ramach jednego polecenia
        - success: uwzględnia też fallback-echo ("Nie znaleziono", "not found" itp.)
          exit_code==0 z fallbackiem echo NIE jest prawdziwym sukcesem
        """
        log_dir = self.project_logs_dir if self.project_logs_dir else self.cache_dir
        operations_file = log_dir / "operations.jsonl"

        run_id, iteration = self._get_run_context(user_input)

        # Frazy w stdout świadczące o semantycznym niepowodzeniu mimo exit 0
        _FAILURE_PHRASES = (
            "nie znaleziono", "not found", "no such file",
            "błąd", "error", "failed", "command not found",
        )

        def _action_success(action: Dict, result) -> bool:
            if isinstance(result, str) and result.startswith("[BŁĄD]"):
                return False
            if isinstance(result, str):
                low = result.lower()
                if any(ph in low for ph in _FAILURE_PHRASES):
                    return False
            if isinstance(result, dict):
                if result.get("type") == "error":
                    return False
                # Poprawka 8: jawny niezerowy returncode = niepowodzenie,
                # nawet jeśli stdout nie zawiera frazy błędu
                if isinstance(result.get("returncode"), int) and result["returncode"] != 0:
                    return False
                out = str(result.get("stdout", "") + result.get("stderr", "")).lower()
                if any(ph in out for ph in _FAILURE_PHRASES):
                    return False
            return True

        action_entries = [
            {
                "type": a.get("type"),
                "path": a.get("path") or a.get("from"),
                "success": _action_success(a, r)
            }
            for a, r in zip(actions, results)
        ]

        entry = {
            "timestamp": datetime.now().isoformat(),
            "run_id": run_id,
            "iteration": iteration,
            "user": self.config.get("nick", "user"),
            "command": user_input,
            "intent": intent,
            "actions_count": len(actions),
            "actions": action_entries,
            "overall_success": all(ae["success"] for ae in action_entries),
        }

        try:
            with open(operations_file, 'a') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            self.error(f"Nie udało się zapisać audit trail: {e}")
    
    def get_recent_operations(self, limit: int = 10) -> List[Dict]:
        """Pobierz ostatnie operacje z audit trail"""
        if not self.project_logs_dir:
            return []
        
        operations_file = self.project_logs_dir / "operations.jsonl"
        
        if not operations_file.exists():
            return []
        
        operations = []
        
        try:
            with open(operations_file, 'r') as f:
                for line in f:
                    try:
                        operations.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception:
            return []
        
        return operations[-limit:]
    
    # === MAINTENANCE ===
    
    def rotate_logs(self, max_size_mb: int = 10):
        """
        Rotacja logów diagnostycznych.
        Jeśli plik > max_size_mb, zmień nazwę na .old i zacznij nowy.
        """
        for log_file in self.cache_dir.glob("*.log"):
            size_mb = log_file.stat().st_size / (1024 * 1024)
            
            if size_mb > max_size_mb:
                old_name = log_file.with_suffix('.log.old')
                
                # Usuń stary backup
                if old_name.exists():
                    old_name.unlink()
                
                # Zmień nazwę obecnego
                log_file.rename(old_name)
                
                self.info(f"Rotacja logu: {log_file.name}")
    
    def cleanup_old_logs(self, days: int = 30):
        """Usuń stare logi z cache (starsze niż X dni)"""
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        
        removed = []
        
        for log_file in self.cache_dir.glob("*.log*"):
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            
            if mtime < cutoff:
                log_file.unlink()
                removed.append(log_file.name)
        
        if removed:
            self.info(f"Usunięto stare logi: {', '.join(removed)}")
        
        return removed
    
    def get_logs_summary(self) -> Dict:
        """Zwróć podsumowanie logów"""
        summary = {
            "cache_dir": str(self.cache_dir),
            "project_logs_dir": str(self.project_logs_dir) if self.project_logs_dir else None,
            "diagnostic_logs": [],
            "total_size_mb": 0
        }
        
        # Logi diagnostyczne
        for log_file in self.cache_dir.glob("*.log*"):
            size_mb = log_file.stat().st_size / (1024 * 1024)
            summary["diagnostic_logs"].append({
                "name": log_file.name,
                "size_mb": round(size_mb, 2),
                "modified": datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
            })
            summary["total_size_mb"] += size_mb
        
        summary["total_size_mb"] = round(summary["total_size_mb"], 2)
        
        # Operacje projektu
        if self.project_logs_dir:
            operations_file = self.project_logs_dir / "operations.jsonl"
            if operations_file.exists():
                summary["project_operations_count"] = sum(1 for _ in open(operations_file))
        
        return summary