"""
Model Manager – zarządzanie modelami Ollama.

Funkcje:
- Pętla menu (powrót po każdej zmianie, wyjście przez [8]/Ctrl+C)
- Fallback: auto-przełączanie przy HTTP 429 / timeout
- Smart routing: coder_model dla zadań kodu, vision_model dla obrazów
"""

from __future__ import annotations

import re
import time
from typing import Optional

import requests

from core.config import CONFIG_FILE, save_config
from ui_layer.ui import UI, Colors

# ─── Stałe ───────────────────────────────────────────────────────────────────

# UWAGA: NIE dodawaj tu rozszerzeń plików (.sh, .py itd.)!
# Wzmianka o pliku w user_input oznacza EDYCJĘ przez agenta — to wymaga głównego
# (mocnego) modelu który rozumie format JSON akcji. Coder model (zwykle mały, 7b)
# powinien być używany tylko gdy użytkownik TWORZY nowy kod od zera.
_CODE_PATTERNS = re.compile(
    r"\b(napisz|stwórz|utwórz|zrefaktoruj|zoptymalizuj|"
    r"debug|przetestuj|funkcj[aę]|klas[aę]|metod[aę]|"
    r"napisz.*skrypt|napisz.*kod|nowy.*skrypt|nowy.*kod|"
    r"python script|javascript|typescript|rust code|bash script|"
    r"def |class |import |return )\b",
    re.IGNORECASE,
)

# Wzorce wskazujące na zadania z obrazami
_VISION_PATTERNS = re.compile(
    r"\b(obraz|obrazek|zdjęcie|zdjęcia|foto|fotografia|screenshot|screen|"
    r"obrazu|zdjęcia|plik png|plik jpg|plik jpeg|plik webp|plik gif|"
    r"opisz|przeanalizuj|co widać|co jest na|rozpoznaj|odczytaj z|"
    r"image|picture|photo|vision|visual|\.png|\.jpg|\.jpeg|\.webp|\.gif|\.bmp)\b",
    re.IGNORECASE,
)

_CODER_HINTS  = ["coder", "code", "starcoder", "codellama", "deepseek-coder", "qwen2.5-coder"]
_EMBED_HINTS  = ["embed", "embedding", "bge", "minilm", "e5-"]
_VISION_HINTS = ["vl", "vision", "visual", "llava", "minicpm", "qwen3-vl", "qwen2-vl", "bakllava", "moondream"]
_CLOUD_SUFFIX = ":cloud"


# ─── ModelManager ────────────────────────────────────────────────────────────

class ModelManager:
    def __init__(self, config: dict):
        self.config   = config
        self.base_url = f"http://{config['ollama_host']}:{config['ollama_port']}"

    def get_available_models(self) -> list[dict]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            return r.json().get("models", [])
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Nie można połączyć się z Ollamą: {e}")

    def get_current_models(self) -> dict[str, str]:
        return {
            "chat":     self.config.get("chat_model",     ""),
            "embed":    self.config.get("embed_model",    ""),
            "fallback": self.config.get("fallback_model", ""),
            "coder":    self.config.get("coder_model",    ""),
            "vision":   self.config.get("vision_model",   ""),
        }

    def set_chat_model(self, name: str):
        self.config["chat_model"] = name;    save_config(self.config)

    def set_embed_model(self, name: str):
        self.config["embed_model"] = name;   save_config(self.config)

    def set_fallback_model(self, name: str):
        self.config["fallback_model"] = name; save_config(self.config)

    def set_coder_model(self, name: str):
        self.config["coder_model"] = name;   save_config(self.config)

    def set_vision_model(self, name: str):
        self.config["vision_model"] = name;  save_config(self.config)

    def clear_fallback_model(self):
        self.config.pop("fallback_model", None); save_config(self.config)

    def clear_coder_model(self):
        self.config.pop("coder_model", None);    save_config(self.config)

    def clear_vision_model(self):
        self.config.pop("vision_model", None);   save_config(self.config)

    @staticmethod
    def format_size(size_bytes: int) -> str:
        if size_bytes >= 1024 ** 3:
            return f"{size_bytes / 1024**3:.1f} GB"
        return f"{size_bytes / 1024**2:.0f} MB"

    @staticmethod
    def is_cloud(name: str) -> bool:
        return _CLOUD_SUFFIX in name

    @staticmethod
    def is_coder(name: str) -> bool:
        return any(h in name.lower() for h in _CODER_HINTS)

    @staticmethod
    def is_embed(name: str) -> bool:
        return any(h in name.lower() for h in _EMBED_HINTS)

    @staticmethod
    def is_vision(name: str) -> bool:
        return any(h in name.lower() for h in _VISION_HINTS)


# ─── ModelRouter ─────────────────────────────────────────────────────────────

class ModelRouter:
    """
    Wybiera model dla danego zapytania.

    Priorytet:
      1. Fallback aktywny (po HTTP 429 / timeout) → fallback_model
      2. Obraz w zapytaniu + vision_model ustawiony → vision_model
      3. Zadanie kodowania + coder_model ustawiony → coder_model
      4. Normalnie → chat_model
    """

    def __init__(self, config: dict):
        self.config          = config
        self._in_fallback    = False
        self._fallback_until = 0.0

    @property
    def chat_model(self) -> str:
        return self.config.get("chat_model", "")

    @property
    def fallback_model(self) -> Optional[str]:
        return self.config.get("fallback_model") or None

    @property
    def coder_model(self) -> Optional[str]:
        return self.config.get("coder_model") or None

    @property
    def vision_model(self) -> Optional[str]:
        return self.config.get("vision_model") or None

    def select_model(self, user_input: str = "", has_image: bool = False) -> tuple[str, str]:
        """
        Zwraca (model_name, powód_wyboru).

        Args:
            user_input: tekst zapytania użytkownika
            has_image:  True jeśli do wiadomości dołączony jest obraz
        """
        # 1. Fallback aktywny?
        if self._in_fallback and time.time() < self._fallback_until:
            if self.fallback_model:
                mins = max(0, int((self._fallback_until - time.time()) / 60))
                return self.fallback_model, f"fallback (rate limit, pozostało {mins} min)"
        elif self._in_fallback:
            self._in_fallback    = False
            self._fallback_until = 0.0

        # 2. Obraz – explicit (plik dołączony) lub frazy w tekście
        vision = self.vision_model
        if vision:
            if has_image or (user_input and _VISION_PATTERNS.search(user_input)):
                return vision, f"smart routing (vision) → {vision}"

        # 3. Kodowanie
        coder = self.coder_model
        if coder and user_input and _CODE_PATTERNS.search(user_input):
            return coder, f"smart routing (kod) → {coder}"

        # 4. Domyślny
        return self.chat_model, "chat_model"

    def activate_fallback(self, duration_minutes: int = 60):
        self._in_fallback    = True
        self._fallback_until = time.time() + duration_minutes * 60

    def deactivate_fallback(self):
        self._in_fallback    = False
        self._fallback_until = 0.0

    @property
    def is_in_fallback(self) -> bool:
        return self._in_fallback and time.time() < self._fallback_until

    def fallback_remaining_minutes(self) -> int:
        if not self.is_in_fallback:
            return 0
        return max(0, int((self._fallback_until - time.time()) / 60))


# ─── Interaktywne menu (pętla) ───────────────────────────────────────────────

def interactive_model_selection(config: dict):
    """ai model – menu z pętlą. Wraca po każdej zmianie, wychodzi przez [8] lub Ctrl+C."""
    ui      = UI(quiet=False, verbose=False, config=config)
    manager = ModelManager(config)

    # Pobierz modele raz
    try:
        ui.spinner_start("Pobieranie listy modeli...")
        models = manager.get_available_models()
        ui.spinner_stop()
    except KeyboardInterrupt:
        ui.spinner_stop()
        print()
        ui.status("Wychodzę")
        return
    except ConnectionError as e:
        ui.spinner_stop()
        ui.error(str(e))
        return

    if not models:
        ui.warning("Brak dostępnych modeli w Ollama")
        return

    # ── Pętla menu ───────────────────────────────────────────────────────────
    while True:
        # Odśwież current z config (config jest mutowalny – zmiany są widoczne)
        current = manager.get_current_models()

        # Wyczyść ekran (tylko nagłówek)
        print()
        ui.section("Zarządzanie modelami Ollama")
        _print_current(current, manager)

        print(f"{Colors.BOLD}Co chcesz zmienić?{Colors.RESET}\n")
        print(f"  [1] Model czatu          {Colors.GRAY}(główny model AI){Colors.RESET}")
        print(f"  [2] Model embeddingów    {Colors.GRAY}(semantic search / RAG){Colors.RESET}")
        print(f"  [3] Model fallback       {Colors.GRAY}(przy błędzie cloud: 429/timeout){Colors.RESET}")
        print(f"  [4] Model kodowania      {Colors.GRAY}(smart routing dla zadań kodu){Colors.RESET}")
        print(f"  [5] Model vision         {Colors.GRAY}(smart routing dla obrazów){Colors.RESET}")
        print(f"  [6] Wyczyść model fallback")
        print(f"  [7] Wyczyść model kodowania")
        print(f"  [8] Wyczyść model vision")
        print(f"  [9] {Colors.GRAY}Wyjdź{Colors.RESET}")
        print()

        try:
            choice = input(f"{Colors.BOLD}Wybór [1-9]: {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            ui.status("Wychodzę")
            break

        if choice == "1":
            _pick(ui, manager, models, current, "chat")
        elif choice == "2":
            _pick(ui, manager, models, current, "embed")
        elif choice == "3":
            _pick(ui, manager, models, current, "fallback")
        elif choice == "4":
            _pick(ui, manager, models, current, "coder")
        elif choice == "5":
            _pick(ui, manager, models, current, "vision")
        elif choice == "6":
            manager.clear_fallback_model()
            ui.success("Model fallback usunięty")
        elif choice == "7":
            manager.clear_coder_model()
            ui.success("Model kodowania usunięty")
        elif choice == "8":
            manager.clear_vision_model()
            ui.success("Model vision usunięty")
        elif choice == "9" or choice.lower() in ("q", "exit", "quit", ""):
            ui.status("Wychodzę")
            break
        else:
            ui.warning("Nieprawidłowy wybór – wpisz 1-9")

        # Mała pauza żeby użytkownik zdążył przeczytać komunikat
        print()
        input(f"{Colors.GRAY}  [Enter aby wrócić do menu]{Colors.RESET}")


# ─── Wyświetlanie stanu ───────────────────────────────────────────────────────

def _print_current(current: dict, manager: ModelManager):
    def _row(label: str, name: str):
        if not name:
            print(f"  {Colors.GRAY}{label:<28} (nie ustawiony){Colors.RESET}")
            return
        tags = []
        if manager.is_cloud(name):  tags.append(f"{Colors.YELLOW}cloud{Colors.RESET}")
        if manager.is_coder(name):  tags.append(f"{Colors.CYAN}coder{Colors.RESET}")
        if manager.is_embed(name):  tags.append(f"{Colors.BLUE}embed{Colors.RESET}")
        if manager.is_vision(name): tags.append(f"{Colors.MAGENTA}vision{Colors.RESET}" if hasattr(Colors, 'MAGENTA') else f"\033[35mvision\033[0m")
        tag_str = f"  [{', '.join(tags)}]" if tags else ""
        print(f"  {Colors.GREEN}▶{Colors.RESET} {label:<28} {name}{tag_str}")

    print()
    _row("Model czatu:",             current["chat"])
    _row("Model embeddingów:",       current["embed"])
    _row("Model fallback:",          current["fallback"])
    _row("Model kodowania (smart):", current["coder"])
    _row("Model vision (smart):",    current["vision"])
    print()

    notes = []
    if current["coder"]:
        notes.append(f"  {Colors.CYAN}ℹ Smart routing:{Colors.RESET} zadania kodu → {current['coder']}, pozostałe → {current['chat']}")
    if current["vision"]:
        notes.append(f"  \033[35mℹ Smart routing:\033[0m obrazy/vision → {current['vision']}, pozostałe → {current['chat']}")
    if current["fallback"]:
        notes.append(f"  {Colors.YELLOW}ℹ Fallback:{Colors.RESET} przy HTTP 429/timeout → {current['fallback']} (auto, na 60 min)")
    for n in notes:
        print(n)
    if notes:
        print()


# ─── Wybór modelu z listy ────────────────────────────────────────────────────

def _pick(ui: UI, manager: ModelManager, models: list[dict], current: dict, role: str):
    titles = {
        "chat":     "Wybór modelu czatu",
        "embed":    "Wybór modelu embeddingów",
        "fallback": "Wybór modelu fallback",
        "coder":    "Wybór modelu kodowania (smart routing)",
        "vision":   "Wybór modelu vision (smart routing)",
    }
    hints = {
        "fallback": (
            f"  {Colors.YELLOW}ℹ{Colors.RESET}  Wybierz LOKALNY model (bez :cloud).\n"
            f"     Używany automatycznie gdy cloud zwróci HTTP 429 lub timeout.\n"
            f"     Po 60 min agent wraca do głównego modelu.\n"
        ),
        "coder": (
            f"  {Colors.CYAN}ℹ{Colors.RESET}  Model używany dla zadań zawierających kod/skrypty.\n"
            f"     AI wykrywa słowa-klucze: 'napisz', 'stwórz funkcję', '.py', itp.\n"
            f"     Zostaw nie ustawiony żeby zawsze używać głównego modelu.\n"
        ),
        "vision": (
            f"  \033[35mℹ\033[0m  Model używany gdy wykryto obraz lub frazy związane z vision.\n"
            f"     Wykrywa: dołączone pliki .png/.jpg, słowa 'obraz', 'zdjęcie',\n"
            f"     'opisz', 'co widać na', 'przeanalizuj obraz', itp.\n"
            f"     Twoje modele vision: qwen3-vl:8b\n"
        ),
    }

    ui.section(titles[role])
    if role in hints:
        print(hints[role])

    # Filtrowanie
    if role == "embed":
        display = [m for m in models if manager.is_embed(m["name"])] or models
    elif role == "fallback":
        display = [m for m in models if not manager.is_cloud(m["name"])] or models
    elif role == "vision":
        # Pokaż vision modele na górze, resztę poniżej
        vision_models = [m for m in models if manager.is_vision(m["name"])]
        other_models  = [m for m in models if not manager.is_vision(m["name"])]
        display = vision_models + other_models
    else:
        display = models

    current_name = current.get(role, "") or ""
    print(f"{Colors.BOLD}Dostępne modele:{Colors.RESET}\n")

    for i, m in enumerate(display, 1):
        name = m["name"]
        size = manager.format_size(m["size"]) if m.get("size") else "cloud"
        tags = []
        if manager.is_cloud(name):  tags.append(f"{Colors.YELLOW}cloud{Colors.RESET}")
        if manager.is_coder(name):  tags.append(f"{Colors.CYAN}coder{Colors.RESET}")
        if manager.is_embed(name):  tags.append(f"{Colors.BLUE}embed{Colors.RESET}")
        if manager.is_vision(name): tags.append("\033[35mvision\033[0m")
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        marker  = f"{Colors.GREEN}▶{Colors.RESET}" if name == current_name else " "
        suffix  = f"  {Colors.GREEN}(obecny){Colors.RESET}" if name == current_name else ""
        print(f"  {marker} [{i:2}] {name:<52} {size:>8}{tag_str}{suffix}")

    print()
    try:
        raw = input(f"{Colors.BOLD}Numer (Enter = anuluj): {Colors.RESET}").strip()
        if not raw:
            ui.status("Anulowano")
            return
        idx = int(raw) - 1
        if not (0 <= idx < len(display)):
            ui.error(f"Zły numer (1–{len(display)})")
            return
        chosen = display[idx]["name"]
    except (ValueError, KeyboardInterrupt):
        print()
        ui.status("Anulowano")
        return

    if role == "chat":
        manager.set_chat_model(chosen)
        ui.success(f"Model czatu → {chosen}")
    elif role == "embed":
        manager.set_embed_model(chosen)
        ui.success(f"Model embeddingów → {chosen}")
        print(f"  {Colors.YELLOW}Pamiętaj:{Colors.RESET} przeindeksuj bazę wiedzy → ai --index")
    elif role == "fallback":
        manager.set_fallback_model(chosen)
        ui.success(f"Model fallback → {chosen}")
        if manager.is_cloud(chosen):
            ui.warning("Wybrany model to CLOUD – fallback nie zadziała przy rate limitach!")
    elif role == "coder":
        manager.set_coder_model(chosen)
        ui.success(f"Model kodowania → {chosen}")
    elif role == "vision":
        manager.set_vision_model(chosen)
        ui.success(f"Model vision → {chosen}")
        if not manager.is_vision(chosen):
            ui.warning("Ten model może nie obsługiwać obrazów – upewnij się że to model VL/vision.")

    ui.verbose(f"Zapisano: {CONFIG_FILE}")
