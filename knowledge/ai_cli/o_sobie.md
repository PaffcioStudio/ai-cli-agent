# AI CLI Agent – informacje o sobie (v1.5.0)

## Czym jestem

Jestem asystentem AI działającym lokalnie w terminalu. Łączę się z modelami językowymi przez Ollama i mam dostęp do plików, terminala, internetu i wiedzy z bazy RAG. Działam per-katalog — każdy katalog projektowy ma swoją pamięć, historię rozmów i logi.

## Gdzie mieszkają moje pliki

```
~/.config/ai/
├── config.json          ← główna konfiguracja
├── memory.json          ← globalna pamięć (zapamiętane fakty)
└── prompt.txt           ← opcjonalny user prompt (personalizacja)

<projekt>/.ai-logs/
├── session.log                  ← czytelna historia sesji
├── operations.jsonl             ← audit trail operacji
├── responses.jsonl              ← surowe odpowiedzi modelu
└── conversation_history.jsonl   ← persystentna historia rozmów
```

## Komendy systemowe

```bash
ai                        # tryb interaktywny
ai "zrób coś"             # jednorazowe polecenie
ai --global / -g          # tryb bez projektu
ai --dry-run              # symulacja bez zmian
ai --plan                 # tylko plan, bez wykonania
ai --yes / -y             # pomiń potwierdzenia
ai --version              # wersja
ai --help                 # zwięzła pomoc
ai --help-all             # pomoc z przykładami
```

## Komendy projektu

```bash
ai init                   # zainicjuj projekt
ai analyze                # przeanalizuj projekt
ai review                 # przegląd kodu
ai audit                  # audit trail operacji
ai stats                  # statystyki projektu
ai history                # historia poleceń
ai export                 # eksportuj sesję do Markdown
ai export raport.md       # eksportuj do podanego pliku
ai export --all           # cała historia (nie tylko dzisiejsza)
ai export --operations    # dodaj tabelę operacji
```

## Konfiguracja — pełna składnia

```bash
ai config                         # pokaż całą konfigurację JSON
ai config list                    # płaska lista wszystkich kluczy
ai config get <klucz>             # pokaż jedną wartość
ai config set <klucz> <wartość>   # ustaw wartość
ai config unset <klucz>           # usuń klucz
ai config edit                    # otwórz w nano
```

Klucze zagnieżdżone przez kropkę, typy konwertowane automatycznie:

```bash
ai config set nick Paffcio
ai config set execution.timeout_seconds 60
ai config set execution.command_output_limit 8000
ai config set web_search.enabled true
ai config set conversation.save_history false
ai config set rag.top_k 10
ai config unset web_search.brave_api_key
ai config get execution.command_output_limit
```

## Historia rozmów (persystentna)

Rozmowy zapisywane są do `.ai-logs/conversation_history.jsonl`. Przy następnym
uruchomieniu `ai` w tym samym katalogu pojawi się pytanie o wznowienie:

```
► Znaleziono historię rozmowy  (2026-03-21 18:47)
  Ostatnie: "na czym skończyliśmy?"

Czy wznowić poprzednią rozmowę?  [T/n]
```

T (lub Enter) → wczytuje historię, AI pamięta kontekst
N → czyści historię, zaczyna od zera

Ustawienia:
```bash
ai config set conversation.save_history true       # włącz/wyłącz zapis
ai config set conversation.resume_prompt true      # włącz/wyłącz pytanie
ai config set conversation.max_saved_messages 40   # limit wiadomości
```

## Web search

```bash
ai web-search enable
ai web-search disable
ai web-search status
ai web-search "zapytanie"
ai web-search scrape https://...
ai web-search cache clear
ai web-search domains add example.com
```

## Wiedza (RAG)

```bash
ai --index                  # przeindeksuj po dodaniu plików .md
ai knowledge status
ai knowledge list
```

```bash
ai config set rag.top_k 8
ai config set rag.min_score 0.1
```

## Pamięć globalna

```bash
ai memory list
ai memory add "fakt"
```

## Modele

```bash
ai model                    # interaktywne menu
ai config set chat_model glm-5:cloud
ai config set coder_model qwen2.5-coder:7b
ai config set vision_model qwen3-vl:235b-instruct-cloud
ai config set embed_model nomic-embed-text-v2-moe:latest
ai config set fallback_model qwen3:14b
```

## Panel web

```bash
ai panel status|start|stop|open    # URL: http://127.0.0.1:21650
```

## Akcje które mogę wykonywać

Operacje na plikach (bezpieczne):
- `read_file`, `list_files`, `semantic_search`

Modyfikacje (potwierdzenie przy >3):
- `create_file`, `edit_file`, `patch_file`, `mkdir`, `chmod`

Destrukcyjne (zawsze potwierdzenie):
- `delete_file`, `move_file`

Wykonywanie (ryzyko zależy od komendy):
- `run_command` — dowolna komenda bash
- `web_search`, `web_scrape`
- `download_media`, `convert_media` (yt-dlp + ffmpeg)
- `process_image`, `batch_images` (Pillow)
- `clipboard_read`, `clipboard_write`
- `save_memory`, `use_template`

## Jak działają prompt layers

Ładowane są tylko potrzebne warstwy zamiast pełnego promptu:
- `core.txt` — zawsze
- `patch_edit.txt` — edycja plików
- `web_search.txt` — wyszukiwanie
- `media.txt` — media
- `images.txt` — obrazy
- `kde_desktop.txt` — pulpit KDE
- `clipboard.txt` — schowek
- `bash_tools.txt` — komendy bash
