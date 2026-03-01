"""
Command Classifier - rozpoznawanie typu komendy systemowej.

PROBLEM:
- find, grep, ls wymagają potwierdzenia (są EXECUTE)
- rm, dd, mkfs również EXECUTE - ale te są niebezpieczne

ROZWIĄZANIE:
- Klasyfikuj komendy na: READ_ONLY, MODIFY, DESTRUCTIVE
- READ_ONLY nie wymaga confirm (chyba że --confirm)
- DESTRUCTIVE zawsze wymaga confirm
"""

from typing import Optional, Tuple
from enum import Enum


class CommandRisk(Enum):
    """Poziom ryzyka komendy systemowej"""
    READ_ONLY = "read_only"       # find, grep, ls - bezpieczne
    MODIFY = "modify"             # touch, mkdir - tworzą coś
    DESTRUCTIVE = "destructive"   # rm, dd - niebezpieczne


class CommandClassifier:
    """
    Klasyfikuje komendy systemowe według poziomu ryzyka.
    
    Używane w agent.py przy run_command.
    """
    
    # Białe listy komend
    READ_ONLY_COMMANDS = {
        # Listowanie
        "ls", "ll", "la", "dir",
        
        # Wyszukiwanie
        "find", "locate", "which", "whereis",
        
        # Grep i teksty
        "grep", "egrep", "fgrep", "rg", "ag",
        "cat", "less", "more", "head", "tail",
        
        # Statystyki i info
        "wc", "stat", "file", "du", "df",
        
        # Porównywanie
        "diff", "cmp", "comm",
        
        # Git read-only
        "git log", "git status", "git diff", "git show", "git branch",
        
        # System info
        "ps", "top", "htop", "uptime", "whoami", "hostname",
        "uname", "lscpu", "lsblk", "free", "vmstat",
        
        # Network read
        "ping", "traceroute", "nslookup", "dig", "host",
        "netstat", "ss", "ip addr", "ip route",
        
        # Package managers (query only)
        "apt list", "apt search", "apt show",
        "yum list", "yum search", "yum info",
        "dpkg -l", "rpm -qa",
        
        # Python/Node
        "pip list", "pip show", "npm list", "npm view",
        
        # Pobieranie danych (nie modyfikują lokalnego systemu)
        "curl", "wget",
        
        # Narzędzia tekstowe
        "sed", "awk", "sort", "uniq", "cut", "tr", "xargs",
        
        # Inne
        "echo", "printf", "date", "cal", "bc",
        "python3", "python",  # odczyt/obliczenia przez pipe
        "xdg-mime", "xdg-open",  # sprawdzanie typów/otwieranie
    }
    
    # Komendy modyfikujące (wymagają confirm, ale nie są destrukcyjne)
    MODIFY_COMMANDS = {
        "touch", "mkdir",
        "git add", "git commit", "git push",
        "npm install", "pip install",
        "apt install", "yum install",
        "cp", "rsync",  # kopiowanie
        "chmod", "chown",  # zmiana uprawnień
        "ln",  # dowiązania
    }
    
    # Komendy destrukcyjne (zawsze wymagają confirm)
    DESTRUCTIVE_COMMANDS = {
        "rm", "rmdir",
        "dd", "shred",
        "mkfs", "fdisk", "parted",
        "git reset --hard", "git clean -fd",
        "npm uninstall", "pip uninstall",
        "apt remove", "apt purge", "yum remove",
        "kill", "pkill", "killall",
        "shutdown", "reboot", "poweroff",
        "mv",  # przenoszenie = potencjalna utrata danych
    }
    
    @classmethod
    def classify(cls, command: str) -> Tuple[CommandRisk, str]:
        """
        Klasyfikuj komendę.
        
        Args:
            command: pełna komenda (np. "find . -name '*.py'")
        
        Returns:
            (CommandRisk, reason: str)
        """
        # Wyciągnij pierwszą komendę (bazę)
        base_cmd = cls._extract_base_command(command)
        
        # Sprawdź multi-word commands (git log, apt list)
        for cmd_prefix in cls.READ_ONLY_COMMANDS:
            if command.strip().startswith(cmd_prefix):
                return (CommandRisk.READ_ONLY, f"'{cmd_prefix}' to komenda read-only")
        
        # Sprawdź destrukcyjne
        for cmd_prefix in cls.DESTRUCTIVE_COMMANDS:
            if command.strip().startswith(cmd_prefix):
                return (CommandRisk.DESTRUCTIVE, f"'{cmd_prefix}' jest destrukcyjna")
        
        # Sprawdź modyfikujące
        for cmd_prefix in cls.MODIFY_COMMANDS:
            if command.strip().startswith(cmd_prefix):
                return (CommandRisk.MODIFY, f"'{cmd_prefix}' modyfikuje system")
        
        # Single-word commands
        if base_cmd in cls.READ_ONLY_COMMANDS:
            return (CommandRisk.READ_ONLY, f"'{base_cmd}' to komenda read-only")
        
        if base_cmd in cls.DESTRUCTIVE_COMMANDS:
            return (CommandRisk.DESTRUCTIVE, f"'{base_cmd}' jest destrukcyjna")
        
        if base_cmd in cls.MODIFY_COMMANDS:
            return (CommandRisk.MODIFY, f"'{base_cmd}' modyfikuje system")
        
        # Heurystyki dla nieznanych komend
        if any(dangerous in command for dangerous in ["rm -rf", "dd if=", "mkfs", "> /dev/"]):
            return (CommandRisk.DESTRUCTIVE, "Komenda zawiera niebezpieczne operacje")
        
        # Sudo = potencjalnie niebezpieczne
        if command.strip().startswith("sudo"):
            # Sprawdź co jest po sudo
            after_sudo = command.strip()[4:].strip()
            sudo_risk, sudo_reason = cls.classify(after_sudo)
            
            # Sudo + read-only = modify (wymaga hasła)
            if sudo_risk == CommandRisk.READ_ONLY:
                return (CommandRisk.MODIFY, f"sudo + {sudo_reason}")
            
            return (sudo_risk, f"sudo + {sudo_reason}")
        
        # Default: nieznana komenda = MODIFY (ostrożność)
        return (CommandRisk.MODIFY, f"Nieznana komenda '{base_cmd}' - wymaga potwierdzenia")
    
    @classmethod
    def _extract_base_command(cls, command: str) -> str:
        """
        Wyciągnij bazową komendę.
        
        "find . -name '*.py'" -> "find"
        "sudo apt update" -> "sudo"
        """
        parts = command.strip().split()
        if not parts:
            return ""
        
        return parts[0]
    
    @classmethod
    def requires_confirm(cls, command: str, auto_confirm_safe: bool = True) -> bool:
        """
        Czy komenda wymaga potwierdzenia?
        
        Args:
            command: komenda do sprawdzenia
            auto_confirm_safe: czy auto-confirm dla READ_ONLY (z configu)
        
        Returns:
            True jeśli wymaga confirm
        """
        risk, _ = cls.classify(command)
        
        # DESTRUCTIVE zawsze wymaga
        if risk == CommandRisk.DESTRUCTIVE:
            return True
        
        # MODIFY wymaga
        if risk == CommandRisk.MODIFY:
            return True
        
        # READ_ONLY - zależy od configu
        if risk == CommandRisk.READ_ONLY:
            return not auto_confirm_safe
        
        return True
    
    @classmethod
    def get_risk_description(cls, command: str) -> str:
        """Zwróć opis ryzyka komendy"""
        risk, reason = cls.classify(command)
        
        descriptions = {
            CommandRisk.READ_ONLY: "✓ Bezpieczna (tylko odczyt)",
            CommandRisk.MODIFY: "⚠ Modyfikuje system",
            CommandRisk.DESTRUCTIVE: "🔴 DESTRUKCYJNA - może usunąć dane"
        }
        
        desc = descriptions.get(risk, "❓ Nieznany poziom ryzyka")
        
        return f"{desc} - {reason}"