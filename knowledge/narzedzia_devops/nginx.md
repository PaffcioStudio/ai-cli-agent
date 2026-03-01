# Nginx – Konfiguracja i zarządzanie

## Instalacja i podstawy

```bash
# Ubuntu/Debian
apt update && apt install nginx -y
systemctl enable nginx
systemctl start nginx
systemctl status nginx

# Sprawdź konfigurację
nginx -t                            # test konfiguracji
nginx -s reload                     # przeładuj bez restartu
```

## Struktura konfiguracji

```
/etc/nginx/
  nginx.conf                        # główna konfiguracja
  sites-available/                  # dostępne wirtualne hosty
  sites-enabled/                    # aktywne (symlinki)
  conf.d/                           # dodatkowe konfiguracje
  snippets/                         # wielokrotnie używane fragmenty
```

## Wirtualny host – podstawowy (HTTP)

Plik: `/etc/nginx/sites-available/moja-strona`

```nginx
server {
    listen 80;
    server_name example.com www.example.com;
    root /var/www/moja-strona;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ =404;
    }

    # Logi
    access_log /var/log/nginx/moja-strona.access.log;
    error_log  /var/log/nginx/moja-strona.error.log;
}
```

```bash
ln -s /etc/nginx/sites-available/moja-strona /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

## Reverse proxy (np. dla aplikacji Python/Node)

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 120s;
    }
}
```

## SSL/TLS z Let's Encrypt (Certbot)

```bash
# Instalacja certbot
apt install certbot python3-certbot-nginx -y

# Uzyskaj certyfikat i automatycznie skonfiguruj Nginx
certbot --nginx -d example.com -d www.example.com

# Tylko certyfikat (bez modyfikacji nginx)
certbot certonly --nginx -d example.com

# Odnów certyfikaty
certbot renew --dry-run              # test odnowienia
certbot renew                        # faktyczne odnowienie
```

### Konfiguracja SSL (po certbocie)

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # Dobre ustawienia SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;

    location / {
        proxy_pass http://127.0.0.1:8000;
        # ... proxy headers
    }
}

# Przekierowanie HTTP → HTTPS
server {
    listen 80;
    server_name example.com www.example.com;
    return 301 https://$server_name$request_uri;
}
```

## Load balancing

```nginx
upstream backend {
    least_conn;                     # algorytm: najmniej połączeń
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
    keepalive 32;
}

server {
    location / {
        proxy_pass http://backend;
    }
}
```

## Ograniczanie szybkości (rate limiting)

```nginx
# W sekcji http {}
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

# W sekcji location
location /api/ {
    limit_req zone=api burst=20 nodelay;
    limit_req_status 429;
    proxy_pass http://backend;
}
```

## Kompresja gzip

```nginx
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
```

## Przydatne komendy diagnostyczne

```bash
nginx -T                            # wyświetl całą konfigurację (merged)
nginx -t                            # test konfiguracji
tail -f /var/log/nginx/error.log    # logi błędów na żywo
tail -f /var/log/nginx/access.log   # logi dostępu na żywo
```
