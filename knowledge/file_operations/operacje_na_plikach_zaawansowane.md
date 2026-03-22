# Zaawansowane operacje na plikach – wzorce dla AI CLI

## Szybkie znajdowanie plików

```bash
find . -name "*.py" -type f                      # pliki .py rekurencyjnie
find . -name "*.log" -mtime +7 -delete           # usuń logi starsze niż 7 dni
find . -size +100M                               # pliki większe niż 100MB
find . -name "*.py" -newer requirements.txt      # nowsze niż plik referencyjny
find . -type f -empty                            # puste pliki
find . -type d -empty                            # puste katalogi
find /home -user username                        # pliki konkretnego użytkownika
find . -name "*.py" -exec grep -l "import os" {} \;  # pliki zawierające wzorzec
```

## grep – szukanie w treści

```bash
grep -r "szukana fraza" .                        # rekurencyjnie
grep -rn "funkcja" . --include="*.py"            # z numerami linii
grep -rl "TODO" .                                # tylko nazwy plików
grep -v "komentarz" plik.txt                     # wiersze NIE zawierające
grep -A3 -B3 "błąd" log.txt                     # 3 linie kontekstu przed i po
grep -E "error|warning|critical" app.log         # wyrażenie regularne
grep -i "Error" plik.txt                         # case-insensitive
grep -c "wzorzec" plik.txt                       # ile pasujących linii
```

## sed – edycja w miejscu

```bash
sed -i 's/stara_fraza/nowa_fraza/g' plik.txt    # zamień wszystkie wystąpienia
sed -i 's/stara/nowa/g' *.txt                    # w wielu plikach naraz
sed -n '10,20p' plik.txt                         # wyświetl linie 10-20
sed -i '/wzorzec/d' plik.txt                     # usuń linie z wzorcem
sed -i '1s/^/# Nagłówek\n/' plik.txt            # wstaw linię na początku
sed -n '/START/,/KONIEC/p' plik.txt              # wydrukuj między znacznikami

# Bezpieczna edycja z backupem
sed -i.bak 's/stare/nowe/g' plik.txt            # .bak = backup oryginału
```

## awk – przetwarzanie kolumn i pól

```bash
awk '{print $1}' plik.txt                        # pierwsza kolumna
awk -F: '{print $1}' /etc/passwd                 # rozdzielnik : (użytkownicy)
awk '{sum += $2} END {print sum}' dane.txt       # suma drugiej kolumny
awk 'NR==5' plik.txt                             # tylko linia 5
awk 'NR>=10 && NR<=20' plik.txt                  # linie 10-20
awk '/wzorzec/ {print NR": "$0}' plik.txt        # z numerami linii dla wzorca
awk '{print NF}' plik.txt                        # liczba pól w każdej linii
awk 'length > 80' plik.txt                       # linie dłuższe niż 80 znaków
```

## Masowe operacje na plikach

```bash
# Zmiana rozszerzenia wszystkich plików
for f in *.txt; do mv "$f" "${f%.txt}.md"; done

# Dodaj prefix do nazw plików
for f in *.jpg; do mv "$f" "2024_$f"; done

# Normalizacja nazw (małe litery, spacje → podkreślenia)
for f in *; do mv "$f" "$(echo $f | tr '[:upper:]' '[:lower:]' | tr ' ' '_')"; done

# Batch resize obrazów (ImageMagick)
for img in *.jpg; do convert "$img" -resize 800x600 "resized/$img"; done

# Kopiuj strukturę katalogów bez plików
find . -type d | cpio -pd /cel/katalog
```

## rsync – synchronizacja i kopiowanie

```bash
rsync -av source/ dest/                          # kopiuj z info
rsync -av --delete source/ dest/                 # usuń pliki nieobecne w source
rsync -av --exclude='*.log' --exclude='node_modules' source/ dest/
rsync -avz user@host:/zdalne/ ./lokalne/         # z serwera (z kompresją)
rsync -avz --progress ./lokalne/ user@host:/zdalne/  # na serwer z progresem
rsync -av --dry-run source/ dest/                # podgląd bez wykonania
```

## Archiwa

```bash
# tar
tar -czf archiwum.tar.gz katalog/               # utwórz .tar.gz
tar -xzf archiwum.tar.gz                        # rozpakuj
tar -xzf archiwum.tar.gz -C /cel/              # do konkretnego miejsca
tar -tzf archiwum.tar.gz                        # lista zawartości
tar -czf backup.tar.gz --exclude='*.log' .      # z wykluczeniem

# zip
zip -r archiwum.zip katalog/
zip -r archiwum.zip katalog/ -x "*.git*"
unzip archiwum.zip -d /cel/
unzip -l archiwum.zip                           # lista zawartości
```

## Porównywanie plików i katalogów

```bash
diff plik1.txt plik2.txt
diff -u plik1.txt plik2.txt                     # unified format (czytelny)
diff -r katalog1/ katalog2/                     # katalogi rekurencyjnie
diff -rq katalog1/ katalog2/                    # tylko nazwy różnych plików
vimdiff plik1.txt plik2.txt                     # wizualny diff w vimie
```

## Uprawnienia i własność

```bash
chmod 755 skrypt.sh                             # rwxr-xr-x
chmod 644 plik.txt                              # rw-r--r--
chmod +x skrypt.sh                              # dodaj prawo wykonania
chmod -R 755 katalog/                           # rekurencyjnie
chown user:group plik.txt
chown -R user:group katalog/
find . -type f -exec chmod 644 {} \;            # ustaw 644 na wszystkich plikach
find . -type d -exec chmod 755 {} \;            # ustaw 755 na wszystkich katalogach
```

## Monitorowanie zmian w plikach

```bash
tail -f /var/log/syslog                         # śledź log live
tail -f app.log | grep -v DEBUG                 # filtruj na bieżąco
watch -n 2 'ls -la /tmp/'                       # odśwież co 2s
inotifywait -m -r -e modify,create,delete ./    # zdarzenia na FS (wymaga inotify-tools)
```

## Duże pliki – analiza miejsca

```bash
du -sh *                                        # rozmiary w bieżącym katalogu
du -sh * | sort -rh | head -20                  # 20 największych
du -sh /home/*                                  # rozmiary katalogów domowych
ncdu /                                          # interaktywny eksplorator (apt install ncdu)
df -h                                           # wolne miejsce na partycjach
ls -lhS                                         # pliki posortowane po rozmiarze
```

## Wzorce bezpiecznej edycji pliku (Python)

```python
import shutil
from pathlib import Path

def safe_write(path: Path, content: str):
    """Zapisz plik z backupem – nie trać danych przy błędzie."""
    backup = path.with_suffix(path.suffix + '.bak')
    if path.exists():
        shutil.copy2(path, backup)
    try:
        path.write_text(content, encoding='utf-8')
        backup.unlink(missing_ok=True)
    except Exception:
        if backup.exists():
            shutil.move(str(backup), str(path))
        raise

def atomic_write(path: Path, content: str):
    """Atomowy zapis – zamień plik jednym ruchem (bez okna uszkodzenia)."""
    tmp = path.with_suffix('.tmp')
    tmp.write_text(content, encoding='utf-8')
    tmp.replace(path)  # atomowe na tym samym FS
```
