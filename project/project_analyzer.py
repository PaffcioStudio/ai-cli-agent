"""
Moduł odpowiedzialny za rozpoznawanie projektu jako całości.
LOGIKA BIZNESOWA - nie prompt.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

class ProjectAnalyzer:
    """
    Analizuje projekt jako spójną całość.
    Odpowiada na pytania: co to jest? do czego służy? jak działa?
    """
    
    def __init__(self, fs_tools):
        self.fs = fs_tools
        self.root = Path(fs_tools.cwd)
    
    def analyze(self) -> Dict:
        """
        Główna metoda analizy projektu.
        Zwraca strukturalny opis projektu.
        """
        result = {
            "type": None,           # web, node, python, cli, library, mono-repo
            "name": None,           # nazwa projektu
            "description": None,    # opis z README lub package.json
            "technology": [],       # [python, javascript, html, css]
            "entry_points": [],     # główne pliki wejściowe
            "structure": {},        # struktura folderów
            "confidence": 0.0       # pewność rozpoznania (0-1)
        }
        
        # 1. Sprawdź README
        readme = self._find_readme()
        if readme:
            result["description"] = self._extract_description_from_readme(readme)
            result["confidence"] += 0.3
        
        # 2. Sprawdź manifesty projektu (package.json, pyproject.toml, etc.)
        manifest = self._find_manifest()
        if manifest:
            manifest_data = self._parse_manifest(manifest)
            result.update(manifest_data)
            result["confidence"] += 0.5
        
        # 3. Analiza struktury plików
        structure = self._analyze_structure()
        result["structure"] = structure
        result["technology"] = self._detect_technologies(structure)
        
        # 4. Wykryj typ projektu
        result["type"] = self._detect_project_type(result)
        
        # 5. Znajdź entry points
        result["entry_points"] = self._find_entry_points(result["type"])
        
        return result
    
    def _find_readme(self) -> Optional[str]:
        """Znajdź i wczytaj README"""
        for pattern in ["README.md", "README.txt", "README", "readme.md"]:
            readme_path = self.root / pattern
            if readme_path.exists():
                try:
                    return readme_path.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    pass
        return None
    
    def _extract_description_from_readme(self, content: str) -> str:
        """Wyciągnij opis z README (pierwsze 3 linie po tytule)"""
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        # Pomiń tytuł (zazwyczaj # Nazwa)
        start_idx = 0
        if lines and lines[0].startswith('#'):
            start_idx = 1
        
        # Weź kolejne 3 niepuste linie
        desc_lines = []
        for line in lines[start_idx:start_idx+3]:
            if not line.startswith('#'):
                desc_lines.append(line)
        
        return ' '.join(desc_lines)[:200]  # max 200 znaków
    
    def _find_manifest(self) -> Optional[Path]:
        """Znajdź główny manifest projektu"""
        manifests = [
            "package.json",      # Node.js
            "pyproject.toml",    # Python (modern)
            "setup.py",          # Python (legacy)
            "Cargo.toml",        # Rust
            "composer.json",     # PHP
            "pom.xml",           # Java (Maven)
            "build.gradle"       # Java (Gradle)
        ]
        
        for manifest in manifests:
            path = self.root / manifest
            if path.exists():
                return path
        
        return None
    
    def _parse_manifest(self, manifest_path: Path) -> Dict:
        """Parsuj manifest i wyciągnij metadane"""
        result = {}
        
        if manifest_path.name == "package.json":
            try:
                data = json.loads(manifest_path.read_text())
                result["name"] = data.get("name")
                result["description"] = data.get("description")
                result["type"] = "node"
                result["technology"] = ["javascript"]
                
                # Wykryj czy to biblioteka czy aplikacja
                if data.get("main") or data.get("bin"):
                    result["entry_points"] = [data.get("main", "index.js")]
                
            except Exception:
                pass
        
        elif manifest_path.name in ["setup.py", "pyproject.toml"]:
            result["type"] = "python"
            result["technology"] = ["python"]
            
            if manifest_path.name == "pyproject.toml":
                try:
                    # Prosty parser TOML dla [project] name i description
                    content = manifest_path.read_text()
                    for line in content.split('\n'):
                        if 'name =' in line:
                            result["name"] = line.split('=')[1].strip().strip('"\'')
                        elif 'description =' in line:
                            result["description"] = line.split('=')[1].strip().strip('"\'')
                except Exception:
                    pass
        
        return result
    
    def _analyze_structure(self) -> Dict:
        """
        Analizuj strukturę folderów projektu.
        Zwraca dict z kluczowymi folderami i ich znaczeniem.
        """
        structure = {
            "has_src": (self.root / "src").is_dir(),
            "has_lib": (self.root / "lib").is_dir(),
            "has_app": (self.root / "app").is_dir(),
            "has_tests": any([
                (self.root / d).is_dir() 
                for d in ["tests", "test", "__tests__"]
            ]),
            "has_docs": (self.root / "docs").is_dir(),
            "has_public": (self.root / "public").is_dir(),
            "has_static": (self.root / "static").is_dir(),
        }
        
        return structure
    
    def _detect_technologies(self, structure: Dict) -> List[str]:
        """Wykryj technologie na podstawie struktury plików"""
        tech = set()
        
        # Sprawdź rozszerzenia plików
        for file_path in self.root.rglob("*"):
            if not file_path.is_file():
                continue
            
            suffix = file_path.suffix.lower()
            
            if suffix == ".py":
                tech.add("python")
            elif suffix in [".js", ".jsx", ".ts", ".tsx"]:
                tech.add("javascript")
            elif suffix == ".html":
                tech.add("html")
            elif suffix == ".css":
                tech.add("css")
            elif suffix in [".rs"]:
                tech.add("rust")
            elif suffix in [".go"]:
                tech.add("go")
            
            # Ogranicz skanowanie (max 100 plików)
            if len(list(self.root.rglob("*"))) > 100:
                break
        
        return list(tech)
    
    def _detect_project_type(self, analysis: Dict) -> str:
        """
        Wykryj typ projektu na podstawie zgromadzonych danych.
        Możliwe typy: web, node, python, cli, library, mono-repo, unknown
        """
        tech = analysis["technology"]
        struct = analysis["structure"]
        
        # Web project
        if "html" in tech and "css" in tech:
            return "web"
        
        # Node application
        if "javascript" in tech and struct.get("has_src"):
            return "node-app"
        
        # Node library
        if "javascript" in tech and not struct.get("has_src"):
            return "node-library"
        
        # Python CLI/app
        if "python" in tech:
            # Sprawdź czy ma entry point
            if (self.root / "main.py").exists() or (self.root / "__main__.py").exists():
                return "python-cli"
            elif struct.get("has_src") or struct.get("has_lib"):
                return "python-app"
            else:
                return "python-library"
        
        # Mono-repo (wiele folderów z różnymi projektami)
        if struct.get("has_app") and struct.get("has_lib"):
            return "mono-repo"
        
        return "unknown"
    
    def _find_entry_points(self, project_type: str) -> List[str]:
        """Znajdź główne pliki wejściowe projektu"""
        entry_points = []
        
        if project_type == "web":
            # HTML entry points
            for html in ["index.html", "main.html", "app.html"]:
                if (self.root / html).exists():
                    entry_points.append(html)
        
        elif project_type.startswith("python"):
            # Python entry points
            for py in ["main.py", "__main__.py", "app.py", "run.py"]:
                if (self.root / py).exists():
                    entry_points.append(py)
        
        elif project_type.startswith("node"):
            # Node entry points
            pkg = self.root / "package.json"
            if pkg.exists():
                try:
                    data = json.loads(pkg.read_text())
                    if data.get("main"):
                        entry_points.append(data["main"])
                except Exception:
                    pass
            
            # Fallback
            if not entry_points:
                for js in ["index.js", "main.js", "app.js"]:
                    if (self.root / js).exists():
                        entry_points.append(js)
        
        return entry_points
    
    def get_summary(self) -> str:
        """
        Zwróć zwięzłe podsumowanie projektu w formie tekstowej.
        To jest główna metoda dla zapytań typu "co robi ten projekt".
        """
        analysis = self.analyze()
        
        lines = []
        
        # Nazwa
        if analysis["name"]:
            lines.append(f"Projekt: {analysis['name']}")
        
        # Typ
        type_names = {
            "web": "Strona/aplikacja webowa",
            "node-app": "Aplikacja Node.js",
            "node-library": "Biblioteka Node.js",
            "python-cli": "Narzędzie CLI w Pythonie",
            "python-app": "Aplikacja Python",
            "python-library": "Biblioteka Python",
            "mono-repo": "Mono-repozytorium (wiele projektów)",
            "unknown": "Projekt (typ nierozpoznany)"
        }
        lines.append(f"Typ: {type_names.get(analysis['type'], 'Nieznany')}")
        
        # Technologie
        if analysis["technology"]:
            lines.append(f"Technologie: {', '.join(analysis['technology'])}")
        
        # Opis
        if analysis["description"]:
            lines.append(f"\n{analysis['description']}")
        
        # Entry points
        if analysis["entry_points"]:
            lines.append(f"\nGłówne pliki: {', '.join(analysis['entry_points'])}")
        
        # Struktura
        structure_desc = []
        if analysis["structure"].get("has_src"):
            structure_desc.append("kod źródłowy w src/")
        if analysis["structure"].get("has_tests"):
            structure_desc.append("testy")
        if analysis["structure"].get("has_docs"):
            structure_desc.append("dokumentacja")
        
        if structure_desc:
            lines.append(f"Struktura: {', '.join(structure_desc)}")
        
        return "\n".join(lines)