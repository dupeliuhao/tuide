#!/usr/bin/env bash

set -euo pipefail

REPO_URL="${TUIDE_REPO_URL:-https://github.com/dupeliuhao/tuide.git}"
REF="${TUIDE_REF:-main}"
INSTALL_DIR="${TUIDE_INSTALL_DIR:-$HOME/.local/share/tuide}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PASSTHROUGH_ARGS=()

usage() {
    cat <<'EOF'
Remote tuide installer

Usage:
  curl -fsSL https://raw.githubusercontent.com/dupeliuhao/tuide/main/scripts/install-remote.sh | bash

Optional args:
  --ref REF             Branch or tag to install
  --install-dir PATH    Where to clone/update tuide
  --python BIN          Python executable to use
  --skip-system-deps    Forwarded to install.sh
  --no-terminal         Forwarded to install.sh
  --launcher-dir PATH   Forwarded to install.sh
  --no-launcher         Forwarded to install.sh
  --help                Show this help

Examples:
  curl -fsSL https://raw.githubusercontent.com/dupeliuhao/tuide/v1.0.1/scripts/install-remote.sh | bash
  curl -fsSL https://raw.githubusercontent.com/dupeliuhao/tuide/main/scripts/install-remote.sh | bash -s -- --ref v1.0.1
EOF
}

log() {
    printf '\n[%s] %s\n' "tuide-bootstrap" "$1"
}

have() {
    command -v "$1" >/dev/null 2>&1
}

run_maybe_sudo() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
        return
    fi
    if have sudo; then
        sudo "$@"
        return
    fi
    return 1
}

ensure_linux() {
    if [ "$(uname -s)" != "Linux" ]; then
        echo "tuide remote installer currently supports Linux only."
        exit 1
    fi
}

ensure_bootstrap_deps() {
    if have git && have "$PYTHON_BIN"; then
        return
    fi

    if have apt-get; then
        log "Installing bootstrap dependencies with apt"
        run_maybe_sudo apt-get update || true
        run_maybe_sudo apt-get install -y git "$PYTHON_BIN" python3-venv python3-pip || true
    elif have dnf; then
        log "Installing bootstrap dependencies with dnf"
        run_maybe_sudo dnf install -y git python3 python3-pip python3-virtualenv || true
    elif have pacman; then
        log "Installing bootstrap dependencies with pacman"
        run_maybe_sudo pacman -Sy --noconfirm git python python-pip || true
    elif have zypper; then
        log "Installing bootstrap dependencies with zypper"
        run_maybe_sudo zypper --non-interactive install git python311 python311-pip python311-virtualenv || true
    fi

    if ! have git; then
        echo "git is required for the remote installer."
        exit 1
    fi
    if ! have "$PYTHON_BIN"; then
        echo "Python 3.11+ is required for the remote installer."
        exit 1
    fi
}

sync_repo() {
    mkdir -p "$(dirname "$INSTALL_DIR")"

    if [ ! -d "$INSTALL_DIR/.git" ]; then
        log "Cloning tuide into $INSTALL_DIR"
        git clone --depth 1 --branch "$REF" "$REPO_URL" "$INSTALL_DIR"
        return
    fi

    log "Updating existing tuide checkout in $INSTALL_DIR"
    git -C "$INSTALL_DIR" fetch --tags origin
    git -C "$INSTALL_DIR" checkout "$REF"
    if git -C "$INSTALL_DIR" ls-remote --exit-code --heads origin "$REF" >/dev/null 2>&1; then
        git -C "$INSTALL_DIR" pull --ff-only origin "$REF"
    fi
}

run_repo_installer() {
    log "Running tuide installer"
    "$INSTALL_DIR/install.sh" --python "$PYTHON_BIN" "${PASSTHROUGH_ARGS[@]}"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --ref)
            shift
            REF="${1:?--ref requires a value}"
            ;;
        --install-dir)
            shift
            INSTALL_DIR="${1:?--install-dir requires a value}"
            ;;
        --python)
            shift
            PYTHON_BIN="${1:?--python requires a value}"
            ;;
        --skip-system-deps|--no-terminal|--launcher-dir|--no-launcher)
            PASSTHROUGH_ARGS+=("$1")
            if [ "$1" = "--launcher-dir" ]; then
                shift
                PASSTHROUGH_ARGS+=("${1:?--launcher-dir requires a value}")
            fi
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo
            usage
            exit 1
            ;;
    esac
    shift
done

ensure_linux
ensure_bootstrap_deps
sync_repo
run_repo_installer
