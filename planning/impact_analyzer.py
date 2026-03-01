"""
Moduł analizy wpływu zmian.
Odpowiada na pytanie: jak ta zmiana wpłynie na resztę projektu?
"""

from typing import Dict, List, Set
from pathlib import Path
import re

class FileRole:
    """Role plików w projekcie"""
    ENTRY_POINT = "entry_point"     # main.py, index.js, app.py
    CONFIG = "config"               # config.py, settings.json
    API_PUBLIC = "api_public"       # publiczny interfejs biblioteki
    UI = "ui"                       # komponenty UI
    LOGIC = "logic"                 # logika biznesowa
    TEST = "test"                   # testy
    DOCS = "docs"                   # dokumentacja
    BUILD = "build"                 # build scripts, tooling
    UNKNOWN = "unknown"

class ImpactAnalyzer:
    """
    Analizuje wpływ zmian na projekt.
    Buduje zależności między plikami i rozumie ich role.

    WAŻNE: analiza jest LAZY — nie odpala się w __init__,
    tylko przy pierwszym wywołaniu analyze_impact().
    Dzięki temu inicjalizacja agenta jest natychmiastowa.
    """

    def __init__(self, fs_tools):
        self.fs = fs_tools
        self.root = Path(fs_tools.cwd)
        self.file_roles: Dict[str, str] = {}
        self.dependencies: Dict[str, Set[str]] = {}
        self._analyzed = False   # flaga lazy init

    def _ensure_analyzed(self):
        """Odpal analizę przy pierwszym użyciu."""
        if self._analyzed:
            return
        self._analyzed = True
        self._identify_file_roles()
        self._build_dependency_graph()

    def _identify_file_roles(self):
        """Określ role plików w projekcie"""

        # Entry points — tylko sprawdzenie czy plik istnieje, bez rglob
        entry_points = [
            "main.py", "__main__.py", "app.py",
            "index.js", "main.js", "index.html"
        ]
        for ep in entry_points:
            if (self.root / ep).exists():
                self.file_roles[ep] = FileRole.ENTRY_POINT

        # Reszta — rglob tylko w obrębie projektu
        config_patterns = ["config", "settings", ".env", "package.json", "pyproject.toml"]

        try:
            for file_path in self.root.rglob("*"):
                if not file_path.is_file():
                    continue

                try:
                    rel_path = str(file_path.relative_to(self.root))
                except ValueError:
                    # Plik poza self.root (symlink itp.) — pomijamy
                    continue

                name_lower = file_path.name.lower()

                if any(pattern in name_lower for pattern in config_patterns):
                    self.file_roles[rel_path] = FileRole.CONFIG

                elif "test" in name_lower or file_path.parent.name in ("tests", "test", "__tests__"):
                    self.file_roles[rel_path] = FileRole.TEST

                elif file_path.parent.name == "docs" or name_lower in ("readme.md", "contributing.md"):
                    self.file_roles[rel_path] = FileRole.DOCS

                elif file_path.suffix in (".html", ".jsx", ".tsx") or "component" in name_lower:
                    self.file_roles[rel_path] = FileRole.UI

                elif name_lower in (
                    "webpack.config.js", "rollup.config.js",
                    "vite.config.js", "setup.py"
                ):
                    self.file_roles[rel_path] = FileRole.BUILD

        except PermissionError:
            pass

    def _build_dependency_graph(self):
        """Zbuduj graf zależności między plikami"""

        try:
            for file_path in self.root.rglob("*"):
                if not file_path.is_file():
                    continue

                if file_path.suffix not in (".py", ".js", ".jsx", ".ts", ".tsx"):
                    continue

                try:
                    rel_path = str(file_path.relative_to(self.root))
                except ValueError:
                    continue

                try:
                    content = file_path.read_text(errors="ignore")
                    imports = self._extract_imports(content, file_path.suffix)
                    self.dependencies[rel_path] = imports
                except Exception:
                    pass

        except PermissionError:
            pass

    def _extract_imports(self, content: str, file_suffix: str) -> Set[str]:
        """Wyciągnij importy z pliku"""
        imports: Set[str] = set()

        if file_suffix == ".py":
            pattern = r'(?:from|import)\s+([a-zA-Z0-9_.]+)'
            for match in re.finditer(pattern, content):
                module = match.group(1)
                if not module.startswith(("os", "sys", "json", "pathlib")):
                    imports.add(module)

        elif file_suffix in (".js", ".jsx", ".ts", ".tsx"):
            pattern = r'(?:import|require)\s*\(?[\'"]([./][^\'"]+)[\'"]'
            for match in re.finditer(pattern, content):
                imports.add(match.group(1))

        return imports

    def analyze_impact(self, actions: List[Dict]) -> Dict:
        """
        Przeanalizuj wpływ akcji na projekt.
        Zwraca raport wpływu.
        """
        # Lazy init — tutaj, nie w __init__
        self._ensure_analyzed()

        affected_files: Set[str] = set()
        roles_affected: Set[str] = set()

        for action in actions:
            if action.get("type") in ("create_file", "edit_file", "delete_file"):
                path = action.get("path", "")
                affected_files.add(path)
                role = self.file_roles.get(path, FileRole.UNKNOWN)
                roles_affected.add(role)

        indirectly_affected: Set[str] = set()
        for affected in affected_files:
            for file, deps in self.dependencies.items():
                if any(affected in dep for dep in deps):
                    indirectly_affected.add(file)

        impact = {
            "directly_affected":   list(affected_files),
            "indirectly_affected": list(indirectly_affected),
            "roles_affected":      list(roles_affected),
            "severity":   self._calculate_severity(roles_affected, len(affected_files)),
            "warnings":   self._generate_warnings(roles_affected, affected_files),
            "suggestions": self._generate_suggestions(roles_affected, affected_files),
        }

        return impact

    def _calculate_severity(self, roles: Set[str], file_count: int) -> str:
        if FileRole.ENTRY_POINT in roles:
            return "critical"
        if FileRole.CONFIG in roles:
            return "high"
        if FileRole.UI in roles and file_count > 3:
            return "medium"
        if roles.issubset({FileRole.TEST, FileRole.DOCS, FileRole.UNKNOWN}):
            return "low"
        return "medium"

    def _generate_warnings(self, roles: Set[str], files: Set[str]) -> List[str]:
        warnings = []

        if FileRole.ENTRY_POINT in roles:
            warnings.append("Zmiany w entry point mogą wpłynąć na uruchamianie aplikacji")
        if FileRole.CONFIG in roles:
            warnings.append("Zmiany w konfiguracji mogą wymagać restartu lub reinicjalizacji")
        if FileRole.API_PUBLIC in roles:
            warnings.append("Zmiany w publicznym API mogą złamać kompatybilność wsteczną")
        if FileRole.UI in roles and len(files) > 5:
            warnings.append("Duża liczba zmian w UI - warto przetestować interakcje użytkownika")
        if FileRole.LOGIC in roles and FileRole.TEST not in roles:
            warnings.append("Zmiany w logice biznesowej bez aktualizacji testów")

        return warnings

    def _generate_suggestions(self, roles: Set[str], files: Set[str]) -> List[str]:
        suggestions = []

        if FileRole.UI in roles:
            suggestions.append("Rozważ aktualizację README z opisem zmian w interfejsie")
            suggestions.append("Sprawdź responsywność na różnych rozdzielczościach")
        if FileRole.LOGIC in roles:
            suggestions.append("Zaktualizuj lub dodaj testy jednostkowe")
            suggestions.append("Sprawdź czy dokumentacja odzwierciedla nowe zachowanie")
        if FileRole.CONFIG in roles:
            suggestions.append("Sprawdź czy dokumentacja zawiera nowe opcje konfiguracji")
            suggestions.append("Rozważ dodanie przykładowej konfiguracji w README")
        if len(files) > 5:
            suggestions.append("Duży zakres zmian - rozważ commitowanie w mniejszych częściach")

        has_tests = any(
            self.file_roles.get(f, FileRole.UNKNOWN) == FileRole.TEST
            for f in self.file_roles
        )
        if not has_tests and FileRole.LOGIC in roles:
            suggestions.append("Projekt nie ma testów - rozważ ich dodanie")

        return suggestions

    def get_file_role(self, path: str) -> str:
        """Zwróć rolę pliku"""
        self._ensure_analyzed()
        return self.file_roles.get(path, FileRole.UNKNOWN)

    def format_impact_report(self, impact: Dict) -> str:
        """Sformatuj raport wpływu do wyświetlenia"""
        lines = []

        severity_emoji = {
            "low":      "✓",
            "medium":   "⚠",
            "high":     "⚠⚠",
            "critical": "🔴",
        }

        emoji = severity_emoji.get(impact["severity"], "•")
        lines.append(f"{emoji} Poziom wpływu: {impact['severity']}")

        if impact["directly_affected"]:
            lines.append(f"\nPliki bezpośrednio zmienione: {len(impact['directly_affected'])}")

        if impact["indirectly_affected"]:
            lines.append(f"Pliki pośrednio dotknięte: {len(impact['indirectly_affected'])}")
            for f in impact["indirectly_affected"][:3]:
                lines.append(f"  • {f}")
            if len(impact["indirectly_affected"]) > 3:
                lines.append(f"  ... i {len(impact['indirectly_affected']) - 3} więcej")

        if impact["warnings"]:
            lines.append("\nOstrzeżenia:")
            for w in impact["warnings"]:
                lines.append(f"  ⚠ {w}")

        if impact["suggestions"]:
            lines.append("\nSugestie:")
            for s in impact["suggestions"]:
                lines.append(f"  → {s}")

        return "\n".join(lines)