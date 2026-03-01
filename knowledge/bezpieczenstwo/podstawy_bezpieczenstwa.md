# Bezpieczeństwo IT – Podstawy i dobre praktyki

## Hasła i uwierzytelnianie

### Silne hasła
- Minimum 12 znaków (zalecane 16+)
- Kombinacja: litery wielkie, małe, cyfry, znaki specjalne
- Nie używaj słów słownikowych, dat urodzin, imion
- Inne hasło dla każdego serwisu
- Używaj menedżera haseł: Bitwarden, KeePass, 1Password

### Uwierzytelnianie wieloskładnikowe (MFA/2FA)
- Zawsze włączaj 2FA dla ważnych kont (email, bank, GitHub)
- Preferuj aplikację TOTP (Google Authenticator, Authy) zamiast SMS
- Klucze sprzętowe (YubiKey) – najwyższy poziom bezpieczeństwa

## Zarządzanie dostępem

### Zasada najmniejszych uprawnień (Principle of Least Privilege)
- Użytkownicy powinni mieć tylko te uprawnienia, których potrzebują
- Konta serwisowe – minimalne uprawnienia, bez logowania interaktywnego
- Regularny przegląd uprawnień i usuwanie nieaktywnych kont

### Linux – bezpieczna konfiguracja użytkowników
```bash
adduser username                    # dodaj użytkownika
usermod -aG sudo username           # dodaj do sudo (zamiast root)
passwd -l username                  # zablokuj konto
passwd -u username                  # odblokuj konto
last                                # historia logowań
lastfail                            # nieudane logowania
who                                 # aktualnie zalogowani użytkownicy
```

## SSH – bezpieczna konfiguracja

Plik: `/etc/ssh/sshd_config`

```
# Wyłącz logowanie roota
PermitRootLogin no

# Tylko klucze (wyłącz hasła)
PasswordAuthentication no
PubkeyAuthentication yes

# Zmień domyślny port (utrudnia skanowanie)
Port 2222

# Ogranicz użytkowników
AllowUsers user1 user2

# Limity prób logowania
MaxAuthTries 3
LoginGraceTime 30
```

Po zmianach: `systemctl restart sshd`

## Aktualizacje i łatanie

```bash
# Debian/Ubuntu
apt update && apt upgrade -y            # aktualizuj pakiety
apt dist-upgrade -y                     # aktualizacja z zależnościami
unattended-upgrades                     # automatyczne aktualizacje bezpieczeństwa

# CentOS/RHEL
yum update -y
dnf update -y
```

**Zasada:** Aktualizuj regularnie – szczególnie kernel i pakiety sieciowe.

## Szyfrowanie

### SSL/TLS
- Używaj TLS 1.2 lub 1.3 (wyłącz TLS 1.0 i 1.1)
- Certyfikaty – Let's Encrypt (darmowe, automatyczne odnowienie)
- Sprawdź konfigurację: `ssllabs.com/ssltest`

### Szyfrowanie dysku
```bash
# LUKS (Linux Unified Key Setup)
cryptsetup luksFormat /dev/sdb1         # zaszyfruj partycję
cryptsetup luksOpen /dev/sdb1 nazwa     # otwórz zaszyfrowaną partycję
cryptsetup luksClose nazwa              # zamknij
```

### GPG – szyfrowanie plików i e-mail
```bash
gpg --gen-key                           # wygeneruj klucz
gpg --encrypt -r email@example.com plik # zaszyfruj plik
gpg --decrypt plik.gpg                  # odszyfruj
gpg --sign plik                         # podpisz plik
gpg --verify plik.sig                   # weryfikuj podpis
```

## Monitorowanie i logi

```bash
# Sprawdzaj nieudane logowania
grep "Failed password" /var/log/auth.log
grep "Invalid user" /var/log/auth.log

# fail2ban – automatyczne blokowanie brute-force
apt install fail2ban
systemctl enable fail2ban
fail2ban-client status                  # status
fail2ban-client status sshd             # status SSH
fail2ban-client unban IP                # odblokuj IP

# auditd – audit systemu
apt install auditd
auditctl -w /etc/passwd -p wa           # monitoruj zmiany w passwd
ausearch -f /etc/passwd                 # szukaj zdarzeń
```

## OWASP Top 10 – najważniejsze zagrożenia webowe

1. **Broken Access Control** – nieprawidłowa kontrola dostępu
2. **Cryptographic Failures** – słabe/brak szyfrowania
3. **Injection** – SQL Injection, Command Injection, XSS
4. **Insecure Design** – błędy projektowe
5. **Security Misconfiguration** – błędy konfiguracji
6. **Vulnerable Components** – podatne biblioteki/zależności
7. **Authentication Failures** – słabe uwierzytelnianie
8. **Integrity Failures** – brak walidacji danych
9. **Logging/Monitoring Failures** – brak monitorowania
10. **SSRF** – fałszowanie żądań po stronie serwera

## Narzędzia bezpieczeństwa

```bash
# Skanowanie portów
nmap -sV -O 192.168.1.1         # skanuj host
nmap -sn 192.168.1.0/24         # wykryj hosty w sieci

# Sprawdzanie podatności
lynis audit system               # audit bezpieczeństwa systemu
nikto -h http://example.com      # skanowanie podatności web

# Analiza ruchu
tcpdump -i eth0                  # przechwytuj pakiety
tcpdump -i eth0 port 80          # tylko HTTP
wireshark                        # graficzny analizator
```

## Kopie zapasowe (backup)

```bash
# rsync – synchronizacja
rsync -avz /dane/ user@backup:/backup/dane/   # backup na zdalny serwer
rsync -avz --delete /dane/ /backup/dane/       # synchronizuj (usuwa stare)

# Harmonogram (cron)
crontab -e
# 0 2 * * * rsync -avz /dane/ /backup/dane/   # codziennie o 2:00 w nocy

# Weryfikacja backup
rsync -avz --checksum /dane/ /backup/dane/    # z weryfikacją sum kontrolnych
```

### Zasada 3-2-1
- **3** kopie danych
- **2** różne nośniki/lokalizacje
- **1** kopia poza siedzibą (off-site, chmura)
