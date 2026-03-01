# Bezpieczeństwo

## Priorytety decyzyjne

Od najwyższego:

1. **Kod aplikacji (Python)** — zawsze nadrzędny nad promptem
2. **Capabilities** (`.ai-context.json`) — twarde ograniczenia per-projekt
3. **Flagi CLI** (`--plan`, `--dry-run`, `--yes`)
4. **Config** (`~/.config/ai/config.json`)
5. **System prompt** (`~/.config/ai/prompt.txt`)

## Poziomy ryzyka akcji

| Poziom | Akcje | Domyślne zachowanie |
|--------|-------|---------------------|
| **SAFE** | `read_file`, `list_files`, `semantic_search` | Wykonane bez pytania |
| **MODIFY** | `create_file`, `edit_file`, `mkdir`, `chmod` | Pytanie jeśli ≥ N plików |
| **DESTRUCTIVE** | `delete_file`, `move_file` | ZAWSZE pytanie |
| **EXECUTE** | `run_command` (modify), `download_media`, `convert_media` | ZAWSZE pytanie |

### Wyjątek: READ_ONLY commands

Komendy bash takie jak `find`, `grep`, `ls`, `cat`, `du`, `wc`, `diff` są klasyfikowane jako `READ_ONLY` przez `CommandClassifier` i wykonywane bez potwierdzenia nawet jeśli należą do kategorii EXECUTE.

Konfiguracja:

```json
{
  "execution": {
    "auto_confirm_safe_commands": true
  }
}
```

## Capability Manager

Kontrola dozwolonych typów akcji **per-projekt**:

```bash
ai capability list                    # Pokaż status
ai capability disable allow_execute  # Blokuj komendy bash
ai capability disable allow_delete   # Blokuj usuwanie
ai capability disable allow_git      # Blokuj git (przyszłe)
ai capability disable allow_network  # Blokuj sieć (przyszłe)
```

Gdy AI spróbuje naruszenia:

```
✗ Akcje naruszają ograniczenia projektu:
  • Akcja #1 (run_command): Capability 'allow_execute' wyłączone

Aby włączyć:
  ai capability enable allow_execute
```

## Blokady destrukcyjne (hardcoded)

Niezależnie od uprawnień, zawsze zablokowane:

**Absolutna blokada** — `rm -rf /` lub `rm -rf ~`

**Blokada kontekstualna** — destrukcyjna komenda bez ścieżki absolutnej gdy:
- CWD == katalog domowy + globy (`*`, `.`)
- CWD poza katalogiem projektu

Aby wykonać taką operację, podaj jawną ścieżkę absolutną lub wykonaj ją ręcznie w terminalu.

## Transaction Manager

Każda modyfikacja pliku jest objęta transakcją:

```
snapshot pliku → modyfikacja → [błąd?] → rollback
                             → [ok?]   → commit
```

Gwarancje:
- Albo WSZYSTKIE pliki w zadaniu są zmodyfikowane
- Albo ŻADNA zmiana nie zostaje

Snapshoty przechowywane tymczasowo w `<projekt>/.ai-tx/` i usuwane po commit.

## Audit trail

Każda operacja jest logowana w `<projekt>/.ai-logs/operations.jsonl`:

```json
{
  "timestamp": "2026-02-28T15:42:00",
  "user": "Paffcio",
  "command": "napraw błędy w app.py",
  "intent": "modify",
  "actions": [
    {"type": "edit_file", "path": "app.py", "success": true}
  ],
  "overall_success": true
}
```

```bash
ai audit  # Czytelny widok ostatnich decyzji
```

## Tryb dry-run i plan

```bash
ai --dry-run usuń stare logi    # Symulacja bez zmian FS
ai --plan stwórz API w Express  # Tylko plan, zero akcji
```

W dry-run: operacje FS są symulowane (pokazują co by się stało), komendy bash **nie są** wykonywane.

## Zalecenia dla repozytoriów produkcyjnych

```bash
# Wyłącz ryzykowne capability
ai capability disable allow_execute
ai capability disable allow_delete
ai capability disable allow_git

# Dodaj do .gitignore
echo ".ai-context.json" >> .gitignore
echo ".ai-logs/" >> .gitignore
echo ".ai-failed-response.txt" >> .gitignore
```

## Web Search — bezpieczeństwo

- Domyślnie WYŁĄCZONY
- Whitelist domen — tylko preapproved
- Max 1MB na stronę, timeout 10s
- Brak wykonywania scraped kodu/JavaScript
- Rate limit: 10 zapytań/minutę

## Modele cloud

Jeśli używasz modeli z suffixem `:cloud`, zapytania trafiają do zewnętrznego API (Ollama Cloud). Zawartość plików projektu przekazywana w kontekście może być transmitowana. Dla projektów z poufnym kodem rozważ modele lokalne.
