"""
Web Search - "Okno na świat" dla AI CLI.

ARCHITEKTURA:
    WebSearchEngine   - główny silnik (search + cache + rate limiting)
    WebScraper        - pobieranie i ekstrakcja treści stron
    WebSearchResult   - struktura wyniku
    SearchCache       - cache wyników (TTL 1h, plik JSON)

BACKENDY:
    - DuckDuckGo (domyślny, bezpłatny, bez klucza API)
    - Brave Search (wymaga API key)
    - Google Custom Search (wymaga API key + cx)

BEZPIECZEŃSTWO:
    - Whitelist domen (pypi.org, npmjs.com, github.com, stackoverflow.com)
    - Potwierdzenie użytkownika dla nowych domen
    - Timeout 10s na request
    - Max 1MB na stronę
    - Brak wykonywania scraped kodu
    - Sanityzacja HTML

RATE LIMITING:
    - Max 10 wyszukiwań/minutę (rolling window)
"""

import json
import re
import time
import hashlib
import urllib.parse
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from collections import deque

# Opcjonalne importy – instaluj przy pierwszym użyciu
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import html2text
    HAS_HTML2TEXT = True
except ImportError:
    HAS_HTML2TEXT = False


# ─── Struktury danych ──────────────────────────────────────────────────────────

@dataclass
class WebSearchResult:
    """Pojedynczy wynik wyszukiwania."""
    title: str
    url: str
    snippet: str
    date: Optional[str] = None
    domain: str = ""

    def __post_init__(self):
        if not self.domain and self.url:
            try:
                self.domain = urllib.parse.urlparse(self.url).netloc.lstrip("www.")
            except Exception:
                self.domain = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    def format_for_prompt(self) -> str:
        date_str = f" [{self.date}]" if self.date else ""
        return (
            f"**{self.title}**{date_str}\n"
            f"URL: {self.url}\n"
            f"{self.snippet}"
        )


@dataclass
class ScrapeResult:
    """Wynik scrapowania strony."""
    url: str
    title: str
    markdown: str
    word_count: int
    success: bool
    error: Optional[str] = None


class WebSearchError(Exception):
    """Błąd podczas wyszukiwania."""
    pass


class RateLimitError(WebSearchError):
    """Przekroczono limit zapytań."""
    pass


class DomainBlockedError(WebSearchError):
    """Domena nie jest na whitelist."""
    pass


# ─── Cache ─────────────────────────────────────────────────────────────────────

class SearchCache:
    """
    Cache wyników wyszukiwania (JSON, TTL 1h).

    Struktura pliku:
        ~/.cache/ai/web-search/<md5(query)>.json
        {
            "query": "...",
            "timestamp": 1700000000.0,
            "results": [...]
        }
    """

    CACHE_DIR = Path.home() / ".cache" / "ai" / "web-search"
    DEFAULT_TTL = 3600  # 1 godzina

    def __init__(self, ttl_seconds: int = DEFAULT_TTL):
        self.ttl = ttl_seconds
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, query: str) -> Path:
        key = hashlib.md5(query.lower().strip().encode()).hexdigest()
        return self.CACHE_DIR / f"{key}.json"

    def get(self, query: str) -> Optional[List[WebSearchResult]]:
        """Pobierz wyniki z cache. None jeśli brak lub expired."""
        path = self._cache_path(query)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            age = time.time() - data.get("timestamp", 0)
            if age > self.ttl:
                path.unlink(missing_ok=True)
                return None
            return [WebSearchResult(**r) for r in data.get("results", [])]
        except Exception:
            return None

    def set(self, query: str, results: List[WebSearchResult]):
        """Zapisz wyniki do cache."""
        path = self._cache_path(query)
        try:
            data = {
                "query": query,
                "timestamp": time.time(),
                "results": [r.to_dict() for r in results]
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass  # Cache jest opcjonalny

    def clear(self):
        """Wyczyść cały cache."""
        for f in self.CACHE_DIR.glob("*.json"):
            f.unlink(missing_ok=True)

    def stats(self) -> Dict:
        """Statystyki cache."""
        files = list(self.CACHE_DIR.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)
        return {
            "entries": len(files),
            "size_kb": round(total_size / 1024, 1),
            "cache_dir": str(self.CACHE_DIR)
        }


# ─── Rate Limiter ──────────────────────────────────────────────────────────────

class RateLimiter:
    """Rolling window rate limiter (max N zapytań na minutę)."""

    def __init__(self, max_per_minute: int = 10):
        self.max_per_minute = max_per_minute
        self._timestamps: deque = deque()

    def check(self) -> Tuple[bool, int]:
        """
        Sprawdź czy można wykonać zapytanie.
        Returns: (allowed, seconds_to_wait)
        """
        now = time.time()
        window_start = now - 60

        # Usuń stare timestampy (poza oknem 60s)
        while self._timestamps and self._timestamps[0] < window_start:
            self._timestamps.popleft()

        if len(self._timestamps) >= self.max_per_minute:
            oldest = self._timestamps[0]
            wait = int(oldest + 60 - now) + 1
            return False, wait

        return True, 0

    def record(self):
        """Zarejestruj wykonane zapytanie."""
        self._timestamps.append(time.time())

    @property
    def remaining(self) -> int:
        """Ile zapytań pozostało w bieżącej minucie."""
        now = time.time()
        window_start = now - 60
        active = sum(1 for t in self._timestamps if t >= window_start)
        return max(0, self.max_per_minute - active)


# ─── Backend: DuckDuckGo ───────────────────────────────────────────────────────

class DuckDuckGoBackend:
    """
    Backend DuckDuckGo (bezpłatny, bez API key).
    Używa DuckDuckGo HTML endpoint (nie oficjalne API).
    """

    SEARCH_URL = "https://html.duckduckgo.com/html/"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    }

    def search(self, query: str, max_results: int = 5, timeout: int = 10) -> List[WebSearchResult]:
        """
        Wyszukaj w DuckDuckGo.
        Zwraca listę WebSearchResult.
        """
        if not HAS_REQUESTS:
            raise WebSearchError("Brak modułu 'requests'. Zainstaluj: pip install requests")
        if not HAS_BS4:
            raise WebSearchError("Brak modułu 'beautifulsoup4'. Zainstaluj: pip install beautifulsoup4")

        try:
            resp = requests.post(
                self.SEARCH_URL,
                data={"q": query, "b": "", "kl": "pl-pl"},
                headers=self.HEADERS,
                timeout=timeout,
                allow_redirects=True
            )
            resp.raise_for_status()
        except requests.Timeout:
            raise WebSearchError(f"Timeout przy wyszukiwaniu (>{timeout}s)")
        except requests.RequestException as e:
            raise WebSearchError(f"Błąd połączenia z DuckDuckGo: {e}")

        return self._parse_html(resp.text, max_results)

    def _parse_html(self, html: str, max_results: int) -> List[WebSearchResult]:
        """Parsuj HTML wyników DuckDuckGo."""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Wyniki organiczne – div.result
        for item in soup.select(".result"):
            if len(results) >= max_results:
                break

            # Tytuł i URL
            title_tag = item.select_one(".result__title a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            raw_url = str(title_tag.get("href", "") or "")

            # DuckDuckGo redirectuje przez /l/?uddg= – wyekstrahuj prawdziwy URL
            url = self._extract_real_url(raw_url)
            if not url or url.startswith("https://duckduckgo.com"):
                continue

            # Snippet
            snippet_tag = item.select_one(".result__snippet")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

            # Data (jeśli jest)
            date = None
            date_tag = item.select_one(".result__timestamp")
            if date_tag:
                date = date_tag.get_text(strip=True)

            results.append(WebSearchResult(
                title=title,
                url=url,
                snippet=snippet,
                date=date
            ))

        return results

    def _extract_real_url(self, ddg_url: str) -> str:
        """Wyekstrahuj prawdziwy URL z DuckDuckGo redirect link."""
        if not ddg_url:
            return ""

        # Format: /l/?uddg=https%3A%2F%2F...
        if ddg_url.startswith("/l/?"):
            try:
                params = urllib.parse.parse_qs(urllib.parse.urlparse(ddg_url).query)
                if "uddg" in params:
                    return urllib.parse.unquote(params["uddg"][0])
            except Exception:
                pass

        # Format: //duckduckgo.com/l/?kh=-1&uddg=...
        if "uddg=" in ddg_url:
            try:
                start = ddg_url.index("uddg=") + 5
                end = ddg_url.find("&", start)
                encoded = ddg_url[start:] if end == -1 else ddg_url[start:end]
                return urllib.parse.unquote(encoded)
            except Exception:
                pass

        return ddg_url if ddg_url.startswith("http") else ""


# ─── Backend: Brave Search ─────────────────────────────────────────────────────

class BraveSearchBackend:
    """
    Backend Brave Search (wymaga klucza API).
    Zarejestruj na: https://api.search.brave.com/
    """

    API_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, max_results: int = 5, timeout: int = 10) -> List[WebSearchResult]:
        if not HAS_REQUESTS:
            raise WebSearchError("Brak modułu 'requests'.")

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key
        }
        params = {
            "q": query,
            "count": min(max_results, 20),
            "search_lang": "pl",
            "country": "PL"
        }

        try:
            resp = requests.get(self.API_URL, headers=headers, params=params, timeout=timeout)
            resp.raise_for_status()
        except requests.Timeout:
            raise WebSearchError(f"Timeout (>{timeout}s)")
        except requests.RequestException as e:
            raise WebSearchError(f"Brave Search error: {e}")

        data = resp.json()
        results = []

        for item in data.get("web", {}).get("results", [])[:max_results]:
            results.append(WebSearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
                date=item.get("page_age")
            ))

        return results


# ─── Web Scraper ───────────────────────────────────────────────────────────────

class WebScraper:
    """
    Pobiera i ekstrahuje treść strony.

    Pipeline:
        1. GET strony (timeout 10s, max 1MB)
        2. BeautifulSoup – usuń: ads, nav, footer, script, style
        3. html2text – konwertuj na Markdown
        4. Zwróć ScrapeResult
    """

    MAX_SIZE_BYTES = 1_024 * 1_024  # 1 MB
    TIMEOUT = 10

    REMOVE_TAGS = ["script", "style", "nav", "footer", "header",
                   "aside", "form", "iframe", "noscript", "ads",
                   ".advertisement", ".ad", "#sidebar", ".sidebar",
                   ".nav", ".footer", ".header", ".cookie-notice"]

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def __init__(self, logger=None):
        self.logger = logger

    def scrape(self, url: str) -> ScrapeResult:
        """Pobierz i przetwórz stronę. Zawsze zwraca ScrapeResult."""
        if not HAS_REQUESTS:
            return ScrapeResult(url=url, title="", markdown="", word_count=0,
                                success=False, error="Brak modułu 'requests'")

        try:
            resp = requests.get(
                url,
                headers=self.HEADERS,
                timeout=self.TIMEOUT,
                stream=True
            )
            resp.raise_for_status()

            # Sprawdź Content-Type
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return ScrapeResult(url=url, title="", markdown="", word_count=0,
                                    success=False, error=f"Nieobsługiwany typ: {content_type}")

            # Pobierz z limitem rozmiaru
            chunks = []
            total = 0
            for chunk in resp.iter_content(chunk_size=8192, decode_unicode=False):
                total += len(chunk)
                if total > self.MAX_SIZE_BYTES:
                    break
                chunks.append(chunk)

            raw_bytes = b"".join(chunks)

            # Dekoduj
            encoding = resp.encoding or "utf-8"
            try:
                html = raw_bytes.decode(encoding, errors="replace")
            except Exception:
                html = raw_bytes.decode("utf-8", errors="replace")

        except requests.Timeout:
            return ScrapeResult(url=url, title="", markdown="", word_count=0,
                                success=False, error=f"Timeout (>{self.TIMEOUT}s)")
        except requests.RequestException as e:
            return ScrapeResult(url=url, title="", markdown="", word_count=0,
                                success=False, error=str(e))

        # Przetwórz HTML
        return self._process_html(url, html)

    def _process_html(self, url: str, html: str) -> ScrapeResult:
        """Przetwórz HTML → Markdown."""
        if not HAS_BS4:
            return ScrapeResult(url=url, title="", markdown=html[:500],
                                word_count=0, success=False,
                                error="Brak modułu 'beautifulsoup4'")

        try:
            soup = BeautifulSoup(html, "html.parser")

            # Tytuł
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

            # Usuń zbędne elementy
            for selector in self.REMOVE_TAGS:
                for tag in soup.select(selector):
                    tag.decompose()

            # Ekstrakcja głównej treści (main > article > body)
            main = (
                soup.find("main")
                or soup.find("article")
                or soup.find(id=re.compile(r"(content|main|article)", re.I))
                or soup.find(class_=re.compile(r"(content|main|article|post)", re.I))
                or soup.body
                or soup
            )

            clean_html = str(main)

            # Konwersja do Markdown
            if HAS_HTML2TEXT:
                h = html2text.HTML2Text()
                h.ignore_links = False
                h.ignore_images = True
                h.ignore_emphasis = False
                h.body_width = 0
                h.protect_links = True
                markdown = h.handle(clean_html)
            else:
                # Fallback: wyciągnij tylko tekst
                markdown = main.get_text(separator="\n", strip=True)

            # Ogranicz długość
            if len(markdown) > 8000:
                markdown = markdown[:8000] + "\n\n[... treść ucięta ...]"

            word_count = len(markdown.split())

            return ScrapeResult(
                url=url,
                title=title,
                markdown=markdown,
                word_count=word_count,
                success=True
            )

        except Exception as e:
            return ScrapeResult(url=url, title="", markdown="", word_count=0,
                                success=False, error=f"Błąd parsowania: {e}")


# ─── Główny silnik ─────────────────────────────────────────────────────────────

class WebSearchEngine:
    """
    Główny silnik wyszukiwania.

    Użycie:
        engine = WebSearchEngine(config)
        results = engine.search("najnowsza wersja pandas")
        content = engine.scrape("https://pypi.org/project/pandas/")
    """

    # Domyślna whitelist domen
    DEFAULT_ALLOWED_DOMAINS = [
        "pypi.org",
        "npmjs.com",
        "github.com",
        "stackoverflow.com",
        "docs.python.org",
        "developer.mozilla.org",
        "wikipedia.org",
        "readthedocs.io",
        "crates.io",
        "packagist.org",
        "rubygems.org",
        "pkg.go.dev",
    ]

    # Frazy wyzwalające wyszukiwanie
    TRIGGER_PHRASES = [
        # Polskie - wersje pakietów
        "najnowsza wersja", "aktualna wersja", "najnowszy",
        "aktualne", "co nowego", "kiedy wydano", "changelog",
        "co sie zmienilo", "nowa wersja", "zaktualizuj",
        "sprawdz wersje", "najnowszy release",
        # Polskie - pogoda i informacje biezace
        "pogoda", "temperatura", "prognoza pogody", "deszcz", "snieg",
        "kurs dolara", "kurs euro", "kurs waluty", "ile kosztuje",
        "aktualnosci", "wiadomosci", "co sie dzieje",
        "jaka jest pogoda", "jaki jest kurs", "jakie sa ceny",
        "sprawdz ", "znajdz ", "szukaj ", "poszukaj ",
        "co to jest", "czym jest", "jak dziala",
        "godziny otwarcia", "jak dojechac",
        # Angielskie - general
        "latest version", "current version", "what's new",
        "release notes", "recent changes", "update to latest",
        "weather in", "weather for", "what is the", "what are the",
        "how much", "price of", "find ", "search for",
        "current price", "exchange rate",
    ]

    def __init__(self, config: Dict, logger=None):
        """
        Args:
            config: słownik config projektu (zawiera sekcję "web_search")
            logger: opcjonalny logger
        """
        self.config = config
        self.logger = logger
        self._ws_config = config.get("web_search", {})

        # Cache
        ttl = self._ws_config.get("cache_ttl_hours", 1) * 3600
        self.cache = SearchCache(ttl_seconds=int(ttl))

        # Rate limiter
        self.rate_limiter = RateLimiter(max_per_minute=10)

        # Scraper
        self.scraper = WebScraper(logger=logger)

        # Backend
        self._backend = self._create_backend()

    def _create_backend(self):
        """Utwórz backend wyszukiwarki wg konfiguracji."""
        engine = self._ws_config.get("engine", "duckduckgo")

        if engine == "brave":
            api_key = self._ws_config.get("brave_api_key", "")
            if not api_key:
                if self.logger:
                    self.logger.warning("Brave Search wymaga 'brave_api_key' w konfiguracji")
            return BraveSearchBackend(api_key)

        # Domyślnie DuckDuckGo
        return DuckDuckGoBackend()

    @property
    def is_enabled(self) -> bool:
        """Czy web search jest włączone w konfiguracji."""
        return self._ws_config.get("enabled", False)

    @property
    def allowed_domains(self) -> List[str]:
        """Lista dozwolonych domen."""
        return self._ws_config.get("allowed_domains", self.DEFAULT_ALLOWED_DOMAINS)

    @property
    def require_confirmation(self) -> bool:
        """Czy wymagać potwierdzenia przed przeszukaniem nieznanej domeny."""
        return self._ws_config.get("require_confirmation", True)

    def is_domain_allowed(self, url: str) -> bool:
        """Sprawdź czy domena URL jest na whitelist."""
        if not url:
            return False
        try:
            domain = urllib.parse.urlparse(url).netloc.lstrip("www.")
            return any(domain == d or domain.endswith("." + d) for d in self.allowed_domains)
        except Exception:
            return False

    def search(self, query: str, max_results: int = 5) -> List[WebSearchResult]:
        """
        Wyszukaj w internecie.

        Args:
            query: zapytanie wyszukiwania
            max_results: max liczba wyników (domyślnie 5)

        Returns:
            lista WebSearchResult

        Raises:
            WebSearchError: gdy silnik wyłączony lub błąd połączenia
            RateLimitError: gdy przekroczono limit zapytań
        """
        if not self.is_enabled:
            raise WebSearchError(
                "Web search jest wyłączone. "
                "Włącz w konfiguracji: web_search.enabled = true"
            )

        max_results = min(max_results, self._ws_config.get("max_results", 5))

        # Sprawdź cache
        cached = self.cache.get(query)
        if cached is not None:
            if self.logger:
                self.logger.debug(f"Web search cache hit: {query!r}")
            return cached[:max_results]

        # Rate limiting
        allowed, wait_seconds = self.rate_limiter.check()
        if not allowed:
            raise RateLimitError(
                f"Przekroczono limit wyszukiwań (10/min). "
                f"Poczekaj {wait_seconds}s."
            )

        if self.logger:
            self.logger.info(f"Web search: {query!r} (remaining: {self.rate_limiter.remaining}/min)")

        # Wykonaj wyszukiwanie
        results = self._backend.search(query, max_results=max_results)
        self.rate_limiter.record()

        # Zapisz do cache
        self.cache.set(query, results)

        return results

    def scrape(self, url: str, force: bool = False) -> ScrapeResult:
        """
        Pobierz i przetwórz treść strony.

        Args:
            url: adres strony
            force: pomiń whitelist domen

        Returns:
            ScrapeResult
        """
        if not force and not self.is_domain_allowed(url):
            domain = urllib.parse.urlparse(url).netloc
            return ScrapeResult(
                url=url, title="", markdown="", word_count=0,
                success=False,
                error=f"Domena '{domain}' nie jest na whitelist. "
                      f"Dodaj do web_search.allowed_domains w konfiguracji."
            )

        return self.scraper.scrape(url)

    def detect_trigger(self, text: str) -> bool:
        """
        Sprawdź czy tekst zawiera frazę wyzwalającą wyszukiwanie.

        Args:
            text: tekst do sprawdzenia (zapytanie użytkownika)

        Returns:
            True jeśli wykryto trigger phrase
        """
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in self.TRIGGER_PHRASES)

    def search_and_scrape(
        self,
        query: str,
        max_results: int = 5,
        max_pages: int = 5
    ) -> Dict:
        """
        Wyszukaj + opcjonalnie scrapuj pierwsze wyniki.

        Args:
            query: zapytanie
            max_results: max wyniki wyszukiwania
            max_pages: max stron do scrapowania

        Returns:
            {
                "results": [...],
                "scraped": [...],
                "query": "...",
                "from_cache": bool
            }
        """
        results = self.search(query, max_results=max_results)

        scraped = []
        scrape_count = 0

        for result in results:
            if scrape_count >= max_pages:
                break
            if self.is_domain_allowed(result.url):
                sr = self.scraper.scrape(result.url)
                if sr.success:
                    scraped.append({
                        "url": result.url,
                        "title": sr.title or result.title,
                        "content": sr.markdown,
                        "word_count": sr.word_count
                    })
                    scrape_count += 1

        return {
            "query": query,
            "results": [r.to_dict() for r in results],
            "scraped": scraped,
            "from_cache": False
        }

    def format_results_for_prompt(self, results: List[WebSearchResult]) -> str:
        """Formatuj wyniki do wstawienia do promptu AI."""
        if not results:
            return "Brak wyników wyszukiwania."

        lines = ["=== WYNIKI WYSZUKIWANIA ===\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"[{i}] {r.format_for_prompt()}\n")

        return "\n".join(lines)

    def get_status(self) -> Dict:
        """Status silnika (dla diagnostyki)."""
        return {
            "enabled": self.is_enabled,
            "engine": self._ws_config.get("engine", "duckduckgo"),
            "allowed_domains": self.allowed_domains,
            "max_results": self._ws_config.get("max_results", 5),
            "cache_ttl_hours": self._ws_config.get("cache_ttl_hours", 1),
            "require_confirmation": self.require_confirmation,
            "rate_limiter": {
                "remaining": self.rate_limiter.remaining,
                "max_per_minute": self.rate_limiter.max_per_minute
            },
            "cache": self.cache.stats(),
            "dependencies": {
                "requests": HAS_REQUESTS,
                "beautifulsoup4": HAS_BS4,
                "html2text": HAS_HTML2TEXT
            }
        }

    def ensure_dependencies(self) -> List[str]:
        """
        Sprawdź i zwróć listę brakujących zależności.

        Returns:
            lista nazw pakietów do zainstalowania
        """
        missing = []
        if not HAS_REQUESTS:
            missing.append("requests")
        if not HAS_BS4:
            missing.append("beautifulsoup4")
        if not HAS_HTML2TEXT:
            missing.append("html2text")
        return missing
