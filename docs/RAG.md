# RAG - Lokalna Baza Wiedzy

System semantycznego wyszukiwania w lokalnych plikach Markdown/tekstowych. Wzbogaca odpowiedzi agenta o wiedzę dziedzinową zapisaną przez użytkownika.

## Jak działa

1. Pliki `.md` i `.txt` z `knowledge/` są dzielone na fragmenty (chunki ~800 znaków z 100-znakowym nakładaniem)
2. Każdy chunk jest wektoryzowany przy pomocy modelu embeddingów (Ollama)
3. Wektory są cache'owane w `~/.cache/ai/rag/knowledge_vectors.*`
4. Przy każdym zapytaniu: top-K najbardziej podobnych chunków jest wstrzykiwanych do system promptu

## Katalogi wiedzy

```
<projekt>/knowledge/          # Wiedza specyficzna dla projektu
~/.config/ai/knowledge/       # Globalna wiedza (wszystkie projekty)
```

Obie lokalizacje są skanowane jednocześnie.

## Szybki start

```bash
# Stwórz katalog i dodaj plik
mkdir knowledge
echo "# Nasze konwencje\n\nUżywamy Pydantic v2..." > knowledge/konwencje.md

# Zindeksuj
ai --index

# Sprawdź status
ai knowledge status

# Listuj pliki
ai knowledge list

# Teraz pytaj - RAG działa automatycznie
ai jak formatujemy modele danych w tym projekcie
```

## Struktura pliku wiedzy

Zwykły Markdown. Każdy plik może zawierać:

```markdown
# Tytuł

Opis dziedziny / kontekst.

## Sekcja

Konkretna wiedza, przykłady kodu, konwencje, reguły...
```

Dobre praktyki:
- Jeden temat per plik
- Krótkie, konkretne sekcje (lepszy retrieval)
- Nagłówki H2/H3 jako naturalne granice chunków

## Przykładowa struktura `knowledge/`

```
knowledge/
├── linux/
│   ├── podstawy.md
│   ├── bash_skrypty.md
│   └── systemd.md
├── python/
│   ├── podstawy_python.md
│   ├── rag_embeddingi.md
│   └── struktura_projektu.md
├── docker/
│   └── docker_podstawy.md
├── git/
│   └── podstawy_git.md
└── bezpieczenstwo/
    └── podstawy_bezpieczenstwa.md
```

## Konfiguracja

```json
{
  "rag": {
    "enabled": true,
    "top_k": 4
  },
  "semantic": {
    "enabled": true,
    "cache_embeddings": true
  }
}
```

Wyłączenie RAG:

```json
{
  "rag": {
    "enabled": false
  }
}
```

## Wymagania

Model embeddingów w Ollama (skonfigurowany jako `embed_model` w config):

```bash
ollama pull nomic-embed-text-v2-moe:latest
```

Alternatywy: `nomic-embed-text`, `mxbai-embed-large`, `bge-m3`.

## Cache i przebudowa

Wektory są cache'owane w `~/.cache/ai/rag/`. Przebuduj indeks gdy:
- Dodajesz nowe pliki do `knowledge/`
- Edytujesz istniejące pliki
- Zmieniasz model embeddingów

```bash
ai --index          # Przebuduj
# lub
ai --reindex        # To samo
```

Wyczyść cache ręcznie:

```bash
rm -rf ~/.cache/ai/rag/
```

## Debugowanie

Logi RAG w `~/.cache/ai-cli/logs/debug.log`:

```
RAG: 3 wyników dla: 'jak formatujemy modele' | źródła: ['knowledge/python/podstawy_python.md']
```

Włącz verbose logi w config:

```json
{
  "debug": {
    "log_level": "debug"
  }
}
```
