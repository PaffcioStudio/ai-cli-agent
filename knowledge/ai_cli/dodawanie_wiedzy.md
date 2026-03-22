# Dodawanie własnej wiedzy do AI CLI (RAG)

## Czym jest baza wiedzy?

AI CLI używa RAG (Retrieval-Augmented Generation) — pliki `.md` są zamieniane na embeddingi i przeszukiwane wektorowo. Gdy zadajesz pytanie, najlepiej pasujące fragmenty są automatycznie dołączane do promptu jako kontekst.

## Gdzie dodawać pliki wiedzy?

### W projekcie (lokalnie)
Utwórz katalog `knowledge/` w katalogu projektu i dodaj tam pliki `.md`:

```
twój-projekt/
└── knowledge/
    ├── api_dokumentacja.md
    ├── konwencje_kodu.md
    └── architektura.md
```

Ta wiedza jest dostępna tylko gdy pracujesz w tym projekcie (`ai` uruchomiony w tym katalogu).

### Globalnie (zawsze dostępna)
Dodaj pliki `.md` do katalogu instalacji:

```
~/.local/share/ai-cli-agent/knowledge/twoja_kategoria/
```

Przykład:
```
~/.local/share/ai-cli-agent/knowledge/
├── moje_narzedzia/
│   └── custom_workflow.md
└── firma/
    └── konwencje.md
```

Po dodaniu plików uruchom indeksowanie:
```bash
ai --index
```

## Obsługiwane rozszerzenia

Tylko pliki `.md` (Markdown) są indeksowane przez RAG. Inne formaty są ignorowane.

## Jak powinien wyglądać dobry plik wiedzy?

### Schemat

```markdown
# Tytuł tematu

Krótki opis czego dotyczy ten plik (1-2 zdania).

## Sekcja 1

Treść. Im bardziej konkretna i techniczna, tym lepiej.
Unikaj ogólników — RAG szuka na podstawie podobieństwa semantycznego.

## Sekcja 2

Przykłady użycia, komendy, konfiguracje.
Kod w blokach ``` zwiększa precyzję wyszukiwania dla technicznych zapytań.
```

### Zasady dobrego pliku wiedzy

**Tytuł i nagłówki** — używaj opisowych nagłówków `#`, `##`, `###`. RAG dzieli pliki na fragmenty po nagłówkach.

**Konkretność** — zamiast "można użyć różnych narzędzi" pisz "używamy `mygit` zamiast `git`, bo obsługuje nasz wewnętrzny token".

**Słowa kluczowe** — użyj terminów których będziesz szukać. Jeśli będziesz pytać "jak zrobić deploy", użyj słowa "deploy" w pliku.

**Długość sekcji** — optymalna sekcja to 100–400 słów. Zbyt długie sekcje są przycinane, zbyt krótkie mają mały kontekst.

**Kod** — przykłady w blokach kodu są bardzo skuteczne:

```python
# Zamiast opisywać — pokaż
def deploy(env: str):
    subprocess.run(["mygit", "push", env])
```

### Przykłady dobrych plików wiedzy

**konwencje_projektu.md**
```markdown
# Konwencje projektu X

## Nazewnictwo
Pliki konfiguracyjne: `config_<env>.yaml` (np. config_prod.yaml)
Moduły: snake_case, bez prefiksu

## Git workflow
Używamy `mygit` zamiast `git` — wrapper dodaje token.
Branch naming: `feature/<ticket>-<opis>`, np. `feature/AI-42-dodaj-rag`

## Środowiska
- dev: lokalnie, port 8080
- staging: 192.168.1.100
- prod: deploy przez CI/CD (GitLab)
```

**api_wewnetrzna.md**
```markdown
# Wewnętrzne API firmy

## Endpoint autoryzacji
POST /auth/token
Body: {"user": "...", "pass": "..."}
Zwraca: {"token": "...", "expires": 3600}

## Klucze API
Klucze są w `.env` jako `INTERNAL_API_KEY`.
Nigdy nie commituj kluczy do repo.
```

## Kiedy uruchomić indeksowanie?

```bash
ai --index   # po każdym dodaniu lub zmianie pliku .md
```

Indeksowanie trwa kilka sekund. Status można sprawdzić przez `ai config`.

## Weryfikacja

Aby sprawdzić czy wiedza jest dostępna, zapytaj AI bezpośrednio:
```
ai "co wiesz o konwencjach projektu?"
ai "jak działa deploy w tym projekcie?"
```

Jeśli AI odpowiada poprawnie — wiedza jest zaindeksowana i dostępna.

## Parametry RAG w config.json

```json
{
  "rag": {
    "enabled": true,
    "top_k": 5,
    "min_score": 0.3
  }
}
```

- `top_k` — ile fragmentów dołączyć do promptu (domyślnie 5)
- `min_score` — minimalny próg podobieństwa (0.0–1.0), niższy = więcej wyników
