"""
Project Detector - wykrywa czy jesteśmy w projekcie.

PROBLEM:
- ai poza katalogiem projektu próbuje analizować cały FS
- rglob na ~/Pobrane = katastrofa wydajnościowa
- brak koncepcji "project root"

ROZWIĄZANIE:
- wykrywaj projekt PO markierach
- jeśli nie znaleziono = tryb SYSTEM/GLOBAL
"""

from pathlib import Path
from typing import Optional

class ProjectDetector:
    """
    Wykrywa czy jesteśmy w katalogu projektu.
    
    Projekt = katalog zawierający którykolwiek z markerów:
    - .ai-context.json (najwyższy priorytet)
    - .git
    - package.json
    - pyproject.toml
    - setup.py
    - Cargo.toml
    - go.mod
    - composer.json
    """
    
    PROJECT_MARKERS = [
        ".ai-context.json",  # Priorytet 1
        ".git",              # Priorytet 2
        "package.json",      # Node
        "pyproject.toml",    # Python modern
        "setup.py",          # Python legacy
        "requirements.txt",  # Python simple
        "Cargo.toml",        # Rust
        "go.mod",            # Go
        "composer.json",     # PHP
        "pom.xml",           # Java Maven
        "build.gradle",      # Java Gradle
    ]
    
    @classmethod
    def detect_project_root(cls, start_path: Optional[Path] = None) -> Optional[Path]:
        """
        Wykryj root projektu.
        
        WAŻNE: Jeśli nie znaleziono markerów, zwróć None.
        Agent potem użyje cwd jako fallback.
        """
        if start_path is None:
            start_path = Path.cwd()
        
        current = start_path.resolve()
        home = Path.home()
        
        # Idź w górę do home dir
        while current != home and current != current.parent:
            # Sprawdź markery w kolejności priorytetu
            for marker in cls.PROJECT_MARKERS:
                marker_path = current / marker
                if marker_path.exists():
                    return current
            
            # Poziom wyżej
            current = current.parent
        
        # Jeśli nic nie znaleziono, zwróć None (a nie home!)
        return None
    
    @classmethod
    def is_in_project(cls, path: Optional[Path] = None) -> bool:
        """Czy jesteśmy w katalogu projektu?"""
        return cls.detect_project_root(path) is not None
    
    @classmethod
    def get_project_type(cls, project_root: Path) -> str:
        """
        Określ typ projektu na podstawie markerów.
        
        Returns:
            "node", "python", "rust", "go", "php", "java", "git-only", "unknown"
        """
        if (project_root / "package.json").exists():
            return "node"
        
        if (project_root / "pyproject.toml").exists() or (project_root / "setup.py").exists():
            return "python"
        
        if (project_root / "requirements.txt").exists():
            return "python"
        
        if (project_root / "Cargo.toml").exists():
            return "rust"
        
        if (project_root / "go.mod").exists():
            return "go"
        
        if (project_root / "composer.json").exists():
            return "php"
        
        if (project_root / "pom.xml").exists() or (project_root / "build.gradle").exists():
            return "java"
        
        if (project_root / ".git").exists():
            return "git-only"
        
        return "unknown"
    
    @classmethod
    def require_project(cls, path: Optional[Path] = None) -> Path:
        """
        Wymaga projektu - jeśli nie znaleziono, rzuć wyjątek.
        
        Raises:
            NotInProjectError
        
        Returns:
            Path do root projektu
        """
        project_root = cls.detect_project_root(path)
        
        if project_root is None:
            raise NotInProjectError(
                "Nie jesteś w katalogu projektu.\n"
                "\n"
                "AI CLI wymaga projektu (katalog z .git, package.json, pyproject.toml itp.)\n"
                "\n"
                "Opcje:\n"
                "  1. Przejdź do katalogu projektu\n"
                "  2. Zainicjuj projekt: git init\n"
                "  3. Użyj trybu globalnego: ai --global <pytanie>\n"
            )
        
        return project_root

class NotInProjectError(Exception):
    """Rzucane gdy operacja wymaga projektu, a nie jesteśmy w projekcie"""
    pass