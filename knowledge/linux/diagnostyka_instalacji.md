# Diagnostyka instalacji – sprawdzanie co jest w systemie

ZASADA: NIE zgaduj stanu systemu. Użyj run_command i sprawdź.

---

## Szybkie sprawdzenie czy program jest zainstalowany

```bash
# Czy binarny plik istnieje?
which godot
which python3
command -v ffmpeg

# Wersja programu
godot --version 2>/dev/null
python3 --version
ffmpeg -version 2>/dev/null | head -1
```

---

## Sprawdzanie metody instalacji (jedno polecenie dla wszystkich)

Gdy user każe "usuń X" a nie wiadomo jak jest zainstalowane — sprawdź wszystko naraz:

```bash
PROG="godot"; \
  echo "=== which ==="; which $PROG 2>/dev/null || echo "brak w PATH"; \
  echo "=== dpkg ==="; dpkg -l "*${PROG}*" 2>/dev/null | grep -v "^un" | head -5; \
  echo "=== snap ==="; snap list 2>/dev/null | grep -i $PROG; \
  echo "=== flatpak ==="; flatpak list 2>/dev/null | grep -i $PROG; \
  echo "=== find /usr /opt ==="; find /usr /opt ~/.local/bin -iname "*${PROG}*" 2>/dev/null | head -5
```

Skrócona wersja jeśli wiesz że to konkretna metoda:

```bash
# apt/deb
dpkg -S /usr/bin/godot 2>/dev/null
dpkg -l godot* 2>/dev/null

# snap
snap list | grep -i godot

# flatpak
flatpak list | grep -i godot

# AppImage / ręczna instalacja
find /usr /opt ~/.local ~/Applications -iname "*godot*" 2>/dev/null
```

---

## Odinstalowywanie — w zależności od metody

```bash
# apt
sudo apt remove godot -y
sudo apt purge godot -y          # usuń też konfigi

# snap
sudo snap remove godot

# flatpak
flatpak uninstall org.godotengine.Godot -y

# AppImage / ręczna
rm /path/do/godot.AppImage
rm ~/.local/share/applications/godot.desktop  # jeśli jest wpis

# pip (Python package)
pip uninstall godot -y
pip3 uninstall godot -y
```

---

## Sprawdzanie zainstalowanych pakietów

```bash
# Wszystkie pakiety apt pasujące do wzorca
dpkg -l | grep -i godot
apt list --installed 2>/dev/null | grep -i godot

# Wszystkie snap
snap list

# Wszystkie flatpak
flatpak list

# Pakiety pip
pip list | grep -i nazwa
pip3 list | grep -i nazwa

# Pakiety npm globalne
npm list -g --depth=0 | grep nazwa
```

---

## Szukanie plików programu

```bash
# Gdzie jest zainstalowany program
which godot
type godot

# Znajdź wszystkie pliki związane z programem
find / -iname "*godot*" 2>/dev/null | grep -v proc | grep -v sys

# Znajdź tylko wykonywalne
find /usr/bin /usr/local/bin ~/.local/bin ~/bin -iname "*godot*" 2>/dev/null

# Pliki konfiguracyjne
find ~/.config ~/.local/share -iname "*godot*" 2>/dev/null
```

---

## Sprawdzanie usług systemd

```bash
# Czy usługa istnieje i jaki ma stan
systemctl status nazwa-usługi
systemctl is-enabled nazwa-usługi

# Lista wszystkich usług
systemctl list-units --type=service | grep -i godot
systemctl list-unit-files | grep -i nazwa
```

---

## Sprawdzanie procesów

```bash
# Czy program aktualnie działa
ps aux | grep -i godot
pgrep -a godot

# Ile zasobów zużywa
top -bn1 | grep -i godot
```

---

## Reguła dla agenta

Gdy użytkownik każe "usuń X", "wyczyść X", "odinstaluj X":

1. Iteracja 1: `run_command` z pełnym sprawdzeniem (which + dpkg + snap + flatpak + find)
2. Iteracja 2: wykonaj właściwe usunięcie na podstawie wyników + `message` z potwierdzeniem

NIE odpowiadaj "Usunięto X" zanim faktycznie wykonasz komendę usuwającą i nie dostaniesz jej wyniku.
NIE pytaj "jak zainstalowałeś?" — sprawdź sam.
