# Linux – Zaawansowane komendy i narzędzia

## Zarządzanie procesami

```bash
ps aux                          # lista wszystkich procesów
ps aux | grep nazwa             # szukaj procesu po nazwie
top                             # monitor procesów na żywo
htop                            # interaktywny monitor (czytelniejszy)
kill PID                        # zakończ proces po PID
kill -9 PID                     # wymuś zakończenie procesu
pkill nazwa                     # zakończ proces po nazwie
jobs                            # lista zadań w tle
bg %1                           # wyślij zadanie do tła
fg %1                           # przywołaj zadanie na pierwszy plan
nohup polecenie &               # uruchom odporne na zamknięcie terminala
```

## Uprawnienia i właściciel pliku

```bash
chmod 755 plik.sh               # rwxr-xr-x (właściciel, grupa, pozostali)
chmod +x plik.sh                # dodaj prawo wykonania
chmod -R 644 folder/            # rekurencyjnie zmień uprawnienia
chown user:group plik           # zmień właściciela i grupę
chown -R user:group folder/     # rekurencyjnie zmień właściciela
ls -l plik                      # sprawdź uprawnienia pliku
```

## Wyszukiwanie i filtry

```bash
find / -name "*.conf" 2>/dev/null          # szukaj plików .conf
find /var -mtime -7                        # pliki zmienione w ostatnich 7 dniach
find . -size +100M                         # pliki większe niż 100MB
grep -r "szukana_fraza" /etc/             # szukaj rekurencyjnie
grep -i "fraza" plik.txt                  # bez rozróżniania wielkości liter
grep -n "fraza" plik.txt                  # z numerami linii
grep -v "fraza" plik.txt                  # wyklucz linie z frazą
awk '{print $1}' plik.txt                 # wydrukuj pierwszą kolumnę
sed 's/stare/nowe/g' plik.txt             # zamień wszystkie wystąpienia
```

## Sieć

```bash
ip addr show                    # adresy IP interfejsów
ip route show                   # tablica routingu
ping -c 4 google.com            # pinguj 4 razy
traceroute google.com           # śledzenie trasy pakietów
ss -tuln                        # otwarte porty (zamiast netstat)
netstat -tuln                   # otwarte porty (starsze systemy)
curl -I https://example.com     # pobierz tylko nagłówki HTTP
wget https://example.com/plik   # pobierz plik
```

## Dysk i system plików

```bash
df -h                           # wolne miejsce na dyskach
du -sh folder/                  # rozmiar katalogu
du -sh *                        # rozmiary elementów w bieżącym katalogu
lsblk                           # lista urządzeń blokowych
mount /dev/sdb1 /mnt/dysk       # montuj partycję
umount /mnt/dysk                # odmontuj
fdisk -l                        # lista partycji
```

## Archiwizacja i kompresja

```bash
tar -czf archiwum.tar.gz folder/     # twórz archiwum gzip
tar -xzf archiwum.tar.gz             # rozpakuj archiwum gzip
tar -cjf archiwum.tar.bz2 folder/   # twórz archiwum bzip2
tar -xjf archiwum.tar.bz2            # rozpakuj bzip2
zip -r archiwum.zip folder/          # twórz archiwum zip
unzip archiwum.zip                   # rozpakuj zip
```

## Zmienne środowiskowe i skrypty

```bash
export ZMIENNA="wartość"        # ustaw zmienną środowiskową
echo $ZMIENNA                   # wyświetl wartość zmiennej
env                             # lista wszystkich zmiennych
printenv PATH                   # wyświetl konkretną zmienną
source ~/.bashrc                # przeładuj konfigurację bash
```

## Użytkownicy i grupy

```bash
whoami                          # bieżący użytkownik
id                              # UID, GID i grupy bieżącego użytkownika
adduser username                # dodaj nowego użytkownika
passwd username                 # zmień hasło użytkownika
usermod -aG sudo username       # dodaj do grupy sudo
groups username                 # pokaż grupy użytkownika
su - username                   # przełącz się na innego użytkownika
sudo polecenie                  # wykonaj jako root
```

## Logi systemowe

```bash
journalctl -xe                  # systemd logi z błędami
journalctl -u nginx             # logi konkretnej usługi
tail -f /var/log/syslog         # podgląd logów na żywo
cat /var/log/auth.log           # logi uwierzytelniania
dmesg | tail -20                # logi kernela
```
