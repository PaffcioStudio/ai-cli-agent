# PDF – Tworzenie, odczyt i manipulacja plikami PDF

Plik dla AI: gdy użytkownik prosi o stworzenie PDF, odczytanie go, połączenie, podzielenie, dodanie watermarku lub cokolwiek związanego z plikami `.pdf` — szukaj tutaj. Używaj systemowego Pythona (`python3`), instaluj biblioteki przez `pip3 install --break-system-packages` lub w venv projektu.

## Które biblioteki do czego

| Zadanie | Biblioteka | Instalacja |
|---|---|---|
| Tworzenie PDF od zera | `reportlab` | `pip3 install reportlab --break-system-packages` |
| Ekstrakcja tekstu / tabel | `pdfplumber` | `pip3 install pdfplumber --break-system-packages` |
| Łączenie, dzielenie, obrót | `pypdf` | `pip3 install pypdf --break-system-packages` |
| OCR zeskanowanych PDF | `pytesseract` + `pdf2image` | `pip3 install pytesseract pdf2image --break-system-packages` |
| Profesjonalne dokumenty | `reportlab` (Platypus) | j.w. |

---

## Tworzenie PDF – reportlab

### Prosty PDF z tekstem (Canvas)
```python
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

c = canvas.Canvas("wyjscie.pdf", pagesize=A4)
width, height = A4

c.setFont("Helvetica", 14)
c.drawString(50, height - 80, "Tytuł dokumentu")
c.setFont("Helvetica", 11)
c.drawString(50, height - 110, "Treść pierwszego akapitu.")

# Linia pozioma
c.line(50, height - 120, width - 50, height - 120)

# Nowa strona
c.showPage()
c.drawString(50, height - 80, "Strona 2")

c.save()
```

### Profesjonalny dokument wielostronicowy (Platypus)
```python
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm

doc = SimpleDocTemplate(
    "raport.pdf",
    pagesize=A4,
    rightMargin=2*cm, leftMargin=2*cm,
    topMargin=2*cm, bottomMargin=2*cm
)
styles = getSampleStyleSheet()
story = []

# Tytuł
story.append(Paragraph("Raport miesięczny", styles['Title']))
story.append(Spacer(1, 0.5*cm))

# Paragraf
story.append(Paragraph("Treść raportu tutaj. Długi tekst zostanie automatycznie zawinięty.", styles['Normal']))
story.append(Spacer(1, 0.3*cm))

# Tabela
data = [
    ["Kolumna A", "Kolumna B", "Kolumna C"],
    ["Wiersz 1",  "100",       "200"],
    ["Wiersz 2",  "300",       "400"],
]
tabela = Table(data, colWidths=[6*cm, 4*cm, 4*cm])
tabela.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.grey),
    ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
    ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
    ('GRID',       (0,0), (-1,-1), 0.5, colors.black),
    ('ALIGN',      (1,0), (-1,-1), 'CENTER'),
]))
story.append(tabela)

# Nowa strona
story.append(PageBreak())
story.append(Paragraph("Strona 2", styles['Heading1']))

doc.build(story)
```

### WAŻNE – polskie znaki w reportlab

Domyślne czcionki (Helvetica, Times) **nie obsługują polskich znaków**. Są dwa sposoby:

**Sposób 1 – użyj czcionki TTF z systemu (zalecane):**
```python
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# Znajdź czcionkę na systemie Linux
ttf_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
if not os.path.exists(ttf_path):
    for p in ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
              "/usr/share/fonts/TTF/DejaVuSans.ttf"]:
        if os.path.exists(p):
            ttf_path = p
            break

pdfmetrics.registerFont(TTFont('DejaVu', ttf_path))

c = canvas.Canvas("polski.pdf", pagesize=A4)
c.setFont("DejaVu", 12)
c.drawString(50, 700, "Zażółć gęślą jaźń – polskie znaki działają!")
c.save()
```

**Sposób 2 – transliteracja (szybki workaround jeśli brak TTF):**
```python
tekst = tekst.encode('latin-1', errors='replace').decode('latin-1')
```

### Indeksy górne i dolne (sub/superscript)
NIGDY nie używaj znaków Unicode (₀₁₂, ⁰¹²) — renderują się jako czarne prostokąty. Używaj tagów XML w `Paragraph`:
```python
# Indeks dolny
Paragraph("H<sub>2</sub>O", styles['Normal'])

# Indeks górny
Paragraph("x<super>2</super> + y<super>2</super>", styles['Normal'])
```

---

## Odczyt i ekstrakcja tekstu – pdfplumber

```python
import pdfplumber

with pdfplumber.open("dokument.pdf") as pdf:
    for i, strona in enumerate(pdf.pages):
        print(f"=== Strona {i+1} ===")
        print(strona.extract_text())
```

### Ekstrakcja tabel z PDF
```python
import pdfplumber
import pandas as pd

with pdfplumber.open("dokument.pdf") as pdf:
    wszystkie_tabele = []
    for strona in pdf.pages:
        tabele = strona.extract_tables()
        for tabela in tabele:
            if tabela:
                df = pd.DataFrame(tabela[1:], columns=tabela[0])
                wszystkie_tabele.append(df)

if wszystkie_tabele:
    wynik = pd.concat(wszystkie_tabele, ignore_index=True)
    wynik.to_excel("tabele.xlsx", index=False)
```

---

## Łączenie i dzielenie – pypdf

### Łączenie wielu PDF w jeden
```python
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()
for plik in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
    reader = PdfReader(plik)
    for strona in reader.pages:
        writer.add_page(strona)

with open("polaczony.pdf", "wb") as f:
    writer.write(f)
```

### Podział PDF na osobne strony
```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("wejscie.pdf")
for i, strona in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(strona)
    with open(f"strona_{i+1}.pdf", "wb") as f:
        writer.write(f)
```

### Obrót stron
```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("wejscie.pdf")
writer = PdfWriter()
for strona in reader.pages:
    strona.rotate(90)  # 90, 180 lub 270 stopni
    writer.add_page(strona)

with open("obrocony.pdf", "wb") as f:
    writer.write(f)
```

### Watermark (znak wodny)
```python
from pypdf import PdfReader, PdfWriter

watermark = PdfReader("watermark.pdf").pages[0]
reader = PdfReader("dokument.pdf")
writer = PdfWriter()

for strona in reader.pages:
    strona.merge_page(watermark)
    writer.add_page(strona)

with open("z_watermarkiem.pdf", "wb") as f:
    writer.write(f)
```

---

## OCR – zeskanowane PDF

```python
# Wymaga: pip3 install pytesseract pdf2image --break-system-packages
# Na systemie: sudo apt install tesseract-ocr tesseract-ocr-pol poppler-utils
import pytesseract
from pdf2image import convert_from_path

obrazy = convert_from_path('skan.pdf')
tekst = ""
for i, obraz in enumerate(obrazy):
    tekst += f"=== Strona {i+1} ===\n"
    # lang='pol' dla polskiego, 'eng' dla angielskiego
    tekst += pytesseract.image_to_string(obraz, lang='pol')
    tekst += "\n\n"

print(tekst)
```

---

## Instalacja i środowisko

### Instalacja systemowa (bez venv)
```bash
pip3 install reportlab pdfplumber pypdf --break-system-packages
```

### Instalacja w venv projektu
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install reportlab pdfplumber pypdf
```

### Dodaj do requirements.txt projektu
```
reportlab
pdfplumber
pypdf
```

### Sprawdzenie czy biblioteki są dostępne
```python
try:
    import reportlab
    import pdfplumber
    import pypdf
    print("Wszystkie biblioteki PDF dostępne")
except ImportError as e:
    print(f"Brakuje: {e}")
    print("Uruchom: pip3 install reportlab pdfplumber pypdf --break-system-packages")
```

---

## Typowe błędy

**`ModuleNotFoundError: No module named 'reportlab'`**
→ `pip3 install reportlab --break-system-packages`

**Polskie znaki wyglądają jako `?` lub `[]`**
→ Użyj czcionki TTF (DejaVu lub Liberation) jak opisano wyżej.

**`externally-managed-environment` przy pip**
→ Dodaj `--break-system-packages` do komendy pip3.

**OCR nie rozpoznaje polskiego**
→ `sudo apt install tesseract-ocr-pol` i `lang='pol'` w pytesseract.
