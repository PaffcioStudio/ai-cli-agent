# Typowe błędy i jak je naprawić

Plik dla AI – gdy użytkownik pokazuje błąd, szukaj tutaj wzorca i podaj rozwiązanie.

## Python – błędy importu i środowisko

ModuleNotFoundError: No module named 'X'
  Przyczyna: brak pakietu w środowisku lub zły venv
  Fix: pip install X  lub  source venv/bin/activate  i sprawdź pip list

ImportError: cannot import name 'X' from 'Y'
  Przyczyna: zła wersja biblioteki lub literówka
  Fix: pip show Y  sprawdź wersję, pip install --upgrade Y

SyntaxError: invalid syntax
  Przyczyna: błąd składni, często brakujący nawias lub dwukropek
  Fix: sprawdź linię wskazaną i linię powyżej (błąd bywa o linię wyżej)

IndentationError: unexpected indent
  Fix: ujednolicij wcięcia – tylko spacje LUB tylko tabulatory, nie mieszaj

RecursionError: maximum recursion depth exceeded
  Fix: dodaj warunek bazowy do funkcji rekurencyjnej lub użyj iteracji

AttributeError: 'NoneType' object has no attribute 'X'
  Przyczyna: zmienna jest None zamiast oczekiwanego obiektu
  Fix: sprawdź czy funkcja na pewno zwraca wartość, dodaj sprawdzenie `if x is not None`

TypeError: unsupported operand type(s)
  Fix: sprawdź typy zmiennych, użyj int(), str(), float() do konwersji

KeyError: 'X'
  Fix: użyj dict.get('X', default) zamiast dict['X']  lub sprawdź czy klucz istnieje

## Python – pliki i kodowanie

UnicodeDecodeError: 'utf-8' codec can't decode
  Fix: open(path, encoding='utf-8', errors='replace')  lub  errors='ignore'

FileNotFoundError: [Errno 2] No such file or directory
  Fix: sprawdź ścieżkę, użyj Path(__file__).parent / 'plik'  dla ścieżek relatywnych

PermissionError: [Errno 13] Permission denied
  Fix: sprawdź uprawnienia pliku (ls -la), użyj chmod lub uruchom z sudo jeśli trzeba

## Bash / Linux – typowe

command not found
  Fix: sprawdź czy zainstalowane (which X), dodaj do PATH lub użyj pełnej ścieżki

Permission denied przy uruchamianiu skryptu
  Fix: chmod +x skrypt.sh

No space left on device
  Fix: df -h  sprawdź zajęte miejsce, du -sh /*  znajdź co zajmuje, docker system prune

Too many open files
  Fix: ulimit -n 65536  (tymczasowo) lub edytuj /etc/security/limits.conf

Address already in use (port zajęty)
  Fix: lsof -i :PORT  lub  ss -tulpn | grep PORT  znajdź i kill PID

kill: (PID): Operation not permitted
  Fix: użyj sudo kill PID

Broken pipe
  Przyczyna: proces odczytujący pipe zakończył się przed piszącym
  Fix: zazwyczaj niegroźne przy pipelining, można zignorować lub dodać || true

## Git – błędy

error: failed to push some refs
  Fix: git pull --rebase origin main  najpierw pobierz zmiany

CONFLICT (content): Merge conflict in X
  Fix: otwórz plik, znajdź <<<<<<< i >>>>>>> , rozwiąż ręcznie, git add X, git commit

Your branch is behind 'origin/main' by N commits
  Fix: git pull  lub  git pull --rebase

detached HEAD state
  Fix: git checkout main  lub  git switch main

fatal: not a git repository
  Fix: git init  lub upewnij się że jesteś w katalogu projektu

error: Your local changes would be overwritten
  Fix: git stash  (zachowaj zmiany) lub  git checkout -- .  (porzuć zmiany)

## Docker – błędy

Error response from daemon: port is already allocated
  Fix: zmień port hosta w docker run -p lub docker-compose.yml

Cannot connect to the Docker daemon
  Fix: sudo systemctl start docker  lub  sudo service docker start

OCI runtime create failed / exec format error
  Przyczyna: obraz zbudowany na inną architekturę (np. ARM vs x86)
  Fix: docker build --platform linux/amd64 .

No space left on device
  Fix: docker system prune -a  (usuń stare obrazy i kontenery)

Permission denied: /var/run/docker.sock
  Fix: sudo usermod -aG docker $USER  i wyloguj/zaloguj się ponownie

## Node.js / npm

npm ERR! EACCES permission denied
  Fix: nie używaj sudo z npm, napraw uprawnienia: sudo chown -R $USER ~/.npm

Module not found: Error: Can't resolve 'X'
  Fix: npm install X  lub sprawdź czy jest w package.json

Cannot find module '../build/Release/X'
  Fix: npm rebuild  lub usuń node_modules i npm install od nowa

EADDRINUSE: address already in use :::3000
  Fix: lsof -i :3000 | grep LISTEN  potem kill -9 PID

## PostgreSQL – błędy

FATAL: password authentication failed for user
  Fix: sprawdź hasło w .env, upewnij się że pg_hba.conf pozwala na połączenie

relation "X" does not exist
  Fix: sprawdź czy tabela istnieje (\dt w psql), sprawdź czy jesteś w dobrej bazie

ERROR: duplicate key value violates unique constraint
  Fix: wartość już istnieje w kolumnie UNIQUE, użyj INSERT ... ON CONFLICT DO NOTHING

ERROR: column X is of type integer but expression is of type text
  Fix: rzutuj: CAST(X AS integer) lub X::integer

could not connect to server: Connection refused
  Fix: sprawdź czy postgres działa: systemctl status postgresql  lub  pg_lsclusters

## SSL / Certyfikaty

SSL: CERTIFICATE_VERIFY_FAILED
  Fix Python: pip install certifi, import ssl; ssl.create_default_context()
  Fix curl: curl -k (tymczasowo, niezalecane) lub --cacert /path/to/cert.pem

certificate has expired
  Fix: certbot renew  lub sprawdź datę: openssl x509 -in cert.pem -noout -dates

## Sieci / HTTP

Connection refused
  Przyczyna: serwis nie działa na tym porcie lub firewall
  Fix: sprawdź czy serwis działa (ps aux | grep X), sprawdź port (ss -tulpn)

Connection timed out
  Przyczyna: firewall blokuje, zły adres IP, serwis nie odpowiada
  Fix: ping HOST, telnet HOST PORT, sprawdź reguły UFW/iptables

curl: (6) Could not resolve host
  Fix: sprawdź DNS (nslookup HOST), sprawdź /etc/resolv.conf, ping 8.8.8.8

403 Forbidden
  Fix: sprawdź uprawnienia pliku/katalogu, konfigurację nginx/apache

502 Bad Gateway (nginx)
  Przyczyna: nginx nie może połączyć się z backendem
  Fix: sprawdź czy backend działa na właściwym porcie, sprawdź logi nginx

## Systemd / usługi

Failed to start X.service: Unit not found
  Fix: sprawdź nazwę pliku .service, systemctl daemon-reload po zmianach

Active: failed (Result: exit-code)
  Fix: journalctl -u NAZWA.service -n 50  sprawdź logi

Job for X.service failed. See 'journalctl -xe'
  Fix: journalctl -xe | grep -A5 NAZWA  szczegółowe logi błędu
