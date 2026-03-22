# AI CLI Agent - Roadmap

**Aktualna wersja:** `1.4.7` 
**Cel:** `2.0.0` (Production Ready)

---

## Legenda

- CRITICAL - bloker, pilne
- HIGH - wazne, nastepny release
- MEDIUM - przydatne, mozna odlozyc
- LOW - mile w posiadaniu
- FUTURE - pomysly na v2.0+

---

## v1.2.x -> v1.3.0 - UKONCZONO

Web Search, Transaction Manager, Intent/Command Classification, stabilnosc.

Ukonczone: HTTP 429 + retry/backoff, Transaction Manager z rollbackiem, Web Search (DuckDuckGo/Brave, cache, whitelist, rate limit), Intent Classifier, Command Classifier, walidacja config, nowoczesny panel webowy.

---

## v1.3.x -> v1.4.0 - UKONCZONO

Global Memory, poprawki zachowania agenta.

Ukonczone: Global Memory (`~/.config/ai/memory.json`), `ai memory` CLI, early intercept "zapamietaj ze...", warstwowy PromptBuilder, poprawka "nie pytaj o potwierdzenie" przy jasnym poleceniu.

---

## v1.4.x -> v1.4.7 - UKONCZONO (sesja 2026-03-21)

Poprawki stabilnosci, Smart Config CLI, historia rozmow, eksport sesji.

### Poprawki loggera i audit trail
- [x] `run_id` + `iteration` w operations.jsonl -- grupowanie iteracji jednego polecenia
- [x] Rzetelny `overall_success` -- uwzglednia returncode != 0 i frazy semantyczne ("not found", "command not found") a nie tylko prefix [BLAD]
- [x] Strip markdown fences w responses.jsonl -- model owijal JSON w ```json```, logger to czyscil przed zapisem
- [x] `reset_run()` we wszystkich sciezkach wyjscia agenta

### Poprawki action_executor
- [x] `list_files` respektuje pole `path` -- executor ignorowal path i szukal pattern w cwd projektu zamiast w podanym katalogu
- [x] Limit stdout/stderr 500 -> 4000 znakow (konfigurowalne przez `execution.command_output_limit`)
- [x] Flaga ` ...[ucieto]` gdy output jest obcinany

### Poprawki agent_runner
- [x] Auto-podsumowanie po serii akcji bez wiadomosci -- agent nie milczal po wykonaniu, automatycznie pytal model o podsumowanie
- [x] `command_timeout` i `command_error` dodane do `ANALYSIS_NEEDED` -- agent informuje uzytkownika zamiast milczec po timeoucie

### Poprawki agent_state
- [x] `StagnationDetector` -- fingerprint `list_files` uwzglednia path+pattern, nie tylko typ akcji (eliminuje falszywy exact-cycle przy eksploracji roznych katalogow)

### Poprawki conversation_state
- [x] Kontekst rozmowy przycinany do 300 znakow z cofaniem do ostatniego separatora zdania (bylo 100, ucinalo w pol slowa)

### Smart Config CLI
- [x] `ai config get <klucz>` -- pobierz jedna wartosc
- [x] `ai config set <klucz> <wartosc>` -- ustaw z auto-konwersja typow (bool/int/float/lista JSON)
- [x] `ai config unset <klucz>` -- usun klucz
- [x] `ai config list` -- plaska lista wszystkich kluczy
- [x] Klucze zagniezdzone przez kropke (execution.timeout_seconds, rag.top_k itp.)

### Persystentna historia rozmow
- [x] Zapis historii do `.ai-logs/conversation_history.jsonl` per katalog
- [x] Pytanie o wznowienie przy starcie gdy wykryto poprzednia sesje
- [x] Wybor T/N (domyslnie T) -- N czysci plik i zaczyna od nowa
- [x] Konfiguracja: `conversation.save_history`, `conversation.resume_prompt`, `conversation.max_saved_messages`
- [x] Automatyczne przycinanie pliku do `max_saved_messages`

### Eksport sesji
- [x] `ai export` -- eksport sesji do pliku Markdown (ai-session-YYYY-MM-DD.md)
- [x] `ai export <plik.md>` -- eksport do podanego pliku
- [x] `ai export --all` -- cala historia, nie tylko dzisiejsza
- [x] `ai export --operations` -- tabela operacji z operations.jsonl

### Pozostale
- [x] `--help-all` / `--examples` -- pomoc z przykladami uzycia (oddzielona od zwiezlego --help)
- [x] Wersja 1.4.7, zaktualizowany help
- [x] `action_validator` waliduje pole `path` w `list_files` i dodano hint `{path, pattern} -> list_files`
- [x] `execution.command_output_limit` w schemacie konfiguracji z wartoscia domyslna 4000
- [x] Zaktualizowane knowledge: `o_sobie.md`, nowe pliki `config_klucze.md`, `conversation_history.md`, `bledy_i_limity.md`, `snap_apt_flatpak.md`

---

## v1.4.7 -> v1.5.0 - W TOKU

**Priorytet:** Smart Package Management

### HIGH - Smart Package Management

Zarzadzanie zaleznosciami projektow bezposrednio z CLI agenta.

```bash
ai check dependencies # sprawdz wersje i luki
ai update dependencies # zaktualizuj plik zaleznosci
ai fix dependencies # napraw brakujace importy
```

Obslugiwane menadzzery pakietow:

- [ ] **pip** -- `requirements.txt`, `setup.py`, `setup.cfg`, `pyproject.toml [tool.pip]`
- [ ] **poetry** -- `pyproject.toml [tool.poetry]`, `poetry.lock`
- [ ] **npm** -- `package.json`, `package-lock.json`
- [ ] **yarn** -- `yarn.lock`
- [ ] **pnpm** -- `pnpm-lock.yaml`
- [ ] **cargo** -- `Cargo.toml`, `Cargo.lock`
- [ ] **go modules** -- `go.mod`, `go.sum`
- [ ] **composer** (PHP) -- `composer.json`, `composer.lock`
- [ ] **bundler** (Ruby) -- `Gemfile`, `Gemfile.lock`

Funkcje:

- [ ] `ai check dependencies` -- wykryj menadzzer z pliku projektu, sprawdz aktualne wersje przez PyPI/npm registry/crates.io, porownaj z zainstalowanymi, wykryj CVE przez OSV API (osv.dev)
- [ ] `ai update dependencies` -- zaktualizuj plik zaleznosci do najnowszych zgodnych wersji, zachowaj ograniczenia wersji (^, ~, >=), opcja `--major` dla aktualizacji lamiacych
- [ ] Detekcja brakujacych importow -- przeskanuj pliki zrodlowe (import/require/use), porownaj z lista zaleznosci, zaproponuj dodanie brakujacych
- [ ] Detekcja nieuzywanych zaleznosci -- znajdz pakiety w pliku zaleznosci ktorych nigdzie nie ma w kodzie
- [ ] Cache wersji -- nie pytaj rejestrow czesciej niz raz na godzine (TTL jak web_search)
- [ ] Raport Markdown -- `ai check dependencies --report deps-report.md`

### MEDIUM - Quality of Life

- [ ] WebSocket w panelu (live logs)
- [ ] Auto-cleanup embeddings cache >7 dni
- [ ] Bash completion (`ai <Tab>`)

---

## v1.5.x -> v1.6.0

**Priorytet:** Integracje - Home Assistant + Minecraft

### HIGH - Home Assistant

```bash
ai wlacz swiatlo w sypialni
ai ustaw termostat na 22 stopnie
ai wylacz wszystkie swiatla
```

- [ ] Setup wizard (`ai ha setup`), discovery, entity cache
- [ ] HA API wrapper, natural language -> API calls
- [ ] Confirmations dla krytycznych akcji (zamki, alarm)

### HIGH - Minecraft Server Manager

```bash
ai minecraft setup / start / stop / status
ai zmien max graczy na 10
ai minecraft plugin install EssentialsX
ai minecraft backup create
```

- [ ] Instalacja serwera (Paper/Vanilla/Spigot/Forge)
- [ ] Kontrola via tmux, natural language config
- [ ] Plugin management, backup system

---

## v1.6.x -> v1.7.0

**Priorytet:** Plugin System

```
~/.config/ai/plugins/
+-- my-plugin/
 +-- plugin.json
 +-- actions.py
 +-- requirements.txt
```

- [ ] Plugin loader + registry
- [ ] `ai plugin list/install/enable/disable/create`
- [ ] Capability checking, hook system (before/after execute)
- [ ] Izolacja zaleznosci

---

## v1.7.x -> v1.8.0

**Priorytet:** Workflows + Templates + AI Code Review

- [ ] `ai workflow create/run` - multi-step pipelines
- [ ] `ai template use <n> <dest>` - rozbudowany template system
- [ ] `ai review <plik>` - issues, score, auto-fixes

---

## v1.8.x -> v2.0.0

**Priorytet:** Production Ready

- [ ] Testy automatyczne >80% coverage + CI/CD
- [ ] Security audit (sandboxing, path traversal, key encryption)
- [ ] Pelna dokumentacja (user guide, API docs, FAQ, video)
- [ ] i18n (EN/PL/DE)
- [ ] Team features (shared knowledge base, role-based capabilities)

---

## Future (Post v2.0)

Multi-agent system, voice interface (Whisper + TTS), fine-tuning na wlasnej codebase, mobile app, cloud sync konfiguracji (E2E encrypted), GUI (Electron/Tauri).

---

**Ostatnia aktualizacja:** 2026-03-21 | **Maintainer:** Paffcio
