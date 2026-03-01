import os
import shutil
from pathlib import Path
from typing import List

class FileSystemTools:
    def __init__(self, dry_run=False, project_root=None):
        """
        Args:
            dry_run: czy symulować operacje
            project_root: Path do roota projektu (opcjonalny, domyślnie cwd)
        """
        if project_root is None:
            self.cwd = os.getcwd()
        else:
            self.cwd = str(project_root)
        
        self.dry_run = dry_run

        # Foldery i pliki do ignorowania (Python + Node + cache)
        self.ignore_dirs = {
            '.git',
            '.venv',
            '__pycache__',
            '.pytest_cache',
            '.cache',
            'node_modules',
            'dist',
            'build',
            '.next',
            '.nuxt',
            'venv',
            'env'
        }

        self.ignore_ext = {
            '.pyc',
            '.log',
            '.lock',
            '.min.js',
            '.min.css'
        }

    def _safe_path(self, path):
        """Bezpieczna ścieżka - zapobiega wyjściu poza katalog roboczy (ale dozwala absolutne w trybie global)"""
        p = Path(path)
        
        # Jeśli absolutna - zwróć bezpośrednio (dla trybu global)
        if p.is_absolute():
            return p
        
        # Relatywna - relatywna do cwd
        p = Path(os.path.abspath(os.path.join(self.cwd, path)))
        
        # Sprawdź czy nie wyszliśmy poza cwd (tylko dla relatywnych)
        if not str(p).startswith(self.cwd):
            raise PermissionError("Poza katalogiem roboczym")
        
        return p

    def _should_ignore(self, path: Path):
        """Sprawdź czy plik/folder powinien być ignorowany"""
        return (
            any(part in self.ignore_dirs for part in path.parts) or
            path.suffix in self.ignore_ext or
            path.name.startswith('.')
        )

    def list_files(self, pattern: str = "*", recursive: bool = False) -> List[str]:
        """
        Listuj pliki wg wzorca glob.

        Obsługuje:
          *.mp4                          → mp4 w cwd projektu
          /abs/path/*.mp4                → mp4 w podanym katalogu
          /abs/path/**/*                 → rekurencyjnie wszystkie pliki
          /abs/path/**/*.mp4             → rekurencyjnie mp4
          subdir/*.py                    → py w podkatalogu projektu
          ~/Downloads/*.mp4              → mp4 w Downloads (~ rozwijane)
          .local/share/...               → automatycznie ~/...

        UWAGA: Path("a/b/**/*").parent == "a/b/**" — to NIE jest katalog.
        Dlatego parsujemy segment po segmencie, a nie przez Path.parent.
        """
        # Rozwiń ~ jeśli present
        pattern = os.path.expanduser(pattern)
        # Normalizuj separatory
        pattern = pattern.replace("\\", "/")

        # Jeśli ścieżka zaczyna się od kropki i wygląda jak ścieżka do home
        # (.local, .config, .steam, .cache itp.) → uzupełnij ~/ na początku
        if pattern.startswith(".") and not pattern.startswith("./") and not pattern.startswith(".."):
            first_seg = pattern.split("/")[0]
            home_dotdirs = {".local", ".config", ".steam", ".cache", ".mozilla",
                           ".gnupg", ".ssh", ".bashrc", ".profile", ".bash_profile"}
            if first_seg in home_dotdirs or first_seg.startswith("."):
                pattern = os.path.expanduser("~/" + pattern)
        GLOB_CHARS = ("*", "?", "[")

        def has_glob(s: str) -> bool:
            return any(c in s for c in GLOB_CHARS)

        # Podziel na segmenty — znajdź pierwszy z globiem
        # Wszystko PRZED pierwszym glob-segmentem = base dir
        # Wszystko OD pierwszego glob-segmentu = wzorzec glob
        segments = pattern.split("/")
        base_segs: list = []
        glob_segs: list = []
        in_glob = False

        for seg in segments:
            if not in_glob and not has_glob(seg):
                base_segs.append(seg)
            else:
                in_glob = True
                glob_segs.append(seg)

        # Zrekonstruuj katalog bazowy
        base_str = "/".join(base_segs)

        if pattern.startswith("/") and not base_str.startswith("/"):
            # Absolutna ścieżka — przywróć leading slash
            base_str = "/" + base_str

        if base_str.strip("/"):
            base = Path(base_str)
        else:
            # Brak konkretnego katalogu → użyj cwd projektu
            base = self._safe_path(".")

        # Wzorzec (pusta lista → listuj wszystkie)
        glob_pattern = "/".join(glob_segs) if glob_segs else "*"

        # ** w wzorcu → zawsze rekurencyjnie
        if "**" in glob_pattern:
            recursive = True

        # Weryfikacja katalogu bazowego
        if not base.exists():
            raise FileNotFoundError(f"Katalog nie istnieje: {base}")
        if not base.is_dir():
            raise NotADirectoryError(f"To nie jest katalog: {base}")

        # Wykonaj glob — Path.glob() obsługuje ** natywnie
        try:
            matched = list(base.glob(glob_pattern))
        except Exception as e:
            raise RuntimeError(f"Błąd glob '{glob_pattern}' w '{base}': {e}")

        # Odfiltruj katalogi (zwracamy tylko pliki), ignorowane pomijamy
        # Dla absolutnych ścieżek spoza projektu NIE ignorujemy (fapzone to nie projekt)
        is_project_path = str(base).startswith(self.cwd)
        results = []
        for p in matched:
            if not p.is_file():
                continue
            # Ignoruj cache/node_modules tylko w katalogu projektu
            if is_project_path and self._should_ignore(p):
                continue
            results.append(str(p))

        return sorted(results)

    def iter_source_files(self, max_size_kb=100):
        """
        Zwraca listę plików źródłowych (Python + JS/TS + inne tekstowe)
        razem z krótką treścią do embeddingów
        """
        results = []

        for p in Path(self.cwd).rglob("*"):
            if not p.is_file():
                continue

            if self._should_ignore(p):
                continue

            if p.stat().st_size > max_size_kb * 1024:
                continue

            try:
                text = p.read_text(errors="ignore")
            except Exception:
                continue

            # bierzemy tylko początek (embedding ≠ indeks pełny)
            snippet = text[:4000]

            results.append({
                "path": str(p.relative_to(self.cwd)),
                "content": snippet
            })

        return results

    def read_file(self, path):
        """Odczytaj zawartość pliku"""
        return self._safe_path(path).read_text()

    def create_file(self, path, content):
        """Utwórz plik z zawartością. Jeśli plik już istnieje z identyczną treścią - pomija."""
        if self.dry_run:
            return f"[DRY-RUN] create_file {path}"
        
        p = self._safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        
        # Jeśli plik już istnieje z identyczną treścią - nie nadpisuj
        if p.exists():
            try:
                existing = p.read_text(encoding="utf-8", errors="replace")
                if existing.strip() == content.strip():
                    return f"Plik {path} już istnieje (bez zmian)"
            except Exception:
                pass
        
        p.write_text(content, encoding="utf-8")
        return f"Utworzono {path}"

    def mkdir(self, path):
        """Utwórz katalog"""
        if self.dry_run:
            return f"[DRY-RUN] mkdir {path}"
        
        self._safe_path(path).mkdir(parents=True, exist_ok=True)
        return f"Utworzono katalog {path}"

    def delete_file(self, path):
        """Usuń plik lub katalog"""
        if self.dry_run:
            return f"[DRY-RUN] delete {path}"
        
        p = self._safe_path(path)
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return f"Usunięto {path}"

    def move_file(self, src, dst):
        """Przenieś plik"""
        if self.dry_run:
            return f"[DRY-RUN] move {src} -> {dst}"
        
        shutil.move(self._safe_path(src), self._safe_path(dst))
        return f"Przeniesiono {src} -> {dst}"

    def chmod(self, path, mode):
        """Zmień uprawnienia pliku"""
        if self.dry_run:
            return f"[DRY-RUN] chmod {mode} {path}"
        
        p = self._safe_path(path)
        if mode == "+x":
            p.chmod(p.stat().st_mode | 0o111)
        return f"chmod {mode} {path}"