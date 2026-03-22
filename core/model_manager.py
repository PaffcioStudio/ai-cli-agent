"""
model_manager.py – zarządzanie modelami Ollama.

Refaktoryzacja: dane katalogowe i stałe przeniesione do model_catalog.py.
Ten plik zawiera: ModelManager, ModelRouter, interactive_model_selection + UI helpers.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from typing import Optional

import requests

from core.config import CONFIG_FILE, save_config
from core.model_catalog import (
    get_system_ram_gb, get_gpu_vram_gb, get_model_recommendations,
    estimate_model_ram,
    _CODE_PATTERNS, _VISION_PATTERNS,
    _CODER_HINTS, _EMBED_HINTS, _VISION_HINTS, _CLOUD_SUFFIX,
    _CUSTOM_NAMESPACE_RE,
)
from ui_layer.ui import UI, Colors

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
        # fallback_models to teraz lista (kaskada), fallback_model to legacy string
        fb_list  = self.config.get("fallback_models", [])
        fb_legacy = self.config.get("fallback_model", "")
        # Wyświetl: pierwszą pozycję z listy lub legacy
        fb_display = fb_list[0] if fb_list else fb_legacy
        return {
            "chat":             self.config.get("chat_model",     ""),
            "embed":            self.config.get("embed_model",    ""),
            "fallback":         fb_display,
            "fallback_cascade": fb_list,
            "coder":            self.config.get("coder_model",    ""),
            "vision":           self.config.get("vision_model",   ""),
        }

    def set_chat_model(self, name: str):
        self.config["chat_model"] = name;    save_config(self.config)

    def set_embed_model(self, name: str):
        self.config["embed_model"] = name;   save_config(self.config)

    def set_fallback_model(self, name: str):
        """Dodaje model na koniec listy fallback (kaskada)."""
        existing = self.config.get("fallback_models", [])
        # Usuń duplikaty, dodaj na koniec
        existing = [m for m in existing if m != name]
        existing.append(name)
        self.config["fallback_models"] = existing
        # Zachowaj compat z legacy
        self.config["fallback_model"] = existing[0]
        save_config(self.config)

    def set_fallback_cascade(self, models: list[str]):
        """Ustawia całą listę kaskady fallback."""
        self.config["fallback_models"] = models
        self.config["fallback_model"]  = models[0] if models else ""
        save_config(self.config)

    def remove_fallback_model(self, name: str):
        """Usuwa jeden model z kaskady."""
        existing = self.config.get("fallback_models", [])
        existing = [m for m in existing if m != name]
        self.config["fallback_models"] = existing
        self.config["fallback_model"]  = existing[0] if existing else ""
        save_config(self.config)

    def set_coder_model(self, name: str):
        self.config["coder_model"] = name;   save_config(self.config)

    def set_vision_model(self, name: str):
        self.config["vision_model"] = name;  save_config(self.config)

    def clear_fallback_model(self):
        self.config.pop("fallback_model", None)
        self.config.pop("fallback_models", None)
        save_config(self.config)

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

    @staticmethod
    def is_unknown(name: str) -> bool:
        """
        Zwraca True dla modeli z niestandardowym namespace (np. x/z-..., ahmadwaqar/...)
        które NIE pasują do żadnej rozpoznanej kategorii.
        Takie modele są pomijane w grupowym benchmarku.
        """
        if not _CUSTOM_NAMESPACE_RE.match(name):
            return False
        name_lower = name.lower()
        # Jeśli namespace-owy model ma rozpoznawalne hinty – NIE jest "unknown"
        if any(h in name_lower for h in _EMBED_HINTS):
            return False
        if any(h in name_lower for h in _VISION_HINTS):
            return False
        if any(h in name_lower for h in _CODER_HINTS):
            return False
        if _CLOUD_SUFFIX in name:
            return False
        return True

    # ─── Install z progress barem ───────────────────────────────────────────

    def install_model(self, model_name: str) -> bool:
        """
        Pobiera model przez `ollama pull` z progress barem.
        Przed pobraniem sprawdza dostępny RAM i ostrzega jeśli może być za mało.
        Zwraca True jeśli sukces.
        """
        # Sprawdź RAM
        ram_gb  = get_system_ram_gb()
        vram_gb = get_gpu_vram_gb()
        if ram_gb > 0:
            # Szacuj wymagany RAM na podstawie nazwy (prosta heurystyka)
            estimated_gb = _estimate_model_ram(model_name)
            if estimated_gb > 0 and estimated_gb > ram_gb * 0.85:
                print(f"\n  {Colors.YELLOW}⚠ Uwaga:{Colors.RESET} model ~{estimated_gb:.0f} GB "
                      f"RAM, masz {ram_gb:.1f} GB – może być za ciasno.")
                try:
                    ans = input("  Kontynuować mimo to? [t/N]: ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    print()
                    return False
                if ans not in ("t", "tak", "y", "yes"):
                    return False

        print(f"\n  Pobieranie {Colors.BOLD}{model_name}{Colors.RESET}...\n")
        try:
            proc = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            print(f"  {Colors.RED}✗ Nie znaleziono komendy 'ollama' w PATH{Colors.RESET}")
            return False

        last_line = ""
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                # Ollama wypisuje postęp jako "pulling sha256:xxx  XX% ▕██████▏ XXX MB/s"
                # Nadpisz tę samą linię
                sys.stdout.write(f"\r  {line[:100]:<100}")
                sys.stdout.flush()
                last_line = line
        except KeyboardInterrupt:
            proc.terminate()
            print(f"\n\n  {Colors.YELLOW}⚠ Przerwano przez użytkownika{Colors.RESET}")
            return False

        proc.wait()
        print()  # nowa linia po progress
        if proc.returncode == 0:
            print(f"  {Colors.GREEN}✓ Model {model_name} zainstalowany pomyślnie{Colors.RESET}")
            return True
        else:
            print(f"  {Colors.RED}✗ Błąd pobierania (kod {proc.returncode}){Colors.RESET}")
            if last_line:
                print(f"  {Colors.GRAY}{last_line}{Colors.RESET}")
            return False

    # ─── Benchmark ──────────────────────────────────────────────────────────

    def _detect_model_type(self, name: str) -> str:
        """Zwraca typ modelu: 'embed', 'cloud', 'vision', 'chat', 'unknown'."""
        if self.is_embed(name):   return "embed"
        if self.is_cloud(name):   return "cloud"
        if self.is_vision(name):  return "vision"
        if self.is_unknown(name): return "unknown"
        return "chat"

    def benchmark_model(self, model_name: str) -> dict:
        """
        Mierzy wydajność modelu generatywnego:
        - TTFT (Time To First Token) w ms
        - tok/s (throughput)
        Zwraca dict z wynikami lub {"error": "...", "skip": True}.
        """
        mtype = self._detect_model_type(model_name)

        # Modele których nie można benchmarkować przez /api/generate
        if mtype == "embed":
            return {"error": f"Model embeddingów – benchmark generacji niedostępny", "skip": True, "model": model_name}
        if mtype == "cloud":
            return {"error": f"Model cloud – benchmark lokalny niedostępny", "skip": True, "model": model_name}
        if mtype == "unknown":
            return {"error": f"Model z niestandardowym namespace – typ nieznany, pomijam", "skip": True, "model": model_name}

        prompt = "Napisz jedno zdanie po polsku o programowaniu."
        url    = f"{self.base_url}/api/generate"

        print(f"\n  Benchmarkowanie {Colors.BOLD}{model_name}{Colors.RESET} [{mtype}]...")
        print(f"  {Colors.GRAY}Prompt: \"{prompt}\"{Colors.RESET}\n")

        # Warmup
        print(f"  {Colors.GRAY}Rozgrzewka (ładowanie modelu)...{Colors.RESET}", end="", flush=True)
        try:
            requests.post(url, json={"model": model_name, "prompt": "hi", "stream": False}, timeout=120)
        except Exception:
            pass
        print(" gotowe")

        # Właściwy pomiar
        t_start = time.perf_counter()
        t_first = None
        tokens  = 0
        output  = []

        try:
            resp = requests.post(
                url,
                json={"model": model_name, "prompt": prompt, "stream": True},
                stream=True,
                timeout=120,
            )
            resp.raise_for_status()

            import json as _json
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                try:
                    chunk = _json.loads(raw_line)
                except Exception:
                    continue
                token = chunk.get("response", "")
                if token:
                    if t_first is None:
                        t_first = time.perf_counter()
                    tokens += 1
                    output.append(token)
                if chunk.get("done"):
                    break

        except requests.exceptions.Timeout:
            return {"error": "Timeout – model nie odpowiedział w 120s", "model": model_name}
        except requests.exceptions.ConnectionError as e:
            return {"error": f"Brak połączenia z Ollamą: {e}", "model": model_name}
        except Exception as e:
            return {"error": str(e), "model": model_name}

        t_end = time.perf_counter()

        if t_first is None:
            return {"error": "Model nie wygenerował żadnej odpowiedzi (sprawdź czy obsługuje /api/generate)", "model": model_name}

        ttft_ms = (t_first - t_start) * 1000
        total_s = t_end - t_start
        tps     = tokens / total_s if total_s > 0 else 0

        return {
            "model":    model_name,
            "type":     mtype,
            "ttft_ms":  round(ttft_ms),
            "tps":      round(tps, 1),
            "tokens":   tokens,
            "total_s":  round(total_s, 2),
            "response": "".join(output).strip(),
        }

    def benchmark_all(self, models: list[dict]) -> list[dict]:
        """
        Benchmarkuje wszystkie lokalne, nie-embeddingowe modele.
        Zwraca posortowaną listę wyników.
        """
        candidates = [
            m for m in models
            if not self.is_cloud(m["name"])
            and not self.is_embed(m["name"])
            and not self.is_unknown(m["name"])
            and m.get("size", 0) > 0
        ]
        results = []
        total   = len(candidates)

        print(f"\n  Grupowy benchmark: {total} modeli lokalnych\n")

        for i, m in enumerate(candidates, 1):
            name = m["name"]
            size = self.format_size(m["size"]) if m.get("size") else "?"
            print(f"  [{i}/{total}] {Colors.BOLD}{name}{Colors.RESET}  {Colors.GRAY}({size}){Colors.RESET}")
            result = self.benchmark_model(name)
            results.append(result)
            if "error" in result and not result.get("skip"):
                print(f"  {Colors.RED}✗ {result['error']}{Colors.RESET}")
            elif result.get("skip"):
                print(f"  {Colors.GRAY}↷ Pominięto: {result['error']}{Colors.RESET}")
            else:
                tps_color = Colors.GREEN if result["tps"] >= 20 else (Colors.YELLOW if result["tps"] >= 8 else Colors.RED)
                print(f"  {tps_color}▶{Colors.RESET} TTFT: {result['ttft_ms']} ms  |  {tps_color}{result['tps']} tok/s{Colors.RESET}")
            print()

        # Posortuj wg tok/s (najszybszy na górze), błędy na końcu
        ok      = [r for r in results if "error" not in r]
        errors  = [r for r in results if "error" in r and not r.get("skip")]
        skipped = [r for r in results if r.get("skip")]
        return sorted(ok, key=lambda r: r["tps"], reverse=True) + errors + skipped



# Backward-compat alias
_estimate_model_ram = estimate_model_ram

class ModelRouter:
    """
    Wybiera model dla danego zapytania.

    Priorytet:
      1. Fallback aktywny (po HTTP 429 / timeout) → kaskada fallback_models[idx]
      2. Obraz w zapytaniu + vision_model ustawiony → vision_model
      3. Zadanie kodowania + coder_model ustawiony → coder_model
      4. Normalnie → chat_model
    """

    def __init__(self, config: dict):
        self.config            = config
        self._in_fallback      = False
        self._fallback_until   = 0.0
        self._fallback_idx     = 0   # aktualny indeks w kaskadzie

    @property
    def chat_model(self) -> str:
        return self.config.get("chat_model", "")

    @property
    def fallback_models(self) -> list[str]:
        """Lista modeli fallback (kaskada). Kompatybilna z legacy fallback_model."""
        cascade = self.config.get("fallback_models", [])
        if cascade:
            return cascade
        legacy = self.config.get("fallback_model", "")
        return [legacy] if legacy else []

    @property
    def fallback_model(self) -> Optional[str]:
        """Aktualnie aktywny model fallback (z kaskady)."""
        cascade = self.fallback_models
        if not cascade:
            return None
        idx = min(self._fallback_idx, len(cascade) - 1)
        return cascade[idx]

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
            fb = self.fallback_model
            if fb:
                cascade = self.fallback_models
                mins    = max(0, int((self._fallback_until - time.time()) / 60))
                pos_str = f"{self._fallback_idx + 1}/{len(cascade)}" if len(cascade) > 1 else ""
                suffix  = f" [{pos_str}]" if pos_str else ""
                return fb, f"fallback{suffix} (rate limit, pozostało {mins} min)"
        elif self._in_fallback:
            self._in_fallback  = False
            self._fallback_idx = 0

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

    def activate_fallback(self, duration_minutes: int = 60, advance_cascade: bool = False):
        """
        Aktywuje tryb fallback.
        advance_cascade=True przesuwa indeks do następnego modelu w kaskadzie.
        """
        if advance_cascade:
            cascade = self.fallback_models
            if cascade and self._fallback_idx < len(cascade) - 1:
                self._fallback_idx += 1
        self._in_fallback    = True
        self._fallback_until = time.time() + duration_minutes * 60

    def next_fallback(self) -> Optional[str]:
        """
        Przesuwa do następnego modelu w kaskadzie.
        Zwraca nowy model lub None jeśli koniec kaskady.
        """
        cascade = self.fallback_models
        if not cascade:
            return None
        if self._fallback_idx < len(cascade) - 1:
            self._fallback_idx += 1
            return cascade[self._fallback_idx]
        return None  # wyczerpano kaskadę

    def deactivate_fallback(self):
        self._in_fallback  = False
        self._fallback_idx = 0

    @property
    def is_in_fallback(self) -> bool:
        return self._in_fallback and time.time() < self._fallback_until

    def fallback_remaining_minutes(self) -> int:
        if not self.is_in_fallback:
            return 0
        return max(0, int((self._fallback_until - time.time()) / 60))


# ─── Interaktywne menu (pętla) ───────────────────────────────────────────────

def interactive_model_selection(config: dict):
    """ai model – menu z pętlą. Wraca po każdej zmianie, wychodzi przez [0] lub Ctrl+C."""
    ui      = UI(quiet=False, verbose=False, config=config)
    manager = ModelManager(config)

    # Pobierz modele raz (może być None jeśli offline)
    models = []
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
        ui.warning(f"Ollama niedostępna: {e}")
        ui.status("Kontynuuję w trybie offline (tylko rekomendacje i konfiguracja)")

    # ── Pętla menu ───────────────────────────────────────────────────────────
    while True:
        current = manager.get_current_models()

        print()
        ui.section("Zarządzanie modelami Ollama")
        _print_current(current, manager)

        print(f"{Colors.BOLD}Co chcesz zrobić?{Colors.RESET}\n")
        print(f"  [1] Ustaw model czatu          {Colors.GRAY}(główny model AI){Colors.RESET}")
        print(f"  [2] Ustaw model embeddingów    {Colors.GRAY}(semantic search / RAG){Colors.RESET}")
        print(f"  [3] Zarządzaj kaskadą fallback {Colors.GRAY}(lista modeli przy 429/timeout){Colors.RESET}")
        print(f"  [4] Ustaw model kodowania      {Colors.GRAY}(smart routing dla kodu){Colors.RESET}")
        print(f"  [5] Ustaw model vision         {Colors.GRAY}(smart routing dla obrazów){Colors.RESET}")
        print(f"  ─")
        print(f"  [6] {Colors.CYAN}Pobierz model{Colors.RESET}              {Colors.GRAY}(ollama pull z progress barem){Colors.RESET}")
        print(f"  [7] {Colors.CYAN}Benchmark modelu{Colors.RESET}           {Colors.GRAY}(pomiar TTFT i tok/s){Colors.RESET}")
        print(f"  [8] {Colors.CYAN}Rekomendacje wg sprzętu{Colors.RESET}    {Colors.GRAY}(co pasuje do Twojego RAM/VRAM){Colors.RESET}")
        print(f"  ─")
        print(f"  [9] Wyczyść model fallback")
        print(f"  [0] {Colors.GRAY}Wyjdź{Colors.RESET}")
        print()

        try:
            choice = input(f"{Colors.BOLD}Wybór [0-9]: {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            ui.status("Wychodzę")
            break

        if choice == "1":
            if models:
                _pick(ui, manager, models, current, "chat")
            else:
                ui.warning("Ollama offline – nie można pobrać listy modeli")
        elif choice == "2":
            if models:
                _pick(ui, manager, models, current, "embed")
            else:
                ui.warning("Ollama offline – nie można pobrać listy modeli")
        elif choice == "3":
            _manage_fallback_cascade(ui, manager, models, current)
        elif choice == "4":
            if models:
                _pick(ui, manager, models, current, "coder")
            else:
                ui.warning("Ollama offline – nie można pobrać listy modeli")
        elif choice == "5":
            if models:
                _pick(ui, manager, models, current, "vision")
            else:
                ui.warning("Ollama offline – nie można pobrać listy modeli")
        elif choice == "6":
            _do_install(ui, manager)
            # Odśwież listę modeli po instalacji
            try:
                models = manager.get_available_models()
            except Exception:
                pass
        elif choice == "7":
            _do_benchmark(ui, manager, models)
        elif choice == "8":
            _show_recommendations(ui)
        elif choice == "9":
            manager.clear_fallback_model()
            ui.success("Kaskada fallback wyczyszczona")
        elif choice == "0" or choice.lower() in ("q", "exit", "quit", ""):
            ui.status("Wychodzę")
            break
        else:
            ui.warning("Nieprawidłowy wybór – wpisz 0-9")

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
        if manager.is_vision(name): tags.append(f"\033[35mvision\033[0m")
        tag_str = f"  [{', '.join(tags)}]" if tags else ""
        print(f"  {Colors.GREEN}▶{Colors.RESET} {label:<28} {name}{tag_str}")

    print()
    _row("Model czatu:",             current["chat"])
    _row("Model embeddingów:",       current["embed"])

    # Kaskada fallback
    cascade = current.get("fallback_cascade", [])
    if cascade:
        print(f"  {Colors.GREEN}▶{Colors.RESET} {'Fallback (kaskada):':<28}", end="")
        for i, m in enumerate(cascade):
            sep = " → " if i > 0 else ""
            print(f"{sep}{m}", end="")
        print()
    else:
        _row("Model fallback:",          current["fallback"])

    _row("Model kodowania (smart):", current["coder"])
    _row("Model vision (smart):",    current["vision"])
    print()

    notes = []
    if current["coder"]:
        notes.append(f"  {Colors.CYAN}ℹ Smart routing:{Colors.RESET} zadania kodu → {current['coder']}, pozostałe → {current['chat']}")
    if current["vision"]:
        notes.append(f"  \033[35mℹ Smart routing:\033[0m obrazy/vision → {current['vision']}, pozostałe → {current['chat']}")
    if cascade:
        chain = " → ".join(cascade)
        notes.append(f"  {Colors.YELLOW}ℹ Fallback kaskada:{Colors.RESET} {chain}")
    elif current["fallback"]:
        notes.append(f"  {Colors.YELLOW}ℹ Fallback:{Colors.RESET} przy HTTP 429/timeout → {current['fallback']} (auto, na 60 min)")
    for n in notes:
        print(n)
    if notes:
        print()


# ─── Zarządzanie kaskadą fallback ────────────────────────────────────────────

def _manage_fallback_cascade(ui: UI, manager: ModelManager, models: list[dict], current: dict):
    """Podmenu zarządzania kaskadą fallback."""
    while True:
        cascade = manager.config.get("fallback_models", [])
        print()
        ui.section("Kaskada fallback")
        if cascade:
            print(f"  {Colors.BOLD}Aktualna kolejność:{Colors.RESET}")
            for i, m in enumerate(cascade):
                print(f"  [{i + 1}] {m}")
        else:
            print(f"  {Colors.GRAY}(pusta – brak fallback){Colors.RESET}")
        print()
        print(f"  [a] Dodaj model na koniec kaskady")
        print(f"  [r] Usuń model z kaskady")
        print(f"  [c] Wyczyść całą kaskadę")
        print(f"  [0] Wróć")
        print()
        try:
            ch = input(f"  Wybór: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if ch == "a":
            if models:
                local = [m for m in models if not manager.is_cloud(m["name"])] or models
                print(f"\n  {Colors.BOLD}Wybierz model do dodania:{Colors.RESET}\n")
                for i, m in enumerate(local, 1):
                    size = manager.format_size(m["size"]) if m.get("size") else "cloud"
                    already = f"  {Colors.GREEN}(już w kaskadzie){Colors.RESET}" if m["name"] in cascade else ""
                    print(f"    [{i:2}] {m['name']:<50} {size:>8}{already}")
                print()
                try:
                    raw = input("  Numer (Enter = anuluj): ").strip()
                    if raw and raw.isdigit():
                        idx = int(raw) - 1
                        if 0 <= idx < len(local):
                            manager.set_fallback_model(local[idx]["name"])
                            ui.success(f"Dodano do kaskady: {local[idx]['name']}")
                except (ValueError, KeyboardInterrupt):
                    pass
            else:
                try:
                    name = input("  Nazwa modelu: ").strip()
                    if name:
                        manager.set_fallback_model(name)
                        ui.success(f"Dodano: {name}")
                except (KeyboardInterrupt, EOFError):
                    pass

        elif ch == "r":
            if not cascade:
                ui.warning("Kaskada jest pusta")
            else:
                try:
                    raw = input("  Numer modelu do usunięcia: ").strip()
                    if raw.isdigit():
                        idx = int(raw) - 1
                        if 0 <= idx < len(cascade):
                            manager.remove_fallback_model(cascade[idx])
                            ui.success(f"Usunięto: {cascade[idx]}")
                except (ValueError, KeyboardInterrupt):
                    pass

        elif ch == "c":
            manager.clear_fallback_model()
            ui.success("Kaskada wyczyszczona")
        elif ch == "0" or ch == "":
            break


# ─── Install z progress barem ────────────────────────────────────────────────

def _do_install(ui: UI, manager: ModelManager):
    """Interaktywne pobieranie modelu."""
    print()
    ui.section("Pobierz model (ollama pull)")

    # Pokaż sugestie z katalogu
    ram_gb  = get_system_ram_gb()
    vram_gb = get_gpu_vram_gb()
    recs    = get_model_recommendations(ram_gb, vram_gb)

    if recs:
        print(f"  {Colors.GRAY}Pasujące modele dla Twojego sprzętu "
              f"(RAM: {ram_gb:.0f} GB, VRAM: {vram_gb:.0f} GB):{Colors.RESET}\n")
        for r in recs[-8:]:  # ostatnie 8 = największe pasujące
            tags_str = ", ".join(r["tags"])
            print(f"    {Colors.CYAN}{r['name']:<40}{Colors.RESET}  {Colors.GRAY}{r['desc']}  [{tags_str}]{Colors.RESET}")
        print()

    try:
        name = input(f"  {Colors.BOLD}Nazwa modelu do pobrania (Enter = anuluj): {Colors.RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return

    if not name:
        ui.status("Anulowano")
        return

    manager.install_model(name)


# ─── Benchmark ───────────────────────────────────────────────────────────────

def _do_benchmark(ui: UI, manager: ModelManager, models: list[dict]):
    """Interaktywny benchmark modelu lub wszystkich."""
    print()
    ui.section("Benchmark modelu")

    if not models:
        ui.warning("Brak listy modeli – Ollama offline?")
        return

    # Pokaż listę z oznaczeniem co można benchmarkować
    print(f"  {Colors.BOLD}Dostępne modele:{Colors.RESET}\n")
    for i, m in enumerate(models, 1):
        name  = m["name"]
        size  = manager.format_size(m["size"]) if m.get("size") else "cloud"
        mtype = manager._detect_model_type(name)
        type_tag = {
            "embed":   f"  {Colors.BLUE}[embed – pomijany]{Colors.RESET}",
            "cloud":   f"  {Colors.YELLOW}[cloud – pomijany]{Colors.RESET}",
            "vision":  f"  \033[35m[vision]\033[0m",
            "unknown": f"  {Colors.GRAY}[unknown – pomijany]{Colors.RESET}",
            "chat":    "",
        }.get(mtype, "")
        print(f"    [{i:2}] {name:<50} {size:>8}{type_tag}")

    local_count = sum(
        1 for m in models
        if not manager.is_cloud(m["name"])
        and not manager.is_embed(m["name"])
        and not manager.is_unknown(m["name"])
        and m.get("size", 0) > 0
    )
    print(f"\n  {Colors.GRAY}[a] Grupowy benchmark wszystkich lokalnych ({local_count} modeli){Colors.RESET}\n")

    try:
        raw = input(f"  {Colors.BOLD}Numer, nazwa lub [a] dla grupowego (Enter = anuluj): {Colors.RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return

    if not raw:
        ui.status("Anulowano")
        return

    # Grupowy benchmark
    if raw.lower() == "a":
        results = manager.benchmark_all(models)
        _print_benchmark_table(ui, results)
        return

    # Pojedynczy model
    model_name = raw
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(models):
            model_name = models[idx]["name"]

    result = manager.benchmark_model(model_name)

    if result.get("skip"):
        ui.warning(f"Pomięto: {result['error']}")
        return

    if "error" in result:
        ui.error(f"Benchmark nieudany: {result['error']}")
        return

    _print_single_benchmark(ui, result)


def _print_single_benchmark(ui: UI, result: dict):
    """Wyświetla wyniki benchmarku jednego modelu."""
    print()
    ui.section(f"Wyniki benchmark: {result['model']}")
    tps = result["tps"]
    tps_color = Colors.GREEN if tps >= 20 else (Colors.YELLOW if tps >= 8 else Colors.RED)
    print(f"  {Colors.BOLD}TTFT:{Colors.RESET}      {result['ttft_ms']} ms  {Colors.GRAY}(czas do pierwszego tokenu){Colors.RESET}")
    print(f"  {Colors.BOLD}Throughput:{Colors.RESET} {tps_color}{tps} tok/s{Colors.RESET}")
    print(f"  {Colors.BOLD}Tokeny:{Colors.RESET}    {result['tokens']} w {result['total_s']}s")
    print()
    print(f"  {Colors.GRAY}Odpowiedź: {result['response'][:120]}{Colors.RESET}")
    print()
    if tps >= 40:   rating = f"{Colors.GREEN}Bardzo szybki{Colors.RESET}"
    elif tps >= 20: rating = f"{Colors.GREEN}Szybki{Colors.RESET}"
    elif tps >= 8:  rating = f"{Colors.YELLOW}Średni{Colors.RESET}"
    else:           rating = f"{Colors.RED}Wolny{Colors.RESET}"
    print(f"  Ocena: {rating}")


def _print_benchmark_table(ui: UI, results: list[dict]):
    """Wyświetla tabelę wyników grupowego benchmarku."""
    ok      = [r for r in results if "error" not in r]
    errors  = [r for r in results if "error" in r and not r.get("skip")]
    skipped = [r for r in results if r.get("skip")]

    print()
    ui.section("Podsumowanie benchmarku grupowego")

    if ok:
        print(f"  {'Model':<42} {'TTFT':>8}  {'tok/s':>7}  {'Ocena'}")
        print(f"  {'-'*42} {'-'*8}  {'-'*7}  {'-'*12}")
        for r in ok:
            tps = r["tps"]
            if tps >= 20:   ocena, col = "Szybki",    Colors.GREEN
            elif tps >= 8:  ocena, col = "Średni",    Colors.YELLOW
            else:           ocena, col = "Wolny",     Colors.RED
            name_short = r["model"][:40]
            print(f"  {name_short:<42} {r['ttft_ms']:>6} ms  {col}{tps:>5.1f}/s  {ocena}{Colors.RESET}")

    if errors:
        print()
        for r in errors:
            print(f"  {Colors.RED}✗ {r['model']}: {r['error']}{Colors.RESET}")

    if skipped:
        print()
        for r in skipped:
            print(f"  {Colors.GRAY}↷ {r['model']}: {r['error']}{Colors.RESET}")
    print()


# ─── Rekomendacje wg sprzętu ─────────────────────────────────────────────────

def _show_recommendations(ui: UI):
    """Pokazuje rekomendowane modele wg dostępnego RAM/VRAM."""
    print()
    ui.section("Rekomendacje modeli wg sprzętu")

    ram_gb  = get_system_ram_gb()
    vram_gb = get_gpu_vram_gb()

    print(f"  RAM systemowy: {Colors.BOLD}{ram_gb:.1f} GB{Colors.RESET}")
    if vram_gb > 0:
        print(f"  VRAM GPU:      {Colors.BOLD}{vram_gb:.1f} GB{Colors.RESET}")
    else:
        print(f"  VRAM GPU:      {Colors.GRAY}nie wykryto (CPU inference){Colors.RESET}")
    print()

    if ram_gb == 0:
        ui.warning("Nie udało się odczytać RAM – nie można dopasować modeli")
        return

    recs = get_model_recommendations(ram_gb, vram_gb)
    if not recs:
        ui.warning(f"Brak modeli pasujących do {ram_gb:.0f} GB RAM")
        return

    # Grupuj wg tagów
    groups = {"chat": [], "coder": [], "vision": [], "reasoning": []}
    for r in recs:
        placed = False
        for tag in ("reasoning", "vision", "coder", "chat"):
            if tag in r["tags"]:
                groups[tag].append(r)
                placed = True
                break
        if not placed:
            groups["chat"].append(r)

    labels = {"chat": "Chat ogólny", "coder": "Kodowanie", "vision": "Vision / obrazy", "reasoning": "Reasoning"}
    for key, label in labels.items():
        group = groups[key]
        if not group:
            continue
        print(f"  {Colors.BOLD}{label}:{Colors.RESET}")
        # Pokaż od największego pasującego
        for r in sorted(group, key=lambda x: x["min_ram"], reverse=True)[:4]:
            ram_str  = f"≥{r['min_ram']:.0f} GB RAM"
            vram_str = f", ≥{r['min_vram']:.0f} GB VRAM" if r["min_vram"] > 0 else ""
            cloud    = f"  {Colors.YELLOW}[cloud]{Colors.RESET}" if "cloud" in r["tags"] else ""
            print(f"    {Colors.CYAN}{r['name']:<40}{Colors.RESET}  "
                  f"{Colors.GRAY}{r['desc']}  ({ram_str}{vram_str}){Colors.RESET}{cloud}")
        print()

    print(f"  {Colors.GRAY}Aby zainstalować model: wybierz opcję [6] z menu głównego{Colors.RESET}")


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
