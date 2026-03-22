# Czytanie plików różnych typów

Nie używaj `cat` na ślepo. Dobierz narzędzie do formatu pliku.

---

## Dispatch – co używać dla danego formatu

| Rozszerzenie              | Pierwsze narzędzie                            |
|---------------------------|-----------------------------------------------|
| `.pdf`                    | `pdfinfo` + `pdftotext`; NIE cat             |
| `.docx`                   | `pandoc plik.docx -t markdown \| head -200`   |
| `.xlsx` / `.xlsm`         | Python + openpyxl (read_only=True)            |
| `.xls` (stary)            | `pd.read_excel(engine="xlrd")`                |
| `.pptx`                   | Python + python-pptx                          |
| `.csv` / `.tsv`           | `pd.read_csv(nrows=5)` – NIE head             |
| `.json`                   | `jq type` + `jq keys`                         |
| `.jsonl`                  | `head -3 plik.jsonl \| jq .`                  |
| `.zip` / `.tar` / `.gz`   | lista zawartości, NIE auto-extract            |
| `.epub` / `.odt`          | `pandoc plik -t plain \| head -200`           |
| `.txt` / `.md` / `.log`   | `wc -c` → decyzja; < 20KB = cat; > 20KB = head/tail/grep |
| nieznane                  | `file plik` + `xxd plik \| head -5`           |

---

## PDF

```bash
pdfinfo plik.pdf
pdftotext -f 1 -l 1 plik.pdf - | head -20
```

```python
from pypdf import PdfReader
r = PdfReader("plik.pdf")
print(f"{len(r.pages)} stron")
print(r.pages[0].extract_text()[:2000])
```

---

## XLSX / XLS

```python
from openpyxl import load_workbook
wb = load_workbook("dane.xlsx", read_only=True)
print("Arkusze:", wb.sheetnames)
ws = wb.active
for row in ws.iter_rows(max_row=5, values_only=True):
    print(row)
```

Stary `.xls`:
```python
import pandas as pd
df = pd.read_excel("stary.xls", engine="xlrd", nrows=5)
```

---

## CSV

```python
import pandas as pd
df = pd.read_csv("dane.csv", nrows=5)
print(df)
print(df.dtypes)
```

Przybliżona liczba wierszy (szybko):
```bash
wc -l dane.csv
```

---

## JSON / JSONL

```bash
# Sprawdź typ i klucze
jq 'type' dane.json
jq 'if type == "array" then length elif type == "object" then keys else . end' dane.json

# JSONL – linia po linii
head -3 dane.jsonl | jq .
wc -l dane.jsonl
```

---

## Archiwum ZIP / TAR

```bash
# Najpierw lista – nigdy nie wypakowuj bez pytania
unzip -l bundle.zip
tar -tf bundle.tar

# Wypakuj jeden konkretny plik
unzip -p bundle.zip ścieżka/w/archiwum/plik.txt

# Standalone .gz (nie tar)
zcat dane.json.gz | head -50
```

---

## Logi i duże pliki tekstowe

```bash
# Sprawdź rozmiar
wc -c plik.log

# < 20KB – cat w porządku
# > 20KB – najpierw koniec (zwykle to co najważniejsze)
tail -200 plik.log

# Szukaj konkretnego błędu
grep -n "ERROR\|CRITICAL" plik.log | tail -20
```

---

## Obrazy

Obrazy `.jpg`, `.png`, `.gif`, `.webp` przesłane przez użytkownika są
dostępne jako wizualne wejście do modelu — nie trzeba ich czytać z dysku.
Disk path potrzebny tylko przy programatycznym przetwarzaniu:

```python
from PIL import Image
img = Image.open("foto.jpg")
print(img.size, img.mode)
```

---

## Zasada ogólna

- Sprawdź rozmiar przed czytaniem (`stat` lub `wc -c`)
- Czytaj tyle ile potrzeba, nie całość
- `cat` na binarnym pliku = garbage output
- `head` na CSV z embedded newlines w polach = błędny wynik → używaj pandas z `nrows`
