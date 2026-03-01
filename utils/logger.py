"""
System logowania dla AI CLI Agent.

LOKALIZACJE:
- ~/.cache/ai-cli/logs/ - logi diagnostyczne (debug, errors)
- <projekt>/.ai-logs/ - audit trail projektu (operacje, decyzje)
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
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
        Zawsze loguje — niezależnie od log_model_raw_output w configu.
        Gdy brak projektu (project_logs_dir=None) — zapisuje do cache_dir.
        """
        log_dir = self.project_logs_dir if self.project_logs_dir else self.cache_dir

        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "raw_response": raw,
            "raw_len": len(raw),
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
        
        Format JSONL (JSON Lines) - każda linia = osobny event
        """
        log_dir = self.project_logs_dir if self.project_logs_dir else self.cache_dir
        operations_file = log_dir / "operations.jsonl"
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user": self.config.get("nick", "user"),
            "command": user_input,
            "intent": intent,
            "actions_count": len(actions),
            "actions": [
                {
                    "type": a.get("type"),
                    "path": a.get("path") or a.get("from"),
                    "success": not (isinstance(r, str) and r.startswith("[BŁĄD]"))
                }
                for a, r in zip(actions, results)
            ],
            "overall_success": all(
                not (isinstance(r, str) and r.startswith("[BŁĄD]"))
                for r in results
            )
        }
        
        # Append do JSONL
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