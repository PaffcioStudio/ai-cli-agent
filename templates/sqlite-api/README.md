# {{PROJECT_NAME}}

**Autor:** {{AUTHOR}} | **Rok:** {{YEAR}}

{{DESCRIPTION}}

## Start

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Docs: http://localhost:8000/docs

## Endpointy

| Metoda | URL              | Opis               |
|--------|------------------|--------------------|
| GET    | /api/items       | Lista itemów        |
| POST   | /api/items       | Utwórz item         |
| GET    | /api/items/{id}  | Pobierz item        |
| DELETE | /api/items/{id}  | Usuń item           |
