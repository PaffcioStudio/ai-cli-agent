#!/usr/bin/env bash

#═══════════════════════════════════════════════════════════════════════════════
#  AI CLI AGENT - INSTALATOR
#═══════════════════════════════════════════════════════════════════════════════

set -e

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
BOLD='\033[1m'
RESET='\033[0m'

# Lokalizacje
INSTALL_DIR="$HOME/.local/share/ai-cli-agent"
VENV_DIR="$INSTALL_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python3"
VENV_PIP="$VENV_DIR/bin/pip"
WRAPPER_PATH="$HOME/.local/bin/ai"
CONFIG_DIR="$HOME/.config/ai"
CONFIG_FILE="$CONFIG_DIR/config.json"
PROMPT_FILE="$CONFIG_DIR/prompt.txt"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="ai-panel.service"
PANEL_PORT=21650

#═══════════════════════════════════════════════════════════════════════════════
# FUNKCJE POMOCNICZE
#═══════════════════════════════════════════════════════════════════════════════

get_local_ip() {
    # Zwraca lokalne IP w sieci LAN (nie 127.0.0.1)
    local ip
    ip=$(python3 -c "
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    print(s.getsockname()[0])
    s.close()
except Exception:
    print('127.0.0.1')
" 2>/dev/null)
    echo "${ip:-127.0.0.1}"
}

panel_url() {
    echo "http://$(get_local_ip):${PANEL_PORT}"
}

print_header() {
    echo -e "${CYAN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║           AI CLI AGENT - INSTALATOR                          ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${RESET}"
}

print_section() {
    echo ""
    echo -e "${BLUE}${BOLD}▶ $1${RESET}"
    echo -e "${GRAY}$(printf '─%.0s' {1..60})${RESET}"
}

print_success() { echo -e "  ${GREEN}✓${RESET} $1"; }
print_error()   { echo -e "  ${RED}✗${RESET} $1"; }
print_warning() { echo -e "  ${YELLOW}⚠${RESET} $1"; }
print_info()    { echo -e "  ${CYAN}ℹ${RESET} $1"; }
print_item()    { echo -e "  ${GRAY}•${RESET} $1"; }

clear_screen() {
    clear
    print_header
}

separator() {
    echo ""
    echo -e "${GRAY}$(printf '─%.0s' {1..60})${RESET}"
    echo ""
}

confirm() {
    local prompt="$1"
    local default="${2:-n}"

    if [[ "$default" == "y" ]]; then
        local hint="${GREEN}T${RESET}${GRAY}/n${RESET}"
    else
        local hint="${GRAY}t/${RESET}${RED}N${RESET}"
    fi

    while true; do
        echo -ne "  ${YELLOW}?${RESET} ${prompt} [${hint}]: "
        read -r answer
        answer="${answer:-$default}"
        case "${answer,,}" in
            t|tak|y|yes) return 0 ;;
            n|nie|no)    return 1 ;;
            *) echo -e "  ${RED}Odpowiedz 't' (tak) lub 'n' (nie)${RESET}" ;;
        esac
    done
}

#═══════════════════════════════════════════════════════════════════════════════
# WYKRYWANIE WERSJI I INSTALACJI
#═══════════════════════════════════════════════════════════════════════════════

get_version_from_dir() {
    local dir="$1"
    if [[ -f "$dir/main.py" ]]; then
        python3 -c "
import re
try:
    with open('$dir/main.py') as f:
        for line in f:
            m = re.search(r'[\"\\']([0-9]+\\.[0-9]+\\.[0-9]+)[\"\\']', line)
            if m and ('version' in line.lower() or 'VERSION' in line):
                print(m.group(1)); break
        else:
            print('unknown')
except:
    print('unknown')
" 2>/dev/null || echo "unknown"
    else
        echo "none"
    fi
}

detect_installation() {
    if [[ -f "$WRAPPER_PATH" ]] || [[ -d "$INSTALL_DIR" ]]; then
        echo "installed"
    else
        echo "none"
    fi
}

get_installed_version() { get_version_from_dir "$INSTALL_DIR"; }
get_new_version()        { get_version_from_dir "$SCRIPT_DIR";  }

#═══════════════════════════════════════════════════════════════════════════════
# VENV — helpers, tworzenie, aktualizacja
#═══════════════════════════════════════════════════════════════════════════════

# Zwraca 0 jeśli venv jest zdrowy (ma python i pip)
venv_is_ok() {
    [[ -x "$VENV_PYTHON" ]] && [[ -x "$VENV_PIP" ]]
}

# Zwraca liczbę zainstalowanych pakietów w venv
venv_pkg_count() {
    "$VENV_PIP" list 2>/dev/null | tail -n +3 | wc -l | tr -d ' '
}

# install_venv [rebuild]
#   rebuild=true  → usuwa stary venv i tworzy od nowa
#   rebuild=false → używa istniejącego jeśli zdrowy
install_venv() {
    local rebuild="${1:-false}"

    print_section "Środowisko Python (venv)"

    # Sprawdź czy python3-venv jest dostępny
    if ! python3 -m venv --help >/dev/null 2>&1; then
        print_warning "Brak modułu venv — próbuję zainstalować python3-venv..."
        if sudo apt-get install -y python3-venv 2>/dev/null; then
            print_success "python3-venv zainstalowany"
        else
            print_error "Nie można zainstalować python3-venv"
            print_info  "Zainstaluj ręcznie: sudo apt install python3-venv"
            return 1
        fi
    fi

    # Usuń stary venv jeśli rebuild
    if [[ "$rebuild" == "true" ]] && [[ -d "$VENV_DIR" ]]; then
        print_info "Usuwanie starego venv..."
        rm -rf "$VENV_DIR"
        print_success "Stary venv usunięty"
    fi

    # Utwórz venv jeśli nie istnieje lub jest uszkodzony
    if ! venv_is_ok; then
        print_info "Tworzenie venv → $VENV_DIR"
        if python3 -m venv "$VENV_DIR"; then
            print_success "venv utworzony"
        else
            print_error "Nie udało się utworzyć venv"
            return 1
        fi
    else
        print_success "venv istnieje: $VENV_DIR"
    fi

    # Upgrade pip
    print_info "Aktualizacja pip..."
    "$VENV_PIP" install --upgrade pip --quiet 2>/dev/null \
        && print_success "pip zaktualizowany" \
        || print_warning "Nie udało się zaktualizować pip (niekrytyczne)"

    # Zainstaluj/zaktualizuj zależności z requirements.txt
    local req="$INSTALL_DIR/requirements.txt"
    if [[ ! -f "$req" ]]; then
        print_warning "Brak requirements.txt — pomijam instalację pakietów"
        return 0
    fi

    print_info "Instalowanie pakietów Python..."
    echo ""

    local pkgs
    pkgs=$(grep -v '^\s*#' "$req" | grep -v '^\s*$' | sed 's/[>=<!].*//' | tr '\n' ' ')
    echo -e "  ${GRAY}Pakiety: $pkgs${RESET}"
    echo ""

    if "$VENV_PIP" install -r "$req" --quiet 2>/tmp/ai-pip-err; then
        local count
        count=$(venv_pkg_count)
        print_success "Zainstalowano $count pakietów"
    else
        print_warning "Niektóre pakiety nie zainstalowały się"
        echo ""
        echo -e "  ${YELLOW}Szczegóły błędu:${RESET}"
        sed 's/^/    /' /tmp/ai-pip-err | head -20
        echo ""
        print_item "Agent będzie działał — opcjonalne pakiety doinstaluj później"
        print_item "Komenda: ai deps"
        return 0  # nie przerywaj instalacji
    fi

    echo ""
}

# update_venv — tylko aktualizacja pakietów (bez tworzenia od nowa)
update_venv() {
    print_section "Aktualizacja pakietów Python"

    if ! venv_is_ok; then
        print_warning "venv nie istnieje lub jest uszkodzony — tworzę od nowa..."
        install_venv "true"
        return
    fi

    print_success "venv: $VENV_DIR"

    local req="$INSTALL_DIR/requirements.txt"
    if [[ ! -f "$req" ]]; then
        print_warning "Brak requirements.txt"
        return 0
    fi

    print_info "Sprawdzanie aktualizacji..."
    local outdated
    outdated=$("$VENV_PIP" list --outdated --format=columns 2>/dev/null | tail -n +3 || true)

    if [[ -z "$outdated" ]]; then
        print_success "Wszystkie pakiety są aktualne"
    else
        echo ""
        echo -e "  ${YELLOW}Pakiety do aktualizacji:${RESET}"
        echo "$outdated" | sed 's/^/    /'
        echo ""
        print_info "Aktualizowanie..."
        "$VENV_PIP" install -r "$req" --upgrade --quiet 2>/tmp/ai-pip-err \
            && print_success "Pakiety zaktualizowane" \
            || print_warning "Błąd aktualizacji — szczegóły: cat /tmp/ai-pip-err"
    fi

    echo ""
}

#═══════════════════════════════════════════════════════════════════════════════
# SYSTEMD SERVICE
#═══════════════════════════════════════════════════════════════════════════════

install_systemd_service() {
    print_section "Instalacja systemd service"

    if ! command -v systemctl >/dev/null 2>&1; then
        print_warning "systemctl niedostępne — pomijam"
        return 1
    fi

    mkdir -p "$SYSTEMD_USER_DIR"

    local service_source="$INSTALL_DIR/web/ai-panel.service"
    if [[ ! -f "$service_source" ]]; then
        print_error "Brak pliku service: $service_source"
        return 1
    fi

    cp "$service_source" "$SYSTEMD_USER_DIR/$SERVICE_NAME"
    print_success "Service skopiowany"

    systemctl --user daemon-reload

    systemctl --user enable "$SERVICE_NAME" 2>/dev/null \
        && print_success "Autostart włączony" \
        || print_warning "Nie udało się włączyć autostartu"

    systemctl --user start "$SERVICE_NAME" 2>/dev/null \
        && print_success "Panel uruchomiony" \
        || print_warning "Nie udało się uruchomić panelu"

    echo ""
    echo -e "  ${CYAN}${BOLD}Panel webowy: $(panel_url)${RESET}"
    echo ""
    print_item "ai panel status   — sprawdź czy działa"
    print_item "ai panel open     — otwórz w przeglądarce"
    print_item "ai panel stop     — zatrzymaj"
    echo ""
    return 0
}

uninstall_systemd_service() {
    [[ ! -f "$SYSTEMD_USER_DIR/$SERVICE_NAME" ]] && return 0
    print_info "Usuwanie systemd service..."
    systemctl --user stop    "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "$SYSTEMD_USER_DIR/$SERVICE_NAME"
    systemctl --user daemon-reload 2>/dev/null || true
    print_success "Service usunięty"
}

#═══════════════════════════════════════════════════════════════════════════════
# STATUS
#═══════════════════════════════════════════════════════════════════════════════

show_status() {
    local status="$1"
    local installed_ver="$2"
    local new_ver="$3"

    print_section "Status instalacji"
    echo ""

    if [[ "$status" == "none" ]]; then
        print_info "AI CLI Agent nie jest jeszcze zainstalowany"
        echo ""
        echo -e "  Wersja do instalacji:  ${BOLD}${new_ver}${RESET}"
    else
        if [[ "$installed_ver" == "$new_ver" ]]; then
            echo -e "  Wersja zainstalowana:  ${BOLD}${installed_ver}${RESET}  ${GREEN}(aktualna)${RESET}"
        else
            echo -e "  Wersja zainstalowana:  ${BOLD}${installed_ver}${RESET}"
            echo -e "  Nowa wersja:           ${BOLD}${new_ver}${RESET}  ${CYAN}(dostępna aktualizacja)${RESET}"
        fi
        echo ""

        # Składniki
        [[ -f "$WRAPPER_PATH" ]] \
            && print_success "Komenda 'ai':   $WRAPPER_PATH" \
            || print_warning "Komenda 'ai':   brak"

        [[ -d "$INSTALL_DIR" ]] \
            && print_success "Pliki agenta:   $INSTALL_DIR" \
            || print_warning "Pliki agenta:   brak"

        # Stan venv
        if venv_is_ok; then
            local count
            count=$(venv_pkg_count)
            print_success "Python venv:    $VENV_DIR  ($count pakietów)"
        else
            print_warning "Python venv:    brak lub uszkodzony"
            print_item    "Napraw: ./install-cli.sh → Reinstaluj"
        fi

        [[ -f "$SYSTEMD_USER_DIR/$SERVICE_NAME" ]] \
            && print_success "Panel webowy:   zainstalowany jako service" \
            || print_item    "Panel webowy:   nie zainstalowany"

        # Konfiguracja
        echo ""
        if [[ -d "$CONFIG_DIR" ]]; then
            print_success "Konfiguracja:   $CONFIG_DIR"
            [[ -f "$CONFIG_FILE" ]]  && print_item "config.json       (serwer, model, nick)"
            [[ -f "$PROMPT_FILE" ]]  && print_item "prompt.txt        (prompt CLI)"

            # Dane web panelu
            local prompt_web="$CONFIG_DIR/prompt-web.txt"
            [[ -f "$prompt_web" ]]   && print_item "prompt-web.txt    (prompt web panelu)"

            local chats_dir="$CONFIG_DIR/web/chats"
            if [[ -d "$chats_dir" ]]; then
                local chat_count
                chat_count=$(find "$chats_dir" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
                if [[ "$chat_count" -gt 0 ]]; then
                    print_item "web/chats/        (historia: ${chat_count} konwersacji)"
                else
                    print_item "web/chats/        (historia: pusta)"
                fi
            fi

            local sessions_dir="$CONFIG_DIR/web/sessions"
            if [[ -d "$sessions_dir" ]]; then
                local session_count
                session_count=$(find "$sessions_dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
                if [[ "$session_count" -gt 0 ]]; then
                    local sessions_size
                    sessions_size=$(du -sh "$sessions_dir" 2>/dev/null | cut -f1)
                    print_item "web/sessions/     (sandbox: ${session_count} sesji, ~${sessions_size})"
                fi
            fi

            local logs_dir="$CONFIG_DIR/web/logs"
            if [[ -d "$logs_dir" ]]; then
                local log_file="$logs_dir/web.log"
                if [[ -f "$log_file" ]]; then
                    local log_size
                    log_size=$(du -sh "$log_file" 2>/dev/null | cut -f1)
                    print_item "web/logs/web.log  (logi panelu: ${log_size})"
                fi
            fi

            local knowledge_dir="$CONFIG_DIR/knowledge"
            if [[ -d "$knowledge_dir" ]]; then
                local kcount
                kcount=$(find "$knowledge_dir" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
                [[ "$kcount" -gt 0 ]] && print_item "knowledge/        (baza wiedzy RAG: ${kcount} plików)"
            fi
        else
            print_item "Konfiguracja:   brak (zostanie utworzona przy pierwszym uruchomieniu)"
        fi
    fi

    echo ""
}

#═══════════════════════════════════════════════════════════════════════════════
# MENU
#═══════════════════════════════════════════════════════════════════════════════

show_menu() {
    local status="$1"
    local installed_ver="$2"
    local new_ver="$3"

    echo -e "${BOLD}  Co chcesz zrobić?${RESET}"
    echo ""

    if [[ "$status" == "none" ]]; then
        echo -e "  ${BOLD}[1]${RESET} Zainstaluj AI CLI Agent ${GRAY}(${new_ver})${RESET}"
        echo -e "  ${BOLD}[2]${RESET} Anuluj"
    else
        if [[ "$installed_ver" == "$new_ver" ]]; then
            echo -e "  ${BOLD}[1]${RESET} Reinstaluj          ${GRAY}(ta sama wersja ${new_ver})${RESET}"
        else
            echo -e "  ${BOLD}[1]${RESET} Aktualizuj          ${GRAY}(${installed_ver} → ${new_ver})${RESET}"
        fi
        echo -e "  ${BOLD}[2]${RESET} Tylko pakiety Python ${GRAY}(pip upgrade bez reinstalacji)${RESET}"
        echo -e "  ${BOLD}[3]${RESET} Odinstaluj"
        echo -e "  ${BOLD}[4]${RESET} Anuluj"
    fi

    echo ""
}

#═══════════════════════════════════════════════════════════════════════════════
# KROKI INSTALACJI (osobne funkcje = osobne ekrany)
#═══════════════════════════════════════════════════════════════════════════════

step_copy_files() {
    print_section "Kopiowanie plików agenta"

    mkdir -p "$(dirname "$WRAPPER_PATH")"
    mkdir -p "$INSTALL_DIR"

    print_info "Kopiowanie plików..."
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/" 2>/dev/null || {
        for file in "$SCRIPT_DIR"/*; do
            [[ -e "$file" ]] && cp -r "$file" "$INSTALL_DIR/"
        done
    }
    rm -f "$INSTALL_DIR/install-cli.sh" 2>/dev/null || true
    print_success "Pliki → $INSTALL_DIR"

    # Baza wiedzy
    local knowledge_src="$SCRIPT_DIR/knowledge"
    local knowledge_dst="$CONFIG_DIR/knowledge"
    if [[ -d "$knowledge_src" ]]; then
        print_info "Kopiowanie bazy wiedzy..."
        mkdir -p "$knowledge_dst"
        cp -r "$knowledge_src"/. "$knowledge_dst/"
        local kcount
        kcount=$(find "$knowledge_dst" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
        print_success "Baza wiedzy → $knowledge_dst ($kcount plików)"
    fi

    # Katalogi danych web panelu (chats, sessions, logs)
    mkdir -p "$CONFIG_DIR/web/chats"
    mkdir -p "$CONFIG_DIR/web/sessions"
    mkdir -p "$CONFIG_DIR/web/logs"
    print_success "Katalogi web → $CONFIG_DIR/web/"

    echo ""
}

step_install_wrapper() {
    print_section "Komenda 'ai'"

    # Wrapper używa venv gdy dostępny, fallback na systemowy python3
    cat > "$WRAPPER_PATH" << 'WRAPPER_EOF'
#!/usr/bin/env bash
INSTALL_DIR="$HOME/.local/share/ai-cli-agent"
VENV_PYTHON="$INSTALL_DIR/venv/bin/python3"
if [[ -x "$VENV_PYTHON" ]]; then
    exec "$VENV_PYTHON" "$INSTALL_DIR/main.py" "$@"
else
    exec python3 "$INSTALL_DIR/main.py" "$@"
fi
WRAPPER_EOF
    chmod +x "$WRAPPER_PATH"
    print_success "Komenda 'ai' → $WRAPPER_PATH"

    # Sprawdź PATH
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo ""
        print_warning "Katalog ~/.local/bin nie jest w PATH"
        echo ""
        echo -e "  Dodaj do ${BOLD}~/.bashrc${RESET} lub ${BOLD}~/.zshrc${RESET}:"
        echo -e "  ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
        echo ""
        echo -e "  Potem przeładuj shell:"
        echo -e "  ${CYAN}source ~/.bashrc${RESET}"
    fi

    echo ""
}

step_ask_panel() {
    clear_screen
    echo -e "  ${CYAN}${BOLD}Interfejs webowy Chat (opcjonalny)${RESET}"
    echo ""
    print_item "Pełny chat AI w przeglądarce (styl ChatGPT/Gemini)"
    print_item "Przełączanie między modelami w locie"
    print_item "Historia rozmów zapisywana lokalnie"
    print_item "Bloki kodu z podświetlaniem składni"
    print_item "Edycja konfiguracji i system promptu"
    print_item "Tryb jasny / ciemny"
    echo ""
    print_info "Dostępny pod: $(panel_url)"
    echo ""

    # Sprawdź aktualny stan panelu
    local panel_was_running=false
    local panel_has_service=false
    if command -v systemctl >/dev/null 2>&1; then
        if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
            panel_was_running=true
        fi
        if [[ -f "$SYSTEMD_USER_DIR/$SERVICE_NAME" ]]; then
            panel_has_service=true
        fi
    fi

    if confirm "Czy chcesz używać interfejsu webowego?" "n"; then
        # Panel chciany - jeśli działał, zatrzymaj przed instalacją
        if $panel_was_running; then
            print_info "Panel jest aktywny — zatrzymuję przed aktualizacją…"
            systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
            print_success "Panel zatrzymany"
            echo ""
        fi

        echo ""
        echo -e "  ${BOLD}Jak uruchamiać panel?${RESET}"
        echo ""
        echo -e "  ${BOLD}[1]${RESET} Autostart ${GRAY}(systemd service)${RESET}"
        echo -e "  ${BOLD}[2]${RESET} Ręcznie   ${GRAY}(uruchamiasz gdy potrzebujesz)${RESET}"
        echo ""
        while true; do
            echo -ne "  ${YELLOW}?${RESET} Wybór [1/2]: "
            read -r panel_choice
            case "$panel_choice" in
                1)
                    echo ""
                    if install_systemd_service; then
                        # install_systemd_service sam startuje - tylko info
                        true
                    else
                        print_warning "Nie udało się zainstalować — uruchom ręcznie:"
                        echo -e "  ${CYAN}ai panel start${RESET}"
                    fi
                    break ;;
                2)
                    echo ""
                    print_info "Pliki panelu zaktualizowane."
                    echo ""
                    # Był uruchomiony lub miał service - zapytaj czy włączyć teraz
                    if $panel_was_running || $panel_has_service; then
                        if confirm "Uruchomić panel teraz?" "t"; then
                            systemctl --user start "$SERVICE_NAME" 2>/dev/null \
                                && print_success "Panel uruchomiony → $(panel_url)" \
                                || print_info "Uruchom ręcznie: ai panel start"
                        else
                            print_info "Uruchom kiedy chcesz: ${CYAN}ai panel start${RESET}"
                        fi
                    else
                        print_info "Uruchom ręcznie: ${CYAN}ai panel start${RESET}"
                    fi
                    break ;;
                *) print_error "Wybierz 1 lub 2" ;;
            esac
        done
    else
        # Panel nieChciany - jeśli działał, zatrzymaj i wyłącz autostart
        echo ""
        if $panel_was_running || $panel_has_service; then
            print_info "Zatrzymuję panel i wyłączam autostart…"
            systemctl --user stop    "$SERVICE_NAME" 2>/dev/null || true
            systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
            print_success "Panel zatrzymany i wyłączony"
        else
            print_item "Panel pominięty — uruchom później: ai panel start"
        fi
    fi

    echo ""
}

step_ask_index() {
    local knowledge_dir="$CONFIG_DIR/knowledge"
    local knowledge_count=0
    [[ -d "$knowledge_dir" ]] && \
        knowledge_count=$(find "$knowledge_dir" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')

    [[ $knowledge_count -eq 0 ]] && return 0

    clear_screen
    echo -e "  ${CYAN}${BOLD}Baza wiedzy (RAG)${RESET}"
    echo ""
    print_info "Znaleziono ${BOLD}${knowledge_count}${RESET} plików wiedzy w $knowledge_dir"
    echo ""
    echo -e "  ${GRAY}AI może przeszukiwać tę bazę (Linux, Python, Docker, Node.js i inne)${RESET}"
    echo -e "  ${GRAY}Wymaga działającego Ollama z modelem embeddingów.${RESET}"
    echo ""
    print_item "Możesz to zrobić teraz lub później: ${BOLD}ai --index${RESET}"
    echo ""

    if confirm "Zaindeksować bazę wiedzy teraz?" "y"; then
        echo ""
        print_info "Uruchamianie indeksowania..."
        echo ""
        local ai_cmd="$WRAPPER_PATH"
        [[ ! -x "$ai_cmd" ]] && ai_cmd="$VENV_PYTHON $INSTALL_DIR/main.py"

        if $ai_cmd --index 2>&1; then
            print_success "Baza wiedzy zaindeksowana"
        else
            print_warning "Indeksowanie nie powiodło się"
            print_item   "Ollama może nie być jeszcze uruchomiona"
            print_item   "Uruchom później: ${BOLD}ai --index${RESET}"
        fi
    else
        echo ""
        print_info "Pominięto — uruchom gdy Ollama jest gotowa: ${CYAN}ai --index${RESET}"
    fi

    echo ""
}

#═══════════════════════════════════════════════════════════════════════════════
# INSTALACJA
#═══════════════════════════════════════════════════════════════════════════════

install_internal() {
    clear_screen
    print_section "Instalacja AI CLI Agent"
    echo ""

    if [[ ! -f "$SCRIPT_DIR/main.py" ]]; then
        print_error "Nie znaleziono main.py w $SCRIPT_DIR"
        print_info  "Uruchom skrypt z katalogu projektu"
        exit 1
    fi

    # Krok 1 — pliki
    step_copy_files

    # Krok 2 — venv + pakiety (osobna sekcja, osobny ekran)
    install_venv "false"

    # Krok 3 — komenda 'ai'
    step_install_wrapper

    # Krok 4 — panel webowy (pyta użytkownika)
    step_ask_panel

    # Krok 5 — baza wiedzy RAG (pyta użytkownika)
    step_ask_index

    # Podsumowanie
    clear_screen
    echo -e "  ${GREEN}${BOLD}✓ Instalacja zakończona!${RESET}"
    echo ""
    print_item "ai help          — lista wszystkich poleceń"
    print_item "ai deps          — sprawdź stan pakietów Python"
    print_item "ai config        — konfiguracja (serwer, model, nick)"
    print_item "ai prompt        — spersonalizowany prompt"
    print_item "ai init          — zainicjalizuj projekt w katalogu"
    print_item "ai --index       — (ponowne) indeksowanie bazy wiedzy"
    echo ""
}

#═══════════════════════════════════════════════════════════════════════════════
# DEINSTALACJA
#═══════════════════════════════════════════════════════════════════════════════

uninstall_internal() {
    local interactive="${1:-true}"

    clear_screen
    print_section "Deinstalacja AI CLI Agent"
    echo ""

    echo -e "  ${BOLD}Zostanie usunięte:${RESET}"
    [[ -f "$WRAPPER_PATH" ]]                   && print_item "Komenda 'ai'      ($WRAPPER_PATH)"
    [[ -d "$INSTALL_DIR" ]]                    && print_item "Pliki agenta      ($INSTALL_DIR)"
    [[ -d "$VENV_DIR" ]]                       && print_item "venv              ($VENV_DIR)"
    [[ -f "$SYSTEMD_USER_DIR/$SERVICE_NAME" ]] && print_item "Systemd service   (ai-panel.service)"
    echo ""

    if [[ -d "$CONFIG_DIR" ]]; then
        echo -e "  ${BOLD}Twoja konfiguracja:${RESET}  ${CYAN}$CONFIG_DIR${RESET}"
        echo ""
        [[ -f "$CONFIG_FILE" ]] && print_item "${BOLD}config.json${RESET}   — serwer Ollama, model, nick"
        [[ -f "$PROMPT_FILE" ]] && print_item "${BOLD}prompt.txt${RESET}    — Twój spersonalizowany prompt"

        local WEB_HAS_SERVICE=false WEB_DATA_PRESENT=false
        [[ -f "$SYSTEMD_USER_DIR/$SERVICE_NAME" ]] && WEB_HAS_SERVICE=true
        [[ -d "$CONFIG_DIR/web" ]]                  && WEB_DATA_PRESENT=true

        if $WEB_HAS_SERVICE || $WEB_DATA_PRESENT; then
            local chat_count=0
            [[ -d "$CONFIG_DIR/web/chats" ]] && \
                chat_count=$(find "$CONFIG_DIR/web/chats" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
            print_item "${BOLD}web/chats/${RESET}   — historia czatu (${chat_count} konwersacji)"
        fi
        [[ -d "$CONFIG_DIR/knowledge" ]] && \
            print_item "${BOLD}knowledge/${RESET}   — baza wiedzy RAG"

        echo ""
        echo -e "  ${YELLOW}Konfiguracja NIE zostanie usunięta chyba że potwierdzisz poniżej.${RESET}"
        echo ""

        if confirm "Usunąć też konfigurację (~/.config/ai)?" "n"; then
            rm -rf "$CONFIG_DIR"
            print_success "Konfiguracja usunięta"
        else
            print_success "Konfiguracja zachowana"
        fi
        echo ""
    fi

    if [[ "$interactive" == "true" ]]; then
        if ! confirm "Potwierdzasz deinstalację?" "n"; then
            print_info "Anulowano"
            exit 0
        fi
        echo ""
    fi

    uninstall_systemd_service

    print_info "Usuwanie plików..."
    rm -f "$WRAPPER_PATH"  2>/dev/null || true
    rm -rf "$INSTALL_DIR"  2>/dev/null || true

    separator
    echo -e "  ${GREEN}${BOLD}✓ Deinstalacja zakończona${RESET}"
    echo ""
}

#═══════════════════════════════════════════════════════════════════════════════
# REINSTALACJA / AKTUALIZACJA
#═══════════════════════════════════════════════════════════════════════════════

reinstall_internal() {
    clear_screen
    print_section "Aktualizacja / Reinstalacja"
    echo ""

    local had_service=false
    [[ -f "$SYSTEMD_USER_DIR/$SERVICE_NAME" ]] && had_service=true
    local had_venv=false
    venv_is_ok && had_venv=true

    echo -e "  ${BOLD}Co się stanie:${RESET}"
    print_item "Pliki agenta zostaną zastąpione nową wersją"
    print_item "Komenda 'ai' zostanie odświeżona"
    if $had_venv; then
        print_item "venv zostanie zachowany — tylko pakiety zostaną zaktualizowane"
    else
        print_item "venv zostanie utworzony od nowa"
    fi
    $had_service && print_item "Service zostanie zrestartowany"
    echo ""
    print_success "Konfiguracja ($CONFIG_DIR) zostanie zachowana"
    echo ""

    if ! confirm "Kontynuować?" "n"; then
        print_info "Anulowano"
        exit 0
    fi

    echo ""

    # Usuń pliki ale NIE venv i NIE konfigurację
    print_section "Usuwanie starych plików"
    print_info "Usuwanie plików agenta (venv zachowany)..."
    rm -f "$WRAPPER_PATH" 2>/dev/null || true
    # Iterujemy po zawartości INSTALL_DIR bez -exec rm {} + żeby nie usunąć
    # samego katalogu (find przekazuje też ścieżkę bazową gdy używasz {} +)
    for _item in "$INSTALL_DIR"/*; do
        [[ "$_item" == "$VENV_DIR" ]] && continue
        [[ -e "$_item" ]] && rm -rf "$_item" 2>/dev/null || true
    done
    for _item in "$INSTALL_DIR"/.*; do
        [[ "$_item" == "$INSTALL_DIR/." || "$_item" == "$INSTALL_DIR/.." ]] && continue
        [[ -e "$_item" ]] && rm -rf "$_item" 2>/dev/null || true
    done
    print_success "Stare pliki usunięte"

    # Krok 1 — nowe pliki
    step_copy_files

    # Krok 2 — venv: zachowaj jeśli zdrowy, odbuduj gdy uszkodzony
    if $had_venv; then
        update_venv
    else
        install_venv "false"
    fi

    # Krok 3 — komenda 'ai'
    step_install_wrapper

    # Krok 4 — panel webowy (zawsze pyta — przy reinstalacji też można zmienić decyzję)
    step_ask_panel

    # Krok 5 — baza wiedzy RAG (zawsze pyta po aktualizacji — mogły przybyć nowe pliki)
    step_ask_index

    clear_screen
    echo -e "  ${GREEN}${BOLD}✓ Aktualizacja zakończona!${RESET}"
    echo ""
    print_item "ai deps   — sprawdź stan pakietów Python"
    print_item "ai help   — pełna lista poleceń"
    echo ""
}

#═══════════════════════════════════════════════════════════════════════════════
# TYLKO PAKIETY PYTHON
#═══════════════════════════════════════════════════════════════════════════════

packages_only_internal() {
    clear_screen
    update_venv

    clear_screen
    echo -e "  ${GREEN}${BOLD}✓ Pakiety zaktualizowane${RESET}"
    echo ""
    print_item "ai deps   — sprawdź aktualny stan pakietów"
    echo ""
}

#═══════════════════════════════════════════════════════════════════════════════
# POMOC
#═══════════════════════════════════════════════════════════════════════════════

show_help_cli() {
    echo ""
    echo -e "  ${CYAN}${BOLD}AI CLI Agent – Instalator${RESET}"
    echo ""
    echo -e "  ${BOLD}Użycie:${RESET}"
    echo -e "    bash install-cli.sh [opcja]"
    echo ""
    echo -e "  ${BOLD}Bez opcji:${RESET}"
    echo -e "    Interaktywne menu (instalacja / aktualizacja / deinstalacja)"
    echo ""
    echo -e "  ${BOLD}Opcje:${RESET}"
    echo ""
    echo -e "    ${GREEN}--install${RESET}          Świeża instalacja (bez pytań o potwierdzenie)"
    echo -e "    ${GREEN}--update${RESET}           Aktualizacja plików + pakietów (bez pytań)"
    echo -e "    ${GREEN}--update-packages${RESET}  Tylko aktualizacja pakietów Python (bez plików)"
    echo -e "    ${GREEN}--uninstall${RESET}        Deinstalacja (pyta o konfigurację, nie pyta o resztę)"
    echo -e "    ${GREEN}--uninstall-all${RESET}    Deinstalacja + usunięcie konfiguracji bez pytań"
    echo -e "    ${GREEN}--status${RESET}           Pokaż aktualny stan instalacji"
    echo -e "    ${GREEN}--help, -h${RESET}         Ta pomoc"
    echo ""
    echo -e "  ${BOLD}Przykłady:${RESET}"
    echo ""
    echo -e "    bash install-cli.sh                  ${GRAY}# interaktywne menu${RESET}"
    echo -e "    bash install-cli.sh --update         ${GRAY}# szybka aktualizacja bez pytań${RESET}"
    echo -e "    bash install-cli.sh --uninstall      ${GRAY}# usuń, zachowaj config${RESET}"
    echo -e "    bash install-cli.sh --uninstall-all  ${GRAY}# usuń wszystko bez pytań${RESET}"
    echo -e "    bash install-cli.sh --status         ${GRAY}# sprawdź co jest zainstalowane${RESET}"
    echo ""
}

#═══════════════════════════════════════════════════════════════════════════════
# MAIN
#═══════════════════════════════════════════════════════════════════════════════

main() {
    # Obsługa argumentów wiersza poleceń
    case "${1:-}" in
        --help|-h)
            show_help_cli
            exit 0
            ;;

        --install)
            clear_screen
            print_section "Instalacja AI CLI Agent (tryb nieinteraktywny)"
            echo ""
            if [[ ! -f "$SCRIPT_DIR/main.py" ]]; then
                print_error "Nie znaleziono main.py w $SCRIPT_DIR"
                exit 1
            fi
            step_copy_files
            install_venv "false"
            step_install_wrapper
            step_ask_panel
            step_ask_index
            clear_screen
            echo -e "  ${GREEN}${BOLD}✓ Instalacja zakończona!${RESET}"
            echo ""
            print_item "ai help   — lista poleceń"
            echo ""
            exit 0
            ;;

        --update)
            clear_screen
            print_section "Aktualizacja AI CLI Agent (tryb nieinteraktywny)"
            echo ""
            local had_venv=false
            venv_is_ok && had_venv=true

            print_info "Usuwanie starych plików agenta (venv + konfiguracja zachowane)..."
            rm -f "$WRAPPER_PATH" 2>/dev/null || true
            for _item in "$INSTALL_DIR"/*; do
                [[ "$_item" == "$VENV_DIR" ]] && continue
                [[ -e "$_item" ]] && rm -rf "$_item" 2>/dev/null || true
            done
            for _item in "$INSTALL_DIR"/.*; do
                [[ "$_item" == "$INSTALL_DIR/." || "$_item" == "$INSTALL_DIR/.." ]] && continue
                [[ -e "$_item" ]] && rm -rf "$_item" 2>/dev/null || true
            done
            print_success "Stare pliki usunięte"

            step_copy_files
            if $had_venv; then
                update_venv
            else
                install_venv "false"
            fi
            step_install_wrapper
            step_ask_panel

            # Restart serwisu jeśli był aktywny
            if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
                systemctl --user restart "$SERVICE_NAME" 2>/dev/null && \
                    print_success "Panel zrestartowany" || true
            fi

            clear_screen
            echo -e "  ${GREEN}${BOLD}✓ Aktualizacja zakończona!${RESET}"
            echo ""
            print_item "ai deps   — sprawdź stan pakietów"
            print_item "ai help   — pełna lista poleceń"
            echo ""
            exit 0
            ;;

        --update-packages)
            clear_screen
            print_section "Aktualizacja pakietów Python"
            echo ""
            update_venv
            clear_screen
            echo -e "  ${GREEN}${BOLD}✓ Pakiety zaktualizowane${RESET}"
            echo ""
            print_item "ai deps   — sprawdź aktualny stan pakietów"
            echo ""
            exit 0
            ;;

        --uninstall)
            uninstall_internal "false"
            exit 0
            ;;

        --uninstall-all)
            clear_screen
            print_section "Deinstalacja AI CLI Agent (pełna, bez pytań)"
            echo ""
            uninstall_systemd_service
            rm -f "$WRAPPER_PATH"  2>/dev/null || true
            rm -rf "$INSTALL_DIR"  2>/dev/null || true
            rm -rf "$CONFIG_DIR"   2>/dev/null || true
            print_success "Usunięto pliki agenta, venv i konfigurację"
            separator
            echo -e "  ${GREEN}${BOLD}✓ Deinstalacja zakończona${RESET}"
            echo ""
            exit 0
            ;;

        --status)
            clear_screen
            local status installed_ver new_ver
            status=$(detect_installation)
            installed_ver=$(get_installed_version)
            new_ver=$(get_new_version)
            show_status "$status" "$installed_ver" "$new_ver"
            exit 0
            ;;

        "")
            # Brak argumentów - interaktywne menu (oryginalne zachowanie)
            ;;

        *)
            echo ""
            echo -e "  ${RED}Nieznana opcja: $1${RESET}"
            echo -e "  Użyj ${CYAN}bash install-cli.sh --help${RESET} aby zobaczyć dostępne opcje."
            echo ""
            exit 1
            ;;
    esac

    # Interaktywne menu (gdy brak argumentów)
    clear_screen

    local status installed_ver new_ver
    status=$(detect_installation)
    installed_ver=$(get_installed_version)
    new_ver=$(get_new_version)

    show_status "$status" "$installed_ver" "$new_ver"
    show_menu   "$status" "$installed_ver" "$new_ver"

    while true; do
        echo -ne "  ${BOLD}Wybór:${RESET} "
        read -r choice

        if [[ "$status" == "none" ]]; then
            case "$choice" in
                1) install_internal;       break ;;
                2) print_info "Anulowano"; exit 0 ;;
                *) print_error "Wybierz 1 lub 2" ;;
            esac
        else
            case "$choice" in
                1) reinstall_internal;        break ;;
                2) packages_only_internal;    break ;;
                3) uninstall_internal "true"; break ;;
                4) print_info "Anulowano";    exit 0 ;;
                *) print_error "Wybierz 1, 2, 3 lub 4" ;;
            esac
        fi
    done
}

main "$@"
