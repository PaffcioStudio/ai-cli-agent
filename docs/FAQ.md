# FAQ - Najczęstsze pytania

## Ogólne

### Czym różni się AI CLI od ChatGPT / Claude w przeglądarce?

AI CLI działa lokalnie (lub z lokalnym Ollama), ma pełny dostęp do systemu plików projektu, wykonuje komendy w terminalu, pamięta kontekst projektu między sesjami i daje Ci pełną kontrolę nad tym co robi. Nie jest to chatbot - to asystent operatorski.

### Czy AI CLI może zepsuć mi pliki?

Każda modyfikacja pliku jest objęta Transaction Managerem - jeśli cokolwiek pójdzie nie tak, zmiany są automatycznie cofane. Dodatkowo dla operacji destrukcyjnych zawsze wymagane jest potwierdzenie, a `rm -rf /` jest absolutnie zablokowane.

### Czy mogę używać AI CLI bez Ollamy?

Nie - Ollama jest wymagana jako backend. Możesz jednak używać modeli cloud przez Ollama (np. `qwen3-coder:480b-cloud`) jeśli masz dostęp.

### Czy działa na Windows?

Projekt jest pisany z myślą o Linuxie/macOS. Na Windows może działać przez WSL2.

---

## Instalacja i konfiguracja

### Jak sprawdzić czy Ollama działa?

```bash
curl http://localhost:11434/api/tags
# lub
ollama list
```

Jeśli Ollama nie odpowiada: `ollama serve`

### Jak zmienić model?

```bash
ai model
# Interaktywne menu wyboru modeli
```

Lub przez CLI (zalecane):

```bash
ai config set chat_model qwen2.5-coder:14b
```

Albo recznie w `~/.config/ai/config.json`:

```json
{
 "chat_model": "qwen2.5-coder:14b"
}
```

### Jaki model jest polecany?

Dla kodu: `qwen2.5-coder:14b` (lokalne 9GB RAM) lub `qwen3-coder:480b-cloud` (cloud). 
Dla embeddingów (RAG): `nomic-embed-text-v2-moe:latest`.

### Jak zresetować konfigurację?

```bash
rm ~/.config/ai/config.json
ai config # Tworzy nową konfigurację
```

---

## Użytkowanie

### Agent pyta o potwierdzenie przy każdej operacji - jak to wyłączyć?

Dla bezpiecznych komend (read, find, grep):

```json
{
 "execution": {
 "auto_confirm_safe_commands": true
 }
}
```

Dla małych modyfikacji (np. do 3 plików jednocześnie):

```json
{
 "execution": {
 "auto_confirm_modify_under": 3
 }
}
```

Uwaga: operacje DESTRUCTIVE (delete, move) zawsze wymagają confirm - to jest celowe.

### Agent ciągle pyta "czy mam to zrobić?" zamiast robić

Upewnij się że prompt systemowy zawiera zasadę "nie pytaj o potwierdzenie gdy dostałem jasne polecenie". Edytuj:

```bash
ai prompt # Otwiera nano z ~/.config/ai/prompt.txt
```

### Jak ograniczyć agenta żeby nie usuwał plików?

```bash
ai capability disable allow_delete
```

Zapis w `.ai-context.json` - per-projekt.

### Jak sprawdzić co agent ostatnio robił?

```bash
ai audit # Ostatnie decyzje z intencjami
ai history # Historia poleceń
ai logs # Surowe logi
```

### Jak wyczyścić pamięć projektu?

```bash
rm .ai-context.json
ai init # Stwórz nowy
```

### Jak wyczyścić globalną pamięć (zapamiętane fakty)?

```bash
ai memory clear
```

---

## Problemy

### "Nie można połączyć się z Ollamą"

1. Sprawdź czy Ollama działa: `ollama list`
2. Uruchom jeśli nie: `ollama serve`
3. Sprawdź config: `ai config` (host, port)
4. Sprawdź firewall jeśli Ollama jest na innym hoście

### "Model zwrócił pustą odpowiedź"

- Spróbuj przeformułować pytanie
- Sprawdź czy model jest załadowany: `ollama ps`
- Sprawdź logi: `ai logs`

### "Błąd parsowania JSON"

Agent nie mógł zdekodować odpowiedzi modelu. Plik błędnej odpowiedzi zapisany w `.ai-failed-response.txt`. Spróbuj z innym modelem lub dodaj do promptu: `ai prompt`.

### Cache embeddingów rośnie bez ograniczeń

```bash
du -sh ~/.cache/ai-cli/embeddings/
rm -rf ~/.cache/ai-cli/embeddings/ # Wyczyść - zostanie przebudowany przy użyciu
```

### Web search nie działa

```bash
ai web-search status # Sprawdź zależności i konfigurację
pip install requests beautifulsoup4 html2text --break-system-packages
ai web-search enable
```

### yt-dlp nie pobiera

```bash
# Sprawdź wersję
yt-dlp --version

# Zaktualizuj
pip install -U yt-dlp --break-system-packages
# lub
sudo apt install yt-dlp
```

---

## Panel webowy

### Panel nie uruchamia się

```bash
ai panel status
ai panel start
# Sprawdź logi systemd:
journalctl -u ai-panel -n 50
```

### Jak zmienić port panelu?

Edytuj `web/server.py` (zmienna `PORT`) i `web/ai-panel.service`.

---

## Historia rozmow i eksport

### Jak AI pamietac na czym skonczylismy rozmowe?

Historia rozmow jest zapisywana do `.ai-logs/conversation_history.jsonl` per katalog projektu.
Przy nastepnym uruchomieniu `ai` w tym samym katalogu pojawi sie pytanie:

```
► Znaleziono historie rozmowy  (2026-03-21 18:47)
  Ostatnie: "na czym skonczylismy?"

Czy wznowic poprzednia rozmowe?  [T/n]
```

T (lub Enter) wczytuje kontekst poprzedniej sesji. N czysci i zaczyna od nowa.

Wylaczenie pytania:

```bash
ai config set conversation.resume_prompt false
```

Wylaczenie zapisu historii:

```bash
ai config set conversation.save_history false
```

### Jak eksportowac sesje do Markdown?

```bash
ai export                    # dzisiejsza sesja -> ai-session-YYYY-MM-DD.md
ai export raport.md          # eksport do podanego pliku
ai export --all              # cala historia (nie tylko dzisiejsza)
ai export --operations       # + tabela operacji z operations.jsonl
```

### Jak zmienic ustawienia konfiguracji bez edycji pliku JSON?

```bash
ai config set execution.timeout_seconds 60
ai config set rag.top_k 12
ai config set web_search.enabled true
ai config get execution.command_output_limit
ai config list    # plaska lista wszystkich kluczy
ai config unset web_search.brave_api_key
```

Klucze zagniezdzone uzywaja kropki. Typy sa konwertowane automatycznie (true/false, liczby, listy JSON).

---

## Bezpieczeństwo

### Czy AI CLI wysyła mój kod gdzieś?

Jeśli używasz modelu lokalnego (Ollama bez `:cloud`) - nie, nic nie opuszcza komputera. Przy modelach cloud (`:cloud` suffix) zapytania trafiają do zewnętrznego API.

### Czy mogę używać AI CLI w repozytorium produkcyjnym?

Tak, ale zalecane środki ostrożności:

```bash
ai capability disable allow_execute
ai capability disable allow_delete
ai capability disable allow_git
```

Wtedy agent może tylko czytać i tworzyć pliki.

### Co to jest `.ai-context.json`?

Plik z metadanymi projektu (typ, tech stack, capabilities, historia). **Nie powinien trafić do repozytorium** - dodaj do `.gitignore`:

```
.ai-context.json
.ai-logs/
.ai-failed-response.txt
```
