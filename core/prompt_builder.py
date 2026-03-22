"""
PromptBuilder – warstwowy system promptów.

Zamiast wysyłać 10000 tokenów system.txt przy każdym zapytaniu,
wysyła tylko core (~2900 tok) + relevantne warstwy inject (~300-1000 tok).

Typowe zapytanie: ~3200-4000 tokenów zamiast 10000 = oszczędność ~65-70%.
"""
from pathlib import Path
import re

LAYERS_DIR = Path(__file__).parent.parent / "prompts" / "layers"

# ── Reguły triggerów ──────────────────────────────────────────────────────────
# Każdy wpis: (nazwa_pliku, [wzorce_regex | callable])
# Dopasowanie do user_input (lowercase)

TRIGGER_RULES = [
    ("patch_edit.txt", [
        r"\bedit\b", r"\bpatch\b", r"\bzamień\b", r"\bzmień\b", r"\bnapraw\b",
        r"\bpopraw\b", r"\bdodaj do\b", r"\busun\b", r"\brefaktor",
        r"\bwstaw\b", r"\bmodyfik", r"\bprzepisz\b", r"\bupdate\b",
        r"\.py\b", r"\.js\b", r"\.ts\b", r"\.html\b", r"\.css\b",
        r"\.json\b", r"\.yaml\b", r"\.toml\b", r"\.sh\b", r"\.md\b",
        # Nowe triggery - operacje na istniejących plikach
        r"\bdodaj mi\b", r"\bdodaj funkcj", r"\bdodaj obsług",
        r"\bdo istniejąc", r"\bdo główn", r"\bdo main\.py\b",
        r"\bdo.*\.py\b", r"\bdo.*\.js\b", r"\bdo.*\.html\b", r"\bdo.*\.css\b",
        r"\brozbuduj\b", r"\brozszerz\b", r"\bprzepisz.*(?:html|css|js|py)\b",
    ]),
    ("project_files.txt", [
        r"\bplik", r"\bfolder", r"\bkatalog\b", r"\bprojekt\b",
        r"\bstruktura\b", r"\bco robi\b", r"\bprzeczytaj\b", r"\bodczytaj\b",
        r"\bpokaż\b", r"\bwytłumacz\b", r"\banaliz", r"\bprzejrzyj\b",
        r"\blist\b", r"\bpliki\b", r"setup\.", r"readme", r"package\.json",
        r"\bimport\b", r"\bmoduł\b", r"\bklasa\b", r"\bfunkcja\b",
    ]),
    ("media.txt", [
        r"\bpobierz\b", r"\bdownload\b", r"\byoutube\b", r"\byt-dlp\b",
        r"\bmp3\b", r"\bmp4\b", r"\baudio\b", r"\bwideo\b", r"\bvideo\b",
        r"\bkonwertuj\b", r"\bffmpeg\b", r"\bformat\b.*\bplik",
        r"\.mp3\b", r"\.mp4\b", r"\.mkv\b", r"\.avi\b", r"\.wav\b", r"\.flac\b",
    ]),
    ("images.txt", [
        r"\.jpg\b", r"\.jpeg\b", r"\.png\b", r"\.webp\b", r"\.gif\b", r"\.bmp\b",
        r"\bobraz", r"\bzdjęci", r"\bfoto\b", r"\bfotografi", r"\bikonk",
        r"\bwizja\b", r"\bvision\b", r"\bco jest na\b", r"\bco widać\b",
        r"\bprocess.?image\b", r"\bresize\b", r"\bkompresuj\b", r"\bkonwertuj obraz",
        r"\bskreens", r"\bscreenshot\b",
    ]),
    ("clipboard.txt", [
        r"\bschowek\b", r"\bclipboard\b", r"\bskopiuj\b", r"\bwklej\b",
        r"\bpaste\b", r"\bcopy\b", r"\bxclip\b", r"\bxsel\b",
    ]),
    ("bash_tools.txt", [
        r"\bsed\b", r"\bgrep\b", r"\bawk\b", r"\bcurl\b", r"\bwget\b",
        r"\bbash\b", r"\bshell\b", r"\bkomend", r"\bterminal\b",
        r"\bscrypt\b", r"\bskrypt\b", r"\bpiping\b", r"\bpipe\b",
        r"\blinia\b.*\bplik", r"\bfragment\b.*\bplik", r"\bszukaj w plik",
        r"\bznajdź w\b", r"\bwyciągnij\b", r"\bprzefiltruj\b",
        # Diagnostyka systemu - sprawdzanie, usuwanie, instalacja
        r"\bsam sprawdź\b", r"\bsprawdź sam\b", r"\bsprawdź czy\b",
        r"\busun\b", r"\busuń\b", r"\bodinstaluj\b", r"\bwywal\b",
        r"\bzainstaluj\b", r"\binstalu\b", r"\binstall\b",
        r"\bapt\b", r"\bsnap\b", r"\bflatpak\b", r"\bdpkg\b",
        r"\bwhich\b", r"\bwersja\b.*\bprogramu", r"\bjak.*zainstalowany",
        r"\bczy.*zainstalowany", r"\bczy.*jest\b", r"\bjest.*zainstalowany",
        # Ponawianie akcji
        r"\bjeszcze raz\b", r"\bpowtórz\b", r"\bponów\b", r"\banulowałem\b",
        r"\bwykonaj ponownie\b", r"\bpowtórz akcję\b",
        # Edycja kodu - żeby AI wiedziało o sed/patch zamiast przepisywać
        r"\bnapraw\b", r"\bnapraw błąd\b", r"\bpopraw\b", r"\bdodaj funkcj",
        r"\bdodaj obsług", r"\bzmień\b", r"\budoskonali", r"\bulepsz\b",
    ]),
    ("web_search.txt", [
        r"\bszukaj\b", r"\bwyszukaj\b", r"\binternet\b", r"\bonline\b",
        r"\bweb\b", r"\bstron", r"\burl\b", r"\bhttp", r"\bwww\.",
        r"\bwikipedia\b", r"\bgithub\b", r"\bstack.?overflow\b",
        r"\bco to jest\b", r"\bczym jest\b", r"\bjakie są\b",
        r"\baktualn", r"\bnajnowsz", r"\bwersja\b", r"\bdokumentacja\b",
        r"\bporadnik\b", r"\btutorial\b",
    ]),
    ("disks_games.txt", [
        r"\bdysk\b", r"\bpartycj", r"\bmount\b", r"\bntfs\b", r"\bexfat\b",
        r"\bsteam\b", r"\bgra\b", r"\bgry\b", r"\bgame\b", r"\bappid\b",
        r"\blutris\b", r"\bheroic\b", r"\bwine\b", r"\bproton\b",
        r"\b/dev/sd", r"\b/mnt/\b", r"\b/media/\b",
    ]),
    ("kde_desktop.txt", [
        r"\bkde\b", r"\bplasma\b", r"\bskrót\b", r"\bpulpit\b",
        r"\b\.desktop\b", r"\baplikacj", r"\blauncher\b", r"\bpanel\b",
        r"\bdolphin\b", r"\bkonsole\b", r"\bkwin\b", r"\bkde connect\b",
        r"\bikonk.*pulpit", r"\bskrót.*gra", r"\butwórz skrót\b",
    ]),
    ("ai_self.txt", [
        r"\bwiedz[ay]\b", r"\bknowledg", r"\bRAG\b", r"\bindeksuj", r"\b--index\b",
        r"\bpamięć\b", r"\bmemory\b",
        r"\bjak.*działasz", r"\bco potrafisz", r"\bco możesz", r"\bco umiesz",
        r"\bjak u ciebie", r"\bo sobie\b", r"\bkonfiguracj",
        r"\bskąd wiesz", r"\bskąd bierzesz", r"\bskąd masz",
        r"\bgdzie.*wrzuc", r"\bgdzie.*dodać\b", r"\bgdzie.*umiesz",
        r"\bgdzie.*plik.*wiedz", r"\bgdzie.*wiedz",
        r"\bai model\b", r"\bai memory\b", r"\bai init\b", r"\bai --index\b",
        r"\bai config\b", r"\bprompt.*layer", r"\bwarstw.*prompt",
        r"\bsystem prompt", r"\bjak.*embedding", r"\bembedding.*działa",
        r"\btwoje.*komendy", r"\bkomendy.*ai\b", r"\bco.*potrafisz",
        r"\bjak.*dzia.*rag\b", r"\brag.*dzia",
    ]),
]

# Precompile regexes
_COMPILED_RULES: list[tuple[str, list]] = []
for fname, patterns in TRIGGER_RULES:
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    _COMPILED_RULES.append((fname, compiled))


class PromptBuilder:
    """
    Buduje system prompt z warstw: core + inject na podstawie user_input.
    """

    def __init__(self, layers_dir: Path = LAYERS_DIR):
        self.layers_dir = layers_dir
        self._cache: dict[str, str] = {}

    def _load(self, filename: str) -> str:
        """Załaduj plik warstwy (z cache)."""
        if filename not in self._cache:
            path = self.layers_dir / filename
            if path.exists():
                self._cache[filename] = path.read_text(encoding="utf-8")
            else:
                self._cache[filename] = ""
        return self._cache[filename]

    def get_layers_for_input(self, user_input: str) -> list[str]:
        """
        Zwróć listę nazw plików warstw które pasują do user_input.
        """
        matched = []
        text = user_input.lower()
        for fname, compiled_patterns in _COMPILED_RULES:
            if any(p.search(text) for p in compiled_patterns):
                matched.append(fname)
        return matched

    def build(self, user_input: str, extra_context: str = "") -> str:
        """
        Zbuduj pełny system prompt dla danego user_input.

        Zwraca: core.txt + pasujące warstwy inject + extra_context
        """
        core = self._load("core.txt")
        if not core:
            # Fallback: stary system.txt
            fallback = self.layers_dir.parent / "system.txt"
            if fallback.exists():
                return fallback.read_text(encoding="utf-8") + extra_context
            return extra_context

        layers = self.get_layers_for_input(user_input)
        inject_parts = [self._load(fname) for fname in layers if self._load(fname)]

        parts = [core]
        if inject_parts:
            parts.append("\n\n" + "\n\n".join(inject_parts))
        if extra_context:
            parts.append(extra_context)

        return "".join(parts)

    def estimate_tokens(self, user_input: str) -> dict:
        """
        Zwróć szacunkowe zużycie tokenów dla danego zapytania.
        """
        core = self._load("core.txt")
        layers = self.get_layers_for_input(user_input)
        inject_tokens = sum(len(self._load(f)) // 4 for f in layers)
        return {
            "core_tokens":   len(core) // 4,
            "inject_tokens": inject_tokens,
            "total_tokens":  len(core) // 4 + inject_tokens,
            "inject_layers": layers,
        }
