# {{PROJECT_NAME}}

**Autor:** {{AUTHOR}} | **Rok:** {{YEAR}}

{{DESCRIPTION}}

## Start z Docker

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f
```

## Start bez Docker

```bash
pip install -r requirements.txt
python main.py
```

## Przydatne komendy

```bash
docker compose ps           # status
docker compose down         # zatrzymaj
docker compose restart app  # restart
```
