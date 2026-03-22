# Docker – Podstawy i praktyczne wzorce

## Instalacja i weryfikacja

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # dodaj do grupy (wyloguj się po tym)
docker --version
docker run hello-world
```

## Kontenery – podstawowe komendy

```bash
docker ps                        # działające kontenery
docker ps -a                     # wszystkie (też zatrzymane)
docker run -it ubuntu bash       # interaktywny
docker run -d -p 8080:80 nginx   # w tle, port host:kontener
docker run --rm alpine echo hi   # usuń po zakończeniu
docker stop / start / restart <id>
docker rm <id>                   # usuń zatrzymany
docker rm -f <id>                # force (też działający)
docker logs -f <id>              # tail logów
docker exec -it <id> bash        # wejdź do działającego
docker stats                     # zużycie zasobów live
docker stats --no-stream         # jednorazowy snapshot
docker cp <id>:/app/plik ./      # kopiuj plik z kontenera
docker inspect <id>              # pełne info JSON
```

## Obrazy

```bash
docker images
docker pull python:3.12-slim
docker rmi <image_id>
docker image prune               # usuń nieużywane (dangling)
docker image prune -a            # wszystkie bez kontenera
docker build -t myapp:latest .
docker build --no-cache -t myapp .
docker history <image>           # warstwy
docker tag myapp:latest myapp:v1.2
```

## Dockerfile – dobry wzorzec Python

```dockerfile
FROM python:3.12-slim
WORKDIR /app

# Kopiuj requirements osobno – cache warstwy przy rebuild
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m appuser
USER appuser

EXPOSE 8000
CMD ["python", "main.py"]
```

## Dockerfile – multi-stage build (mały obraz końcowy)

```dockerfile
FROM node:20 AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-slim AS runtime
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
EXPOSE 3000
CMD ["node", "dist/index.js"]
```

## .dockerignore – zawsze twórz

```
node_modules
.git
.env
*.log
__pycache__
.pytest_cache
dist
build
```

## Docker Compose – wzorzec z bazą danych

```yaml
version: '3.9'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/mydb
    volumes:
      - ./data:/app/data
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: mydb
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine

volumes:
  postgres_data:
```

```bash
docker compose up -d
docker compose up --build        # z przebudowaniem
docker compose down
docker compose down -v           # też usuń volumes
docker compose logs -f app
docker compose exec app bash
docker compose ps
docker compose pull              # pobierz nowe wersje obrazów
```

## Volumes

```bash
docker volume ls / create / inspect / rm / prune

# Bind mount (katalog hosta)
docker run -v /home/user/data:/app/data myapp
# Named volume
docker run -v mydata:/app/data myapp
# Read-only
docker run -v /config:/app/config:ro myapp
```

## Czyszczenie

```bash
docker system df                 # ile miejsca zajmuje Docker
docker system prune              # zatrzymane kontenery + sieci + dangling images
docker system prune -a           # też nieużywane obrazy
docker system prune -a --volumes # też volumes (ostrożnie!)
```

## Health check w Dockerfile

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

## Typowe problemy

Port already in use: zmień port hosta w -p lub compose.yml
Permission denied na volume: dodaj `user: "1000:1000"` w compose
Container exits immediately: CMD musi trzymać proces na pierwszym planie
Cannot connect to db: użyj depends_on z condition: service_healthy
Image za duży: użyj slim/alpine i multi-stage build
Kontener nie startuje: docker logs <id> i docker inspect <id>
