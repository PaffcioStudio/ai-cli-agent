"""
Template Manager - obsługa szablonów projektów AI CLI
Szablony: ~/.local/share/ai-cli-agent/templates/<nazwa>/
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime


# Katalog z szablonami (obok tego pliku → po instalacji w INSTALL_DIR)
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"  # utils/ -> root


def list_templates() -> list[dict]:
    """
    Zwróć listę dostępnych szablonów.
    Każdy element: {"name": "python", "path": Path, "files": [...]}
    """
    if not TEMPLATES_DIR.exists():
        return []

    templates = []
    for entry in sorted(TEMPLATES_DIR.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            files = [
                str(f.relative_to(entry))
                for f in entry.rglob("*")
                if f.is_file()
            ]
            templates.append({
                "name": entry.name,
                "path": entry,
                "files": sorted(files),
            })
    return templates


def get_template(name: str) -> dict | None:
    """Pobierz szablon po nazwie. Zwraca None jeśli nie istnieje."""
    tpl_path = TEMPLATES_DIR / name
    if not tpl_path.exists() or not tpl_path.is_dir():
        # Próba częściowego dopasowania (np. "py" → "python")
        for entry in TEMPLATES_DIR.iterdir():
            if entry.is_dir() and entry.name.startswith(name):
                tpl_path = entry
                name = entry.name
                break
        else:
            return None

    files = [
        str(f.relative_to(tpl_path))
        for f in tpl_path.rglob("*")
        if f.is_file()
    ]
    return {
        "name": name,
        "path": tpl_path,
        "files": sorted(files),
    }


def apply_variables(content: str, variables: dict) -> str:
    """
    Zamień zmienne {{VARIABLE}} w treści pliku.
    
    Standardowe zmienne:
    - {{PROJECT_NAME}}      - nazwa projektu (np. "Mój Projekt")
    - {{PROJECT_NAME_SLUG}} - slug (my-projekt, małe litery, myślniki)
    - {{AUTHOR}}            - nick/imię autora
    - {{DESCRIPTION}}       - opis projektu
    - {{YEAR}}              - aktualny rok
    """
    # Dodaj standardowe zmienne jeśli nie ma
    variables.setdefault("YEAR", str(datetime.now().year))

    # Generuj slug jeśli nie podano
    if "PROJECT_NAME_SLUG" not in variables and "PROJECT_NAME" in variables:
        slug = variables["PROJECT_NAME"].lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
        variables["PROJECT_NAME_SLUG"] = slug

    def replace_var(match):
        key = match.group(1)
        return variables.get(key, match.group(0))  # zostaw oryginał jeśli brak

    return re.sub(r"\{\{(\w+)\}\}", replace_var, content)


def apply_template(
    template_name: str,
    dest_dir: Path,
    variables: dict,
    overwrite: bool = False,
) -> dict:
    """
    Skopiuj szablon do dest_dir, podstawiając zmienne.
    
    Returns:
        {
          "success": bool,
          "template": str,
          "created": [str],   - lista stworzonych plików
          "skipped": [str],   - pliki pominięte (już istnieją)
          "error": str | None
        }
    """
    tpl = get_template(template_name)
    if not tpl:
        return {
            "success": False,
            "template": template_name,
            "created": [],
            "skipped": [],
            "error": f"Szablon '{template_name}' nie istnieje. Dostępne: {[t['name'] for t in list_templates()]}",
        }

    tpl_path: Path = tpl["path"]
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    created = []
    skipped = []

    for rel_file in tpl["files"]:
        src = tpl_path / rel_file
        dst = dest_dir / rel_file

        # Nie nadpisuj istniejących (chyba że overwrite=True)
        if dst.exists() and not overwrite:
            skipped.append(rel_file)
            continue

        # Utwórz katalogi jeśli potrzeba
        dst.parent.mkdir(parents=True, exist_ok=True)

        # Wczytaj, podstaw zmienne, zapisz
        try:
            raw = src.read_text(encoding="utf-8")
            processed = apply_variables(raw, variables)
            dst.write_text(processed, encoding="utf-8")

            # Zachowaj uprawnienia (np. *.sh = wykonywalny)
            src_mode = src.stat().st_mode
            dst.chmod(src_mode)

            created.append(rel_file)
        except Exception as e:
            return {
                "success": False,
                "template": template_name,
                "created": created,
                "skipped": skipped,
                "error": f"Błąd kopiowania {rel_file}: {e}",
            }

    return {
        "success": True,
        "template": template_name,
        "created": created,
        "skipped": skipped,
        "error": None,
    }


def format_template_list() -> str:
    """Zwróć sformatowaną listę szablonów dla UI."""
    templates = list_templates()
    if not templates:
        return "Brak dostępnych szablonów."

    lines = []
    for tpl in templates:
        files_preview = ", ".join(tpl["files"][:4])
        if len(tpl["files"]) > 4:
            files_preview += f" (+{len(tpl['files']) - 4} więcej)"
        lines.append(f"  {tpl['name']:<12} — {files_preview}")
    return "\n".join(lines)


def get_template_context_for_prompt() -> str:
    """
    Zwróć kontekst o szablonach do wstrzyknięcia w system prompt.
    """
    templates = list_templates()
    if not templates:
        return ""

    names = [t["name"] for t in templates]
    lines = ["====================", "SZABLONY PROJEKTÓW", "====================", ""]
    lines.append(f"Dostępne szablony: {', '.join(names)}")
    lines.append("")
    lines.append("Gdy użytkownik prosi o nowy projekt lub scaffold, użyj akcji use_template:")
    lines.append("")
    lines.append('{"type": "use_template", "template": "python", "dest": ".", "variables": {"PROJECT_NAME": "Mój projekt", "DESCRIPTION": "Opis"}}')
    lines.append("")
    lines.append("Zmienne szablonu:")
    lines.append("  {{PROJECT_NAME}}      - nazwa projektu")
    lines.append("  {{PROJECT_NAME_SLUG}} - slug (url-friendly, auto-generowany)")
    lines.append("  {{AUTHOR}}            - autor (pobierz z kontekstu: nick użytkownika)")
    lines.append("  {{DESCRIPTION}}       - opis projektu (zapytaj jeśli nie podano)")
    lines.append("  {{YEAR}}              - rok (auto-generowany)")
    lines.append("")
    lines.append("Szczegóły szablonów:")
    for tpl in templates:
        lines.append(f"  {tpl['name']}: {', '.join(tpl['files'])}")
    lines.append("")

    return "\n".join(lines)
