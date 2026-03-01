"""
Tryb REVIEW - analiza projektu bez planu ani wykonania.
Odpowiada na pytanie: co jest dobrze, co można poprawić, co dalej?

ZASADA: NIE używaj bezpośredniego dostępu do FS.
Wszystko przez ProjectAnalyzer lub ProjectMemory.
"""

from typing import Dict, List
from pathlib import Path

class ProjectReviewer:
    """
    Analizuje projekt i generuje rekomendacje.
    NIE tworzy planu akcji.
    NIE wykonuje nic.
    Tylko OCENIA i SUGERUJE.
    """
    
    def __init__(self, fs_tools, analyzer, memory):
        self.fs = fs_tools
        self.analyzer = analyzer  # ProjectAnalyzer
        self.memory = memory      # ProjectMemory
        self.root = Path(fs_tools.cwd)
    
    def review(self) -> Dict:
        """
        Przeprowadź pełny przegląd projektu.
        Zwraca strukturalny raport.
        """
        analysis = self.analyzer.analyze()
        
        review = {
            "summary": self._generate_summary(analysis),
            "strengths": self._identify_strengths(analysis),
            "weaknesses": self._identify_weaknesses(analysis),
            "missing": self._identify_missing(analysis),
            "recommendations": self._generate_recommendations(analysis),
            "next_steps": self._suggest_next_steps(analysis)
        }
        
        return review
    
    def _generate_summary(self, analysis: Dict) -> str:
        """Krótkie podsumowanie stanu projektu"""
        project_type = analysis.get("type", "unknown")
        tech = ", ".join(analysis.get("technology", []))
        
        if not tech:
            return f"Projekt typu {project_type}, technologia nierozpoznana."
        
        return f"Projekt typu {project_type} w {tech}."
    
    def _identify_strengths(self, analysis: Dict) -> List[str]:
        """Co jest dobrze w projekcie"""
        strengths = []
        
        # Sprawdź przez analyzer czy ma README
        if analysis.get("description"):
            strengths.append("Projekt ma dokumentację (README.md)")
        
        # Ma testy
        if analysis["structure"].get("has_tests"):
            strengths.append("Projekt zawiera testy")
        
        # Ma wyraźną strukturę
        if analysis["structure"].get("has_src") or analysis["structure"].get("has_lib"):
            strengths.append("Kod źródłowy zorganizowany w dedykowanym folderze")
        
        # Ma manifestu (package.json, pyproject.toml)
        if analysis.get("name"):
            strengths.append("Projekt ma manifest z metadanymi")
        
        # Ma entry point
        if analysis.get("entry_points"):
            strengths.append(f"Jasny punkt wejścia: {', '.join(analysis['entry_points'])}")
        
        # Pamięć projektu istnieje
        if self.memory.data.get("project_type"):
            strengths.append("AI zna kontekst projektu (pamięć aktywna)")
        
        return strengths if strengths else ["Podstawowa struktura projektu"]
    
    def _identify_weaknesses(self, analysis: Dict) -> List[str]:
        """Co można poprawić"""
        weaknesses = []
        
        # Brak README - wykrywamy przez brak description
        if not analysis.get("description"):
            weaknesses.append("Brak README.md - dokumentacja projektu")
        
        # Brak testów
        if not analysis["structure"].get("has_tests"):
            weaknesses.append("Brak testów - trudniej utrzymać jakość kodu")
        
        # Brak .gitignore - sprawdzamy przez fs_tools (ale nie bezpośrednio!)
        try:
            # Użyj fs_tools.read_file zamiast bezpośredniego dostępu
            self.fs.read_file(".gitignore")
        except Exception:
            weaknesses.append("Brak .gitignore - ryzyko commitowania zbędnych plików")
        
        # Płaska struktura dla większego projektu
        # Zliczamy przez analyzer, nie przez glob
        if analysis["type"] and not (analysis["structure"].get("has_src") or analysis["structure"].get("has_lib")):
            # Sprawdź czy jest dużo plików w root (heurystyka: wiele technologii = wiele plików)
            if len(analysis.get("technology", [])) > 2:
                weaknesses.append("Płaska struktura - rozważ organizację w foldery (src/, lib/)")
        
        # Web projekt bez osobnego CSS - wykrywamy przez analysis
        if analysis["type"] == "web":
            # Sprawdź czy HTML istnieje
            try:
                html_content = self.fs.read_file("index.html")
                if "<style>" in html_content:
                    # Sprawdź czy jest osobny CSS
                    try:
                        self.fs.read_file("style.css")
                    except Exception:
                        weaknesses.append("Style inline w HTML - lepiej wydzielić do osobnego pliku CSS")
            except Exception:
                pass
        
        # Node bez scripts w package.json
        if analysis["type"] in ["node-app", "node-library"]:
            try:
                import json
                pkg_content = self.fs.read_file("package.json")
                pkg = json.loads(pkg_content)
                if not pkg.get("scripts"):
                    weaknesses.append("package.json bez scripts - dodaj npm run dev/build/test")
            except Exception:
                pass
        
        return weaknesses if weaknesses else ["Brak istotnych słabości"]
    
    def _identify_missing(self, analysis: Dict) -> List[str]:
        """Czego brakuje w projekcie"""
        missing = []
        
        project_type = analysis.get("type")
        
        # Wspólne dla wszystkich - sprawdź przez fs_tools
        try:
            self.fs.read_file("LICENSE")
        except Exception:
            missing.append("Licencja (LICENSE) - ważne dla projektów open source")
        
        if not analysis["structure"].get("has_docs") and analysis.get("name"):
            missing.append("Folder docs/ z dokumentacją rozszerzoną")
        
        # Specyficzne dla typu projektu
        if project_type == "web":
            try:
                self.fs.read_file("favicon.ico")
            except Exception:
                missing.append("favicon.ico - ikona strony")
        
        if project_type in ["node-app", "node-library"]:
            try:
                self.fs.read_file("package-lock.json")
            except Exception:
                missing.append("package-lock.json - uruchom npm install")
        
        if project_type in ["python-app", "python-cli"]:
            has_requirements = False
            has_pyproject = False
            
            try:
                self.fs.read_file("requirements.txt")
                has_requirements = True
            except Exception:
                pass
            
            try:
                self.fs.read_file("pyproject.toml")
                has_pyproject = True
            except Exception:
                pass
            
            if not has_requirements and not has_pyproject:
                missing.append("requirements.txt lub pyproject.toml - zależności projektu")
        
        # CI/CD - sprawdź przez structure
        has_ci = False
        try:
            # .github folder wykryty przez analyzer
            self.fs.read_file(".github/workflows/ci.yml")
            has_ci = True
        except Exception:
            pass
        
        try:
            self.fs.read_file(".gitlab-ci.yml")
            has_ci = True
        except Exception:
            pass
        
        if not has_ci:
            missing.append("CI/CD (GitHub Actions, GitLab CI) - automatyzacja testów i deploymentu")
        
        return missing if missing else ["Projekt ma kompletną podstawową strukturę"]
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Rekomendacje ulepszeń"""
        recommendations = []
        
        weaknesses = self._identify_weaknesses(analysis)
        missing = self._identify_missing(analysis)
        
        # Priorytet 1: Dokumentacja
        if any("README" in w for w in weaknesses):
            recommendations.append("[PRIORYTET] Dodaj README.md z opisem projektu, instalacją i użyciem")
        
        # Priorytet 2: Testy
        if any("test" in w.lower() for w in weaknesses):
            recommendations.append("[PRIORYTET] Dodaj testy - zacznij od testów jednostkowych dla kluczowej logiki")
        
        # Organizacja kodu
        if any("Płaska struktura" in w for w in weaknesses):
            recommendations.append("Reorganizuj kod w foldery (src/ dla źródeł, tests/ dla testów)")
        
        # Web specyficzne
        if analysis["type"] == "web":
            if any("Style inline" in w for w in weaknesses):
                recommendations.append("Przenieś style CSS do osobnego pliku dla lepszej organizacji")
        
        # Tooling - sprawdź przez fs_tools
        try:
            self.fs.read_file(".editorconfig")
        except Exception:
            recommendations.append("Dodaj .editorconfig dla spójnego formatowania kodu")
        
        # Git
        if any("gitignore" in w.lower() for w in weaknesses):
            recommendations.append("Dodaj .gitignore dopasowany do używanej technologii")
        
        return recommendations if recommendations else ["Projekt w dobrej kondycji - kontynuuj rozwój"]
    
    def _suggest_next_steps(self, analysis: Dict) -> List[str]:
        """Zasugeruj konkretne następne kroki"""
        steps = []
        
        # Na podstawie historii decyzji z pamięci
        recent_decisions = self.memory.data.get("decisions", [])[-3:]
        
        if recent_decisions:
            last_action = recent_decisions[-1].get("command", "")
            
            # Jeśli ostatnio tworzono projekt
            if any(word in last_action.lower() for word in ["stwórz", "zrób", "utwórz"]):
                steps.append("Przetestuj utworzoną funkcjonalność")
                steps.append("Dodaj .gitignore i zainicjuj git repo (git init)")
                steps.append("Zrób pierwszy commit")
        
        # Ogólne propozycje rozwoju na podstawie analysis
        project_type = analysis.get("type")
        
        if project_type == "web":
            steps.append("Dodaj meta tagi dla SEO (description, keywords)")
            steps.append("Sprawdź responsywność na urządzeniach mobilnych")
            steps.append("Rozważ dodanie Progressive Web App (PWA)")
        
        if project_type in ["python-cli", "python-app"]:
            steps.append("Dodaj type hints dla lepszej czytelności")
            steps.append("Skonfiguruj pre-commit hooks (black, flake8)")
            steps.append("Rozważ używanie poetry zamiast pip")
        
        if project_type in ["node-app", "node-library"]:
            steps.append("Dodaj linting (eslint) i formatowanie (prettier)")
            steps.append("Skonfiguruj pre-commit hooks (husky)")
            steps.append("Rozważ TypeScript dla lepszej type safety")
        
        return steps[:5] if steps else ["Projekt gotowy do dalszego rozwoju"]
    
    def format_review(self, review: Dict) -> str:
        """Sformatuj raport przeglądu do wyświetlenia"""
        lines = []
        
        lines.append(review["summary"])
        lines.append("")
        
        if review["strengths"]:
            lines.append("CO JEST DOBRZE:")
            for s in review["strengths"]:
                lines.append(f"  ✓ {s}")
            lines.append("")
        
        if review["weaknesses"]:
            lines.append("CO MOŻNA POPRAWIĆ:")
            for w in review["weaknesses"]:
                lines.append(f"  • {w}")
            lines.append("")
        
        if review["missing"]:
            lines.append("CZEGO BRAKUJE:")
            for m in review["missing"]:
                lines.append(f"  ○ {m}")
            lines.append("")
        
        if review["recommendations"]:
            lines.append("REKOMENDACJE:")
            for r in review["recommendations"]:
                lines.append(f"  → {r}")
            lines.append("")
        
        if review["next_steps"]:
            lines.append("NASTĘPNE KROKI:")
            for i, step in enumerate(review["next_steps"], 1):
                lines.append(f"  {i}. {step}")
        
        return "\n".join(lines)