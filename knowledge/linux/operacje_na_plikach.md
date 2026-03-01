# Operacje na plikach i katalogach w Linux

ls -la                          # pełna lista z ukrytymi
ls -lh                          # rozmiary w czytelnej formie

cp -r src/ dest/                # kopiuj katalog rekurencyjnie
mv stary.txt nowy.txt           # przenoszenie/zmiana nazwy
rm -rf folder/                  # kasuj bez pytania (uważaj)

touch plik.txt                  # stwórz pusty plik
cat plik.txt                    # wyświetl zawartość
less plik.txt                   # przeglądanie z przewijaniem

echo "tekst" > plik.txt         # nadpisz
echo "tekst" >> plik.txt        # dopisz na końcu

find /home -name "*.log"        # szukaj plików
grep -r "szukany_tekst" .       # szukaj w zawartości