# PyInstaller i Pygame – pełna wiedza praktyczna

## PyInstaller – pakowanie aplikacji Python do .exe/.bin

PyInstaller zamraża aplikację Python w jeden wykonywalny plik lub katalog. Działa na Windows, Linux, macOS. NIE kompiluje do natywnego kodu – dołącza interpreter Pythona i wszystkie zależności.

### Instalacja i podstawy

```bash
pip install pyinstaller

# Buduj z jednego pliku głównego
pyinstaller main.py

# Jeden plik .exe (wolniejszy start, wygodniejszy)
pyinstaller --onefile main.py

# Bez okna konsoli (dla GUI apps)
pyinstaller --onefile --windowed main.py

# Z ikoną
pyinstaller --onefile --windowed --icon=assets/icon.ico main.py

# Z nazwą
pyinstaller --onefile --name MojaAplikacja main.py
```

Po budowaniu:
- `dist/` – gotowy plik wykonywalny lub katalog
- `build/` – pliki tymczasowe (możesz usunąć)
- `*.spec` – plik konfiguracyjny (możesz edytować i używać ponownie)

```bash
pyinstaller main.spec                # buduj z pliku spec
pyinstaller --clean main.spec        # wyczyść cache przed budowaniem
```

### Plik .spec – pełna kontrola

```python
# main.spec
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets/', 'assets'),          # kopiuj katalog assets
        ('config.yaml', '.'),           # kopiuj plik do katalogu głównego
        ('templates/', 'templates'),    # szablony Jinja2 itp.
    ],
    hiddenimports=[
        'pkg_resources.py2_compat',     # często potrzebne
        'PySide6.QtSvg',                # moduły Qt które nie są auto-wykrywane
        'sqlalchemy.dialects.sqlite',   # dialekty baz danych
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'email', 'xml'],  # zmniejsz rozmiar
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MojaAplikacja',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                          # kompresja UPX (zmniejsza rozmiar)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                     # True = okno konsoli, False = bez konsoli
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)
```

### Dostęp do zasobów (assets) w spakowanej aplikacji

KRYTYCZNE: ścieżki względne nie działają w spakowanej aplikacji. Użyj tego wzorca:

```python
import sys
from pathlib import Path

def get_resource_path(relative_path: str) -> Path:
    """Zwraca ścieżkę do zasobu – działa zarówno w dev jak i po PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        # Uruchomiony przez PyInstaller – zasoby w tymczasowym katalogu
        base_path = Path(sys._MEIPASS)
    else:
        # Normalny tryb deweloperski
        base_path = Path(__file__).parent
    return base_path / relative_path

# Użycie
icon_path = get_resource_path('assets/icon.png')
config_path = get_resource_path('config.yaml')
```

### Typowe problemy i rozwiązania

Problem: brakujące moduły (ModuleNotFoundError po pakowaniu)
Przyczyna: PyInstaller nie wykrył dynamicznie importowanych modułów
Fix: dodaj do hiddenimports w .spec lub użyj --hidden-import na CLI
```bash
pyinstaller --hidden-import=modul --hidden-import=inny_modul main.py
```

Problem: brakujące pliki danych (FileNotFoundError)
Fix: dodaj do datas w .spec, użyj get_resource_path()

Problem: antywirus blokuje .exe
Przyczyna: PyInstaller .exe są często fałszywie oznaczane
Fix: podpisz cyfrowo (kosztuje), użyj Nuitka zamiast PyInstaller, lub poinformuj użytkownika

Problem: duży rozmiar pliku (100MB+)
Fix: wirtualne środowisko tylko z potrzebnymi pakietami, lista excludes w .spec
```bash
# Utwórz czysty venv tylko dla pakowania
python -m venv build_venv
source build_venv/bin/activate
pip install tylko_potrzebne_pakiety
pip install pyinstaller
pyinstaller --onefile main.py
```

Problem: wolny start (--onefile)
Przyczyna: --onefile rozpakowuje się do /tmp przy każdym uruchomieniu
Fix: użyj --onedir (katalog zamiast jednego pliku) – szybszy start

Problem: moduły PySide6/PyQt6 nie działają
Fix: dodaj wszystkie używane moduły Qt do hiddenimports
```python
hiddenimports=[
    'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
    'PySide6.QtNetwork', 'PySide6.QtSql',
]
```

### Alternatywy dla PyInstaller

Nuitka – kompiluje do C, mniejszy plik, szybszy, ale dłuższy czas kompilacji
```bash
pip install nuitka
python -m nuitka --standalone --onefile --windows-disable-console main.py
```

cx_Freeze – podobny do PyInstaller, lepsza integracja z setuptools
PyOxidizer – kompiluje z interpretorem w Rust, bardzo szybki start

### Automatyczny build skrypt

```bash
#!/bin/bash
# build.sh
set -e
echo "Czyszczenie..."
rm -rf build dist

echo "Budowanie..."
pyinstaller \
    --onefile \
    --windowed \
    --name "MojaAplikacja" \
    --icon "assets/icon.ico" \
    --add-data "assets:assets" \
    --add-data "config.yaml:." \
    main.py

echo "Gotowe: dist/MojaAplikacja"
ls -lh dist/
```

---

## Pygame – tworzenie gier i grafiki 2D

Pygame to biblioteka do gier 2D w Pythonie. Obsługuje: okno, grafikę, dźwięk, klawiaturę, mysz, gamepad.

### Instalacja i minimalna gra

```bash
pip install pygame
# lub nowsza wersja:
pip install pygame-ce     # pygame Community Edition (szybsza, aktywniej rozwijana)
```

```python
import pygame
import sys

# Inicjalizacja
pygame.init()
pygame.mixer.init()        # dźwięk

# Stałe
WIDTH, HEIGHT = 800, 600
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (220, 50, 50)
BLUE = (50, 100, 220)

# Okno
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption('Moja Gra')
clock = pygame.time.Clock()

# Pętla główna
running = True
while running:
    # 1. Obsługa zdarzeń
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

    # 2. Logika gry
    keys = pygame.key.get_pressed()

    # 3. Rysowanie
    screen.fill(BLACK)
    pygame.draw.rect(screen, RED, (100, 100, 50, 50))
    pygame.draw.circle(screen, BLUE, (400, 300), 30)

    # 4. Wyświetl i utrzymaj FPS
    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()
```

### Sprite – obiektowy wzorzec

```python
class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((40, 40), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (50, 200, 50), (0, 0, 40, 40), border_radius=6)
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 300         # piksele na sekundę
        self.vel = pygame.math.Vector2(0, 0)

    def update(self, dt):
        # dt = czas od ostatniej klatki w sekundach (clock.tick(FPS) / 1000)
        keys = pygame.key.get_pressed()
        self.vel.x = (keys[pygame.K_d] - keys[pygame.K_a]) * self.speed
        self.vel.y = (keys[pygame.K_s] - keys[pygame.K_w]) * self.speed
        self.rect.centerx += self.vel.x * dt
        self.rect.centery += self.vel.y * dt
        # Trzymaj w ekranie
        self.rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))

class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((30, 30))
        self.image.fill((220, 50, 50))
        self.rect = self.image.get_rect(center=(x, y))

# Grupy sprite
all_sprites = pygame.sprite.Group()
enemies = pygame.sprite.Group()
player = Player(400, 300)
all_sprites.add(player)

for i in range(5):
    e = Enemy(100 + i * 120, 100)
    all_sprites.add(e)
    enemies.add(e)

# W pętli głównej:
dt = clock.tick(FPS) / 1000.0       # delta time w sekundach
all_sprites.update(dt)

# Detekcja kolizji
hits = pygame.sprite.spritecollide(player, enemies, False)
if hits:
    print('Kolizja!')

all_sprites.draw(screen)
```

### Ładowanie zasobów

```python
# Obrazy
img = pygame.image.load('assets/player.png').convert_alpha()  # convert_alpha() = szybsze
img = pygame.transform.scale(img, (64, 64))
img = pygame.transform.rotate(img, 90)

# Dźwięki
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
sound = pygame.mixer.Sound('assets/jump.wav')
sound.set_volume(0.5)
sound.play()
sound.play(-1)             # loop (-1 = nieskończenie)

# Muzyka
pygame.mixer.music.load('assets/music.ogg')
pygame.mixer.music.set_volume(0.3)
pygame.mixer.music.play(-1)  # loop
pygame.mixer.music.stop()

# Czcionki
font = pygame.font.Font(None, 36)          # domyślna czcionka, rozmiar 36
font = pygame.font.Font('assets/font.ttf', 24)
text_surface = font.render('Score: 100', True, WHITE)
screen.blit(text_surface, (10, 10))
```

### Kamera – podążanie za graczem

```python
class Camera:
    def __init__(self, width, height):
        self.offset = pygame.math.Vector2(0, 0)
        self.width = width
        self.height = height

    def update(self, target):
        # Wyśrodkuj kamerę na graczu
        self.offset.x = target.rect.centerx - WIDTH // 2
        self.offset.y = target.rect.centery - HEIGHT // 2

    def apply(self, sprite):
        return sprite.rect.move(-self.offset.x, -self.offset.y)

# W pętli rysowania:
camera = Camera(MAP_WIDTH, MAP_HEIGHT)
camera.update(player)
for sprite in all_sprites:
    screen.blit(sprite.image, camera.apply(sprite))
```

### Tilemap z Tiled (.tmx)

```bash
pip install pytmx
```

```python
import pytmx
tmx_data = pytmx.load_pygame('maps/level1.tmx')

# Rysuj warstwy
for layer in tmx_data.visible_layers:
    if hasattr(layer, 'data'):
        for x, y, image in layer.tiles():
            screen.blit(image, (x * tmx_data.tilewidth, y * tmx_data.tileheight))
```

### Particle system – prosty wzorzec

```python
import random

class Particle:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = random.uniform(-100, 100)
        self.vy = random.uniform(-200, -50)
        self.life = 1.0                  # 1.0 = pełna, 0.0 = martwa
        self.color = (255, 200, 50)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 200 * dt              # grawitacja
        self.life -= dt * 2

    def draw(self, surface):
        if self.life > 0:
            radius = int(5 * self.life)
            alpha = int(255 * self.life)
            color = (*self.color, alpha)
            surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (radius, radius), radius)
            surface.blit(surf, (int(self.x) - radius, int(self.y) - radius))

particles = []
# Dodawaj cząsteczki: particles.extend([Particle(x, y) for _ in range(20)])
# W update: particles = [p for p in particles if p.life > 0]
# W draw: for p in particles: p.draw(screen)
```

### Stany gry (Game State Machine)

```python
class GameState:
    def handle_event(self, event): pass
    def update(self, dt): pass
    def draw(self, screen): pass

class MenuState(GameState):
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            return 'game'
    def draw(self, screen):
        screen.fill((20, 20, 30))
        font = pygame.font.Font(None, 72)
        text = font.render('NACIŚNIJ ENTER', True, (255, 255, 255))
        screen.blit(text, text.get_rect(center=(WIDTH//2, HEIGHT//2)))

class GameplayState(GameState):
    def __init__(self):
        self.player = Player(400, 300)
    def update(self, dt):
        self.player.update(dt)
    def draw(self, screen):
        screen.fill((10, 10, 20))
        screen.blit(self.player.image, self.player.rect)

# Menedżer stanów
states = {'menu': MenuState(), 'game': GameplayState()}
current_state = 'menu'

# W pętli:
for event in pygame.event.get():
    result = states[current_state].handle_event(event)
    if result:
        current_state = result

states[current_state].update(dt)
states[current_state].draw(screen)
```

### Optymalizacja i wydajność

```python
# convert() i convert_alpha() – ZAWSZE używaj po załadowaniu obrazu
img = pygame.image.load('sprite.png').convert_alpha()  # z przezroczystością
img = pygame.image.load('background.png').convert()    # bez przezroczystości

# Nie twórz Surface w każdej klatce – twórz raz, cache
# ŹLE:
def draw(screen):
    font = pygame.font.Font(None, 36)         # tworzy czcionkę co klatkę!
    text = font.render('Score: ' + str(score), True, WHITE)  # tworzy surface co klatkę!

# DOBRZE:
self.font = pygame.font.Font(None, 36)        # raz w __init__
# i aktualizuj surface tylko gdy zmienia się wartość

# Dirty rect rendering – aktualizuj tylko zmieniły się części ekranu
pygame.display.update(dirty_rects)  # zamiast pygame.display.flip()

# FPS niezależny ruch – zawsze używaj delta time
dt = clock.tick(60) / 1000.0       # sekundy od ostatniej klatki
player.x += speed * dt             # nie: player.x += speed
```

### PyInstaller + Pygame – pakowanie

```python
# spec dla gry pygame
datas=[
    ('assets/', 'assets'),          # obrazy, dźwięki, czcionki
    ('maps/', 'maps'),              # mapy Tiled
],
hiddenimports=['pygame', 'pygame.mixer', 'pygame._sdl2'],
```

```python
# get_resource_path dla assets w grze
import sys
from pathlib import Path

def res(path):
    base = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(__file__).parent
    return str(base / path)

# Użycie
img = pygame.image.load(res('assets/player.png'))
pygame.mixer.music.load(res('assets/music.ogg'))
```

### Przydatne biblioteki do gier pygame

pygame-ce – fork pygame, szybszy, aktywniej rozwijany (pip install pygame-ce)
pytmx – wczytywanie map Tiled (.tmx)
pymunk – fizyka 2D (Chipmunk) dla pygame
noise – Perlin noise do generowania terenu
pyinstaller – pakowanie gry do .exe
