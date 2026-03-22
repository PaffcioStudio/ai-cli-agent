# Python – Popularne biblioteki i kiedy ich używać

Plik dla AI: gdy użytkownik prosi o dobór biblioteki, szukaj tutaj. Podaj uzasadnienie wyboru i alternatywy.

## HTTP i Web Scraping

### requests
Najpopularniejsza biblioteka HTTP. Używaj do: API REST, pobieranie stron, wysyłanie formularzy.
```python
import requests
r = requests.get('https://api.example.com/data', headers={'Authorization': 'Bearer TOKEN'})
r.raise_for_status()   # rzuć wyjątek przy 4xx/5xx
data = r.json()

# Session (reużywa połączenie TCP, szybsze przy wielu requestach)
session = requests.Session()
session.headers.update({'Authorization': 'Bearer TOKEN'})
r = session.get('https://api.example.com/users')
```

### httpx
Nowoczesna alternatywa dla requests. Używaj gdy potrzebujesz: async/await, HTTP/2, type hints.
```python
import httpx
# Sync
with httpx.Client() as client:
    r = client.get('https://api.example.com')

# Async
async with httpx.AsyncClient() as client:
    r = await client.get('https://api.example.com')
```

### aiohttp
Async HTTP klient i serwer. Używaj do: masowego pobierania (100+ requestów równolegle).
```python
import aiohttp, asyncio
async def fetch_all(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [session.get(url) for url in urls]
        responses = await asyncio.gather(*tasks)
        return [await r.json() for r in responses]
```

### BeautifulSoup4 (bs4)
Parsowanie HTML/XML. Używaj do: web scraping statycznych stron.
```python
from bs4 import BeautifulSoup
soup = BeautifulSoup(html_content, 'html.parser')
title = soup.find('h1').text
links = [a['href'] for a in soup.find_all('a', href=True)]
```

### playwright / selenium
Automatyzacja przeglądarki. Używaj do: scraping dynamicznych stron (JS), testy e2e.
playwright – nowszy, szybszy, lepszy API. selenium – starszy, więcej zasobów online.
```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('https://example.com')
    content = page.content()
    browser.close()
```

## Dane i Analiza

### pandas
Analiza i manipulacja danych tabelarycznych. Absolutna podstawa data science.
```python
import pandas as pd
df = pd.read_csv('data.csv')
df = pd.read_excel('data.xlsx')
df.head() / df.info() / df.describe()
df[df['wiek'] > 18]                   # filtrowanie
df.groupby('miasto')['sprzedaz'].sum() # groupby
df.merge(df2, on='id', how='left')     # join
df.to_csv('wynik.csv', index=False)
```

### polars
Szybsza alternatywa dla pandas (Rust pod spodem). Używaj gdy: duże pliki (>1GB), potrzebujesz wydajności.
```python
import polars as pl
df = pl.read_csv('data.csv')
result = df.filter(pl.col('wiek') > 18).groupby('miasto').agg(pl.col('sprzedaz').sum())
```

### numpy
Obliczenia numeryczne, tablice wielowymiarowe. Podstawa całego ekosystemu data science.
```python
import numpy as np
arr = np.array([1, 2, 3, 4, 5])
arr.mean() / arr.std() / arr.reshape(5, 1)
np.zeros((3, 4)) / np.ones((3, 4)) / np.random.rand(3, 4)
```

### matplotlib / seaborn
Wykresy i wizualizacja. matplotlib – niskopoziomowy, pełna kontrola. seaborn – wyższy poziom, ładniejszy domyślnie.
```python
import matplotlib.pyplot as plt
plt.plot(x, y, label='dane')
plt.title('Tytuł') / plt.xlabel('X') / plt.ylabel('Y')
plt.legend() / plt.savefig('wykres.png') / plt.show()

import seaborn as sns
sns.heatmap(df.corr(), annot=True)
sns.boxplot(x='kategoria', y='wartość', data=df)
```

### SQLAlchemy
ORM i narzędzie do baz danych. Używaj do: dowolnej relacyjnej bazy (PostgreSQL, SQLite, MySQL).
```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import DeclarativeBase, Session

engine = create_engine('postgresql://user:pass@localhost/mydb')
# lub SQLite: create_engine('sqlite:///local.db')

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))

Base.metadata.create_all(engine)
with Session(engine) as session:
    session.add(User(name='Jan'))
    session.commit()
    users = session.query(User).filter(User.name == 'Jan').all()
```

## API i Web Frameworki

### FastAPI
Najlepszy framework do budowania API. Używaj do: REST API, microservices, backend aplikacji.
Automatyczna dokumentacja Swagger, type hints, async.
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str
    price: float

@app.get('/items/{item_id}')
async def get_item(item_id: int):
    return {'id': item_id, 'name': 'example'}

@app.post('/items/')
async def create_item(item: Item):
    return item

# Uruchom: uvicorn main:app --reload
```

### Flask
Lekki framework web. Używaj do: proste API, małe aplikacje webowe, szybki prototyp.
FastAPI jest zazwyczaj lepszym wyborem dla nowych projektów.
```python
from flask import Flask, jsonify, request
app = Flask(__name__)

@app.route('/api/data', methods=['GET', 'POST'])
def data():
    if request.method == 'POST':
        return jsonify(request.json), 201
    return jsonify({'status': 'ok'})
```

### Django
Full-stack framework. Używaj do: duże aplikacje webowe z adminem, ORM, auth, szablonami.
Zbyt duży overhead dla prostych API – wtedy lepszy FastAPI.

### pydantic
Walidacja danych i settings. Używaj wszędzie gdzie masz dane przychodzące z zewnątrz.
```python
from pydantic import BaseModel, EmailStr, validator
from typing import Optional

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    age: int

    @validator('age')
    def age_must_be_positive(cls, v):
        if v < 0:
            raise ValueError('wiek musi być dodatni')
        return v

user = UserCreate(name='Jan', email='jan@example.com', age=25)
```

## Automatyzacja i Narzędzia Systemowe

### pathlib
Operacje na ścieżkach (wbudowana). Używaj zamiast os.path.
```python
from pathlib import Path
p = Path('/home/user/documents')
p.exists() / p.is_file() / p.is_dir()
p.mkdir(parents=True, exist_ok=True)
p.read_text(encoding='utf-8') / p.write_text('content')
list(p.glob('*.py'))               # pliki .py
list(p.rglob('*.md'))              # rekurencyjnie
p.parent / p.stem / p.suffix / p.name
new_path = p / 'subdir' / 'plik.txt'
```

### subprocess
Uruchamianie komend systemowych (wbudowana).
```python
import subprocess
result = subprocess.run(['ls', '-la'], capture_output=True, text=True)
print(result.stdout)

# Shell command (ostrożnie z user input!)
result = subprocess.run('grep -r "error" logs/', shell=True, capture_output=True, text=True)

# Sprawdź kod wyjścia
result.returncode  # 0 = sukces
result.check_returncode()  # rzuć wyjątek jeśli != 0
```

### schedule
Planowanie zadań w Pythonie. Używaj do: cykliczne zadania bez cron.
```python
import schedule, time
schedule.every(10).minutes.do(job)
schedule.every().hour.do(job)
schedule.every().day.at('10:30').do(job)
while True:
    schedule.run_pending()
    time.sleep(1)
```

### python-dotenv
Wczytywanie zmiennych z pliku .env.
```python
from dotenv import load_dotenv
import os
load_dotenv()  # wczytaj .env z bieżącego katalogu
db_url = os.getenv('DATABASE_URL', 'sqlite:///default.db')
```

### loguru
Lepszy logging niż standardowy logging. Prosta konfiguracja, kolorowe logi, rotacja.
```python
from loguru import logger
logger.info('Start aplikacji')
logger.warning('Ostrzeżenie: {value}', value=42)
logger.error('Błąd: {}', err)
logger.add('app.log', rotation='10 MB', retention='30 days', level='WARNING')
```

### rich
Bogate formatowanie w terminalu: tabele, progress bary, kolory, syntax highlighting.
```python
from rich.console import Console
from rich.table import Table
from rich.progress import track

console = Console()
console.print('[bold green]Sukces![/]')
console.print_json(json_string)

# Progress bar
for item in track(items, description='Przetwarzam...'):
    process(item)

# Tabela
table = Table(title='Wyniki')
table.add_column('Nazwa') / table.add_column('Wartość')
table.add_row('test', '42')
console.print(table)
```

### click / typer
Budowanie CLI. click – sprawdzony. typer – oparty na type hints, nowszy.
```python
import typer
app = typer.Typer()

@app.command()
def main(name: str, count: int = 1, verbose: bool = False):
    for _ in range(count):
        typer.echo(f'Hello {name}')

if __name__ == '__main__':
    app()
# Użycie: python script.py Jan --count 3 --verbose
```

## Testowanie

### pytest
Standard testowania w Python. Używaj zawsze zamiast unittest.
```python
# test_myfunc.py
import pytest
from mymodule import divide

def test_divide_normal():
    assert divide(10, 2) == 5

def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)

@pytest.fixture
def sample_user():
    return {'name': 'Jan', 'age': 25}

def test_user_name(sample_user):
    assert sample_user['name'] == 'Jan'
```

```bash
pytest                          # uruchom wszystkie testy
pytest -v                       # verbose
pytest -k 'test_divide'         # tylko pasujące
pytest --cov=mymodule           # pokrycie kodu
```

### unittest.mock
Mockowanie w testach (wbudowana).
```python
from unittest.mock import patch, MagicMock
with patch('mymodule.requests.get') as mock_get:
    mock_get.return_value.json.return_value = {'id': 1}
    result = my_function()
    assert result == {'id': 1}
```

## Parsowanie i Formaty Danych

### pyyaml
Parsowanie YAML.
```python
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)  # zawsze safe_load, nie load
yaml.dump(data, default_flow_style=False)
```

### tomllib / tomli
Parsowanie TOML (tomllib wbudowana od Python 3.11).
```python
import tomllib
with open('pyproject.toml', 'rb') as f:
    config = tomllib.load(f)
```

### python-dateutil
Parsowanie dat w różnych formatach.
```python
from dateutil.parser import parse
d = parse('2024-01-15')
d = parse('January 15, 2024')
d = parse('15/01/2024')
```

### arrow
Nowoczesna praca z datami i strefami czasowymi.
```python
import arrow
now = arrow.now()
utc = arrow.utcnow()
shifted = now.shift(hours=+3, days=-1)
formatted = now.format('YYYY-MM-DD HH:mm:ss')
```

## Kryptografia i Bezpieczeństwo

### cryptography
Solidna biblioteka kryptograficzna.
```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
f = Fernet(key)
token = f.encrypt(b'secret message')
message = f.decrypt(token)
```

### passlib
Hashowanie haseł. Używaj do: przechowywania haseł użytkowników.
```python
from passlib.hash import bcrypt
hashed = bcrypt.hash('hasło_użytkownika')
bcrypt.verify('hasło_użytkownika', hashed)  # True/False
```

### python-jose / PyJWT
Tokeny JWT.
```python
import jwt
token = jwt.encode({'user_id': 123, 'exp': datetime(2025,1,1)}, 'secret', algorithm='HS256')
payload = jwt.decode(token, 'secret', algorithms=['HS256'])
```

## Kolejki i Async

### celery
Kolejka zadań. Używaj do: background tasks (wysyłanie maili, długie obliczenia).
```python
from celery import Celery
app = Celery('tasks', broker='redis://localhost/0')

@app.task
def send_email(to, subject, body):
    # długotrwałe zadanie w tle
    pass

# Wywołanie
send_email.delay('user@example.com', 'Temat', 'Treść')
send_email.apply_async(args=[...], countdown=60)  # z opóźnieniem
```

### asyncio
Wbudowana biblioteka async. Używaj do: I/O bound tasks (nie CPU).
```python
import asyncio

async def fetch(url):
    await asyncio.sleep(1)  # symulacja I/O
    return f'data from {url}'

async def main():
    results = await asyncio.gather(
        fetch('url1'), fetch('url2'), fetch('url3')
    )
    return results

asyncio.run(main())
```

## Obrazy i Media

### Pillow (PIL)
Podstawowe operacje na obrazach.
```python
from PIL import Image
img = Image.open('photo.jpg')
img = img.resize((800, 600))
img = img.convert('RGB')
img.save('wynik.jpg', quality=85)
img.thumbnail((300, 300))  # proporcjonalne zmniejszenie
```

### opencv-python (cv2)
Zaawansowane przetwarzanie obrazów i wideo.
```python
import cv2
img = cv2.imread('photo.jpg')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
cv2.imwrite('gray.jpg', gray)
# Wideo
cap = cv2.VideoCapture(0)  # kamera
ret, frame = cap.read()
```

## Kiedy NIE używać danej biblioteki

requests zamiast urllib – zawsze używaj requests lub httpx, urllib jest zbyt niskopoziomowe
pickle do serializacji danych zewnętrznych – nigdy, ryzyko RCE; używaj json lub msgpack
exec()/eval() z danymi użytkownika – nigdy, ryzyko RCE
xml.etree z danymi zewnętrznymi – użyj defusedxml (ochrona przed XXE)
