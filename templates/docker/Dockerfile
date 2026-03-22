FROM python:3.12-slim

WORKDIR /app

# Zależności systemowe
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kod aplikacji
COPY app/ ./app/
COPY main.py .

EXPOSE 8000

CMD ["python", "main.py"]
