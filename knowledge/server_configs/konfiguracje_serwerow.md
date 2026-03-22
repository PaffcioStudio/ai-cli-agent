# Konfiguracje serwerów – gotowe wzorce

## Nginx – reverse proxy dla aplikacji

```nginx
# /etc/nginx/sites-available/myapp
server {
    listen 80;
    server_name moja-domena.pl www.moja-domena.pl;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name moja-domena.pl www.moja-domena.pl;

    ssl_certificate /etc/letsencrypt/live/moja-domena.pl/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/moja-domena.pl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000" always;

    # Gzip
    gzip on;
    gzip_types text/plain application/json application/javascript text/css;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    # Statyczne pliki bezpośrednio
    location /static/ {
        alias /app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Upload limit
    client_max_body_size 50M;
}
```

```bash
nginx -t                                # sprawdź konfigurację
systemctl reload nginx                  # przeładuj bez restartu
systemctl restart nginx
tail -f /var/log/nginx/error.log
tail -f /var/log/nginx/access.log
```

## Nginx – websockets

```nginx
location /ws/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400s;         # 24h dla długich połączeń
}
```

## Nginx – load balancer

```nginx
upstream myapp {
    least_conn;                         # najmniej aktywnych połączeń
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
    keepalive 32;
}

server {
    location / {
        proxy_pass http://myapp;
    }
}
```

## SSL – Certbot (Let's Encrypt)

```bash
apt install certbot python3-certbot-nginx

# Uzyskaj certyfikat (nginx musi działać na porcie 80)
certbot --nginx -d moja-domena.pl -d www.moja-domena.pl

# Tylko certyfikat (bez modyfikacji nginx)
certbot certonly --webroot -w /var/www/html -d moja-domena.pl

# Odnów ręcznie
certbot renew
certbot renew --dry-run              # test bez odnowienia

# Automatyczne odnowienie (sprawdź czy jest w cron)
systemctl status certbot.timer
crontab -l | grep certbot

# Sprawdź datę ważności
openssl x509 -in /etc/letsencrypt/live/moja-domena.pl/cert.pem -noout -dates
certbot certificates                 # lista certyfikatów
```

## UFW – Firewall

```bash
ufw status verbose
ufw enable
ufw disable

ufw allow 22/tcp                    # SSH
ufw allow 80/tcp                    # HTTP
ufw allow 443/tcp                   # HTTPS
ufw allow from 192.168.1.0/24       # całą sieć lokalną
ufw allow from 10.0.0.5 to any port 5432  # PostgreSQL tylko z konkretnego IP
ufw deny 3306                       # zablokuj MySQL z zewnątrz
ufw delete allow 8080               # usuń regułę
ufw reload

# Sprawdź co jest otwarte
ss -tulpn
nmap -sV localhost
```

## SSH – konfiguracja bezpieczna

```bash
# /etc/ssh/sshd_config – kluczowe ustawienia
PermitRootLogin no
PasswordAuthentication no           # tylko klucze
PubkeyAuthentication yes
Port 22                             # rozważ zmianę na niestandardowy
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
AllowUsers username                 # tylko konkretni użytkownicy
```

```bash
# Generuj klucz na lokalnej maszynie
ssh-keygen -t ed25519 -C "komentarz"

# Kopiuj klucz na serwer
ssh-copy-id user@host
# lub ręcznie
cat ~/.ssh/id_ed25519.pub | ssh user@host "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

# Config lokalny (~/.ssh/config)
Host myserver
    HostName 192.168.1.100
    User admin
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60

# Użycie
ssh myserver                        # zamiast ssh admin@192.168.1.100
```

## systemd – serwis aplikacji

```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=My Application
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=appuser
WorkingDirectory=/app
Environment=NODE_ENV=production
Environment=PORT=3000
EnvironmentFile=/app/.env
ExecStart=/usr/bin/node /app/dist/index.js
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable myapp
systemctl start myapp
systemctl status myapp
journalctl -u myapp -f
journalctl -u myapp --since "1 hour ago"
```

## PostgreSQL – konfiguracja produkcyjna

```bash
# pg_hba.conf – kto może się połączyć
# local all postgres peer
# host mydb myuser 127.0.0.1/32 md5
# host mydb myuser 10.0.0.0/8 md5

# postgresql.conf – wydajność (dla serwera 8GB RAM)
max_connections = 100
shared_buffers = 2GB                # 25% RAM
effective_cache_size = 6GB          # 75% RAM
work_mem = 16MB
maintenance_work_mem = 512MB
wal_buffers = 64MB
checkpoint_completion_target = 0.9
random_page_cost = 1.1              # SSD

# Restart wymagany po zmianach
systemctl restart postgresql
```

```bash
# Backup PostgreSQL
pg_dump mydb > backup_$(date +%Y%m%d).sql
pg_dump -Fc mydb > backup.dump        # custom format (szybszy restore)
pg_dumpall > all_dbs_backup.sql       # wszystkie bazy

# Restore
psql mydb < backup.sql
pg_restore -d mydb backup.dump
```

## Redis – podstawowa konfiguracja

```bash
# /etc/redis/redis.conf – kluczowe
bind 127.0.0.1                      # nasłuchuj tylko lokalnie
requirepass TwojeHaslo
maxmemory 256mb
maxmemory-policy allkeys-lru        # LRU eviction przy pełnej pamięci
save 900 1                          # zapis co 900s jeśli 1+ zmian (RDB)
appendonly yes                      # AOF – trwalsze
```

```bash
redis-cli ping                      # PONG = działa
redis-cli -a TwojeHaslo info server
redis-cli monitor                   # live stream komend (debug)
redis-cli --stat                    # statystyki live
```

## Monitoring – podstawowy stack

```bash
# Htop – procesy
htop

# Glances – wszystko naraz
pip install glances
glances

# Netdata – metryki w przeglądarce (port 19999)
bash <(curl -Ss https://my-netdata.io/kickstart.sh)

# Sprawdzenie obciążenia jedną komendą
echo "=== CPU ===" && top -bn1 | grep "Cpu(s)"
echo "=== RAM ===" && free -h
echo "=== Dysk ===" && df -h /
echo "=== Sieć ===" && ss -s
echo "=== Procesy ===" && ps aux --sort=-%cpu | head -10
```
