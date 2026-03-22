# Historia rozmów — persystentna pamięć sesji

## Problem który rozwiązuje

Bez historii rozmów: po zamknięciu terminala (Ctrl+C, Ctrl+Q, exit) cały
kontekst rozmowy znika. Przy kolejnym uruchomieniu AI nie wie "na czym
skończyliśmy" i odpowiada "to nowa sesja, nie pamiętam".

Z historią rozmów: AI pyta czy wznowić poprzednią sesję i wczytuje kontekst.

## Jak to działa

Historia zapisywana jest do `.ai-logs/conversation_history.jsonl` w katalogu
projektu. Każda linia = jedna wiadomość w formacie JSON:

```json
{"role": "user", "content": "znajdź pliki mp4", "timestamp": "2026-03-21T18:47:52"}
{"role": "assistant", "content": "Znalazłem 3 pliki...", "timestamp": "2026-03-21T18:47:55"}
```

Historia jest **per katalog** — każdy projekt/katalog ma swoją osobną historię.

## Pytanie przy starcie

Gdy w katalogu istnieje historia z poprzedniej sesji:

```
► Znaleziono historię rozmowy  (2026-03-21 18:47)
  Ostatnie: "znajdź czy mam gdzieś jakieś porno na dysku…"

Czy wznowić poprzednią rozmowę?  [T/n]
```

- **T lub Enter** (domyślne) → wczytuje ostatnie `max_saved_messages` wiadomości
  do pamięci sesji, AI może się odwoływać do poprzedniej rozmowy
- **N** → usuwa plik historii, zaczyna od zera

## Ustawienia

```bash
# Włącz/wyłącz zapis historii do pliku
ai config set conversation.save_history true
ai config set conversation.save_history false

# Włącz/wyłącz pytanie o wznowienie przy starcie
ai config set conversation.resume_prompt true
ai config set conversation.resume_prompt false

# Ile wiadomości trzymać (starsze są automatycznie usuwane)
ai config set conversation.max_saved_messages 40
```

## Gdzie są pliki historii

```
<projekt>/.ai-logs/conversation_history.jsonl
```

Można podejrzeć ręcznie:
```bash
cat .ai-logs/conversation_history.jsonl | python3 -m json.tool
```

Lub wyeksportować do czytelnego Markdown:
```bash
ai export              # dzisiejsza sesja
ai export --all        # cała historia
```

## Różnica między historią a pamięcią globalną

| | Historia rozmów | Pamięć globalna |
|---|---|---|
| Zasięg | Per katalog/projekt | Wszędzie |
| Co trzyma | Całe dialogi user↔AI | Konkretne fakty |
| Jak dodać | Automatycznie | `ai memory add` lub auto-ekstrakcja |
| Plik | `.ai-logs/conversation_history.jsonl` | `~/.config/ai/memory.json` |
| Przy starcie | Pytanie o wznowienie | Wstrzykiwane zawsze |

## Ograniczenia

- Historia nie jest wysyłana do modelu w całości — tylko ostatnie
  `max_saved_messages` wiadomości są wczytywane do `ConversationState`
- `ConversationState` dodatkowo przycina do `max_history` (domyślnie 10)
  — stare wiadomości wypadają z kontekstu modelu ale zostają w pliku
- Historia **nie zastępuje** pamięci projektu (`ProjectMemory`) —
  ta nadal trzyma decyzje, edytowane pliki, statystyki projektu
