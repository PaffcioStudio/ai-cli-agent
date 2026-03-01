# Ollama – Lokalny serwer modeli językowych (LLM)

## Instalacja i uruchomienie

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Sprawdź status
systemctl status ollama
ollama serve                        # uruchom ręcznie (jeśli nie jako usługa)
```

## Zarządzanie modelami

```bash
ollama list                         # lista pobranych modeli
ollama pull llama3.2                # pobierz model
ollama pull qwen2.5:7b              # konkretna wersja
ollama pull nomic-embed-text        # model do embeddingów
ollama rm model:tag                 # usuń model
ollama show model:tag               # informacje o modelu
ollama ps                           # aktualnie uruchomione modele
```

## Uruchamianie modeli

```bash
ollama run llama3.2                 # interaktywny chat
ollama run llama3.2 "Twoje pytanie" # jednorazowe pytanie
ollama run llama3.2 < prompt.txt    # z pliku
```

## API – komunikacja z Ollama

### Generowanie odpowiedzi (POST /api/generate)
```json
{
  "model": "llama3.2",
  "prompt": "Pytanie do modelu",
  "stream": false,
  "options": {
    "temperature": 0.7,
    "top_p": 0.9,
    "num_ctx": 4096
  }
}
```

### Chat (POST /api/chat)
```json
{
  "model": "llama3.2",
  "messages": [
    {"role": "system", "content": "Jesteś pomocnym asystentem."},
    {"role": "user", "content": "Pytanie użytkownika"}
  ],
  "stream": false
}
```

### Embeddingi (POST /api/embed)
```json
{
  "model": "nomic-embed-text",
  "input": "Tekst do przetworzenia"
}
```

### Lista modeli (GET /api/tags)
```bash
curl http://localhost:11434/api/tags
```

### Test połączenia
```bash
curl http://localhost:11434/api/version
curl http://localhost:11434/
```

## Python – komunikacja z Ollama

```python
import requests
import json

BASE_URL = "http://localhost:11434"

# Generowanie
def generate(prompt, model="llama3.2"):
    r = requests.post(f"{BASE_URL}/api/generate", json={
        "model": model,
        "prompt": prompt,
        "stream": False
    })
    return r.json()["response"]

# Embeddingi
def get_embedding(text, model="nomic-embed-text"):
    r = requests.post(f"{BASE_URL}/api/embed", json={
        "model": model,
        "input": text
    })
    return r.json()["embeddings"][0]

# Streamowanie
def stream_generate(prompt, model="llama3.2"):
    with requests.post(f"{BASE_URL}/api/generate",
                       json={"model": model, "prompt": prompt, "stream": True},
                       stream=True) as r:
        for line in r.iter_lines():
            if line:
                data = json.loads(line)
                print(data.get("response", ""), end="", flush=True)
    print()
```

## Popularne modele

| Model | Rozmiar | Zastosowanie |
|-------|---------|-------------|
| llama3.2:3b | ~2GB | Szybki, ogólny |
| llama3.2:8b | ~5GB | Dobry balans |
| qwen2.5:7b | ~5GB | Wielojęzyczny |
| qwen3:4b | ~2.6GB | Myślenie chain-of-thought |
| mistral:7b | ~4GB | Instrukcje, kod |
| codellama:7b | ~4GB | Programowanie |
| deepseek-coder:6.7b | ~4GB | Programowanie |
| nomic-embed-text | ~274MB | Embeddingi (768 dim) |
| nomic-embed-text-v2-moe | ~550MB | Embeddingi (768 dim) |
| mxbai-embed-large | ~670MB | Embeddingi (1024 dim) |
| all-minilm | ~46MB | Embeddingi lekkie (384 dim) |

## Konfiguracja Ollama

### Zmienne środowiskowe
```bash
OLLAMA_HOST=0.0.0.0:11434          # nasłuchuj na wszystkich interfejsach
OLLAMA_MODELS=/ścieżka/do/modeli   # custom katalog modeli
OLLAMA_NUM_PARALLEL=2              # równoległe żądania
OLLAMA_MAX_LOADED_MODELS=2         # max załadowanych modeli
```

### Systemd – własna konfiguracja
Plik: `/etc/systemd/system/ollama.service.d/override.conf`
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_NUM_PARALLEL=4"
```

## Ollama w Docker

```bash
docker run -d -p 11434:11434 --name ollama ollama/ollama
docker exec -it ollama ollama run llama3.2

# Z GPU NVIDIA
docker run -d --gpus all -p 11434:11434 ollama/ollama
```

## Modelfile – własny model

```
FROM llama3.2

SYSTEM """
Jesteś pomocnym asystentem mówiącym po polsku.
Odpowiadasz zwięźle i precyzyjnie.
"""

PARAMETER temperature 0.3
PARAMETER num_ctx 8192
```

```bash
ollama create moj-model -f Modelfile
ollama run moj-model
```
