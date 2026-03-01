# CI/CD – Continuous Integration i Continuous Deployment

## Czym jest CI/CD?

**CI (Continuous Integration)** – automatyczne budowanie i testowanie kodu po każdym pushu do repozytorium.
**CD (Continuous Deployment/Delivery)** – automatyczne wdrażanie przetestowanego kodu na środowisko.

## GitHub Actions – przykłady

### Podstawowy workflow (Python)
Plik: `.github/workflows/test.yml`

```yaml
name: Testy CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Ustaw Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Zainstaluj zależności
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov flake8

      - name: Lintowanie (flake8)
        run: flake8 . --count --select=E9,F63,F7,F82 --max-line-length=127

      - name: Uruchom testy
        run: pytest tests/ --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

### Workflow z deploymentem na serwer
```yaml
name: Deploy

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy przez SSH
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/aplikacja
            git pull origin main
            source .venv/bin/activate
            pip install -r requirements.txt
            systemctl restart moja-aplikacja
```

## GitLab CI – przykład

Plik: `.gitlab-ci.yml`

```yaml
stages:
  - test
  - build
  - deploy

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"

cache:
  paths:
    - .cache/pip
    - .venv/

before_script:
  - python -m venv .venv
  - source .venv/bin/activate
  - pip install -r requirements.txt

test:
  stage: test
  script:
    - pytest tests/ -v

build-docker:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t moja-aplikacja:$CI_COMMIT_SHA .
    - docker push registry.example.com/moja-aplikacja:$CI_COMMIT_SHA
  only:
    - main

deploy-production:
  stage: deploy
  script:
    - ssh deploy@serwer "cd /opt/app && docker pull ... && docker compose up -d"
  only:
    - main
  when: manual  # wymaga ręcznego zatwierdzenia
```

## Testy automatyczne

```bash
# pytest – uruchamianie testów
pytest                              # wszystkie testy
pytest tests/                       # konkretny katalog
pytest tests/test_api.py            # konkretny plik
pytest -k "test_login"              # według nazwy
pytest -v                           # tryb verbose
pytest --cov=app --cov-report=html  # z pokryciem kodu

# Struktura testów (pytest)
tests/
  __init__.py
  test_unit.py
  test_integration.py
  conftest.py                       # wspólne fixtures
```

## Docker w CI/CD

```bash
# Budowanie i tagowanie
docker build -t app:${GIT_SHA} .
docker tag app:${GIT_SHA} registry.com/app:latest
docker push registry.com/app:${GIT_SHA}
docker push registry.com/app:latest

# Health check w Dockerfile
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8080/health || exit 1
```

## Zmienne środowiskowe i sekrety

W GitHub Actions:
```yaml
env:
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
  API_KEY: ${{ vars.API_KEY }}        # nie-sekretne zmienne
```

Nigdy nie umieszczaj sekretów w kodzie! Używaj:
- GitHub Secrets (repozytoria GitHub)
- GitLab CI/CD Variables
- Vault (HashiCorp)
- Docker Secrets
- Kubernetes Secrets
