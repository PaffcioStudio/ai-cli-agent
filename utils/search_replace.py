"""
SearchReplacePatcher - precyzyjny silnik edycji plików.

OBSŁUGIWANE FORMATY WEJŚCIOWE (obydwa naraz):

FORMAT A — "patches" lista słowników (PREFEROWANY, zero escaping):
    {
      "type": "patch_file",
      "path": "app.py",
      "patches": [
        {
          "search":  ["def foo():", "    return 1"],
          "replace": ["def foo():", "    return 42"]
        },
        {
          "search":  ["VERSION = \"1.0\""],
          "replace": ["VERSION = \"2.0\""]
        }
      ]
    }

FORMAT B — "diff" string z blokami SEARCH/REPLACE (czytelny dla człowieka):
    {
      "type": "patch_file",
      "path": "app.py",
      "diff": "<<<<<<< SEARCH\\ndef foo():\\n    return 1\\n=======\\ndef foo():\\n    return 42\\n>>>>>>> REPLACE"
    }

DLACZEGO FORMAT A JEST LEPSZY:
- Zero escaping: każda linia to osobny element tablicy JSON
- Model nie musi pisać \\n ani \\" wewnątrz stringów
- Parser po stronie Pythona robi "\n".join(lines) — trywialne
- Mniej błędów przy generowaniu przez LLM

FALLBACK CHAIN PRZY DOPASOWANIU:
1. exact         — str.find(), najszybszy
2. strip         — normalizacja trailing whitespace, taby→spacje, CRLF→LF  
3. fuzzy_indent  — porównanie linia-po-linii z .strip() (różne wcięcia)
4. sequence      — difflib.SequenceMatcher ≥ 0.82 (ostrzeżenie przy użyciu)

ATOMOWOŚĆ:
Jeśli JEDEN blok w patches nie zostanie znaleziony → plik NIE jest modyfikowany.
Zero ryzyka "half-patched" stanu.

WERYFIKACJA DUPLIKATÓW:
Jeśli SEARCH pasuje do więcej niż jednego miejsca w pliku → błąd z podpowiedzią
żeby użytkownik dodał więcej kontekstu.
"""

import re
import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union


# ──────────────────────────────────────────────────────────────────────────────
# Stałe separatorów (Format B)
# ──────────────────────────────────────────────────────────────────────────────

_RE_SEARCH  = re.compile(r"^<{4,}\s*SEARCH\s*$", re.IGNORECASE)
_RE_DIV     = re.compile(r"^={4,}\s*$")
_RE_REPLACE = re.compile(r"^>{4,}\s*REPLACE\s*$", re.IGNORECASE)


# ──────────────────────────────────────────────────────────────────────────────
# Typy danych
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SearchReplaceBlock:
    search:  str
    replace: str
    index:   int = 0


@dataclass
class PatchResult:
    success:       bool
    content:       Optional[str] = None
    error:         Optional[str] = None
    match_method:  str = "exact"
    lines_changed: int = 0


@dataclass
class FilePatchResult:
    path:          str
    success:       bool
    blocks_ok:     int = 0
    blocks_failed: int = 0
    errors:        list = field(default_factory=list)
    lines_changed: int = 0
    final_content: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Parser — Format B (<<<<<<< SEARCH bloki)
# ──────────────────────────────────────────────────────────────────────────────

class SearchReplaceParser:
    """Parsuje string z blokami SEARCH/REPLACE."""

    @staticmethod
    def parse(diff_text: str) -> list:
        lines  = diff_text.splitlines()
        blocks = []
        i      = 0

        while i < len(lines):
            if not _RE_SEARCH.match(lines[i].strip()):
                i += 1
                continue

            block_idx     = len(blocks) + 1
            search_lines  = []
            replace_lines = []
            state = "search"
            i += 1

            while i < len(lines):
                cur = lines[i]
                if state == "search":
                    if _RE_DIV.match(cur.strip()):
                        state = "div"; i += 1; continue
                    if _RE_SEARCH.match(cur.strip()):
                        raise ValueError(f"Blok #{block_idx}: zagnieżdżony <<<<<<< SEARCH")
                    search_lines.append(cur)
                elif state == "div":
                    if _RE_REPLACE.match(cur.strip()):
                        state = "done"; i += 1; break
                    if _RE_DIV.match(cur.strip()):
                        raise ValueError(f"Blok #{block_idx}: podwójny =======")
                    replace_lines.append(cur)
                i += 1

            if state != "done":
                missing = "=======" if state == "search" else ">>>>>>> REPLACE"
                raise ValueError(f"Blok #{block_idx}: niekompletny — brak {missing}")

            search_text = "\n".join(search_lines)
            if not search_text.strip():
                raise ValueError(
                    f"Blok #{block_idx}: sekcja SEARCH jest pusta. "
                    "Użyj ostatniej istniejącej linii jako SEARCH i dołącz nowy tekst w REPLACE."
                )

            blocks.append(SearchReplaceBlock(
                search=search_text,
                replace="\n".join(replace_lines),
                index=block_idx
            ))

        return blocks

    @staticmethod
    def from_patches_list(patches: list) -> list:
        """
        Konwertuj Format A (lista słowników) na listę SearchReplaceBlock.

        Każdy element patches to:
          {"search": ["linia1", "linia2"], "replace": ["linia1", "linia2"]}
        lub (krótki string dla prostych zamian):
          {"search": "stary tekst", "replace": "nowy tekst"}
        """
        blocks = []
        for i, patch in enumerate(patches, 1):
            if not isinstance(patch, dict):
                raise ValueError(f"Patch #{i}: musi być słownikiem, nie {type(patch).__name__}")

            if "search" not in patch:
                raise ValueError(f"Patch #{i}: brak pola 'search'")
            if "replace" not in patch:
                raise ValueError(f"Patch #{i}: brak pola 'replace'")

            s = patch["search"]
            r = patch["replace"]

            # Obsługa list i stringów
            if isinstance(s, list):
                search_text = "\n".join(str(x) for x in s)
            elif isinstance(s, str):
                search_text = s
            else:
                raise ValueError(f"Patch #{i}: 'search' musi być stringiem lub listą linii")

            if isinstance(r, list):
                replace_text = "\n".join(str(x) for x in r)
            elif isinstance(r, str):
                replace_text = r
            else:
                raise ValueError(f"Patch #{i}: 'replace' musi być stringiem lub listą linii")

            if not search_text.strip():
                raise ValueError(
                    f"Patch #{i}: 'search' jest pusty. "
                    "Podaj co najmniej jedną linię kontekstu do znalezienia."
                )

            blocks.append(SearchReplaceBlock(search=search_text, replace=replace_text, index=i))

        return blocks


# ──────────────────────────────────────────────────────────────────────────────
# Silnik dopasowania
# ──────────────────────────────────────────────────────────────────────────────

class SearchReplaceMatcher:
    """
    Fallback chain: exact → strip → fuzzy_indent → sequence.
    Dodatkowo: wykrywa gdy SEARCH pasuje do wielu miejsc (duplikat).
    """

    SEQUENCE_THRESHOLD = 0.82

    @classmethod
    def find_and_replace(cls, content: str, block: SearchReplaceBlock) -> PatchResult:
        methods = [
            ("exact",        cls._try_exact),
            ("strip",        cls._try_strip),
            ("fuzzy_indent", cls._try_fuzzy_indent),
            ("sequence",     cls._try_sequence),
        ]

        for method_name, fn in methods:
            result = fn(content, block.search, block.replace)
            if result is not None:
                new_content, lines_changed = result
                return PatchResult(
                    success=True,
                    content=new_content,
                    match_method=method_name,
                    lines_changed=lines_changed,
                )

        hint = cls._build_hint(content, block.search)
        return PatchResult(
            success=False,
            error=(
                f"Blok #{block.index}: nie znaleziono fragmentu SEARCH.\n"
                f"  Pierwsze 80 znaków SEARCH: {block.search[:80]!r}\n"
                f"  {hint}\n"
                f"  → Użyj read_file aby zobaczyć aktualną treść, "
                f"dodaj więcej linii kontekstu do SEARCH."
            )
        )

    # ── Weryfikacja duplikatów ──────────────────────────────────────────────

    @classmethod
    def check_ambiguous(cls, content: str, search: str) -> Optional[str]:
        """
        Sprawdź czy SEARCH pasuje do więcej niż jednego miejsca.
        Zwraca ostrzeżenie jeśli tak, None jeśli unikalne.
        """
        count = 0
        start = 0
        while True:
            pos = content.find(search, start)
            if pos == -1:
                break
            count += 1
            start = pos + 1
            if count > 1:
                break

        if count > 1:
            return (
                f"Fragment SEARCH pasuje do {count}+ miejsc w pliku. "
                f"Dodaj więcej linii kontekstu (linię przed i po), "
                f"żeby jednoznacznie wskazać miejsce zmiany."
            )
        return None

    # ── Strategie ──────────────────────────────────────────────────────────

    @staticmethod
    def _count_changed(s1: str, s2: str) -> int:
        lines1 = s1.splitlines()
        lines2 = s2.splitlines()
        changed = sum(1 for a, b in zip(lines1, lines2) if a != b)
        changed += abs(len(lines1) - len(lines2))
        return changed

    @classmethod
    def _try_exact(cls, content: str, search: str, replace: str):
        # Weryfikacja duplikatów tylko dla exact (najszybsza ścieżka)
        pos = content.find(search)
        if pos == -1:
            return None
        # Sprawdź duplikaty
        warn = cls.check_ambiguous(content, search)
        if warn:
            # Duplikat — nie robimy nic, błąd wyżej
            return None  # Traktuj jak brak dopasowania → wymusi błąd z podpowiedzią
        new = content[:pos] + replace + content[pos + len(search):]
        return new, cls._count_changed(search, replace)

    @staticmethod
    def _normalize(t: str) -> str:
        t = t.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
        return "\n".join(line.rstrip() for line in t.splitlines())

    @classmethod
    def _try_strip(cls, content: str, search: str, replace: str):
        nc = cls._normalize(content)
        ns = cls._normalize(search)
        pos = nc.find(ns)
        if pos == -1:
            return None
        # Weryfikacja duplikatów
        if nc.find(ns, pos + 1) != -1:
            return None
        n_lines = nc[:pos].count("\n")
        s_count = ns.count("\n") + 1
        o_lines = content.splitlines()
        if n_lines + s_count > len(o_lines):
            return None
        new_lines = o_lines[:n_lines] + replace.splitlines() + o_lines[n_lines + s_count:]
        new = "\n".join(new_lines)
        if content.endswith("\n"):
            new += "\n"
        return new, s_count

    @staticmethod
    def _try_fuzzy_indent(content: str, search: str, replace: str):
        s_lines  = search.splitlines()
        c_lines  = content.splitlines()
        s_strip  = [l.strip() for l in s_lines]
        if not s_strip or not s_strip[0]:
            return None

        matches = []
        for i in range(len(c_lines) - len(s_lines) + 1):
            block = [l.strip() for l in c_lines[i:i + len(s_lines)]]
            if block == s_strip:
                matches.append(i)

        if len(matches) != 1:
            return None  # 0 = nie znaleziono, >1 = niejednoznaczne

        i = matches[0]
        new_lines = c_lines[:i] + replace.splitlines() + c_lines[i + len(s_lines):]
        new = "\n".join(new_lines)
        if content.endswith("\n"):
            new += "\n"
        return new, len(s_lines)

    @classmethod
    def _try_sequence(cls, content: str, search: str, replace: str):
        s_lines = search.splitlines()
        c_lines = content.splitlines()
        n = len(s_lines)
        if n == 0 or n > len(c_lines):
            return None

        best_ratio = 0.0
        best_i     = -1
        second_best = 0.0

        for i in range(len(c_lines) - n + 1):
            ratio = difflib.SequenceMatcher(
                None,
                "\n".join(s_lines),
                "\n".join(c_lines[i:i + n])
            ).ratio()
            if ratio > best_ratio:
                second_best = best_ratio
                best_ratio  = ratio
                best_i      = i
            elif ratio > second_best:
                second_best = ratio

        # Wymaga jasnej dominacji — nie tylko progu
        if best_ratio < cls.SEQUENCE_THRESHOLD:
            return None
        if second_best > 0.70:
            return None  # Za dużo podobnych fragmentów — niejednoznaczne

        new_lines = c_lines[:best_i] + replace.splitlines() + c_lines[best_i + n:]
        new = "\n".join(new_lines)
        if content.endswith("\n"):
            new += "\n"
        return new, n

    @staticmethod
    def _build_hint(content: str, search: str) -> str:
        first_line = search.strip().splitlines()[0].strip() if search.strip() else ""
        if not first_line:
            return "Wskazówka: sekcja SEARCH wydaje się pusta."
        first_word = first_line.split()[0] if first_line.split() else ""
        candidates = []
        for i, line in enumerate(content.splitlines(), 1):
            if first_word and first_word in line:
                candidates.append(f"  Linia {i}: {line.strip()[:80]!r}")
            if len(candidates) >= 3:
                break
        if candidates:
            return "Zbliżone linie w pliku:\n" + "\n".join(candidates)
        return f"Pierwsze słowo '{first_word}' nie znalezione — sprawdź read_file."


# ──────────────────────────────────────────────────────────────────────────────
# Główny interfejs
# ──────────────────────────────────────────────────────────────────────────────

class SearchReplacePatcher:

    @classmethod
    def apply_to_file(
        cls,
        path: str,
        diff_text: str = None,
        fs = None,
        dry_run: bool = False,
        patches: list = None,
    ) -> FilePatchResult:
        """
        Zastosuj zmiany na plik.

        Podaj JEDEN z:
          diff_text — string z blokami <<<<<<< SEARCH (Format B)
          patches   — lista {"search": [...], "replace": [...]} (Format A)
        """
        result = FilePatchResult(path=path, success=False)

        # Parsowanie wejścia
        try:
            if patches is not None:
                blocks = SearchReplaceParser.from_patches_list(patches)
            elif diff_text is not None:
                blocks = SearchReplaceParser.parse(diff_text)
            else:
                result.errors.append("[BŁĄD] patch_file: podaj 'patches' (lista) lub 'diff' (string)")
                return result
        except ValueError as e:
            result.errors.append(f"[BŁĄD] Parsowanie: {e}")
            return result

        if not blocks:
            result.errors.append("[BŁĄD] Brak bloków SEARCH/REPLACE")
            return result

        return cls._apply_blocks(path, blocks, fs, dry_run, result)

    @classmethod
    def _apply_blocks(
        cls,
        path: str,
        blocks: list,
        fs,
        dry_run: bool,
        result: FilePatchResult
    ) -> FilePatchResult:
        # Wczytaj plik
        try:
            file_path = fs._safe_path(path)
            content   = file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            result.errors.append(
                f"[BŁĄD] Plik '{path}' nie istnieje. "
                "Użyj create_file zamiast patch_file dla nowych plików."
            )
            return result
        except Exception as e:
            result.errors.append(f"[BŁĄD] Nie można wczytać '{path}': {e}")
            return result

        # Zastosuj bloki sekwencyjnie
        current = content

        for block in blocks:
            patch = SearchReplaceMatcher.find_and_replace(current, block)

            if patch.success:
                current = patch.content
                result.blocks_ok      += 1
                result.lines_changed  += patch.lines_changed
                if patch.match_method in ("fuzzy_indent", "sequence"):
                    result.errors.append(
                        f"[OSTRZEŻENIE] Blok #{block.index}: "
                        f"dopasowanie przez {patch.match_method} "
                        f"(wcięcia lub drobne różnice zostały zignorowane)"
                    )
            else:
                result.blocks_failed += 1
                result.errors.append(patch.error)

        # Atomowość — nie zapisuj jeśli cokolwiek się nie powiodło
        if result.blocks_failed > 0:
            result.success = False
            result.errors.insert(0,
                f"[BŁĄD] {result.blocks_failed}/{len(blocks)} bloków nie pasuje. "
                "Plik NIE został zmodyfikowany (atomowy rollback)."
            )
            return result

        if current == content:
            result.success = False
            result.errors.append("[OSTRZEŻENIE] Patch nie zmienił zawartości pliku.")
            return result

        result.final_content = current

        if not dry_run:
            try:
                file_path.write_text(current, encoding="utf-8")
            except Exception as e:
                result.success = False
                result.errors.append(f"[BŁĄD] Nie można zapisać '{path}': {e}")
                return result

        result.success = True
        return result

    @classmethod
    def format_result(cls, result: FilePatchResult) -> str:
        if result.success:
            warnings = [e for e in result.errors if e.startswith("[OSTRZEŻENIE]")]
            msg = (
                f"Zaktualizowano '{result.path}': "
                f"{result.blocks_ok} blok(ów), "
                f"~{result.lines_changed} linii zmieniono"
            )
            if warnings:
                msg += "\n" + "\n".join(warnings)
            return msg
        return "\n".join(result.errors)
