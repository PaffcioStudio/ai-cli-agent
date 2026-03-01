# Precyzyjna nawigacja i edycja plików kodu

## Wzorzec 1 — sed do podglądu fragmentu po numerze linii

Gdy znasz zakres linii lub chcesz zobaczyć konkretny fragment bez ładowania całego pliku:

```bash
sed -n '230,250p' ui_layer/commands.py
sed -n '1266,1310p' core/agent.py
sed -n '1,30p' main.py         # pierwsze 30 linii
tail -20 main.py               # ostatnie 20 linii
```

Użycie w run_command:
```json
{"type": "run_command", "command": "sed -n '230,250p' /home/user/projekt/ui_layer/commands.py"}
```

Kiedy używać: duży plik (>200 linii), znasz zakres linii, chcesz oszczędzić tokeny.

---

## Wzorzec 2 — grep + kontekst do znajdowania funkcji i definicji

Znajdź funkcję i wyświetl N linii po niej:

```bash
# -n = numery linii, -A N = N linii po dopasowaniu
grep -n "def interactive_model_selection" core/model_manager.py -A 50 | head -80

# Przez cat (gdy chcesz podejrzeć wynik od razu)
cat core/model_manager.py | grep -n "interactive_model_selection" -A 50 | head -80

# Znajdź wszystkie definicje funkcji i klas
grep -n "^def \|^class " core/agent.py

# Szukaj wzorca rekurencyjnie w całym projekcie
grep -rn "spinner_start" . --include="*.py"

# Znajdź i pokaż kontekst wokół (B = linie przed, A = linie po)
grep -n "cmd_model" ui_layer/commands.py -B 2 -A 10
```

Złożony przykład — znajdź funkcję i wytnij jej zakres:
```bash
# 1. Znajdź numer startowy linii funkcji
grep -n "def cmd_knowledge" ui_layer/commands.py
# Wynik: 798:def cmd_knowledge(...)

# 2. Wyświetl od linii 798 przez 80 linii
sed -n '798,878p' ui_layer/commands.py
```

---

## Wzorzec 3 — Python heredoc do złożonych zamian w plikach

Gdy zamiana zawiera wieloliniowy tekst z wcięciami, apostrofami i znakami specjalnymi — Python jest niezawodny tam gdzie sed/awk zawodzi:

```bash
cd /ścieżka/do/projektu && python3 << 'PYEOF'
content = open('main.py').read()

old = '''    flags = [
        "--dry-run", "--plan",
        "--quiet", "-q",
    ]'''

new = '''    flags = [
        "--dry-run", "--plan",
        "--quiet", "-q",
        "--index",
        "--reindex",
    ]'''

content = content.replace(old, new, 1)   # ,1 = tylko pierwsze wystąpienie
open('main.py', 'w').write(content)
print('OK')
PYEOF
```

Zasady:
- `'PYEOF'` (w apostrofach) = heredoc NIE interpretuje zmiennych basha, bezpieczne
- `.replace(old, new, 1)` — zawsze podaj `1` żeby nie podmienić przypadkowych duplikatów
- Wcięcia w `old` muszą dokładnie zgadzać się z plikiem (spacje, taby)
- Sprawdź zawartość pliku przed zamianą: `grep -n "flags = \[" main.py`

Weryfikacja po zamianie:
```bash
cd /projekt && python3 << 'PYEOF'
content = open('main.py').read()
# Sprawdź czy zamiana się powiodła
if '--index' in content:
    print('OK - flaga dodana')
else:
    print('BŁĄD - nie znaleziono')
PYEOF
```

---

## Wzorzec 4 — sed -i do prostych zamian w miejscu

```bash
# Zamień pierwsze wystąpienie w każdej linii
sed -i 's/stary_tekst/nowy_tekst/' plik.py

# Zamień wszystkie wystąpienia (flaga g)
sed -i 's/stary/nowy/g' plik.py

# Usuń konkretną linię
sed -i '42d' plik.py

# Wstaw linię przed linią 42
sed -i '42i\nowa linia tutaj' plik.py

# Zamień linię 42 nową treścią
sed -i '42s/.*/nowa zawartość linii/' plik.py

# Usuń linie pasujące do wzorca
sed -i '/wzorzec_do_usuniecia/d' plik.py
```

---

## Kiedy co używać

| Sytuacja | Narzędzie |
|----------|-----------|
| Chcę zobaczyć linie 100-200 dużego pliku | `sed -n '100,200p'` |
| Szukam gdzie jest funkcja `def foo` | `grep -n "def foo"` |
| Chcę zobaczyć funkcję i jej ciało | `grep -n "def foo" plik -A 40 | head -50` |
| Prosta zamiana 1 linii | `sed -i 's/stare/nowe/'` lub `edit_file` |
| Zamiana wieloliniowego bloku z wcięciami | Python heredoc |
| Wiele zmian naraz w dużym pliku | `patch_file` z `patches` listą |
| Nowy plik | `create_file` |

---

## Przykład flow — debugowanie i naprawa dużego pliku

```bash
# Krok 1: znajdź gdzie jest błąd
grep -n "interactive_model_selection\|KeyboardInterrupt" core/model_manager.py

# Krok 2: obejrzyj fragment
sed -n '200,220p' core/model_manager.py

# Krok 3: napraw przez Python heredoc (bezpieczna zamiana wieloliniowa)
cd /home/user/.local/share/ai-cli-agent && python3 << 'PYEOF'
content = open('core/model_manager.py').read()
old = '''    # Pobierz modele raz
    ui.spinner_start("Pobieranie listy modeli...")
    try:
        models = manager.get_available_models()
        ui.spinner_stop()
    except ConnectionError as e:'''
new = '''    # Pobierz modele raz
    try:
        ui.spinner_start("Pobieranie listy modeli...")
        models = manager.get_available_models()
        ui.spinner_stop()
    except KeyboardInterrupt:
        ui.spinner_stop()
        return
    except ConnectionError as e:'''
assert old in content, "BŁĄD: fragment nie znaleziony - sprawdź wcięcia"
content = content.replace(old, new, 1)
open('core/model_manager.py', 'w').write(content)
print('OK')
PYEOF

# Krok 4: weryfikuj
sed -n '200,220p' core/model_manager.py
```
