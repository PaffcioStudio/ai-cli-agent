# Web Search - „Okno na świat"

Moduł dający agentowi dostęp do internetu. Domyślnie **WYŁĄCZONY** ze względów bezpieczeństwa.

## Szybki start

```bash
ai web-search enable          # Włącz
ai web-search status          # Sprawdź status i zależności

# Po włączeniu - auto-trigger:
ai jaka jest pogoda w Gdańsku
ai najnowsza wersja pandas
ai co nowego w Python 3.13
ai kurs dolara dziś

# Bezpośrednie zapytanie:
ai web-search react hooks tutorial

# Scraping strony:
ai web-search scrape https://pypi.org/project/pandas/
```

## Architektura

```
WebSearchEngine
  ├── SearchCache (TTL 1h, ~/.cache/ai/web-search/)
  ├── RateLimiter (10 zapytań/minutę, rolling window)
  ├── DuckDuckGoBackend (bezpłatny, bez klucza)
  ├── BraveSearchBackend (wymaga API key)
  └── WebScraper
        ├── requests + BeautifulSoup
        ├── html2text (HTML → Markdown)
        └── Filtrowanie: ads, nav, footer
```

## Silniki wyszukiwania

### DuckDuckGo (domyślny)

Bezpłatny, bez klucza API. Wystarczający do większości zastosowań.

### Brave Search

Wymaga klucza API. Lepsze wyniki, większe limity.

```json
{
  "web_search": {
    "engine": "brave",
    "brave_api_key": "BSA..."
  }
}
```

### Google Custom Search

Wymaga klucza API + Custom Search Engine ID.

```json
{
  "web_search": {
    "engine": "google",
    "google_api_key": "AIza...",
    "google_cx": "..."
  }
}
```

## Auto-trigger

Gdy `web_search.enabled = true` i `auto_trigger = true`, agent automatycznie wyszukuje gdy wykryje frazy wyzwalające:

```
pogoda, jaka jest, najnowsza wersja, aktualna wersja,
kurs, cena, news, aktualności, sprawdź, dziś, teraz,
latest, current, co się dzieje, ile kosztuje...
```

Wyniki są wstrzykiwane do kontekstu systemu promptu przed odpowiedzią.

## Bezpieczeństwo

### Whitelist domen

Domyślnie dozwolone:

```
pypi.org, npmjs.com, github.com, stackoverflow.com,
docs.python.org, developer.mozilla.org, rust-lang.org,
nodejs.org, reactjs.org, vuejs.org, svelte.dev,
crates.io, pkg.go.dev
```

Zarządzanie:

```bash
ai web-search domains add example.com
ai web-search domains list
```

### Rate limiting

Max 10 zapytań/minutę (rolling window). Po przekroczeniu: `RateLimitError` z czasem oczekiwania.

### Scraping limity

- Timeout: 10 sekund
- Maksymalny rozmiar strony: 1MB
- Sanityzacja HTML przed przetworzeniem
- Brak wykonywania scraped JavaScript

## Konfiguracja

```json
{
  "web_search": {
    "enabled": false,
    "engine": "duckduckgo",
    "max_results": 5,
    "cache_ttl_hours": 1,
    "allowed_domains": ["pypi.org", "github.com", "..."],
    "auto_trigger": true,
    "brave_api_key": "",
    "google_api_key": "",
    "google_cx": ""
  }
}
```

## Cache

Wyniki cache'owane w `~/.cache/ai/web-search/` (JSON files, hash klucza = query).

```bash
ai web-search cache clear    # Wyczyść cache
ai web-search cache status   # Rozmiar cache
```

## Struktura wyników

```python
@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str
    date: Optional[str]
    domain: str
```

## Wymagania systemowe

```bash
pip install requests beautifulsoup4 html2text --break-system-packages
```

Agent sprawdza zależności przy `ai web-search status` i oferuje instalację jeśli brakuje.

## Tryb globalny (`ai --global`)

W trybie bez projektu, gdy web_search wyłączone, agent automatycznie używa `curl` jako fallback:

```bash
# Pogoda
curl -s 'wttr.in/Gdansk?format=3&lang=pl'

# Wersja pakietu PyPI
curl -s 'https://pypi.org/pypi/pandas/json' | python3 -c '...'

# DuckDuckGo API
curl -s 'https://api.duckduckgo.com/?q=...&format=json' | python3 -c '...'
```
