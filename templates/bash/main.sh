#!/usr/bin/env bash
# {{PROJECT_NAME}}
# Autor: {{AUTHOR}}
# {{DESCRIPTION}}

set -euo pipefail

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RESET='\033[0m'

print_info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
print_success() { echo -e "${GREEN}[OK]${RESET}   $*"; }
print_warn()    { echo -e "${YELLOW}[WARN]${RESET} $*"; }
print_error()   { echo -e "${RED}[ERR]${RESET}  $*" >&2; }

main() {
  print_info "Uruchamianie {{PROJECT_NAME}}..."
  print_success "Gotowe!"
}

main "$@"
