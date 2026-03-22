# AI CLI — pełna lista kluczy konfiguracji

Wszystkie klucze do użycia z `ai config set <klucz> <wartość>`.
Notacja z kropką dla zagnieżdżonych kluczy.

## Podstawowe

```
nick                          string    nazwa użytkownika (wyświetlana w logach)
chat_model                    string    główny model LLM (np. glm-5:cloud)
coder_model                   string    model do zadań z kodem
vision_model                  string    model do obrazów
fallback_model                string    model zapasowy przy błędach
embed_model                   string    model embeddingów (RAG)
ollama_host                   string    adres serwera Ollama (domyślnie 127.0.0.1)
ollama_port                   int       port Ollama (domyślnie 11434)
```

## behavior — zachowanie agenta

```
behavior.default_confirm              bool    czy domyślnie pytać o potwierdzenie
behavior.max_actions_per_run          int     limit akcji w jednej rundzie (domyślnie 10)
behavior.prefer_read_before_edit      bool    czytaj plik przed edycją
behavior.allow_multi_step_reasoning   bool    pozwól na iteracje
```

## execution — wykonywanie komend

```
execution.auto_confirm_safe           bool    auto-potwierdź bezpieczne komendy
execution.auto_confirm_safe_commands  bool    auto-potwierdź komendy read-only
execution.auto_confirm_modify_under   int     auto-potwierdź modyfikacje jeśli <N plików
execution.timeout_seconds             int     limit czasu komendy w sekundach (domyślnie 120)
execution.shell                       string  powłoka (domyślnie /bin/bash)
execution.command_output_limit        int     max znaków stdout/stderr (domyślnie 4000)
```

## conversation — historia rozmów

```
conversation.save_history             bool    zapisuj historię do pliku (domyślnie true)
conversation.resume_prompt            bool    pytaj o wznowienie przy starcie (domyślnie true)
conversation.max_saved_messages       int     ile wiadomości trzymać w pliku (domyślnie 40)
```

## rag — baza wiedzy

```
rag.enabled                   bool    czy używać RAG
rag.top_k                     int     ile fragmentów dołączyć do promptu (domyślnie 8)
rag.min_score                 float   minimalny próg podobieństwa 0.0–1.0 (domyślnie 0.1)
rag.embed_model               string  osobny model embeddingów dla RAG (puste = embed_model)
rag.show_sources              bool    pokaż skąd pochodzi wiedza
rag.max_per_file              int     max fragmentów z jednego pliku
```

## semantic — wyszukiwanie semantyczne w kodzie

```
semantic.enabled                      bool
semantic.max_files                    int     max plików do przeszukania
semantic.max_file_size_kb             int     max rozmiar pliku
semantic.cache_embeddings             bool    cachuj embeddingi
semantic.prefer_frequently_edited     bool    preferuj często edytowane pliki
semantic.boost_paths                  list    ścieżki do boostowania ["src/","app/"]
```

## web_search — wyszukiwanie internetowe

```
web_search.enabled                    bool
web_search.engine                     string  duckduckgo | brave
web_search.max_results                int
web_search.cache_ttl_hours            int     czas życia cache w godzinach
web_search.allowed_domains            list    whitelist domen
web_search.require_confirmation       bool    pytaj przed każdym wyszukiwaniem
web_search.brave_api_key              string  klucz API Brave Search
web_search.auto_trigger               bool    auto-wykrywaj frazy wyzwalające
```

## memory — pamięć globalna

```
memory.auto_extract           bool    auto-wyciągaj fakty z rozmowy
memory.show_saved             bool    pokazuj co zostało zapamiętane
```

## ui — interfejs

```
ui.spinner                    bool    animacja ładowania
ui.show_diff_preview          bool    podgląd zmian przed zapisem
ui.color_output               bool    kolory w terminalu
ui.show_action_summary        bool    podsumowanie akcji przed wykonaniem
ui.silent_safe_actions        bool    nie pokazuj bezpiecznych akcji
```

## project — ustawienia projektu

```
project.auto_analyze_on_start         bool    analizuj projekt przy starcie
project.auto_analyze_on_change        bool    analizuj przy zmianach
project.remember_intents              bool    zapamiętuj intencje poleceń
project.max_history                   int     długość historii projektu
```

## debug — diagnostyka

```
debug.log_level                       string  debug | info | warning | error
debug.log_semantic_queries            bool    loguj zapytania semantyczne
debug.log_model_raw_output            bool    loguj surowe odpowiedzi modelu
debug.save_failed_responses           bool    zapisuj nieudane odpowiedzi
```

## Przykłady szybkich zmian

```bash
# Zwiększ limit outputu komend (przydatne przy find/snap/df)
ai config set execution.command_output_limit 8000

# Wyłącz pytanie o historię rozmów
ai config set conversation.resume_prompt false

# Więcej fragmentów wiedzy w każdym zapytaniu
ai config set rag.top_k 12

# Włącz logowanie surowych odpowiedzi modelu (debug)
ai config set debug.log_model_raw_output true

# Wyłącz auto-analizę projektu przy starcie (szybszy start)
ai config set project.auto_analyze_on_start false

# Zwiększ timeout dla wolnych komend
ai config set execution.timeout_seconds 300
```
