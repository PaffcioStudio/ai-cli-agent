# Bash – Pisanie skryptów

## Podstawowa struktura skryptu

```bash
#!/bin/bash
# Opis: Opis co robi skrypt
# Autor: Imię Nazwisko
# Data: 2024-01-01

set -e          # zakończ przy pierwszym błędzie
set -u          # błąd przy niezdefiniowanej zmiennej
set -o pipefail # błąd gdy pipe się nie powiedzie
# set -x        # tryb debug (wypisuje każde polecenie)

# Katalog skryptu (nie bieżący!)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
```

## Zmienne i parametry

```bash
# Zmienne
NAZWA="wartość"
LICZBA=42
WYNIK=$(polecenie)              # podstawienie polecenia
WYNIK=`polecenie`               # starszy styl (unikaj)

# Parametry skryptu
$0          # nazwa skryptu
$1, $2...   # argumenty pozycyjne
$@          # wszystkie argumenty (jako lista)
$*          # wszystkie argumenty (jako string)
$#          # liczba argumentów
$?          # kod wyjścia poprzedniego polecenia
$$          # PID bieżącego skryptu

# Domyślne wartości
ZMIENNA="${1:-domyślna}"        # jeśli $1 puste, użyj "domyślna"
ZMIENNA="${ZMIENNA:-wartość}"   # jeśli ZMIENNA nieustawiona
```

## Warunki

```bash
# if-elif-else
if [ "$zmienna" = "wartość" ]; then
    echo "Równe"
elif [ "$zmienna" = "inne" ]; then
    echo "Inne"
else
    echo "Różne"
fi

# Podwójne nawiasy (bardziej czytelne)
if [[ "$string" == *"szukane"* ]]; then
    echo "Zawiera substring"
fi

# Porównania liczbowe
if [ "$liczba" -gt 10 ]; then echo "Większe niż 10"; fi
if [ "$liczba" -eq 0 ]; then echo "Równa 0"; fi
# -eq =, -ne ≠, -lt <, -le <=, -gt >, -ge >=

# Sprawdzanie plików i katalogów
if [ -f "plik.txt" ]; then echo "Istnieje plik"; fi
if [ -d "katalog" ]; then echo "Istnieje katalog"; fi
if [ -e "ścieżka" ]; then echo "Istnieje (plik lub katalog)"; fi
if [ -x "skrypt.sh" ]; then echo "Wykonywalny"; fi
if [ -z "$zmienna" ]; then echo "Pusta zmienna"; fi
if [ -n "$zmienna" ]; then echo "Niepusta zmienna"; fi
```

## Pętle

```bash
# for – po elementach
for element in jeden dwa trzy; do
    echo "$element"
done

# for – po plikach
for plik in *.txt; do
    echo "Przetwarzam: $plik"
done

# for – zakres liczb
for i in {1..10}; do
    echo "$i"
done

# for – styl C
for ((i=0; i<10; i++)); do
    echo "$i"
done

# while
while [ "$i" -lt 10 ]; do
    echo "$i"
    ((i++))
done

# while – czytanie linii z pliku
while IFS= read -r linia; do
    echo "Linia: $linia"
done < "plik.txt"

# until (pętla dopóki warunek jest fałszywy)
until [ "$i" -ge 10 ]; do
    ((i++))
done
```

## Funkcje

```bash
# Definicja
powitanie() {
    local imie="${1:-świecie}"   # zmienna lokalna
    echo "Witaj, $imie!"
    return 0                     # kod wyjścia
}

# Wywołanie
powitanie "Jan"
powitanie               # użyje wartości domyślnej

# Zwracanie wartości (przez podstawienie)
oblicz() {
    echo $((${1:-0} + ${2:-0}))
}
wynik=$(oblicz 5 3)
echo "Wynik: $wynik"
```

## Obsługa błędów i sygnałów

```bash
# Trap – przechwytuj sygnały
cleanup() {
    echo "Czyszczę tymczasowe pliki..."
    rm -f /tmp/moj_skrypt_*
}
trap cleanup EXIT          # przy wyjściu
trap cleanup INT TERM      # przy Ctrl+C lub kill

# Sprawdzanie błędów
if ! polecenie; then
    echo "Polecenie nie powiodło się!" >&2
    exit 1
fi

# Własny error handler
blad() {
    echo "BŁĄD: $1" >&2
    exit "${2:-1}"
}

[ -f "plik.txt" ] || blad "Plik nie istnieje!"
```

## Parsowanie argumentów

```bash
# Prosty sposób
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help)      echo "Pomoc"; exit 0 ;;
        -v|--verbose)   VERBOSE=true ;;
        -f|--file)      PLIK="$2"; shift ;;
        -n|--number)    LICZBA="$2"; shift ;;
        *)              echo "Nieznany argument: $1" >&2; exit 1 ;;
    esac
    shift
done

# getopts (wbudowane, dla krótkich opcji)
while getopts "hvf:n:" opt; do
    case $opt in
        h) echo "Pomoc"; exit 0 ;;
        v) VERBOSE=true ;;
        f) PLIK="$OPTARG" ;;
        n) LICZBA="$OPTARG" ;;
        ?) exit 1 ;;
    esac
done
```

## Przydatne wzorce

```bash
# Wymagaj root
if [[ $EUID -ne 0 ]]; then
    echo "Ten skrypt wymaga uprawnień root!" >&2
    exit 1
fi

# Sprawdź czy polecenie istnieje
if ! command -v docker &>/dev/null; then
    echo "Docker nie jest zainstalowany!"
    exit 1
fi

# Spinner (animacja oczekiwania)
spinner() {
    local pid=$!
    local delay=0.1
    local spinstr='|/-\'
    while kill -0 $pid 2>/dev/null; do
        local tmp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        spinstr=$tmp${spinstr%"$tmp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
}
```

## Kolory w terminalu

```bash
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'    # No Color / Reset

echo -e "${GREEN}✓ Sukces${NC}"
echo -e "${RED}✗ Błąd${NC}"
echo -e "${YELLOW}⚠ Ostrzeżenie${NC}"
echo -e "${BLUE}ℹ Informacja${NC}"
```
