# Zarządzanie pakietami — snap, apt, flatpak

## Wykrywanie skąd zainstalowany program

```bash
which thunderbird                          # gdzie jest binarka
dpkg -l | grep -i thunderbird             # czy przez apt/deb
snap list | grep -i thunderbird           # czy przez snap
flatpak list | grep -i thunderbird        # czy przez flatpak
```

Jeśli `dpkg` i `snap list` zwracają "Nie znaleziono" ale program działa,
sprawdź flatpak lub AppImage w /opt, ~/Applications.

## snap

```bash
snap list                                  # lista zainstalowanych
snap install <nazwa>                       # instalacja
snap remove <nazwa>                        # odinstalowanie
snap refresh <nazwa>                       # aktualizacja jednego
snap refresh                               # aktualizacja wszystkich
snap find <szukaj>                         # szukaj w store
snap info <nazwa>                          # szczegóły pakietu
snap connections <nazwa>                   # uprawnienia/połączenia
```

Snap przechowuje dane w:
```
~/snap/<nazwa>/                            # dane użytkownika
/var/snap/<nazwa>/                         # dane systemowe
/snap/<nazwa>/                             # pliki programu (read-only)
```

## apt (Debian/Ubuntu)

```bash
apt list --installed | grep <nazwa>        # czy zainstalowany
sudo apt install <nazwa>                   # instalacja
sudo apt remove <nazwa>                    # odinstalowanie (zostają konfigi)
sudo apt purge <nazwa>                     # odinstalowanie z konfigami
sudo apt autoremove                        # usuń niepotrzebne zależności
sudo apt update && sudo apt upgrade        # aktualizacja wszystkiego
apt-cache search <szukaj>                  # szukaj pakietu
apt-cache show <nazwa>                     # szczegóły
dpkg -l | grep <nazwa>                     # lista z filtrem
dpkg -L <nazwa>                            # pliki zainstalowane przez pakiet
```

## flatpak

```bash
flatpak list                               # lista zainstalowanych
flatpak install flathub <nazwa>            # instalacja z Flathub
flatpak uninstall <nazwa>                  # odinstalowanie
flatpak update                             # aktualizacja wszystkich
flatpak search <szukaj>                    # szukaj
flatpak info <nazwa>                       # szczegóły
flatpak run <nazwa>                        # uruchom
```

Flatpak przechowuje dane w:
```
~/.var/app/<reverse.domain>/              # dane użytkownika
```

## Typowe problemy

### Program jest "wszędzie" ale nie wiadomo skąd

```bash
# Sprawdź wszystkie źródła naraz
for cmd in dpkg snap flatpak; do
    echo "=== $cmd ===" && $cmd list 2>/dev/null | grep -i <nazwa> || echo "brak"
done
```

### snap list pokazuje "Nie znaleziono" ale snap remove działa

`grep` nie znalazł nazwy (bo np. szukałeś "thunderbird" a pakiet to "thunderbird-snap").
Najpierw `snap list` bez grepa, znajdź dokładną nazwę pakietu.

### dpkg zwraca wynik ale apt remove nie usuwa

Program mógł być zainstalowany jako `.deb` bezpośrednio przez `dpkg -i`:
```bash
sudo dpkg -r <nazwa>      # usuń przez dpkg bezpośrednio
```

### Kolizja snap + apt (dwie wersje tego samego programu)

```bash
which -a <nazwa>          # pokaż wszystkie ścieżki
ls -la $(which <nazwa>)   # sprawdź czy symlink do snap
```

## Priorytety uruchamiania

Gdy ten sam program jest zainstalowany przez apt i snap jednocześnie:
- snap zwykle ma wyższy priorytet (binarka w `/snap/bin/` jest wcześniej w PATH)
- `which thunderbird` pokaże aktywną wersję

## Szybki audyt co jest zainstalowane

```bash
# Podsumowanie liczby pakietów z każdego źródła
echo "apt: $(dpkg -l | grep '^ii' | wc -l)"
echo "snap: $(snap list 2>/dev/null | tail -n +2 | wc -l)"
echo "flatpak: $(flatpak list 2>/dev/null | wc -l)"
```

---

## Reguła dla agenta — obowiązkowa weryfikacja przed usunięciem

Gdy użytkownik każe usunąć program, ZAWSZE najpierw sprawdź metodą run_command:

```bash
# Jedno polecenie które sprawdza wszystko naraz
PROG="godot" && \
  echo "=which=:" && which $PROG 2>/dev/null || echo "brak w PATH"; \
  echo "=dpkg=:" && dpkg -l "*${PROG}*" 2>/dev/null | grep "^ii"; \
  echo "=snap=:" && snap list 2>/dev/null | grep -i $PROG; \
  echo "=flatpak=:" && flatpak list 2>/dev/null | grep -i $PROG; \
  echo "=find=:" && find /usr/bin /usr/local/bin /opt ~/.local/bin -iname "*${PROG}*" 2>/dev/null
```

NIE odpowiadaj {"message": "Usunięto X"} bez wykonania komendy usuwającej.
NIE pytaj "jak zainstalowałeś?" — sprawdź sam powyższą komendą.
