# Sieci komputerowe – Podstawy i diagnostyka

## Model OSI i TCP/IP

### Warstwy modelu OSI
1. **Fizyczna** – sygnały elektryczne, kable, Wi-Fi
2. **Łącza danych** – ramki, MAC adresy, Ethernet, switche
3. **Sieciowa** – pakiety, adresy IP, routery
4. **Transportowa** – TCP (niezawodny), UDP (szybki), porty
5. **Sesji** – zarządzanie połączeniami
6. **Prezentacji** – kodowanie, szyfrowanie, SSL/TLS
7. **Aplikacji** – HTTP, DNS, SMTP, FTP

## Adresy IP i podsieci

### IPv4
- Adres 32-bitowy, zapis: `192.168.1.100`
- Maska podsieci: `255.255.255.0` = `/24`
- Klasy:
  - A: `10.0.0.0/8` – sieci prywatne duże
  - B: `172.16.0.0/12` – sieci prywatne średnie
  - C: `192.168.0.0/16` – sieci prywatne małe
  - `127.0.0.1` – loopback (localhost)

### Obliczanie podsieci
- `/24` = 254 hosty, maska `255.255.255.0`
- `/25` = 126 hostów, maska `255.255.255.128`
- `/26` = 62 hosty, maska `255.255.255.192`
- `/30` = 2 hosty (połączenia punkt-punkt)

### IPv6
- Adres 128-bitowy: `2001:db8::1`
- Loopback: `::1`
- Link-local: `fe80::/10`

## Protokoły i porty

| Port | Protokół | Opis |
|------|----------|------|
| 21 | FTP | Transfer plików |
| 22 | SSH | Bezpieczne połączenie |
| 23 | Telnet | Połączenie (nieszyfrowane) |
| 25 | SMTP | Wysyłanie e-mail |
| 53 | DNS | Rozwiązywanie nazw |
| 80 | HTTP | Strony www |
| 110 | POP3 | Odbieranie e-mail |
| 143 | IMAP | Odbieranie e-mail |
| 443 | HTTPS | Bezpieczne strony www |
| 3306 | MySQL | Baza danych |
| 5432 | PostgreSQL | Baza danych |
| 6379 | Redis | Cache/baza |
| 11434 | Ollama | Serwer LLM |
| 27017 | MongoDB | Baza NoSQL |

## Diagnostyka sieci w Linux

```bash
# Sprawdzanie łączności
ping 8.8.8.8                    # pinguj Google DNS
ping6 ::1                       # ping IPv6
traceroute google.com           # śledzenie trasy
mtr google.com                  # traceroute na żywo (zainstaluj: apt install mtr)

# Konfiguracja interfejsów
ip addr show                    # adresy IP wszystkich interfejsów
ip addr show eth0               # adres konkretnego interfejsu
ip link show                    # status interfejsów
ip route show                   # tablica routingu
ip neigh show                   # tabela ARP

# Otwarte porty i połączenia
ss -tuln                        # otwarte porty (nasłuchujące)
ss -tulnp                       # z nazwami procesów
ss -tn state established        # nawiązane połączenia TCP
netstat -tuln                   # alternatywa (starszy)
lsof -i :8080                   # który proces używa portu 8080

# DNS
nslookup google.com             # zapytanie DNS
dig google.com                  # szczegółowe zapytanie DNS
dig +short google.com           # tylko adresy IP
dig -x 8.8.8.8                  # odwrotne DNS (reverse lookup)
host google.com                 # proste zapytanie DNS

# Testy HTTP
curl -v https://example.com     # szczegółowe połączenie HTTP
curl -I https://example.com     # tylko nagłówki
curl -o /dev/null -s -w "%{http_code}" https://example.com  # kod HTTP
wget --spider https://example.com  # sprawdź dostępność
```

## Firewall (iptables / ufw)

```bash
# UFW (prostszy)
ufw status                      # status firewalla
ufw enable                      # włącz firewall
ufw allow 22                    # zezwól na SSH
ufw allow 80/tcp                # zezwól na HTTP
ufw deny 23                     # blokuj Telnet
ufw allow from 192.168.1.0/24   # zezwól z podsieci
ufw delete allow 80             # usuń regułę

# iptables (zaawansowany)
iptables -L -n -v               # lista reguł
iptables -A INPUT -p tcp --dport 22 -j ACCEPT  # zezwól SSH
iptables -A INPUT -j DROP       # blokuj resztę
```

## SSH – bezpieczne połączenie

```bash
ssh user@192.168.1.100          # połącz się
ssh -p 2222 user@host           # niestandardowy port
ssh -i ~/.ssh/klucz user@host   # klucz prywatny
ssh -L 8080:localhost:80 user@host  # tunel lokalny (port forwarding)
ssh -D 1080 user@host           # socks proxy

# Generowanie kluczy
ssh-keygen -t ed25519 -C "email@example.com"  # generuj klucz (zalecany)
ssh-copy-id user@host           # skopiuj klucz publiczny na serwer
cat ~/.ssh/id_ed25519.pub       # wyświetl klucz publiczny
```

## Konfiguracja DNS (/etc/resolv.conf)

```
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
search example.com
```
