"""
Global Mode - tryb systemowy bez projektu.

FILOZOFIA:
- Nie wszystko wymaga projektu
- "która godzina" = runtime, nie AI
- "jaka jest data" = runtime, nie AI
- Proste pytania systemowe = instant odpowiedź

KIEDY używać:
- Poza katalogiem projektu
- Flaga --global
- Pytania o system (czas, data, hostname, pwd)
"""

import datetime
import os
import socket
from pathlib import Path
from typing import Optional, Dict

class GlobalMode:
    """
    Obsługuje zapytania systemowe bez kontekstu projektu.
    
    To są kompetencje RUNTIME, nie LLM.
    """
    
    # Pytania które ZAWSZE odpowiada runtime, nie model
    SYSTEM_QUERIES = {
        # Czas
        "która godzina": "time",
        "która jest godzina": "time",
        "jaka godzina": "time",
        "która": "time",
        
        # Data
        "jaka data": "date",
        "jaki dzień": "date",
        "który dzisiaj": "date",
        "dzisiaj": "date",
        
        # Dzień tygodnia
        "jaki dziś dzień tygodnia": "weekday",
        "który dzień tygodnia": "weekday",
        
        # System
        "gdzie jestem": "pwd",
        "pwd": "pwd",
        "hostname": "hostname",
        "jaki host": "hostname",
    }
    
    @classmethod
    def is_system_query(cls, query: str) -> bool:
        """Czy to pytanie systemowe?"""
        query_lower = query.lower().strip()
        return query_lower in cls.SYSTEM_QUERIES
    
    @classmethod
    def handle_system_query(cls, query: str) -> Optional[str]:
        """
        Obsłuż pytanie systemowe.
        
        Returns:
            Odpowiedź lub None jeśli to nie system query
        """
        query_lower = query.lower().strip()
        
        if query_lower not in cls.SYSTEM_QUERIES:
            return None
        
        query_type = cls.SYSTEM_QUERIES[query_lower]
        
        if query_type == "time":
            now = datetime.datetime.now()
            return f"Godzina: {now.strftime('%H:%M:%S')}"
        
        elif query_type == "date":
            now = datetime.datetime.now()
            weekday_names = [
                "poniedziałek", "wtorek", "środa", "czwartek",
                "piątek", "sobota", "niedziela"
            ]
            weekday = weekday_names[now.weekday()]
            return f"Data: {now.strftime('%Y-%m-%d')} ({weekday})"
        
        elif query_type == "weekday":
            now = datetime.datetime.now()
            weekday_names = [
                "poniedziałek", "wtorek", "środa", "czwartek",
                "piątek", "sobota", "niedziela"
            ]
            return f"Dzień tygodnia: {weekday_names[now.weekday()]}"
        
        elif query_type == "pwd":
            return f"Katalog roboczy: {os.getcwd()}"
        
        elif query_type == "hostname":
            return f"Hostname: {socket.gethostname()}"
        
        return None
    
    @classmethod
    def get_system_context(cls) -> Dict[str, str]:
        """
        Zwróć kontekst systemowy dla promptu.
        
        To pozwala AI wiedzieć o systemie bez pytania.
        """
        now = datetime.datetime.now()
        weekday_names = [
            "poniedziałek", "wtorek", "środa", "czwartek",
            "piątek", "sobota", "niedziela"
        ]
        
        return {
            "current_time": now.strftime('%H:%M:%S'),
            "current_date": now.strftime('%Y-%m-%d'),
            "current_weekday": weekday_names[now.weekday()],
            "current_dir": os.getcwd(),
            "hostname": socket.gethostname(),
        }
    
    @classmethod
    def format_system_context_for_prompt(cls) -> str:
        """Sformatuj kontekst systemowy dla promptu AI"""
        ctx = cls.get_system_context()
        
        return f"""
====================
KONTEKST SYSTEMOWY
====================

Czas: {ctx['current_time']}
Data: {ctx['current_date']} ({ctx['current_weekday']})
Katalog: {ctx['current_dir']}
Hostname: {ctx['hostname']}

WAŻNE: Jeśli użytkownik pyta o czas, datę lub dzień tygodnia,
użyj tych informacji zamiast mówić "nie mam dostępu".
"""