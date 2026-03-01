"""
Formalny model stanu agenta.

PROBLEM (przed):
    Implicit state rozrzucony po agent.py:
    - execution_failed flag
    - collect_only_iterations licznik
    - 15+ return w środku pętli
    - force_action bool przekazywany ad-hoc
    - brak jednego miejsca które mówi "agent jest teraz X"

ROZWIĄZANIE (teraz):
    AgentState enum          — co agent teraz robi
    StepResult dataclass     — co zwraca każda iteracja
    IterationContext         — persystentny kontekst między iteracjami
    StagnationDetector       — wykrywanie zapętlenia akcji

FILOZOFIA:
    Nie enterprise. Nie overengineering.
    Tylko tyle żeby debugowanie nie było "szukaj return w linii 847".
    Każde wyjście z pętli ma teraz nazwę i powód.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ─── Stan agenta ──────────────────────────────────────────────────────────────

class AgentState(Enum):
    """
    Stany w jakich może być agent podczas wykonania jednego run().

    Przejścia:
        THINKING   → EXECUTING      (model zwrócił akcje)
        THINKING   → DONE           (model zwrócił message bez akcji)
        THINKING   → FAILED         (błąd połączenia / parsowania)
        THINKING   → WAITING_USER   (akcje wymagają potwierdzenia → user anulował)
        EXECUTING  → THINKING       (wyniki wymagają follow-up)
        EXECUTING  → DONE           (zadanie ukończone)
        EXECUTING  → FAILED         (rollback / błąd krytyczny)
        WAITING_USER → EXECUTING    (user zatwierdził)
        WAITING_USER → DONE         (user anulował)
    """
    THINKING     = "thinking"      # Czekamy na odpowiedź modelu
    EXECUTING    = "executing"     # Wykonujemy akcje
    WAITING_USER = "waiting_user"  # Czekamy na potwierdzenie użytkownika
    DONE         = "done"          # Zadanie ukończone (sukces lub anulowanie)
    FAILED       = "failed"        # Błąd krytyczny


# ─── Powody zakończenia ───────────────────────────────────────────────────────

class DoneReason(Enum):
    """Dlaczego agent zakończył działanie."""
    MODEL_MESSAGE        = "model_message"        # Model zwrócił message → koniec
    USER_CANCELLED       = "user_cancelled"       # User nie potwierdził akcji
    NO_FOLLOWUP_NEEDED   = "no_followup_needed"   # Wyniki nie wymagają kolejnej iteracji
    MAX_ITERATIONS       = "max_iterations"       # Osiągnięto limit iteracji
    PLAN_ONLY            = "plan_only"            # Tryb --plan, zero wykonania
    SYSTEM_QUERY         = "system_query"         # Szybka odpowiedź (czas, data)


class FailedReason(Enum):
    """Dlaczego agent trafił w FAILED."""
    OLLAMA_CONNECTION     = "ollama_connection"     # Brak połączenia z Ollama
    JSON_PARSE_ERROR      = "json_parse_error"      # Model zwrócił invalid JSON
    ACTION_VALIDATION     = "action_validation"     # Akcje nie przeszły walidacji
    CAPABILITY_VIOLATION  = "capability_violation"  # Naruszenie capability
    PLAN_INVALID          = "plan_invalid"          # Plan ma błędy krytyczne
    TRANSACTION_ROLLBACK  = "transaction_rollback"  # Transakcja cofnięta
    STAGNATION            = "stagnation"            # Wykryto zapętlenie
    KEYBOARD_INTERRUPT    = "keyboard_interrupt"    # Ctrl+C


# ─── Wynik kroku ─────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    """
    Wynik jednej iteracji pętli agenta.

    Zamiast 15+ return w środku pętli mamy jeden obiekt
    który mówi dokładnie co się stało i dlaczego.
    """
    state: AgentState

    # Dla DONE
    done_reason: Optional[DoneReason] = None

    # Dla FAILED
    failed_reason: Optional[FailedReason] = None
    error_message: Optional[str] = None

    # Payload dla następnej iteracji (THINKING)
    messages_to_append: Optional[List[Dict]] = None

    # Payload dla EXECUTING
    actions: Optional[List[Dict]] = None
    results: Optional[List[Any]] = None

    # Meta
    iteration: int = 0
    had_rollback: bool = False

    @classmethod
    def thinking(cls, iteration: int = 0) -> "StepResult":
        return cls(state=AgentState.THINKING, iteration=iteration)

    @classmethod
    def done(cls, reason: DoneReason, iteration: int = 0) -> "StepResult":
        return cls(state=AgentState.DONE, done_reason=reason, iteration=iteration)

    @classmethod
    def failed(cls, reason: FailedReason, message: str = "", iteration: int = 0) -> "StepResult":
        return cls(
            state=AgentState.FAILED,
            failed_reason=reason,
            error_message=message,
            iteration=iteration
        )

    @classmethod
    def executing(cls, actions: List[Dict], iteration: int = 0) -> "StepResult":
        return cls(state=AgentState.EXECUTING, actions=actions, iteration=iteration)

    def is_terminal(self) -> bool:
        """Czy ten stan kończy pętlę?"""
        return self.state in (AgentState.DONE, AgentState.FAILED)

    def __str__(self) -> str:
        if self.state == AgentState.DONE:
            return f"DONE({self.done_reason.value if self.done_reason else '?'})"
        if self.state == AgentState.FAILED:
            return f"FAILED({self.failed_reason.value if self.failed_reason else '?'}): {self.error_message or ''}"
        return f"{self.state.value.upper()}"


# ─── Kontekst iteracji ────────────────────────────────────────────────────────

@dataclass
class IterationContext:
    """
    Persystentny kontekst między iteracjami pętli.

    Przed: collect_only_iterations, execution_failed, last_failed_command
    jako zmienne lokalne w run() — niewidoczne w logach.

    Teraz: jeden obiekt z historią który można zalogować i debugować.
    """
    max_iterations: int = 8
    current_iteration: int = 0

    # Licznik iteracji bez tworzenia/edycji plików (detect stagnation)
    collect_only_streak: int = 0
    force_action_threshold: int = 2  # Po ilu "collect only" wstrzyknąć force_action

    # Historia akcji per iteracja (dla cycle detection)
    action_history: List[Tuple[int, str]] = field(default_factory=list)
    # (iteration_num, action_fingerprint)

    # Stan wykonania
    last_failed_command: Optional[str] = None
    had_any_modification: bool = False

    def tick(self) -> bool:
        """
        Przejdź do kolejnej iteracji.
        Zwraca False jeśli osiągnięto max_iterations.
        """
        self.current_iteration += 1
        return self.current_iteration <= self.max_iterations

    def record_actions(self, actions: List[Dict]) -> None:
        """Zapisz fingerprint akcji do historii."""
        fingerprint = _actions_fingerprint(actions)
        self.action_history.append((self.current_iteration, fingerprint))

        had_create = any(
            a.get("type") in ("create_file", "edit_file", "patch_file")
            for a in actions
        )
        if had_create:
            self.collect_only_streak = 0
            self.had_any_modification = True
        else:
            self.collect_only_streak += 1

    @property
    def should_force_action(self) -> bool:
        return self.collect_only_streak >= self.force_action_threshold

    @property
    def remaining_iterations(self) -> int:
        return self.max_iterations - self.current_iteration

    def summary(self) -> str:
        return (
            f"iter={self.current_iteration}/{self.max_iterations} "
            f"collect_streak={self.collect_only_streak} "
            f"modified={self.had_any_modification}"
        )


# ─── Stagnation Detector ──────────────────────────────────────────────────────

class StagnationDetector:
    """
    Wykrywa zapętlenie akcji agenta.

    Wzorce które wykrywamy:
    1. Exact cycle:     [read,grep] → [read,grep] → [read,grep]
    2. Partial repeat:  te same typy akcji w >=3 z ostatnich 4 iteracji
    3. No-progress:     >=4 iteracje bez żadnej modyfikacji pliku

    Filozofia: nie blokujemy agresywnie — lepiej False negative niż
    False positive który przerwie prawdziwe zadanie.
    """

    CYCLE_WINDOW = 4       # Ile ostatnich iteracji sprawdzamy
    EXACT_CYCLE_MIN = 2    # Ile powtórzeń tego samego fingerprinta = cykl
    NO_PROGRESS_LIMIT = 4  # Ile iteracji bez modyfikacji = stagnacja

    def check(self, ctx: IterationContext) -> Tuple[bool, str]:
        """
        Sprawdź czy agent jest w stagnacji.

        Returns:
            (is_stagnant, reason_description)
        """
        history = ctx.action_history
        if len(history) < 2:
            return False, ""

        # ── Exact cycle detection ─────────────────────────────────────────
        recent = [fp for _, fp in history[-self.CYCLE_WINDOW:]]
        if len(recent) >= self.EXACT_CYCLE_MIN:
            # Liczymy powtórzenia ostatniego fingerprinta
            last_fp = recent[-1]
            count = sum(1 for fp in recent if fp == last_fp)
            if count >= self.EXACT_CYCLE_MIN:
                return True, (
                    f"Exact cycle detected: akcje '{last_fp}' "
                    f"powtórzyły się {count}x w ostatnich {len(recent)} iteracjach"
                )

        # ── No-progress detection ─────────────────────────────────────────
        if ctx.collect_only_streak >= self.NO_PROGRESS_LIMIT:
            return True, (
                f"No-progress: {ctx.collect_only_streak} iteracji "
                f"bez żadnej modyfikacji pliku"
            )

        return False, ""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _actions_fingerprint(actions: List[Dict]) -> str:
    """
    Stwórz krótki fingerprint listy akcji do porównania.
    Np. [read_file:app.py, run_command:grep] → "read:app.py|run:grep"
    """
    parts = []
    for a in actions:
        t = a.get("type", "?")
        # Skróć typ
        short_type = t.split("_")[0] if "_" in t else t
        # Klucz identyfikujący cel akcji
        target = a.get("path") or a.get("command", "")[:30] or a.get("query", "")[:20] or ""
        parts.append(f"{short_type}:{target}")
    return "|".join(parts)
