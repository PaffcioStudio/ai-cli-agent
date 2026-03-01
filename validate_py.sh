#!/bin/bash
# ============================================================
#  validate_py.sh — AI CLI Code Quality Validator
#  Wersja: 2.0.0
#  Sprawdza: skladnie, nieuzywane zmienne, importy, bledy typow,
#            problemy UI, brakujace metody, puste wyjatki i wiecej
# ============================================================

set -uo pipefail

RED='\033[91m'
GREEN='\033[92m'
YELLOW='\033[93m'
BLUE='\033[94m'
CYAN='\033[96m'
GRAY='\033[90m'
BOLD='\033[1m'
RESET='\033[0m'

VERBOSE=0
ONLY_ERRORS=0
TARGET_DIR="."

usage() {
    echo "Uzycie: $0 [opcje] [katalog]"
    echo ""
    echo "Opcje:"
    echo "  -v, --verbose       Pokaz szczegoly wszystkich sprawdzen"
    echo "  -e, --errors-only   Pokaz tylko bledy (pomij ostrzezenia)"
    echo "  -h, --help          Ta pomoc"
    echo ""
    echo "Przyklady:"
    echo "  $0                  # Sprawdz biezacy katalog"
    echo "  $0 -v               # Z pelnym outputem"
    echo "  $0 -e               # Tylko bledy"
    echo "  $0 web/             # Sprawdz podkatalog web/"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--verbose)     VERBOSE=1; shift ;;
        -e|--errors-only) ONLY_ERRORS=1; shift ;;
        -h|--help)        usage ;;
        -*)               echo "Nieznana flaga: $1"; usage ;;
        *)                TARGET_DIR="$1"; shift ;;
    esac
done

TOTAL_FILES=0
TOTAL_ERRORS=0
TOTAL_WARNINGS=0
declare -a FAILED_FILES=()

ok()      { echo -e "  ${GREEN}OK${RESET} $*"; }
err_msg() { echo -e "  ${RED}ERR${RESET} $*"; ((TOTAL_ERRORS++)) || true; }
warn()    { [[ $ONLY_ERRORS -eq 1 ]] && return; echo -e "  ${YELLOW}WARN${RESET} $*"; ((TOTAL_WARNINGS++)) || true; }
info()    { [[ $VERBOSE -eq 1 ]] && echo -e "  ${GRAY}>>${RESET} $*" || true; }
section() { echo -e "\n${CYAN}${BOLD}── $* ──${RESET}"; }
subsec()  { echo -e "${BLUE}>>>${RESET} $*"; }

collect_py() {
    find "$TARGET_DIR" -name "*.py" \
        -not -path "*/venv/*" \
        -not -path "*/__pycache__/*" \
        -not -path "*/.git/*" \
        -not -path "*/node_modules/*" \
        | sort
}

# ── 1. SKLADNIA ─────────────────────────────────────────────
check_syntax() {
    subsec "py_compile — skladnia"
    local ok_count=0 err_count=0
    while IFS= read -r file; do
        ((TOTAL_FILES++)) || true
        local output
        if output=$(python3 -m py_compile "$file" 2>&1); then
            info "OK: $file"
            ((ok_count++)) || true
        else
            err_msg "Blad skladni: ${BOLD}$file${RESET}"
            echo -e "    ${GRAY}$output${RESET}"
            FAILED_FILES+=("$file")
            ((err_count++)) || true
        fi
    done < <(collect_py)
    [[ $err_count -eq 0 ]] && ok "Wszystkie $ok_count plikow: poprawna skladnia"
}

# ── 2. AST — wzorce ─────────────────────────────────────────
check_ast() {
    subsec "AST — analiza wzorcow"
    export _VALIDATE_TARGET="$TARGET_DIR"

    local ast_result
    ast_result=$(python3 - << 'PYEOF'
import ast, os, sys
from pathlib import Path

target = os.environ.get("_VALIDATE_TARGET", ".")

# Zbierz metody klasy UI
UI_METHODS = set()
ui_path = Path(target) / "ui.py"
if not ui_path.exists():
    ui_path = Path("ui.py")
if ui_path.exists():
    try:
        tree = ast.parse(ui_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "UI":
                for item in ast.walk(node):
                    if isinstance(item, ast.FunctionDef):
                        UI_METHODS.add(item.name)
    except Exception:
        pass

def collect_files(base):
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ("venv","__pycache__",".git","node_modules")]
        for f in sorted(files):
            if f.endswith(".py"):
                yield Path(os.path.join(root, f))

errors = 0
warns  = 0

for fpath in collect_files(target):
    try:
        src  = fpath.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(fpath))
    except SyntaxError:
        continue

    lines = src.splitlines()

    for node in ast.walk(tree):
        # --- Niezdefiniowane metody UI ---
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "ui"
                and UI_METHODS):
            m = node.func.attr
            if m not in UI_METHODS and not m.startswith("_"):
                print(f"ERROR|{fpath}:{node.lineno}|Nieistniejaca metoda UI: .{m}() — dostepne: {sorted(UI_METHODS)[:5]}")
                errors += 1

        # --- Puste wyjatki: except: pass ---
        if isinstance(node, ast.ExceptHandler):
            if all(isinstance(s, ast.Pass) for s in node.body):
                print(f"WARN|{fpath}:{node.lineno}|Pusty except:pass — wyjatok polykany bez logowania")
                warns += 1

        # --- eval/exec ---
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ("eval","exec"):
                print(f"WARN|{fpath}:{node.lineno}|Uzyta funkcja {node.func.id}() — potencjalnie niebezpieczne")
                warns += 1

        # --- Ekstremalnie dlugie linie ---
        if hasattr(node, "lineno"):
            idx = node.lineno - 1
            if 0 <= idx < len(lines) and len(lines[idx]) > 200:
                print(f"WARN|{fpath}:{node.lineno}|Bardzo dluga linia: {len(lines[idx])} znakow (>200)")
                warns += 1

    # --- Zduplikowane importy ---
    seen_imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                k = alias.name
                if k in seen_imports:
                    print(f"WARN|{fpath}:{node.lineno}|Zduplikowany import: '{k}' (wczesniej linia {seen_imports[k]})")
                    warns += 1
                seen_imports[k] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            m = node.module or ""
            for alias in node.names:
                k = f"{m}.{alias.name}"
                if k in seen_imports:
                    print(f"WARN|{fpath}:{node.lineno}|Zduplikowany from-import: '{alias.name}' z '{m}'")
                    warns += 1
                seen_imports[k] = node.lineno

print(f"SUMMARY|{errors}|{warns}")
PYEOF
    )

    local e=0 w=0
    while IFS='|' read -r tag loc msg; do
        case "$tag" in
            ERROR)
                err_msg "${BOLD}$loc${RESET}: $msg"
                ;;
            WARN)
                [[ $ONLY_ERRORS -eq 0 ]] && warn "${BOLD}$loc${RESET}: $msg"
                ;;
            SUMMARY)
                e="$loc"; w="$msg"
                ;;
        esac
    done <<< "$ast_result"

    [[ "${e:-0}" -eq 0 && "${w:-0}" -eq 0 ]] && ok "Brak problemow AST"
}

# ── 3. GREP — heurystyki ────────────────────────────────────
check_grep() {
    subsec "grep — wzorce kodu"

    # Bare except:
    local bare
    bare=$(collect_py | xargs grep -cnP "^\s*except\s*:" 2>/dev/null | grep -v ":0$" | wc -l || true)
    [[ $bare -gt 0 ]] && warn "Bare 'except:' (bez wyjatku) w $bare plikach — lapie KeyboardInterrupt!"

    # TODO / FIXME
    local todos
    todos=$(collect_py | xargs grep -cE "TODO|FIXME|HACK|XXX" 2>/dev/null | grep -v ":0$" | wc -l || true)
    [[ $todos -gt 0 ]] && warn "TODO/FIXME/HACK w $todos plikach"

    # Windows CRLF
    while IFS= read -r f; do
        if grep -qP "\r" "$f" 2>/dev/null; then
            warn "Windows CRLF line endings: $f"
        fi
    done < <(collect_py)

    # sys.exit bez import sys
    while IFS= read -r f; do
        local uses_exit imp_sys
        uses_exit=$(grep -c "sys\.exit" "$f" 2>/dev/null || true)
        imp_sys=$(grep -cE "^import sys|^from sys" "$f" 2>/dev/null || true)
        if [[ $uses_exit -gt 0 && $imp_sys -eq 0 ]]; then
            warn "sys.exit() bez 'import sys': $f"
        fi
    done < <(collect_py)

    # Mozliwe hardcoded credentials
    local creds
    creds=$(collect_py | xargs grep -nEi \
        '(password|passwd|api_key|secret)\s*=\s*["'"'"'][^"'"'"']{8,}' \
        2>/dev/null \
        | grep -vE "config\.get|os\.environ|getenv|your_|dummy|test_|example|placeholder" \
        | wc -l || true)
    [[ $creds -gt 0 ]] && warn "Mozliwe hardcoded credentials: $creds trafien (sprawdz recznie)"

    ok "Sprawdzenie grep zakonczone"
}

# ── 4. SKRYPTY SHELL ────────────────────────────────────────
check_shell() {
    subsec "Skrypty .sh"
    local sh_files
    sh_files=$(find "$TARGET_DIR" -name "*.sh" -not -path "*/venv/*" | sort)
    [[ -z "$sh_files" ]] && info "Brak skryptow .sh" && return

    while IFS= read -r f; do
        if command -v shellcheck &>/dev/null; then
            if shellcheck -S warning "$f" &>/dev/null; then
                info "OK: $f"
            else
                warn "ShellCheck: problemy w $f"
                [[ $VERBOSE -eq 1 ]] && shellcheck -S warning "$f" 2>&1 | head -10 | \
                    while IFS= read -r l; do echo -e "    ${GRAY}$l${RESET}"; done
            fi
        else
            bash -n "$f" 2>/dev/null && info "Syntax OK: $f" || { err_msg "Blad bash syntax: $f"; FAILED_FILES+=("$f"); }
        fi
    done <<< "$sh_files"
}

# ── 5. KODOWANIE ────────────────────────────────────────────
check_encoding() {
    subsec "Kodowanie plikow"
    while IFS= read -r f; do
        local ftype
        ftype=$(file "$f" | cut -d: -f2)
        if echo "$ftype" | grep -qE "BOM|CRLF|Non-ISO"; then
            warn "Podejrzane kodowanie: $f — $ftype"
        fi
    done < <(collect_py)
    ok "Kodowanie OK"
}

# ── 6. DOCSTRINGI (opcjonalne) ──────────────────────────────
check_docstrings() {
    [[ $ONLY_ERRORS -eq 1 ]] && return
    subsec "Docstringi publicznych metod"
    export _VALIDATE_TARGET="$TARGET_DIR"

    local doc_result
    doc_result=$(python3 - << 'PYEOF'
import ast, os
from pathlib import Path

target = os.environ.get("_VALIDATE_TARGET", ".")
count = 0

for root, dirs, files in os.walk(target):
    dirs[:] = [d for d in dirs if d not in ("venv","__pycache__",".git")]
    for fname in sorted(files):
        if not fname.endswith(".py"):
            continue
        fpath = Path(os.path.join(root, fname))
        try:
            tree = ast.parse(fpath.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name.startswith("_"):
                            continue
                        has_doc = (item.body
                                   and isinstance(item.body[0], ast.Expr)
                                   and isinstance(item.body[0].value, ast.Constant))
                        if not has_doc and len(item.body) > 2:
                            print(f"WARN|{fpath}:{item.lineno}|Brak docstringa: {node.name}.{item.name}()")
                            count += 1
                            if count >= 15:
                                print(f"WARN|summary|Pokazano 15 z wielu brakujacych docstringow")
                                import sys; sys.exit(0)
PYEOF
    )

    local w=0
    while IFS='|' read -r tag loc msg; do
        [[ "$tag" == "WARN" ]] && warn "${BOLD}$loc${RESET}: $msg" && ((w++)) || true
    done <<< "$doc_result"
    [[ $w -eq 0 ]] && ok "Docstringi wyglądają OK"
}

# ── GLOWNA SEKCJA ────────────────────────────────────────────
echo -e "\n${CYAN}${BOLD}======================================================${RESET}"
echo -e "${CYAN}${BOLD}  AI CLI Code Validator v2.0                          ${RESET}"
echo -e "${CYAN}${BOLD}======================================================${RESET}"
echo -e "${GRAY}Katalog: $(realpath "$TARGET_DIR")${RESET}"
echo -e "${GRAY}Tryb: $([ $VERBOSE -eq 1 ] && echo verbose || echo normalny) $([ $ONLY_ERRORS -eq 1 ] && echo '| tylko-bledy' || echo '')${RESET}"

section "1. SKLADNIA PYTHON"
check_syntax

section "2. ANALIZA AST"
check_ast

section "3. WZORCE GREP"
check_grep

section "4. SKRYPTY SHELL"
check_shell

section "5. KODOWANIE PLIKOW"
check_encoding

section "6. DOCSTRINGI (klasy publiczne)"
check_docstrings

# ── PODSUMOWANIE ────────────────────────────────────────────
echo -e "\n${CYAN}${BOLD}======================================================${RESET}"
echo -e "${CYAN}${BOLD}  PODSUMOWANIE                                        ${RESET}"
echo -e "${CYAN}${BOLD}======================================================${RESET}"
echo -e "  Plikow:      ${BOLD}${TOTAL_FILES}${RESET}"

if [[ $TOTAL_ERRORS -gt 0 ]]; then
    echo -e "  Bledy:       ${RED}${BOLD}${TOTAL_ERRORS}${RESET}"
else
    echo -e "  Bledy:       ${GREEN}${TOTAL_ERRORS}${RESET}"
fi

if [[ $ONLY_ERRORS -eq 0 ]]; then
    if [[ $TOTAL_WARNINGS -gt 0 ]]; then
        echo -e "  Ostrzezenia: ${YELLOW}${TOTAL_WARNINGS}${RESET}"
    else
        echo -e "  Ostrzezenia: ${GREEN}${TOTAL_WARNINGS}${RESET}"
    fi
fi

if [[ ${#FAILED_FILES[@]} -gt 0 ]]; then
    echo ""
    echo -e "  ${RED}${BOLD}Pliki z bledami:${RESET}"
    for f in "${FAILED_FILES[@]}"; do
        echo -e "    ${RED}  $f${RESET}"
    done
fi

echo ""
if [[ $TOTAL_ERRORS -gt 0 ]]; then
    echo -e "${RED}${BOLD}WYNIK: NIEUDANA — $TOTAL_ERRORS bledy do naprawienia${RESET}"
    exit 1
else
    echo -e "${GREEN}${BOLD}WYNIK: UDANA${RESET}"
    [[ $TOTAL_WARNINGS -gt 0 && $ONLY_ERRORS -eq 0 ]] && \
        echo -e "${YELLOW}  ($TOTAL_WARNINGS ostrzezen do rozwazenia)${RESET}"
    exit 0
fi
