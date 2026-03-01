# Git – Podstawy i zaawansowane komendy

## Inicjalizacja i konfiguracja

```bash
git init                                    # inicjalizuj nowe repozytorium
git clone https://github.com/user/repo.git # klonuj zdalne repozytorium
git config --global user.name "Imię"       # ustaw nazwę użytkownika
git config --global user.email "email@example.com"  # ustaw email
git config --list                           # pokaż konfigurację
```

## Cykl pracy (staging, commit)

```bash
git status                      # status plików (zmienione, nowe, staged)
git add plik.txt                # dodaj plik do staging
git add .                       # dodaj wszystkie zmienione pliki
git add -p                      # interaktywny wybór fragmentów
git commit -m "opis zmian"      # zatwierdź zmiany
git commit --amend              # popraw ostatni commit (wiadomość/zawartość)
git diff                        # różnice między working dir a staging
git diff --staged               # różnice między staging a ostatnim commitem
```

## Historia i przeglądanie

```bash
git log                         # pełna historia commitów
git log --oneline               # skrócona historia (jedna linia)
git log --oneline --graph --all # graf gałęzi
git log -p plik.txt             # historia zmian konkretnego pliku
git show abc1234                # szczegóły konkretnego commita
git blame plik.txt              # kto zmienił którą linię
```

## Gałęzie (branches)

```bash
git branch                      # lista lokalnych gałęzi
git branch -a                   # lista wszystkich (lokalnych + zdalnych)
git branch nowa-galaz            # utwórz nową gałąź
git checkout nowa-galaz          # przejdź do gałęzi
git checkout -b nowa-galaz       # utwórz i przejdź jednocześnie
git switch nowa-galaz            # nowszy sposób przełączania (git 2.23+)
git switch -c nowa-galaz         # utwórz i przejdź (nowszy sposób)
git branch -d galaz              # usuń gałąź (tylko gdy scal)
git branch -D galaz              # usuń gałąź na siłę
```

## Scalanie i rebasing

```bash
git merge galaz                 # scal gałąź do bieżącej
git merge --no-ff galaz         # scal z commit merge (bez fast-forward)
git rebase main                 # przenieś commity na koniec main
git rebase -i HEAD~3            # interaktywny rebase ostatnich 3 commitów
git cherry-pick abc1234         # przenieś konkretny commit do bieżącej gałęzi
```

## Zdalne repozytoria (remote)

```bash
git remote -v                   # lista zdalnych repozytoriów
git remote add origin URL       # dodaj zdalne repozytorium
git push origin main            # wypchnij do zdalnego
git push -u origin main         # wypchnij i ustaw upstream
git push --force-with-lease     # force push (bezpieczniejszy)
git pull                        # pobierz i scal
git fetch origin                # pobierz bez scalania
git fetch --prune               # usuń nieistniejące zdalne gałęzie
```

## Cofanie zmian

```bash
git restore plik.txt            # cofnij zmiany w working dir (nowy)
git checkout -- plik.txt        # cofnij zmiany (stary sposób)
git restore --staged plik.txt   # cofnij z staging (unstage)
git reset HEAD plik.txt         # cofnij z staging (stary sposób)
git reset --soft HEAD~1         # cofnij commit, zachowaj zmiany staged
git reset --mixed HEAD~1        # cofnij commit, zachowaj w working dir
git reset --hard HEAD~1         # cofnij commit i wszystkie zmiany (nieodwracalne)
git revert abc1234              # stwórz nowy commit cofający zmiany
```

## Stash (odkładanie zmian na bok)

```bash
git stash                       # odłóż niezatwierdzone zmiany
git stash push -m "opis"        # odłóż z opisem
git stash list                  # lista odłożonych zmian
git stash pop                   # przywróć ostatnio odłożone zmiany
git stash apply stash@{1}       # przywróć konkretne stash
git stash drop stash@{0}        # usuń konkretne stash
git stash clear                 # wyczyść wszystkie stash
```

## Tagi

```bash
git tag                         # lista tagów
git tag v1.0.0                  # utwórz tag lekki
git tag -a v1.0.0 -m "wersja"  # utwórz tag z adnotacją
git push origin v1.0.0          # wypchnij tag do zdalnego
git push origin --tags          # wypchnij wszystkie tagi
```

## .gitignore – przykład

```
# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.egg-info/
dist/
build/

# Środowisko
.env
.env.local
secrets.yaml

# IDE
.idea/
.vscode/
*.swp

# Logi
*.log
logs/

# OS
.DS_Store
Thumbs.db
```
