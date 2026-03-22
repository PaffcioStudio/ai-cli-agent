# AI CLI — błędy, limity i zachowanie agenta

## Stagnacja (zapętlenie)

Agent wykrywa zapętlenie i zatrzymuje się gdy:
- Te same akcje powtarzają się ≥2 razy z rzędu (exact cycle)
- ≥4 iteracje bez żadnej modyfikacji pliku (no-progress)
- ≥3 iteracje samych odczytów bez zapisu (read-only loop)

Komunikat: `⚠ Wykryto zapętlenie: Exact cycle detected…`

Co zrobić: przeformułuj polecenie bardziej konkretnie, podaj ścieżkę bezpośrednio.

## Limit iteracji

Domyślnie max 8 iteracji na jedno polecenie. Po przekroczeniu:
```
(osiągnięto limit 8 iteracji)
```

Zmiana:
```bash
# Nie ma bezpośredniego klucza config — limit jest w kodzie (agent_state.py)
# Obejście: rozbij zadanie na mniejsze polecenia
```

## Limit akcji w jednej rundzie

```bash
ai config set behavior.max_actions_per_run 10   # domyślnie 10
```

Gdy model zaproponuje więcej akcji niż limit — pyta o potwierdzenie.

## Timeout komend

```bash
ai config set execution.timeout_seconds 120     # domyślnie 120s
```

Po timeoucie zwracany jest `command_timeout` — agent informuje użytkownika
i może zaproponować ponowienie lub alternatywę.

## Ucięty output komend

```bash
ai config set execution.command_output_limit 4000  # domyślnie 4000 znaków
```

Gdy stdout jest ucięty, w wyniku pojawia się ` …[ucięto]`. Zwiększ limit
jeśli komendy generują długi output (np. `find` z setkami wyników).

## Rollback transakcji

Gdy jedna z akcji w batchu się nie powiedzie, agent może cofnąć pozostałe
(rollback). Dotyczy tylko operacji na plikach (create, edit, patch, delete, move).

Komendy bash (`run_command`) są **nieodwracalne** — rollback ich nie cofa.

Komunikat po rollbacku:
```
⚠ Operacja nie powiodła się (rollback) — patrz błędy powyżej.
```

## Poziomy ryzyka akcji i potwierdzenia

| Poziom | Akcje | Kiedy wymaga potwierdzenia |
|---|---|---|
| SAFE | read_file, list_files, semantic_search | Nigdy |
| MODIFY | create_file, edit_file, patch_file, mkdir | Gdy >3 pliki lub wyłączone auto_confirm |
| DESTRUCTIVE | delete_file, move_file | Zawsze |
| EXECUTE | run_command, download_media | Zależy od komendy (read-only = auto) |

## Sukces vs niepowodzenie akcji

Akcja jest oznaczona jako niepowodzenie (`success: false`) gdy:
- Wynik zaczyna się od `[BŁĄD]`
- `returncode != 0` (dla run_command)
- stdout/stderr zawiera: "nie znaleziono", "not found", "error", "failed", "command not found"

Sama komenda może zwrócić exit 0 ale semantycznie zawieść (np. grep zwraca
"Nie znaleziono przez snap" jako fallback echo). Logger wykrywa to i oznacza
`success: false` mimo exit 0.

## Brak odpowiedzi po serii akcji

Jeśli agent wykonał akcje ale nie zwrócił wiadomości tekstowej, automatycznie
wysyła rundę podsumowującą. Nie trzeba pisać "i co?" — agent sam podsumuje.

## Błędy JSON od modelu

Model czasem zwraca JSON owinięty w markdown fences (` ```json ``` `).
Parser automatycznie to czyści. Jeśli to się powtarza, sygnalizuje że model
ignoruje instrukcje — rozważ zmianę na inny model lub zwiększ temperaturę.

## Fałszywy cykl przy przeglądaniu katalogów

`list_files` dla różnych katalogów nie powoduje wykrycia cyklu — fingerprint
uwzględnia zarówno ścieżkę jak i wzorzec (`/Pobrane/*.mp4` ≠ `/Wideo/*.mp4`).

## Kiedy agent milczy

Możliwe przyczyny gdy AI nie odpowiada:
1. Timeout połączenia z Ollama — sprawdź `ai config get ollama_host`
2. Model załadowany zbyt długo — poczekaj lub sprawdź `ollama ps`
3. Pusta odpowiedź modelu — zobaczysz `Model zwrócił pustą odpowiedź`
4. Błąd parsowania JSON — zobaczysz `Błąd parsowania JSON`

Diagnostyka:
```bash
ai logs                         # podsumowanie błędów
cat ~/.cache/ai-cli/logs/errors.log
ai config set debug.log_level debug    # więcej logów
```
