#!/bin/sh

set -e

VENV_DIR="venv"
REQ_FILE="requirements.txt"

echo "Sprawdzanie obecności Python 3..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 nie jest zainstalowany."
    exit 1
fi

echo "Sprawdzanie dostępności modułu venv..."
python3 -m venv --help >/dev/null 2>&1 || {
    echo "Moduł venv nie jest dostępny w tej instalacji Pythona."
    exit 1
}

if [ ! -d "$VENV_DIR" ]; then
    echo "Tworzenie środowiska wirtualnego..."
    python3 -m venv "$VENV_DIR"
else
    echo "Środowisko wirtualne już istnieje."
fi

echo "Aktywowanie środowiska wirtualnego..."
. "$VENV_DIR/bin/activate"

echo "Aktualizacja pip..."
pip install --upgrade pip

if [ -f "$REQ_FILE" ]; then
    echo "Instalowanie zależności z requirements.txt..."
    pip install -r "$REQ_FILE"
else
    echo "Plik requirements.txt nie został znaleziony. Pomijanie instalacji zależności."
fi

echo "Zakończono."
echo "Aby ręcznie aktywować środowisko wirtualne, wykonaj:"
echo "source venv/bin/activate"
