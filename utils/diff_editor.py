"""
DiffEditor - poprawiona wersja z:
1. Normalizacją wcięć przed porównaniem (fix dla match/replace)
2. Bezpiecznym edit line_start/line_end (re-read przed każdą edycją)
3. Fuzzy matching jako fallback (gdy match nie jest identyczny)
4. Lepszymi komunikatami błędów
"""

import re
from pathlib import Path


class DiffEditor:

    @staticmethod
    def edit(path, fs, match=None, replace=None, line_start=None, line_end=None, content=None):
        file_path = fs._safe_path(path)

        # --- Wczytaj aktualną treść ---
        try:
            original_content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"[BŁĄD] Nie można wczytać pliku {path}: {e}"

        lines = original_content.splitlines()
        new_content = original_content

        # ==============================
        # TRYB: match / replace
        # ==============================
        if match is not None and replace is not None:

            if match in original_content:
                # Idealne dopasowanie
                new_content = original_content.replace(match, replace, 1)

            else:
                # Spróbuj fuzzy: normalizuj białe znaki
                normalized_original = DiffEditor._normalize_whitespace(original_content)
                normalized_match    = DiffEditor._normalize_whitespace(match)

                if normalized_match in normalized_original:
                    # Znajdź i zastąp przez rekonstrukcję
                    new_content = DiffEditor._fuzzy_replace(original_content, match, replace)
                    if new_content is None:
                        return (
                            f"[BŁĄD] Znaleziono zbliżony tekst w {path}, ale nie udało się zastąpić.\n"
                            f"  Szukany (pierwsze 60 znaków): {match[:60]!r}\n"
                            f"  Wskazówka: użyj edit_file z line_start/line_end zamiast match/replace"
                        )
                else:
                    # Pokaż kontekst gdzie mógłby być
                    hint = DiffEditor._find_closest_line(lines, match)
                    return (
                        f"[BŁĄD] Nie znaleziono tekstu do zastąpienia w {path}.\n"
                        f"  Szukany (pierwsze 60 znaków): {match[:60]!r}\n"
                        f"  {hint}\n"
                        f"  Wskazówka: najpierw użyj read_file aby zobaczyć aktualną treść."
                    )

        # ==============================
        # TRYB: line_start / line_end
        # ==============================
        elif line_start is not None and line_end is not None and content is not None:

            total_lines = len(lines)

            # Walidacja
            if line_start < 1:
                return f"[BŁĄD] line_start={line_start} musi być >= 1"

            if line_start > total_lines + 1:
                return (
                    f"[BŁĄD] line_start={line_start} poza zakresem "
                    f"(plik ma {total_lines} linii).\n"
                    f"  Wskazówka: użyj read_file aby sprawdzić aktualną liczbę linii."
                )

            # Naprawka: line_end może równać się total_lines (ostatnia linia)
            # lub być tuż za nim (doklejanie na końcu)
            if line_end < line_start:
                return f"[BŁĄD] line_end={line_end} < line_start={line_start}"

            if line_end > total_lines:
                # Zamiast blokować — przytnij do ostatniej linii
                # (model często podaje +1 lub +2 przez pomyłkę)
                if line_end <= total_lines + 2:
                    line_end = total_lines
                else:
                    return (
                        f"[BŁĄD] line_end={line_end} poza zakresem (plik ma {total_lines} linii).\n"
                        f"  Wskazówka: użyj read_file aby sprawdzić aktualną liczbę linii."
                    )

            new_lines = lines[:line_start - 1] + content.splitlines() + lines[line_end:]
            new_content = "\n".join(new_lines)

            # Zachowaj trailing newline jeśli oryginał go miał
            if original_content.endswith("\n") and not new_content.endswith("\n"):
                new_content += "\n"

        else:
            return f"[BŁĄD] Niepoprawne parametry edit_file dla {path}. Wymagane: (match+replace) LUB (line_start+line_end+content)"

        # --- Sprawdź czy coś się zmieniło ---
        if new_content == original_content:
            return f"[OSTRZEŻENIE] Edycja {path} nie zmieniła zawartości pliku"

        # --- Zapisz ---
        try:
            file_path.write_text(new_content, encoding="utf-8")
        except Exception as e:
            return f"[BŁĄD] Nie można zapisać {path}: {e}"

        # --- Weryfikacja ---
        verification = DiffEditor._verify_edit(original_content, new_content, match, replace)

        if verification["success"]:
            return f"Zaktualizowano plik: {path} ({verification['lines_changed']} linii zmieniono)"
        else:
            return f"[OSTRZEŻENIE] {path} zapisano, ale: {verification['warning']}"

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Normalizuj spacje i taby — pomocne przy fuzzy match."""
        # Zamień taby na spacje, znormalizuj końce linii
        text = text.replace("\t", "    ").replace("\r\n", "\n").replace("\r", "\n")
        # Usuń trailing whitespace z każdej linii
        lines = [line.rstrip() for line in text.splitlines()]
        return "\n".join(lines)

    @staticmethod
    def _fuzzy_replace(original: str, match: str, replace: str):
        """
        Zastąp match w original ignorując różnice w wcięciach.
        Zwraca nową treść lub None przy niepowodzeniu.
        """
        match_lines = match.splitlines()
        orig_lines  = original.splitlines()

        if not match_lines:
            return None

        # Szukaj pierwszej linii match w oryginale (strip obu)
        first_stripped = match_lines[0].strip()

        for i, orig_line in enumerate(orig_lines):
            if orig_line.strip() != first_stripped:
                continue

            # Sprawdź czy kolejne linie też pasują (po strip)
            match_len = len(match_lines)
            if i + match_len > len(orig_lines):
                continue

            block = orig_lines[i:i + match_len]
            if all(b.strip() == m.strip() for b, m in zip(block, match_lines)):
                # Znaleziono! Zastąp
                new_lines = orig_lines[:i] + replace.splitlines() + orig_lines[i + match_len:]
                result = "\n".join(new_lines)
                if original.endswith("\n"):
                    result += "\n"
                return result

        return None

    @staticmethod
    def _find_closest_line(lines, match_text: str) -> str:
        """Znajdź linię w pliku najbliższą szukanemu tekstowi — hint dla użytkownika."""
        first_word = match_text.strip().split()[0] if match_text.strip() else ""
        if not first_word:
            return "Wskazówka: plik może być pusty lub match jest pusty."

        for i, line in enumerate(lines, 1):
            if first_word in line:
                return f"Zbliżona linia #{i}: {line.strip()[:80]!r}"

        return f"Pierwsze słowo {first_word!r} nie znalezione w pliku — sprawdź read_file."

    @staticmethod
    def _verify_edit(original: str, new: str, match=None, replace=None) -> dict:
        original_lines = original.splitlines()
        new_lines      = new.splitlines()

        lines_changed = sum(
            1 for o, n in zip(original_lines, new_lines) if o != n
        )
        lines_changed += abs(len(new_lines) - len(original_lines))

        if lines_changed == 0:
            return {"success": False, "lines_changed": 0, "warning": "Żadna linia nie została zmieniona"}

        if match and replace and match in new:
            return {
                "success": False,
                "lines_changed": lines_changed,
                "warning": f"Tekst '{match[:30]}...' nadal obecny w pliku (replace nie zastąpił wszystkich wystąpień?)"
            }

        return {"success": True, "lines_changed": lines_changed, "warning": None}