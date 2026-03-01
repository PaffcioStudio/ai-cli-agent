# Python – Przydatne wzorce, narzędzia i dobre praktyki

## Środowisko wirtualne

```bash
python3 -m venv .venv               # utwórz środowisko wirtualne
source .venv/bin/activate           # aktywuj (Linux/Mac)
.venv\Scripts\activate              # aktywuj (Windows)
deactivate                          # dezaktywuj
pip install -r requirements.txt     # zainstaluj zależności
pip freeze > requirements.txt       # zapisz aktualne zależności
pip list                            # lista zainstalowanych pakietów
pip show pakiet                     # informacje o pakiecie
pip install --upgrade pip           # aktualizuj pip
```

## Zarządzanie pakietami z pip

```bash
pip install requests                # zainstaluj pakiet
pip install requests==2.28.0        # konkretna wersja
pip install "requests>=2.28"        # minimalna wersja
pip install -e .                    # zainstaluj w trybie edycji (development)
pip uninstall pakiet                # odinstaluj pakiet
pip cache purge                     # wyczyść cache pip
```

## Typy danych i struktury

```python
# Listy
lista = [1, 2, 3]
lista.append(4)
lista.extend([5, 6])
lista.insert(0, 0)
lista.remove(3)
lista.pop()                         # usuwa i zwraca ostatni element
len(lista)
sorted(lista)
lista[::-1]                         # odwróć listę

# Słowniki
d = {"klucz": "wartość"}
d.get("klucz", "domyślna")         # bezpieczne pobieranie
d.items()                           # pary (klucz, wartość)
d.keys()
d.values()
{k: v for k, v in d.items() if v > 0}  # słownikowe rozumienie

# Zbiory (set)
s = {1, 2, 3}
s.add(4)
s.discard(1)                        # usuwa bez błędu jeśli brak
s1 & s2                             # część wspólna
s1 | s2                             # suma
s1 - s2                             # różnica
```

## Obsługa plików

```python
# Odczyt
with open("plik.txt", "r", encoding="utf-8") as f:
    zawartość = f.read()

with open("plik.txt", "r", encoding="utf-8") as f:
    for linia in f:
        print(linia.strip())

# Zapis
with open("plik.txt", "w", encoding="utf-8") as f:
    f.write("treść\n")

with open("plik.txt", "a", encoding="utf-8") as f:
    f.write("dopisz\n")

# JSON
import json
with open("dane.json", "r", encoding="utf-8") as f:
    dane = json.load(f)

with open("dane.json", "w", encoding="utf-8") as f:
    json.dump(dane, f, ensure_ascii=False, indent=2)
```

## Ścieżki plików (pathlib)

```python
from pathlib import Path

p = Path(".")
p = Path("/home/user/projekt")

p.exists()                          # czy istnieje?
p.is_file()
p.is_dir()
p.parent                            # katalog nadrzędny
p.name                              # nazwa pliku
p.stem                              # nazwa bez rozszerzenia
p.suffix                            # rozszerzenie (.txt)
p / "podkatalog" / "plik.txt"       # łączenie ścieżek
p.mkdir(parents=True, exist_ok=True)  # utwórz katalogi
list(p.glob("*.py"))                # lista plików .py
list(p.rglob("*.py"))               # rekurencyjnie
p.read_text(encoding="utf-8")       # odczyt
p.write_text("treść", encoding="utf-8")  # zapis
```

## Klasy i dziedziczenie

```python
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class Osoba:
    imie: str
    nazwisko: str
    wiek: int = 0
    tagi: List[str] = field(default_factory=list)

    @property
    def pelne_imie(self) -> str:
        return f"{self.imie} {self.nazwisko}"

    def __repr__(self) -> str:
        return f"Osoba({self.imie} {self.nazwisko}, {self.wiek})"
```

## Obsługa wyjątków

```python
try:
    wynik = 10 / 0
except ZeroDivisionError as e:
    print(f"Błąd: {e}")
except (ValueError, TypeError) as e:
    print(f"Błąd wartości: {e}")
except Exception as e:
    print(f"Nieznany błąd: {e}")
    raise  # ponownie rzuć wyjątek
else:
    print("Sukces")  # tylko gdy brak wyjątku
finally:
    print("Zawsze się wykona")
```

## Wyrażenia generatorowe i rozumienia list

```python
# List comprehension
kwadraty = [x**2 for x in range(10) if x % 2 == 0]

# Generator (pamięć oszczędna)
gen = (x**2 for x in range(10000))

# Dict comprehension
d = {k: v for k, v in zip(klucze, wartosci)}

# Set comprehension
s = {x % 5 for x in range(20)}
```

## Dekoratory

```python
import functools, time

def mierz_czas(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        wynik = func(*args, **kwargs)
        print(f"{func.__name__}: {time.time() - start:.4f}s")
        return wynik
    return wrapper

@mierz_czas
def moja_funkcja():
    time.sleep(0.5)
```

## Logowanie (logging)

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.debug("Debugowanie")
logger.info("Informacja")
logger.warning("Ostrzeżenie")
logger.error("Błąd")
logger.exception("Błąd z traceback")  # tylko w bloku except
```

## Przydatne wbudowane funkcje

```python
enumerate(lista)                    # indeks + wartość
zip(lista1, lista2)                 # parowanie list
map(func, lista)                    # zastosuj funkcję
filter(func, lista)                 # filtruj według funkcji
any([True, False])                  # czy jakaś wartość jest True?
all([True, True])                   # czy wszystkie są True?
max(lista), min(lista)
sum(lista)
sorted(lista, key=lambda x: x[1], reverse=True)
```
