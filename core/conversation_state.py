"""
Conversation State - krótkotrwała pamięć rozmowy.

PROBLEM:
- AI pyta "czy wdrożyć"
- User odpowiada "tak"
- AI nie pamięta co pytało

ROZWIĄZANIE jest proste :D
- Pamięć dialogowa w obrębie sesji
- Śledzenie pending operations
- Inteligentne rozpoznawanie odpowiedzi - i.. tyle xD
"""

from typing import Optional, Dict, List
from datetime import datetime, timedelta

class ConversationState:
    """
    Zarządza stanem rozmowy w obrębie sesji.
    
    NIE JEST TO:
    - Długotrwała pamięć (to ProjectMemory)
    - Persystencja (to zapisywane w .ai-context.json)
    
    TO JEST:
    - Pamięć ostatnich 5-10 wymian
    - Pending confirmations
    - Awaiting decisions
    """
    
    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self.messages: List[Dict] = []
        self.pending_confirmation: Optional[Dict] = None
        self.last_ai_question: Optional[str] = None
        self.last_ai_response_time: Optional[datetime] = None
    
    def add_user_message(self, content: str):
        """Dodaj wiadomość użytkownika"""
        self.messages.append({
            "role": "user",
            "content": content,
            "timestamp": datetime.now()
        })
        
        # Ogranicz historię
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]
    
    def add_ai_message(self, content: str, question: Optional[str] = None):
        """
        Dodaj wiadomość AI.
        
        Args:
            content: Treść odpowiedzi
            question: Czy AI zadało pytanie? (np. "czy wdrożyć?")
        """
        self.messages.append({
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now()
        })
        
        if question:
            self.last_ai_question = question
            self.last_ai_response_time = datetime.now()
        
        # Ogranicz historię
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]
    
    def set_pending_confirmation(self, actions: List[Dict], description: str):
        """
        Ustaw pending confirmation.
        
        AI zaproponowało akcje i czeka na potwierdzenie.
        """
        self.pending_confirmation = {
            "actions": actions,
            "description": description,
            "asked_at": datetime.now()
        }
    
    def clear_pending_confirmation(self):
        """Wyczyść pending confirmation"""
        self.pending_confirmation = None
        self.last_ai_question = None
    
    def has_pending_confirmation(self) -> bool:
        """Czy jest pending confirmation?"""
        if not self.pending_confirmation:
            return False
        
        # Wygaś po 5 minutach
        asked_at = self.pending_confirmation.get("asked_at")
        if asked_at and datetime.now() - asked_at > timedelta(minutes=5):
            self.clear_pending_confirmation()
            return False
        
        return True
    
    def is_confirmation_response(self, user_input: str) -> bool:
        """
        Czy user input to odpowiedź na pytanie AI?
        
        Rozpoznaje:
        - "tak", "t", "yes", "y"
        - "nie", "n", "no"
        - "zrób", "wdrażaj", "wykonaj"
        - "anuluj", "stop"
        """
        if not self.has_pending_confirmation():
            return False
        
        lower = user_input.lower().strip()
        
        # Pozytywne
        positive = ["tak", "t", "yes", "y", "zrób", "wdrażaj", "wykonaj", "ok", "dobra"]
        
        # Negatywne
        negative = ["nie", "n", "no", "anuluj", "stop", "cancel"]
        
        return lower in positive or lower in negative
    
    def get_confirmation_decision(self, user_input: str) -> bool:
        """
        Zwróć decyzję użytkownika (True = tak, False = nie).
        
        Returns:
            True jeśli pozytywna odpowiedź
            False jeśli negatywna
        """
        lower = user_input.lower().strip()
        
        positive = ["tak", "t", "yes", "y", "zrób", "wdrażaj", "wykonaj", "ok", "dobra"]
        
        return lower in positive
    
    def get_pending_actions(self) -> Optional[List[Dict]]:
        """Zwróć pending actions jeśli istnieją"""
        if not self.has_pending_confirmation():
            return None
        
        if self.pending_confirmation is None:
            return None
        
        return self.pending_confirmation.get("actions")
    
    def get_recent_context(self, last_n: int = 5) -> List[Dict]:
        """
        Zwróć ostatnie N wymian dla kontekstu.
        
        To pozwala AI pamiętać ostatnie 2-3 pytania.
        """
        return self.messages[-last_n:]
    
    def format_context_for_prompt(self) -> str:
        """
        Sformatuj ostatnie wymiany dla promptu AI.
        
        To pozwala AI pamiętać co było wcześniej.
        """
        if not self.messages:
            return ""
        
        recent = self.get_recent_context(last_n=3)
        
        if not recent:
            return ""
        
        lines = ["\n===================="]
        lines.append("OSTATNIA ROZMOWA")
        lines.append("====================\n")
        
        for msg in recent:
            role = "User" if msg["role"] == "user" else "AI"
            raw = msg["content"]
            # Usprawnienie: 300 znaków zamiast 100, przycinamy po ostatnim zdaniu
            # żeby nie urywać w połowie słowa/myśli
            if len(raw) > 300:
                cut = raw[:300]
                # cofnij do ostatniego separatora zdania
                for sep in (".", "!", "?", "\n", ","):
                    idx = cut.rfind(sep)
                    if idx > 150:
                        cut = cut[:idx + 1]
                        break
                snippet = cut
            else:
                snippet = raw
            lines.append(f"{role}: {snippet}")
        
        lines.append("\nPamiętaj kontekst tej rozmowy przy odpowiedzi.")
        
        return "\n".join(lines)
    
    def clear(self):
        """Wyczyść całą historię (nowa sesja)"""
        self.messages = []
        self.pending_confirmation = None
        self.last_ai_question = None
        self.last_ai_response_time = None