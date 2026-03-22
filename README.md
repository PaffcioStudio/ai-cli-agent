# AI CLI Agent - Asystent developerski dla terminala

**Wersja:** `1.5.1`  
**Wymaga:** Python 3.11+, [Ollama](https://ollama.com)

Narzędzie CLI wspomagające pracę z projektami przez AI. Nie jest to autonomiczny bot, a kontrolowane narzędzie operatorskie z pelna przejrzystoscia i mozliwoscia cofniecia zmian.

> **UWAGA:** AI CLI nie jest narzedziem do automatyzacji, tylko do wspomaganego podejmowania decyzji technicznych.

---

## Dokumentacja

- [Architektura](docs/ARCHITECTURE.md)
- [FAQ](docs/FAQ.md)
- [Media Pipeline](docs/MEDIA_PIPELINE.md)
- [RAG](docs/RAG.md)
- [Web Search](docs/WEB_SEARCH.md)
- [Security](docs/SECURITY.md)
- [Roadmap](docs/ROADMAP.md)

---

## Instalacja

```bash
# Instalacja interaktywna (zalecana)
bash install-cli.sh

# Nieinteraktywna (bez pytan)
bash install-cli.sh --install
```

### Opcje instalatora

```bash
bash install-cli.sh                    # interaktywne menu
bash install-cli.sh --install          # swiezza instalacja bez pytan
bash install-cli.sh --update           # aktualizacja plikow + pakietow
bash install-cli.sh --update-packages  # tylko pakiety Python (pip upgrade)
bash install-cli.sh --uninstall        # usun, zachowaj konfiguracje
bash install-cli.sh --uninstall-all    # usun wszystko bez pytan
bash install-cli.sh --status           # stan instalacji
bash install-cli.sh --help             # pomoc
```

---

## Tryby pracy

| Flaga | Opis |
|-------|------|
| *(brak)* | Normalny - wykonuje akcje z potwierdzeniami |
| `--plan` | Tylko plan, zero zmian w plikach |
| `--dry-run` | Symulacja - bez modyfikacji FS |
| `--yes` | Auto-confirm, bez pytan (niebezpieczne!) |
| `--global` | Bez kontekstu projektu |
| `--verbose` | Diagnostyczne logi w konsoli |

---

## Funkcje

### Analiza i eksploracja projektu

```bash
ai analyze              # Pelna analiza projektu
ai review               # Przeglad: co poprawic, co dalej
ai co robi ten projekt  # Szybkie pytanie o projekt
```

### Klasyfikacja intencji i komend

`IntentClassifier` rozpoznaje zamiar uzytkownika zanim polecenie trafi do modelu. `CommandClassifier` kategoryzuje ryzyko komend bash: `READ_ONLY` (bez confirm), `MODIFY`, `DESTRUCTIVE` (zawsze confirm).

### Transaction Manager - ACID rollback

Kazda operacja modyfikujaca pliki jest objetana transakcja z automatycznym rollbackiem przy bledzie.

### Capability Manager

```bash
ai capability list
ai capability disable allow_execute
ai capability enable allow_delete
```

Capability: `allow_execute`, `allow_delete`, `allow_git`, `allow_network`.

### Pamiec projektu i audit trail

```bash
ai audit      # Dlaczego AI podjal dane decyzje
ai history    # Historia polecen z intencjami
```

### Globalna pamiec persystentna

```bash
ai memory list
ai memory add uzywam neovim jako edytor
ai memory rm <id>
```

Fraza "zapamietaj ze..." jest przechwytywana automatycznie. Dane w `~/.config/ai/memory.json`.

### Web Search

```bash
ai web-search enable
ai web-search status
ai jaka jest pogoda w Gdansku
```

Silniki: DuckDuckGo (bez klucza) lub Brave Search (z kluczem). Cache 1h TTL. Domyslnie WYLACZONY.

### RAG - lokalna baza wiedzy

```bash
ai --index          # Przebuduj indeks
ai knowledge status
```

Zalecany model embeddingowy: `qwen3-embedding:8b`.

### Media Pipeline

```bash
ai pobierz https://youtube.com/watch?v=...
ai pobierz i przekonwertuj na mp3 https://...
ai pobierz w 720p https://...
```

### Szablony projektow

```bash
ai stworz projekt fastapi moja-api
```

Dostepne: `python`, `fastapi`, `node`, `react`, `web`, `bash`, `rust`.

### Panel webowy

Pelny interfejs chat w przegladarce (styl ChatGPT), dostepny w sieci LAN.

```bash
ai panel start    # uruchom
ai panel open     # otworz w przegladarce
ai panel status   # stan serwisu
ai panel stop     # zatrzymaj
ai panel log      # ostatnie 30 linii logow
ai panel log 100  # ostatnie N linii
ai panel --help   # pelna pomoc
```

**Funkcje panelu:**
- Chat AI z przelaczaniem modeli w locie
- Upload plikow i archiwow ZIP - AI analizuje projekt od razu (tresc wstrzykiwana do kontekstu automatycznie, bez potrzeby wykonywania kodu)
- Workspace sandbox z podgladem plikow sesji i pobieraniem ZIP
- Historia rozmow (tytul = nazwa wgranego pliku lub pierwsze zdanie)
- Bloki kodu z podswietlaniem skladni i przyciskiem kopiowania
- Tryb jasny / ciemny
- System prompt: wspolny z CLI (`prompt.txt`), wlasny dla web (`prompt-web.txt`) lub wylaczony
- Panel logow bledow z czyszczeniem
- Edycja konfiguracji Ollama

Panel uruchamia sie jako systemd user service (autostart po zalogowaniu). URL z IP sieci LAN wyswietlany automatycznie przy starcie serwisu.

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
ai deps
ai panel [status|start|stop|open|log|--help]
ai help | --version
```

---

## Konfiguracja

Plik: `~/.config/ai/config.json`

```json
{
  "nick": "user",
  "ollama_host": "127.0.0.1",
  "ollama_port": 11434,
  "chat_model": "qwen3:14b",
  "embed_model": "qwen3-embedding:8b",
  "web_prompt_mode": "disabled",

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

### Tryby system promptu dla web panelu (`web_prompt_mode`)

| Wartosc | Opis |
|---------|------|
| `disabled` | Brak system promptu w web panelu (domyslnie) |
| `cli` | Uzywa `~/.config/ai/prompt.txt` (wspolny z CLI) |
| `web` | Uzywa `~/.config/ai/prompt-web.txt` (wlasny dla panelu) |

Zmiana przez Ustawienia w panelu lub: `ai config set web_prompt_mode cli`

---

## Dane uzytkownika

```
~/.config/ai/
  config.json          - konfiguracja (model, serwer, opcje)
  prompt.txt           - system prompt CLI
  prompt-web.txt       - system prompt web panelu (opcjonalny)
  memory.json          - globalna pamiec persystentna
  knowledge/           - baza wiedzy RAG (.md/.txt)
  web/
    chats/             - historia rozmow web panelu (JSON)
    sessions/          - sandbox plikow sesji (workspace, uploads, outputs)
    logs/web.log       - logi bledow web panelu (JSON-lines)
```

---

## Architektura

```
main.py                     CLI entry point
core/
  agent.py                  Glowna logika - petla wykonania (max 8 iteracji)
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
  action_planner.py         Plan i walidacja kolejnosci akcji
  action_validator.py       Typy i ryzyko akcji
  impact_analyzer.py        Analiza wplywu zmian

project/
  capability_manager.py     Ograniczenia per-projekt
  global_memory.py          Persystentna pamiec ~/.config/ai/memory.json
  project_analyzer.py       Typ projektu, stos technologiczny
  project_memory.py         .ai-context.json - konwencje, intenty
  semantic_decisions.py     Wykrywanie zmian semantycznych

rag/
  knowledge_base.py         Indeksowanie + wyszukiwanie wektorowe

tasks/
  image_tasks.py            Przetwarzanie obrazow
  media_tasks.py            Pobieranie/konwersja mediow
  web_search.py             Web search + scraper

utils/
  logger.py                 Centralny logger (debug + audit trail)
  transaction_manager.py    ACID rollback dla operacji FS
  diff_editor.py            Edycja plikow z walidacja
  search_replace.py         Patch-based edycja
  template_manager.py       Szablony projektow
  clipboard_utils.py        Schowek systemowy

ui_layer/
  commands.py               Komendy CLI (panel log, panel --help, get_panel_url)
  ui.py                     Interfejs (Rich / fallback)
  review_mode.py            Tryb przegladu projektu

web/                        Panel webowy (http.server, port 21650)
  server.py                 Router HTTP
  handlers/
    base.py                 Stale, helpery sandboxa, log_error()
    config_handler.py       Config, prompt (CLI/web/disabled), logi
    chat_handler.py         Proxy AI (Ollama), pamiec, historia
    sandbox_handler.py      Upload (wlasny parser multipart), workspace, download
  js/
    main.js                 Entry point
    chats.js                Historia konwersacji
    sandbox.js              Upload, workspace tree, download
    settings.js             Modal ustawien (tryby promptu, logi, autozapis)
    memory.js               Panel pamieci
    messages.js             Renderowanie wiadomosci
    input.js                Input box, wysylanie do AI
    models.js               Picker modeli Ollama
  style.css                 Style (dark/light theme, CSS variables)
  index.html                SPA

prompts/layers/             Warstwy system promptu
knowledge/                  Lokalna baza wiedzy RAG
templates/                  Szablony nowych projektow
install-cli.sh              Instalator (--install/--update/--uninstall/--help)
```

---

## Bezpieczenstwo

**Priorytety decyzyjne:** kod Python > capabilities > flagi CLI > config > prompt.

**Blokady CLI:** `rm -rf /`, `rm -rf ~`, destrukcyjne komendy z globami w home, destrukcyjne komendy poza katalogiem projektu bez jawnej sciezki absolutnej.

**Sandbox web panelu:** pliki sesji izolowane w `~/.config/ai/web/sessions/<id>/`, walidacja path traversal przy uploadzie ZIP, max 100 MB na plik.

---

## Logowanie

```
~/.cache/ai-cli/logs/
  debug.log          Diagnostyka CLI
  errors.log         Bledy krytyczne

~/.config/ai/web/logs/
  web.log            Bledy web panelu (JSON-lines z timestampem)

<projekt>/.ai-logs/
  operations.jsonl   Audit trail (JSONL)
  session.log        Czytelny log sesji
  responses.jsonl    Surowe odpowiedzi modelu
```

Logi panelu dostepne przez: `ai panel log` lub zakladke Logi w Ustawieniach panelu.

---

## Ograniczenia

- Dziala tylko w biezacym katalogu (bezpieczenstwo)
- Wymaga Ollama z odpowiednimi modelami
- Brak trybu multi-user
- Brak retry policy dla operacji webowych
- Brak limitow kosztu tokenow per-zadanie
- Brak testow automatycznych
- Parser multipart wlasny (modul `cgi` usuniety w Python 3.13+)

---

## Licencja

MIT - uzywaj jak chcesz, na wlasna odpowiedzialnosc.

**Wersja**: 1.5.1 | **Data**: 2026-03-22
