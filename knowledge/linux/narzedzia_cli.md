# Narzędzia CLI – precyzyjna edycja i analiza plików

Używaj tych komend zamiast przepisywać pliki od zera.
Zasada: najpierw zlokalizuj (grep/sed -n), potem edytuj (sed) albo przekaż dalej (xargs/patch).

---

## sed – wycinanie i edycja fragmentów pliku

```bash
# Pokaż tylko linie 115-145 (bez edycji pliku)
sed -n '115,145p' main.py

# Zamień pierwsze wystąpienie w każdej linii
sed 's/stare/nowe/' plik.txt

# Zamień wszystkie wystąpienia (g = global)
sed 's/stare/nowe/g' plik.txt

# Edycja in-place (zmień plik bezpośrednio)
sed -i 's/stare/nowe/g' plik.txt

# Usuń linie 10-20
sed -i '10,20d' plik.txt

# Wstaw linię po linii nr 5
sed -i '5a\nowa linia tutaj' plik.txt

# Linie z numeracją (połączenie nl + sed)
nl main.py | sed -n '100,140p'
```

---

## awk – operacje na kolumnach i warunkach

```bash
# Wypisz kolumny 1 i 3
awk '{print $1, $3}' plik.txt

# Znajdź "error" + numer linii
awk '/error/ {print NR, $0}' log.txt

# Warunkowe filtrowanie (kolumna 2 > 100)
awk '$2 > 100 {print $0}' dane.txt

# Suma kolumny 3
awk '{sum += $3} END {print sum}' dane.txt

# Separator inny niż spacja (np. CSV)
awk -F',' '{print $1, $2}' plik.csv
```

---

## grep – wyszukiwanie tekstu

```bash
# Szukaj rekurencyjnie we wszystkich plikach w folderze
grep -R "pygame" .

# Znajdź i pokaż numer linii
grep -n "def main" main.py

# Pokaż 5 linii przed i po wyniku
grep -A 5 -B 5 "error" log.txt

# Tylko pasujące pliki (bez zawartości)
grep -rl "import os" .

# Odwróć wynik (linie BEZ wzorca)
grep -v "DEBUG" log.txt

# Wyrażenia regularne
grep -E "def (get|set)_" main.py
```

---

## cut – wycinanie kolumn z tekstu

```bash
# Pierwsza kolumna (separator :)
cut -d':' -f1 /etc/passwd

# Kolumny 1 i 3 (separator ,)
cut -d',' -f1,3 dane.csv

# Wytnij znaki 1-10 z każdej linii
cut -c1-10 plik.txt
```

---

## sort + uniq – liczenie i deduplikacja

```bash
# Policz i posortuj najczęstsze linie
sort log.txt | uniq -c | sort -nr

# Tylko unikalne linie
sort -u plik.txt

# Sortuj po kolumnie 2 numerycznie
sort -k2 -n plik.txt
```

---

## xargs – przekazywanie listy jako argumenty

```bash
# Usuń pliki z listy
cat lista.txt | xargs rm

# Policz linie w plikach .py
find . -name "*.py" | xargs wc -l

# Uruchom komendę dla każdego pliku osobno (-I = placeholder)
find . -name "*.log" | xargs -I{} mv {} /tmp/logi/
```

---

## find – szukanie plików

```bash
# Znajdź duże pliki .py (> 1MB)
find . -name "*.py" -size +1M

# Usuń wszystkie logi
find . -name "*.log" -delete

# Znajdź pliki zmienione ostatnie 24h
find . -mtime -1

# Połączenie z xargs
find . -name "*.py" | xargs grep -l "import pygame"
```

---

## watch – odświeżanie co X sekund

```bash
# Podgląd GPU na żywo (co 1 sekundę)
watch -n 1 nvidia-smi

# Podgląd procesów
watch -n 2 "ps aux | grep python"
```

---

## less – przeglądanie dużych plików

```bash
# Otwórz od linii 120
less +120 main.py

# Pokaż numery linii
less -N main.py
```

Sterowanie w środku:
- `q` – wyjście
- `/tekst` – szukaj
- `n` – następny wynik
- `g` – początek pliku
- `Shift+G` – koniec pliku

---

## tee – zapis + wyświetlanie jednocześnie

```bash
# Pokaż output i zapisz do pliku
python main.py | tee log.txt

# Dołącz do istniejącego pliku
python main.py | tee -a log.txt
```

---

## diff – różnice między plikami

```bash
# Podstawowe różnice
diff file1.py file2.py

# Czytelniejszy format (jak git diff)
diff -u file1.py file2.py

# Różnice katalogów rekurencyjnie
diff -ur katalog1/ katalog2/
```

---

## tr – zmiana znaków

```bash
# Zamiana na małe litery
echo "ABC" | tr 'A-Z' 'a-z'

# Usuń znaki nowej linii
cat plik.txt | tr -d '\n'

# Zamień spacje na podkreślniki
echo "hello world" | tr ' ' '_'
```

---

## Strategia edycji pliku (bez przepisywania od zera)

Gdy użytkownik prosi o zmianę/dodanie/naprawienie fragmentu kodu:

1. **Zlokalizuj** – `grep -n "nazwa_funkcji" plik.py` → znajdź numer linii
2. **Podejrzyj kontekst** – `sed -n '50,80p' plik.py` → sprawdź otoczenie
3. **Edytuj precyzyjnie** – `sed -i 's/stare/nowe/g' plik.py` dla prostych zamian
4. **Dla złożonych zmian** – użyj `diff -u` żeby wygenerować patch i zastosować `patch -p0 < zmiany.patch`
5. **Zweryfikuj** – `grep -n "nowa_wartość" plik.py` → potwierdź zmianę

Nie przepisuj pliku od zera jeśli zmieniasz mniej niż 30% zawartości.
