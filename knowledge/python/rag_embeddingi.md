# RAG – Retrieval Augmented Generation

## Czym jest RAG?

RAG (Retrieval Augmented Generation) to technika łącząca:
1. **Wyszukiwanie** (Retrieval) – znalezienie relevantnych fragmentów z bazy wiedzy
2. **Generowanie** (Generation) – stworzenie odpowiedzi przez LLM na podstawie tych fragmentów

Dzięki RAG model LLM może odpowiadać na pytania dotyczące dokumentów, których nie widział podczas treningu.

## Architektura RAG

```
Dokumenty → Chunking → Embeddingi → Baza wektorowa
                                           ↓
Pytanie → Embedding pytania → Wyszukiwanie → Top-K chunki → Prompt → LLM → Odpowiedź
```

## Embeddingi – co to jest?

Embedding to reprezentacja tekstu jako wektor liczb (np. 768 liczb zmiennoprzecinkowych).
Podobne teksty mają podobne embeddingi (mała odległość cosinusowa).

```python
# Przykład: embedding tekstu
import numpy as np

# Dwa podobne teksty będą miały wysokie podobieństwo cosinusowe
def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# Wartości: 1.0 = identyczne, 0.0 = niepowiązane, -1.0 = przeciwne
```

## Chunking – podział dokumentów

Dokumenty należy podzielić na fragmenty (chunks) przed indeksowaniem:

```python
def chunk_text(text, chunk_size=500, overlap=50):
    """Dziel tekst na fragmenty z nakładaniem."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap  # nakładanie
    return chunks
```

### Dobre praktyki chunkingu
- Rozmiar: 200-1000 znaków (zależy od modelu i treści)
- Nakładanie (overlap): 10-20% rozmiaru chunka
- Dziel na granicach zdań/akapitów, nie w środku słowa
- Każdy chunk powinien być sensowny samodzielnie

## Wyszukiwanie (Vector Search)

```python
import numpy as np

def search_vectors(query_embedding, embeddings, texts, top_k=3):
    """Wyszukaj top_k najbardziej podobnych fragmentów."""
    similarities = []
    for i, emb in enumerate(embeddings):
        sim = cosine_similarity(query_embedding, emb)
        similarities.append((i, sim))

    # Posortuj malejąco
    similarities.sort(key=lambda x: x[1], reverse=True)

    results = []
    for i, sim in similarities[:top_k]:
        results.append({
            "text": texts[i],
            "similarity": sim
        })
    return results
```

## Budowanie promptu RAG

```python
def build_rag_prompt(context_chunks, question):
    """Zbuduj prompt z kontekstem i pytaniem."""
    context = "\n\n---\n\n".join([c["text"] for c in context_chunks])

    prompt = f"""Odpowiedz na pytanie wyłącznie na podstawie poniższego kontekstu.
Jeśli odpowiedź nie wynika z kontekstu, napisz "Nie mam wystarczającej wiedzy."

KONTEKST:
{context}

PYTANIE: {question}

ODPOWIEDŹ:"""
    return prompt
```

## Modele embeddingów dla języka polskiego

| Model | Wymiar | Rozmiar | Wsparcie PL |
|-------|--------|---------|-------------|
| nomic-embed-text | 768 | 274MB | Tak |
| nomic-embed-text-v2-moe | 768 | 550MB | Lepsze |
| mxbai-embed-large | 1024 | 670MB | Tak |
| bge-m3 | 1024 | 1.2GB | Bardzo dobre |
| all-minilm | 384 | 46MB | Podstawowe |

## Metryki jakości RAG

- **Precision@K** – ile z K zwróconych wyników jest relevantnych
- **Recall** – czy wszystkie relevantne fragmenty zostały znalezione
- **MRR** – Mean Reciprocal Rank (czy pierwszy wynik jest dobry)
- **Faithfulness** – czy odpowiedź jest wierna kontekstowi
- **Answer Relevancy** – czy odpowiedź jest istotna dla pytania

## Optymalizacja RAG

1. **Jakość embeddingów** – dobierz model do języka i domeny
2. **Rozmiar chunków** – eksperymentuj z 200-800 znaków
3. **Top-K** – zazwyczaj 3-8 fragmentów (więcej = więcej tokenów w kontekście)
4. **Re-ranking** – oceń wyniki wyszukiwania przed przekazaniem do LLM
5. **Hybrid search** – połącz wyszukiwanie wektorowe z BM25 (keyword search)
6. **Query expansion** – rozszerz zapytanie o synonimy/parafrazę
7. **Metadata filtering** – filtruj po kategorii/dacie przed wyszukiwaniem wektorowym
