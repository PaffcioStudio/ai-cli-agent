# Python – Struktura projektu i dobre praktyki

## Zalecana struktura projektu

```
moj-projekt/
├── app/                    # kod aplikacji
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   └── utils.py
├── tests/                  # testy
│   ├── __init__.py
│   ├── conftest.py         # wspólne fixtures pytest
│   ├── test_main.py
│   └── test_utils.py
├── knowledge/              # pliki wiedzy (dla RAG)
│   ├── linux/
│   └── python/
├── data/                   # pliki konfiguracyjne, dane
│   └── settings.yaml
├── embeddings/             # wektory bazy wiedzy
├── .venv/                  # środowisko wirtualne (nie w git!)
├── .gitignore
├── requirements.txt
├── requirements-dev.txt    # dodatkowe narzędzia dev
├── README.md
├── run.sh                  # skrypt uruchamiający
└── venv.sh                 # skrypt tworzący venv
```

## requirements.txt – dobre praktyki

```
# Produkcyjne zależności z wersjami
requests>=2.28.0,<3.0.0
pyyaml>=6.0
numpy>=1.24.0
sentence-transformers>=2.2.0

# Przynij konkretne wersje dla stabilności prod
Flask==3.0.0
SQLAlchemy==2.0.23
```

```
# requirements-dev.txt
pytest>=7.0
pytest-cov
black
flake8
mypy
isort
```

## pyproject.toml – nowoczesne podejście

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "moj-projekt"
version = "0.1.0"
description = "Opis projektu"
requires-python = ">=3.10"
dependencies = [
    "requests>=2.28",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest", "black", "flake8"]

[tool.black]
line-length = 100
target-version = ["py310"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=app"

[tool.mypy]
python_version = "3.10"
strict = true
```

## Konfiguracja aplikacji (wzorzec)

```python
# app/config.py
from dataclasses import dataclass, field
from pathlib import Path
import yaml
import os

@dataclass
class Config:
    server_ip: str = "127.0.0.1"
    server_port: int = 11434
    embed_model: str = "nomic-embed-text"
    gen_model: str = "qwen3:4b"
    top_k: int = 3
    debug: bool = False

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """Wczytaj konfigurację z pliku YAML."""
        path = Path(path)
        if not path.exists():
            return cls()  # domyślna konfiguracja
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        srv = data.get("server", {})
        return cls(
            server_ip=srv.get("ip", cls.server_ip),
            server_port=srv.get("port", cls.server_port),
            embed_model=data.get("embed_model", cls.embed_model),
            gen_model=data.get("gen_model", cls.gen_model),
        )

    @classmethod
    def from_env(cls) -> "Config":
        """Wczytaj konfigurację ze zmiennych środowiskowych."""
        return cls(
            server_ip=os.getenv("OLLAMA_HOST", cls.server_ip),
            server_port=int(os.getenv("OLLAMA_PORT", str(cls.server_port))),
            embed_model=os.getenv("EMBED_MODEL", cls.embed_model),
            gen_model=os.getenv("GEN_MODEL", cls.gen_model),
            top_k=int(os.getenv("RAG_TOP_K", str(cls.top_k))),
            debug=os.getenv("RAG_DEBUG", "").lower() in ("1", "true", "yes"),
        )
```

## Logging – dobry wzorzec

```python
# app/logger.py
import logging
import sys
from pathlib import Path

def setup_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
    return logging.getLogger(__name__)
```

## Testy – przykłady z pytest

```python
# tests/conftest.py
import pytest
from app.config import Config

@pytest.fixture
def config():
    return Config(server_ip="127.0.0.1", server_port=11434)

@pytest.fixture
def sample_text():
    return "Przykładowy tekst do testów embeddingów."

# tests/test_config.py
def test_default_config():
    cfg = Config()
    assert cfg.server_ip == "127.0.0.1"
    assert cfg.server_port == 11434

def test_config_from_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_PORT", "12345")
    cfg = Config.from_env()
    assert cfg.server_port == 12345

def test_top_k_positive(config):
    assert config.top_k > 0
```

## Narzędzia jakości kodu

```bash
# Formatowanie kodu
black .                         # formatuj wszystkie pliki
black --check .                 # tylko sprawdź (bez modyfikacji)

# Sortowanie importów
isort .
isort --check-only .

# Lintowanie
flake8 app/ tests/
pylint app/

# Sprawdzanie typów
mypy app/

# Uruchom wszystko naraz (pre-commit)
pre-commit run --all-files
```

### .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black

  - repo: https://github.com/PyCQA/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/PyCQA/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
```
