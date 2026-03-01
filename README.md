# AI CLI Agent — Asystent developerski dla terminala

**Wersja:** `1.4.6`  
**Wymaga:** Python 3.11+, [Ollama](https://ollama.com)

Narzędzie CLI wspomagające pracę z projektami przez AI. Nie jest to autonomiczny bot, a kontrolowane narzędzie operatorskie z pełną przejrzystością i możliwością cofnięcia zmian.

> **UWAGA:** AI CLI nie jest narzędziem do automatyzacji, tylko do wspomaganego podejmowania decyzji technicznych.

---

## Filozofia

**Co TO JEST:**
- Asystent developerski wspierający pracę z kodem i terminalem
- Warstwa decyzyjna NAD terminalem (nie zamiast terminala)
- Narzędzie z pełną kontrolą użytkownika i audit trailem
- Pipeline zadaniowy z walidacją środowiska i rollbackiem

**Czego TO NIE JEST:**
- Chatbot prowadzący rozmowy
- Autonomiczny agent podejmujący decyzje bez wiedzy użytkownika
- System "AI wie lepiej"

---

## Instalacja

```bash
# 1. Sklonuj projekt
cd ai-cli

# 2. Zainstaluj zależności
pip install -r requirements.txt --break-system-packages

# 3. Zainstaluj alias 'ai' (opcjonalnie)
./install-cli.sh install

# 4. Konfiguracja przy pierwszym uruchomieniu
ai config

# 5. (Opcjonalnie) Zainstaluj narzędzia medialne
sudo apt install yt-dlp ffmpeg
```

---

## Tryby pracy

| Flaga | Opis |
|-------|------|
| *(brak)* | Normalny — wykonuje akcje z potwierdzeniami |
| `--plan` | Tylko plan, zero zmian w plikach |
| `--dry-run` | Symulacja — bez modyfikacji FS |
| `--yes` | Auto-confirm, bez pytań (niebezpieczne!) |
| `--global` | Bez kontekstu projektu |
| `--verbose` | Diagnostyczne logi w konsoli |

---

## Funkcje

### Analiza i eksploracja projektu

Agent automatycznie rozpoznaje typ projektu (Python, Node.js, React, Rust itd.) przy starcie i utrzymuje kontekst w `.ai-context.json`. Dostępne komendy:

```bash
ai analyze              # Pełna analiza projektu
ai review               # Przegląd: co poprawić, co dalej
ai co robi ten projekt  # Szybkie pytanie o projekt
```

### Klasyfikacja intencji i komend

`IntentClassifier` rozpoznaje zamiar użytkownika zanim polecenie trafi do modelu: `explore`, `create`, `modify`, `refactor`, `execute`, `download_media`. `CommandClassifier` kategoryzuje ryzyko komend bash: `READ_ONLY` (bez confirm), `MODIFY`, `DESTRUCTIVE` (zawsze confirm).

### Transaction Manager — ACID rollback

Każda operacja modyfikująca pliki jest objęta transakcją z automatycznym rollbackiem przy błędzie. Albo wszystkie akcje przechodzą, albo żadna.

### Capability Manager

Kontrola dozwolonych akcji per-projekt:

```bash
ai capability list
ai capability disable allow_execute  # np. dla repo produkcyjnego
ai capability enable allow_delete
```

Capability: `allow_execute`, `allow_delete`, `allow_git`, `allow_network`.

### Pamięć projektu i audit trail

```bash
ai audit      # Dlaczego AI podjął dane decyzje
ai history    # Historia poleceń z intencjami
```

### Globalna pamięć persystentna

Fakty zapisywane między sesjami i projektami w `~/.config/ai/memory.json`:

```bash
ai memory list
ai memory add używam neovim jako edytor
ai memory rm <id>
```

Fraza "zapamiętaj że..." jest przechwytywana automatycznie.

### Web Search

```bash
ai web-search enable
ai web-search status
# Auto-trigger gdy włączone:
ai jaka jest pogoda w Gdańsku
ai najnowsza wersja pandas
```

Silniki: DuckDuckGo (bez klucza) lub Brave Search (z kluczem). Cache 1h TTL, rate limit 10/min, whitelist domen. Domyślnie WYŁĄCZONY.

### RAG — lokalna baza wiedzy

Semantyczne wyszukiwanie w plikach `.md`/`.txt` z katalogu `knowledge/`:

```bash
ai --index          # Przebuduj indeks
ai knowledge status
```

Wyniki automatycznie wstrzykiwane do kontekstu promptu.

### Media Pipeline

```bash
ai pobierz https://youtube.com/watch?v=...
ai pobierz i przekonwertuj na mp3 https://...
ai pobierz tylko audio z https://...
ai pobierz w 720p https://...
```

Obsługuje YouTube, Vimeo, SoundCloud i 1000+ innych źródeł (via yt-dlp). Narzędzia instalowane automatycznie jeśli brakuje (apt → pip → GitHub).

### Przetwarzanie obrazów

```bash
ai stwórz favicon z logo.png
ai przekonwertuj wszystkie PNG na WebP
ai skompresuj zdjęcia w folderze
```

### Schowek systemowy

```bash
ai wyjaśnij kod ze schowka
ai napraw błąd ze schowka
ai skopiuj wynik do schowka
```

### Szablony projektów

Gotowe szablony: `python`, `fastapi`, `node`, `react`, `web`, `bash`, `rust`:

```bash
ai stwórz projekt fastapi moja-api
```

### Warstwowy system promptu

Prompt budowany per-request z warstw `prompts/layers/` (core + inject wg triggera). Warstwy: `bash_tools`, `web_search`, `media`, `images`, `clipboard`, `patch_edit`, `kde_desktop`, `project_files`, `disks_games`.

### Panel webowy

```bash
ai panel start   # http://127.0.0.1:21650
ai panel open
ai panel status
ai panel stop
```

Panel do: podglądu statusu, edycji config i promptu, przeglądania logów. Panel NIE wykonuje poleceń.

---

## Komendy CLI

```bash
# Projekt
ai analyze | review | audit | stats | history

# Konfiguracja
ai config [edit]
ai model
ai prompt
ai capability [list|enable|disable|reset]
ai web-search [enable|disable|status|scrape|cache|domains]
ai memory [list|add|rm|clear|show]
ai knowledge [status|list] | ai --index

# Diagnostyka
ai logs [clean|rotate]
ai panel [status|start|stop|open]
ai help | --version
```

---

## Konfiguracja

Plik: `~/.config/ai/config.json`

```json
{
  "nick": "Paffcio",
  "ollama_host": "127.0.0.1",
  "ollama_port": 11434,
  "chat_model": "qwen3-coder:480b-cloud",
  "embed_model": "nomic-embed-text-v2-moe:latest",

  "behavior": {
    "max_actions_per_run": 10,
    "prefer_read_before_edit": true
  },
  "execution": {
    "auto_confirm_safe_commands": true,
    "auto_confirm_modify_under": 3,
    "timeout_seconds": 30
  },
  "web_search": {
    "enabled": false,
    "engine": "duckduckgo",
    "cache_ttl_hours": 1,
    "auto_trigger": true
  },
  "rag": {
    "enabled": true,
    "top_k": 4
  },
  "debug": {
    "log_level": "info",
    "save_failed_responses": true
  }
}
```

---

## Architektura

```
main.py                     CLI entry point
core/
  agent.py                  Główna logika — pętla wykonania (max 8 iteracji)
  action_executor.py        Wykonywanie akcji
  conversation_state.py     Historia dialogu (max 10 tur)
  json_parser.py            Parsowanie + rescue odpowiedzi modelu
  model_manager.py          Smart routing (chat/coder/vision/embed)
  ollama.py                 Klient Ollama z retry/backoff
  prompt_builder.py         Warstwowy builder systemu promptu

classification/
  intent_classifier.py      Rozpoznawanie zamiaru
  command_classifier.py     Klasyfikacja ryzyka komend

planning/
  action_planner.py         Plan i walidacja kolejności akcji
  action_validator.py       Typy i ryzyko akcji
  impact_analyzer.py        Analiza wpływu zmian

project/
  capability_manager.py     Ograniczenia per-projekt
  global_memory.py          Persystentna pamięć ~/.config/ai/memory.json
  project_analyzer.py       Typ projektu, stos technologiczny
  project_memory.py         .ai-context.json — konwencje, intenty
  semantic_decisions.py     Wykrywanie zmian semantycznych

rag/
  knowledge_base.py         Indeksowanie + wyszukiwanie wektorowe

tasks/
  image_tasks.py            Przetwarzanie obrazów
  media_tasks.py            Pobieranie/konwersja mediów
  web_search.py             Web search + scraper

utils/
  logger.py                 Centralny logger (debug + audit trail)
  transaction_manager.py    ACID rollback dla operacji FS
  diff_editor.py            Edycja plików z walidacją
  search_replace.py         Patch-based edycja
  template_manager.py       Szablony projektów
  clipboard_utils.py        Schowek systemowy

ui_layer/
  commands.py               Implementacje komend
  ui.py                     Interfejs (Rich / fallback)
  review_mode.py            Tryb przeglądu projektu

prompts/layers/             Warstwy system promptu
knowledge/                  Lokalna baza wiedzy RAG
templates/                  Szablony nowych projektów
web/                        Panel administracyjny (Flask)
```

---

## Bezpieczeństwo

**Priorytety decyzyjne:** kod Python > capabilities > flagi CLI > config > prompt.

**Blokady:** `rm -rf /`, `rm -rf ~`, destrukcyjne komendy z globami w home, destrukcyjne komendy poza katalogiem projektu bez jawnej ścieżki absolutnej.

---

## Logowanie

```
~/.cache/ai-cli/logs/
  debug.log          Diagnostyka
  errors.log         Błędy krytyczne

<projekt>/.ai-logs/
  operations.jsonl   Audit trail (JSONL)
  session.log        Czytelny log sesji
  responses.jsonl    Surowe odpowiedzi modelu
```

---

## Ograniczenia

- Działa tylko w bieżącym katalogu (bezpieczeństwo)
- Wymaga Ollama z odpowiednimi modelami
- Brak trybu multi-user
- Brak retry policy dla operacji webowych
- Brak limitów kosztu tokenów per-zadanie
- Brak testów automatycznych
- Brak wersjonowania promptów

---

## Licencja

MIT — używaj jak chcesz, na własną odpowiedzialność.

**Wersja**: 1.4.6 | **Autor**: Paffcio | **Data**: 2026-02-28
