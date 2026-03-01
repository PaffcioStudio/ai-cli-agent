# Architektura - AI CLI Agent

## Przepływ wywołania

```
Użytkownik → main.py (CLI + flagi)
                ↓
          AIAgent.run()
                ↓
     IntentClassifier.classify()     ← rozpoznanie zamiaru
                ↓
     Web Search auto-trigger?        ← opcjonalne
                ↓
     RAG: KnowledgeBase.search()     ← opcjonalne
                ↓
     PromptBuilder.build()           ← core + warstwy inject
                ↓
     OllamaClient.chat()             ← retry/backoff, smart routing
                ↓
     JSONParser.extract_json()       ← parsowanie + rescue
                ↓
     ActionValidator.validate()      ← typy, ryzyko
     CapabilityManager.validate()    ← ograniczenia projektu
     ActionPlanner.create_plan()     ← kolejność, walidacja planu
                ↓
     UI: pokazanie akcji + confirm   ← jeśli potrzebne
                ↓
     TransactionManager.begin()
                ↓
     ActionExecutor.execute()        ← każda akcja z backupem
                ↓
     TransactionManager.commit/rollback
                ↓
     Logger.log_operation()          ← audit trail
     ProjectMemory.update()          ← konwencje, intenty
                ↓
     Następna iteracja lub koniec    ← max 8 iteracji
```

## Kluczowe klasy

### AIAgent (`core/agent.py`)

Główna klasa. Inicjalizuje wszystkie moduły, orkiestruje pętlę wykonania.

**Pętla wykonania (max 8 iteracji):**
1. Wyślij prompt do modelu
2. Parsuj JSON z odpowiedzi
3. Jeśli `message` (bez akcji) → wyświetl i zakończ
4. Jeśli akcje → waliduj → pytaj o confirm → wykonaj
5. Jeśli wyniki wymagają follow-up (np. `file_content`, `command_result`) → dodaj do historii i powtórz
6. Jeśli model za długo zbiera dane bez tworzenia plików → wstrzyknij `force_action`

**Historia rozmowy:** max 6 wiadomości (3 pary) - starsze są przycinane.

**Token savings:** do historii trafia skrót akcji (`{type, path}`) + wyniki max 300 znaków, nie cały surowy JSON.

### OllamaClient (`core/ollama.py`)

Klient HTTP do Ollama API.

**Smart routing:**
- `coder_model` jeśli wykryto wzorzec kodu (`def `, `.py`, `napisz funkcję`...)
- `vision_model` jeśli są ścieżki do obrazów (`.png`, `.jpg`...)
- `chat_model` dla reszty

**Retry policy:** 3 próby z exponential backoff (1s, 2s, 4s) dla błędów połączenia i 429. Zaimplementowane w `ollama.py`.

### PromptBuilder (`core/prompt_builder.py`)

Warstwowy builder per-request. Każde zapytanie dostaje:
1. `core.txt` - zawsze
2. Warstwy inject wg triggerów w tekście użytkownika
3. Statyczny kontekst (nick, projekt, pamięć, capabilities)

### ActionExecutor (`core/action_executor.py`)

Wykonuje poszczególne typy akcji:

| Typ akcji | Opis |
|-----------|------|
| `read_file` | Odczyt pliku |
| `create_file` | Tworzenie pliku |
| `edit_file` | Zastąpienie zawartości pliku |
| `patch_file` | Diff-based edycja (SearchReplace) |
| `delete_file` | Usunięcie pliku |
| `move_file` | Przeniesienie pliku |
| `list_files` | Listowanie plików (glob) |
| `run_command` | Komenda bash |
| `semantic_search` | Wyszukiwanie semantyczne w projekcie |
| `web_search` | Wyszukiwanie w internecie |
| `web_scrape` | Pobranie treści strony |
| `download_media` | Pobranie media (yt-dlp) |
| `convert_media` | Konwersja media (ffmpeg) |
| `process_image` | Przetwarzanie obrazu |
| `batch_images` | Batch przetwarzanie obrazów |
| `clipboard_read` | Odczyt schowka |
| `clipboard_write` | Zapis do schowka |
| `open_path` | Otwarcie pliku/URL (xdg-open) |
| `use_template` | Zastosowanie szablonu projektu |

### TransactionManager (`utils/transaction_manager.py`)

ACID dla operacji na plikach:

1. `tx.begin()` - start transakcji
2. `tx.stage_backup(path)` - snapshot pliku przed modyfikacją
3. Wykonanie akcji
4. `tx.commit()` - sukces, usuń snapshoty
5. `tx.rollback(reason)` - przywróć snapshoty

Snapshoty przechowywane w `<projekt>/.ai-tx/` (tymczasowo).

### Logger (`utils/logger.py`)

Centralny logger z dwoma poziomami:

**Diagnostyczny** (`~/.cache/ai-cli/logs/`):
- `debug.log` - wszystko
- `errors.log` - tylko błędy

**Audit trail** (`<projekt>/.ai-logs/`):
- `operations.jsonl` - każda operacja (JSONL): timestamp, user, command, intent, akcje, sukces
- `session.log` - czytelny log: `[ts] USER: "..." | AI: "..." | ACTIONS: edit_file:app.py`
- `responses.jsonl` - surowe odpowiedzi modelu

### ConversationState (`core/conversation_state.py`)

Bufor ostatnich 10 tur dialogu. Format: `[{role: user/assistant, content: ...}]`.

Obsługuje też pending confirmation - gdy akcja wymaga potwierdzenia, AI wraca do inputu użytkownika.

## Bezpieczeństwo - warstwy

```
Wejście użytkownika
        ↓
IntentClassifier          ← co chce zrobić?
        ↓
ActionValidator           ← czy akcje są poprawne? (typy, wymagane pola)
        ↓
CapabilityManager         ← czy projekt na to pozwala?
        ↓
ActionPlanner             ← czy plan ma sens? kolejność?
        ↓
_needs_confirm()          ← czy pytać o zgodę?
        ↓
_validate_destructive_context()  ← czy nie usuwamy czegoś krytycznego?
        ↓
TransactionManager        ← backup + rollback
        ↓
Wykonanie
```

## Tryb globalny vs projektowy

**Tryb projektowy** (domyślny): pełna inicjalizacja, dostęp do FS, pamięć projektu, capabilities, semantic search, transaction manager.

**Tryb globalny** (`--global` lub brak markera projektu w home): uproszczona inicjalizacja, ograniczony zestaw akcji (`run_command`, `list_files`, `read_file`, `web_search`, `clipboard_*`, `open_path`, `use_template`), brak loggera projektu.

## Konfiguracja embeddingów i semantic search

Embeddingi projektowe cache'owane per-plik w `~/.cache/ai-cli/embeddings/`. Klucz = hash ścieżki + mtime. Przy semantic_search agent wysyła zapytanie, dostaje top-K plików i ogranicza read do tych plików.

SemanticDecisionManager (`project/semantic_decisions.py`) wykrywa "semantyczne zmiany" - np. zmiana nazwy klasy - i sugeruje powiązane pliki do aktualizacji.
