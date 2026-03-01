# Docker – Komendy i najlepsze praktyki

## Podstawowe operacje na kontenerach

```bash
docker run -it ubuntu bash          # uruchom kontener interaktywnie
docker run -d -p 8080:80 nginx      # uruchom w tle, mapuj porty
docker run --name moj-kontener nginx # uruchom z nazwą
docker run --rm ubuntu echo "hello" # usuń kontener po zakończeniu
docker ps                            # lista uruchomionych kontenerów
docker ps -a                         # lista wszystkich (w tym zatrzymanych)
docker stop kontener                 # zatrzymaj kontener
docker start kontener                # uruchom zatrzymany kontener
docker restart kontener              # zrestartuj kontener
docker rm kontener                   # usuń zatrzymany kontener
docker rm -f kontener                # usuń na siłę (nawet uruchomiony)
```

## Obrazy (images)

```bash
docker images                       # lista lokalnych obrazów
docker pull nginx:latest            # pobierz obraz z Docker Hub
docker push user/obraz:tag          # wypchnij obraz do rejestru
docker build -t moj-obraz:1.0 .     # zbuduj obraz z Dockerfile
docker build --no-cache -t obraz .  # zbuduj bez cache
docker rmi obraz                    # usuń obraz
docker image prune                  # usuń nieużywane obrazy
docker tag obraz user/obraz:tag     # otaguj obraz
```

## Logi i diagnostyka

```bash
docker logs kontener                # logi kontenera
docker logs -f kontener             # podgląd logów na żywo
docker logs --tail 50 kontener      # ostatnie 50 linii
docker inspect kontener             # szczegółowe informacje JSON
docker stats                        # zużycie zasobów na żywo
docker top kontener                 # procesy w kontenerze
docker exec -it kontener bash       # wejdź do uruchomionego kontenera
docker exec kontener polecenie      # wykonaj polecenie w kontenerze
```

## Wolumeny (volumes)

```bash
docker volume create moj-wolumin    # utwórz wolumin
docker volume ls                    # lista woluminów
docker volume rm moj-wolumin        # usuń wolumin
docker volume prune                 # usuń nieużywane woluminy
docker run -v moj-wolumin:/data nginx  # montuj wolumin
docker run -v /host/path:/container/path nginx  # montuj katalog hosta
```

## Sieci (networks)

```bash
docker network ls                   # lista sieci
docker network create moja-siec     # utwórz sieć
docker network rm moja-siec         # usuń sieć
docker run --network moja-siec nginx # uruchom w sieci
docker network connect siec kontener  # podłącz kontener do sieci
docker network disconnect siec kontener  # odłącz kontener od sieci
```

## Dockerfile – przykład (Python/Flask)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Kopiuj tylko requirements najpierw (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiuj resztę aplikacji
COPY . .

# Użytkownik bez uprawnień root (bezpieczeństwo)
RUN adduser --disabled-password --gecos '' appuser
USER appuser

EXPOSE 5000

CMD ["python", "app.py"]
```

## Docker Compose – przykład

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8080:5000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/mydb
    depends_on:
      - db
    volumes:
      - ./uploads:/app/uploads
    restart: unless-stopped

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: mydb
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - app

volumes:
  postgres_data:
```

## Docker Compose – komendy

```bash
docker compose up                   # uruchom wszystkie serwisy
docker compose up -d                # uruchom w tle
docker compose down                 # zatrzymaj i usuń kontenery
docker compose down -v              # usuń też woluminy
docker compose ps                   # status serwisów
docker compose logs -f app          # logi konkretnego serwisu
docker compose build                # zbuduj obrazy
docker compose pull                 # pobierz najnowsze obrazy
docker compose exec app bash        # wejdź do kontenera serwisu
docker compose restart app          # zrestartuj serwis
```

## Czyszczenie systemu

```bash
docker system prune                 # usuń nieużywane obiekty
docker system prune -a              # usuń wszystko (w tym nieużywane obrazy)
docker system df                    # zajmowane miejsce przez Docker
```

## Najlepsze praktyki

1. Używaj `.dockerignore` (jak `.gitignore`) – wyklucz `.venv`, `node_modules`, `.git`, `*.log`
2. Minimalizuj warstwy – łącz `RUN` polecenia `&&`
3. Używaj wieloetapowego budowania (`multi-stage build`) dla mniejszych obrazów produkcyjnych
4. Nie uruchamiaj kontenerów jako root (`USER appuser`)
5. Używaj konkretnych tagów (`python:3.11-slim`) a nie `latest` w produkcji
6. Przechowuj sekrety w Docker Secrets lub zmiennych środowiskowych, nie w obrazie
