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
WRAPPER_PATH="$HOME/.local/bin/ai"
CONFIG_DIR="$HOME/.config/ai"
CONFIG_FILE="$CONFIG_DIR/config.json"
PROMPT_FILE="$CONFIG_DIR/prompt.txt"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="ai-panel.service"

#═══════════════════════════════════════════════════════════════════════════════
# FUNKCJE POMOCNICZE
#═══════════════════════════════════════════════════════════════════════════════

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

print_success() {
    echo -e "  ${GREEN}✓${RESET} $1"
}

print_error() {
    echo -e "  ${RED}✗${RESET} $1"
}

print_warning() {
    echo -e "  ${YELLOW}⚠${RESET} $1"
}

print_info() {
    echo -e "  ${CYAN}ℹ${RESET} $1"
}

print_item() {
    echo -e "  ${GRAY}•${RESET} $1"
}

# Separator wizualny
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
# WYKRYWANIE INSTALACJI I WERSJI
#═══════════════════════════════════════════════════════════════════════════════

get_version_from_dir() {
    local dir="$1"
    if [[ -f "$dir/main.py" ]]; then
        python3 -c "
import sys, re
try:
    with open('$dir/main.py', 'r') as f:
        for line in f:
            if '__version__' in line or 'VERSION' in line:
                match = re.search(r'[\"\\']([0-9]+\\.[0-9]+\\.[0-9]+)[\"\\']', line)
                if match:
                    print(match.group(1))
                    break
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
    local wrapper_exists=false
    local install_dir_exists=false

    [[ -f "$WRAPPER_PATH" ]] && wrapper_exists=true
    [[ -d "$INSTALL_DIR" ]] && install_dir_exists=true

    if $wrapper_exists || $install_dir_exists; then
        echo "installed"
    else
        echo "none"
    fi
}

get_installed_version() { get_version_from_dir "$INSTALL_DIR"; }
get_new_version()        { get_version_from_dir "$SCRIPT_DIR";  }

#═══════════════════════════════════════════════════════════════════════════════
# SYSTEMD SERVICE
#═══════════════════════════════════════════════════════════════════════════════

install_systemd_service() {
    print_section "Instalacja systemd service"

    if ! command -v systemctl >/dev/null 2>&1; then
        print_warning "systemctl niedostępne — pomijam instalację service"
        return 1
    fi

    mkdir -p "$SYSTEMD_USER_DIR"

    local service_source="$INSTALL_DIR/web/ai-panel.service"
    local service_dest="$SYSTEMD_USER_DIR/$SERVICE_NAME"

    if [[ ! -f "$service_source" ]]; then
        print_error "Plik service nie istnieje: $service_source"
        return 1
    fi

    cp "$service_source" "$service_dest"
    print_success "Skopiowano service do $service_dest"

    systemctl --user daemon-reload

    if systemctl --user enable "$SERVICE_NAME" 2>/dev/null; then
        print_success "Autostart włączony"
    else
        print_warning "Nie udało się włączyć autostartu"
    fi

    if systemctl --user start "$SERVICE_NAME" 2>/dev/null; then
        print_success "Panel uruchomiony"
    else
        print_warning "Nie udało się uruchomić panelu"
    fi

    echo ""
    echo -e "  ${CYAN}${BOLD}Panel webowy: http://127.0.0.1:21650${RESET}"
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
# WYŚWIETLANIE STATUSU
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
        # Wersje
        if [[ "$installed_ver" == "$new_ver" ]]; then
            echo -e "  Wersja zainstalowana:  ${BOLD}${installed_ver}${RESET}  ${GREEN}(aktualna)${RESET}"
        else
            echo -e "  Wersja zainstalowana:  ${BOLD}${installed_ver}${RESET}"
            echo -e "  Nowa wersja:           ${BOLD}${new_ver}${RESET}  ${CYAN}(dostępna aktualizacja)${RESET}"
        fi
        echo ""

        # Składniki
        if [[ -f "$WRAPPER_PATH" ]]; then
            print_success "Komenda 'ai':   $WRAPPER_PATH"
        else
            print_warning "Komenda 'ai':   brak ($WRAPPER_PATH)"
        fi

        if [[ -d "$INSTALL_DIR" ]]; then
            print_success "Pliki agenta:   $INSTALL_DIR"
        else
            print_warning "Pliki agenta:   brak ($INSTALL_DIR)"
        fi

        if [[ -f "$SYSTEMD_USER_DIR/$SERVICE_NAME" ]]; then
            print_success "Panel webowy:   zainstalowany jako service"
        else
            print_item    "Panel webowy:   nie zainstalowany"
        fi

        # Konfiguracja
        echo ""
        if [[ -d "$CONFIG_DIR" ]]; then
            print_success "Konfiguracja:   $CONFIG_DIR"
            if [[ -f "$CONFIG_FILE" ]]; then
                print_item "config.json     (adres serwera, model, nick)"
            fi
            if [[ -f "$PROMPT_FILE" ]]; then
                print_item "prompt.txt      (Twój spersonalizowany prompt)"
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
            echo -e "  ${BOLD}[1]${RESET} Reinstaluj  ${GRAY}(ta sama wersja ${new_ver})${RESET}"
        else
            echo -e "  ${BOLD}[1]${RESET} Aktualizuj  ${GRAY}(${installed_ver} → ${new_ver})${RESET}"
        fi
        echo -e "  ${BOLD}[2]${RESET} Odinstaluj"
        echo -e "  ${BOLD}[3]${RESET} Anuluj"
    fi

    echo ""
}

#═══════════════════════════════════════════════════════════════════════════════
# INSTALACJA
#═══════════════════════════════════════════════════════════════════════════════

install_internal() {
    print_section "Instalacja AI CLI Agent"
    echo ""

    if [[ ! -f "$SCRIPT_DIR/main.py" ]]; then
        print_error "Nie znaleziono main.py w $SCRIPT_DIR"
        print_info  "Uruchom skrypt z katalogu projektu"
        exit 1
    fi

    # Utwórz katalogi
    print_info "Tworzenie katalogów..."
    mkdir -p "$(dirname "$WRAPPER_PATH")"
    mkdir -p "$INSTALL_DIR"
    print_success "Katalogi gotowe"

    # Kopiuj pliki
    print_info "Kopiowanie plików agenta..."
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/" 2>/dev/null || {
        for file in "$SCRIPT_DIR"/*; do
            [[ -e "$file" ]] && cp -r "$file" "$INSTALL_DIR/"
        done
    }
    rm -f "$INSTALL_DIR/install-cli.sh" 2>/dev/null || true
    print_success "Pliki skopiowane → $INSTALL_DIR"

    # Kopiuj knowledge/ do ~/.config/ai/knowledge/ (jeśli istnieje w źródle)
    KNOWLEDGE_SRC="$SCRIPT_DIR/knowledge"
    KNOWLEDGE_DST="$CONFIG_DIR/knowledge"
    if [[ -d "$KNOWLEDGE_SRC" ]]; then
        print_info "Kopiowanie bazy wiedzy (knowledge/)..."
        mkdir -p "$KNOWLEDGE_DST"
        cp -r "$KNOWLEDGE_SRC"/. "$KNOWLEDGE_DST/"
        local kcount
        kcount=$(find "$KNOWLEDGE_DST" -name "*.md" -o -name "*.txt" 2>/dev/null | wc -l)
        print_success "Baza wiedzy → $KNOWLEDGE_DST ($kcount plików)"
    else
        print_item "Brak katalogu knowledge/ — pomijam"
    fi

    # Utwórz wrapper
    print_info "Tworzenie komendy 'ai'..."
    cat > "$WRAPPER_PATH" << 'EOF'
#!/usr/bin/env bash
exec python3 "$HOME/.local/share/ai-cli-agent/main.py" "$@"
EOF
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

    # ── Panel webowy ──────────────────────────────────────────────────────────
    separator

    echo -e "  ${CYAN}${BOLD}Panel webowy (opcjonalny)${RESET}"
    echo ""
    print_item "Edycja konfiguracji przez przeglądarkę"
    print_item "Zmiana modelu Ollama"
    print_item "Edycja system promptu"
    print_item "Podgląd logów i statusu"
    echo ""
    print_warning "Panel służy tylko do konfiguracji — nie wykonuje poleceń AI"
    echo ""

    if confirm "Czy chcesz używać panelu webowego?" "n"; then
        echo ""
        echo -e "  ${BOLD}Jak uruchamiać panel?${RESET}"
        echo ""
        echo -e "  ${BOLD}[1]${RESET} Autostart ${GRAY}(systemd service — startuje razem z systemem)${RESET}"
        echo -e "  ${BOLD}[2]${RESET} Ręcznie   ${GRAY}(uruchamiasz gdy potrzebujesz)${RESET}"
        echo ""

        while true; do
            echo -ne "  ${YELLOW}?${RESET} Wybór [1/2]: "
            read -r panel_choice
            case "$panel_choice" in
                1)
                    echo ""
                    if install_systemd_service; then
                        print_success "Panel zainstalowany i uruchomiony"
                    else
                        print_warning "Nie udało się zainstalować service"
                        echo ""
                        print_info "Uruchom panel ręcznie:"
                        echo -e "  ${CYAN}python3 ~/.local/share/ai-cli-agent/web/server.py${RESET}"
                    fi
                    break
                    ;;
                2)
                    echo ""
                    print_info "Panel nie jest zainstalowany jako service"
                    echo ""
                    echo -e "  Uruchomienie ręczne:"
                    echo -e "  ${CYAN}python3 ~/.local/share/ai-cli-agent/web/server.py${RESET}"
                    echo ""
                    print_item "Możesz zainstalować service później — instrukcje: ai help"
                    break
                    ;;
                *)
                    print_error "Wybierz 1 lub 2"
                    ;;
            esac
        done
    else
        echo ""
        print_info "Panel nie został skonfigurowany"
        echo -e "  ${GRAY}Możesz uruchomić go ręcznie: python3 ~/.local/share/ai-cli-agent/web/server.py${RESET}"
    fi

    # ── Podsumowanie ─────────────────────────────────────────────────────────
    separator

    echo -e "  ${GREEN}${BOLD}✓ Instalacja zakończona pomyślnie!${RESET}"
    echo ""
    print_item "ai help          — lista wszystkich poleceń"
    print_item "ai config        — sprawdź konfigurację (serwer, model, nick)"
    print_item "ai prompt        — ustaw swój spersonalizowany prompt"
    print_item "ai init          — zainicjalizuj projekt w bieżącym katalogu"
    echo ""
}

#═══════════════════════════════════════════════════════════════════════════════
# DEINSTALACJA
#═══════════════════════════════════════════════════════════════════════════════

uninstall_internal() {
    local interactive="${1:-true}"

    print_section "Deinstalacja AI CLI Agent"
    echo ""

    # Co zostanie usunięte
    echo -e "  ${BOLD}Zostanie usunięte:${RESET}"
    [[ -f "$WRAPPER_PATH" ]]                 && print_item "Komenda 'ai'      ($WRAPPER_PATH)"
    [[ -d "$INSTALL_DIR" ]]                  && print_item "Pliki agenta      ($INSTALL_DIR)"
    [[ -f "$SYSTEMD_USER_DIR/$SERVICE_NAME" ]] && print_item "Systemd service   (ai-panel.service)"
    echo ""

    # Konfiguracja — pytanie ze szczegółowym opisem
    if [[ -d "$CONFIG_DIR" ]]; then
        echo -e "  ${BOLD}Twoja konfiguracja:${RESET}  ${CYAN}$CONFIG_DIR${RESET}"
        echo ""

        if [[ -f "$CONFIG_FILE" ]]; then
            print_item "${BOLD}config.json${RESET}  — adres serwera Ollama, model, Twój nick"
        fi
        if [[ -f "$PROMPT_FILE" ]]; then
            print_item "${BOLD}prompt.txt${RESET}   — Twój spersonalizowany system prompt (jeśli ustawiałeś)"
        fi
        if [[ ! -f "$CONFIG_FILE" && ! -f "$PROMPT_FILE" ]]; then
            print_item "katalog konfiguracji (pusty lub inne pliki)"
        fi

        echo ""
        echo -e "  ${YELLOW}Jeśli usuniesz konfigurację, przy kolejnej instalacji${RESET}"
        echo -e "  ${YELLOW}trzeba będzie ustawić serwer, model i nick od nowa.${RESET}"
        echo ""

        if confirm "Usunąć również konfigurację?" "n"; then
            rm -rf "$CONFIG_DIR"
            print_success "Konfiguracja usunięta"
        else
            print_success "Konfiguracja zachowana — przy reinstalacji wszystko zadziała od razu"
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

    # Usuń service
    uninstall_systemd_service

    # Usuń pliki
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
    print_section "Aktualizacja / Reinstalacja"
    echo ""

    local had_service=false
    [[ -f "$SYSTEMD_USER_DIR/$SERVICE_NAME" ]] && had_service=true

    # Wyjaśnij co się stanie
    echo -e "  ${BOLD}Co się stanie:${RESET}"
    print_item "Pliki agenta zostaną zastąpione nową wersją"
    print_item "Komenda 'ai' zostanie odświeżona"
    if $had_service; then
        print_item "Service zostanie zrestartowany"
    fi
    echo ""
    print_success "Twoja konfiguracja ($CONFIG_DIR) zostanie zachowana"
    echo ""

    if ! confirm "Kontynuować?" "n"; then
        print_info "Anulowano"
        exit 0
    fi

    echo ""
    uninstall_internal "false"
    echo ""
    install_internal

    if $had_service; then
        echo ""
        print_info "Wcześniej używałeś panelu webowego jako service"
        if confirm "Zainstalować service ponownie?" "y"; then
            install_systemd_service
        fi
    fi
}

#═══════════════════════════════════════════════════════════════════════════════
# MAIN
#═══════════════════════════════════════════════════════════════════════════════

main() {
    print_header

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
                1) install_internal; break ;;
                2) print_info "Anulowano"; exit 0 ;;
                *) print_error "Wybierz 1 lub 2" ;;
            esac
        else
            case "$choice" in
                1) reinstall_internal; break ;;
                2) uninstall_internal "true"; break ;;
                3) print_info "Anulowano"; exit 0 ;;
                *) print_error "Wybierz 1, 2 lub 3" ;;
            esac
        fi
    done
}

main