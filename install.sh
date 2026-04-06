#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/vtuide"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_LINUX_EXTRA=1
INSTALL_SYSTEM_DEPS=1
INSTALL_LAUNCHER=1
LAUNCHER_DIR="${LAUNCHER_DIR:-$HOME/.local/bin}"

usage() {
    cat <<'EOF'
tuide installer

Usage:
  ./install.sh [options]

Options:
  --skip-system-deps   Do not try to install git/rg/fd/python packages
  --no-terminal        Install without textual-terminal extras
  --venv-dir PATH      Use a custom virtualenv directory
  --python BIN         Use a specific Python executable
  --launcher-dir PATH  Install the tuide launcher into this directory
  --no-launcher        Do not install a launcher into ~/.local/bin
  --help               Show this help

Examples:
  ./install.sh
  ./install.sh --skip-system-deps
  ./install.sh --venv-dir .venv
  ./install.sh --no-terminal
  ./install.sh --launcher-dir ~/.local/bin
EOF
}

log() {
    printf '\n[%s] %s\n' "tuide" "$1"
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

warn_manual_system_install() {
    echo "Could not install system packages automatically."
    echo "Install git, Python 3.11+, python venv support, ripgrep, and fd manually, then rerun ./install.sh --skip-system-deps."
}

ensure_linux() {
    if [ "$(uname -s)" != "Linux" ]; then
        echo "tuide install.sh currently supports Linux only."
        exit 1
    fi
}

ensure_repo_root() {
    if [ ! -f "$ROOT_DIR/pyproject.toml" ]; then
        echo "Could not find pyproject.toml. Run this script from the tuide repo root."
        exit 1
    fi
}

ensure_python_version() {
    if ! "$PYTHON_BIN" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    then
        echo "tuide requires Python 3.11 or newer."
        exit 1
    fi
}

install_system_deps() {
    if [ "$INSTALL_SYSTEM_DEPS" -ne 1 ]; then
        return
    fi

    log "Checking system dependencies"

    if have git && have "$PYTHON_BIN" && have rg && (have fd || have fdfind); then
        log "System dependencies already look good"
        return
    fi

    if have apt-get; then
        log "Installing Linux packages with apt"
        if ! run_maybe_sudo apt-get update; then
            warn_manual_system_install
            return
        fi
        run_maybe_sudo apt-get install -y git "$PYTHON_BIN" python3-venv python3-pip ripgrep fd-find || {
            warn_manual_system_install
        }
        return
    fi

    if have dnf; then
        log "Installing Linux packages with dnf"
        if ! have sudo && [ "$(id -u)" -ne 0 ]; then
            warn_manual_system_install
            return
        fi
        run_maybe_sudo dnf install -y git python3 python3-pip python3-virtualenv ripgrep fd-find || {
            warn_manual_system_install
        }
        return
    fi

    if have pacman; then
        log "Installing Linux packages with pacman"
        if ! have sudo && [ "$(id -u)" -ne 0 ]; then
            warn_manual_system_install
            return
        fi
        run_maybe_sudo pacman -Sy --noconfirm git python python-pip ripgrep fd || {
            warn_manual_system_install
        }
        return
    fi

    if have zypper; then
        log "Installing Linux packages with zypper"
        if ! have sudo && [ "$(id -u)" -ne 0 ]; then
            warn_manual_system_install
            return
        fi
        run_maybe_sudo zypper --non-interactive install git python311 python311-pip python311-virtualenv ripgrep fd || {
            warn_manual_system_install
        }
        return
    fi

    echo "No supported package manager detected. Install git, Python 3.11+, ripgrep, and fd manually."
}

create_venv() {
    log "Creating virtual environment at $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
}

ensure_fd_alias() {
    if [ -x "$VENV_DIR/bin/fd" ]; then
        return
    fi
    if have fd; then
        return
    fi
    if have fdfind; then
        ln -sf "$(command -v fdfind)" "$VENV_DIR/bin/fd"
        log "Linked fdfind as fd inside the virtual environment"
    fi
}

install_python_deps() {
    log "Installing Python dependencies"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip

    if [ "$INSTALL_LINUX_EXTRA" -eq 1 ]; then
        if "$VENV_DIR/bin/pip" install -e "$ROOT_DIR[linux]"; then
            return
        fi
        log "Linux extra install failed; falling back to base install"
    fi

    "$VENV_DIR/bin/pip" install -e "$ROOT_DIR"
}

install_launcher() {
    if [ "$INSTALL_LAUNCHER" -ne 1 ]; then
        return
    fi

    mkdir -p "$LAUNCHER_DIR"
    cat >"$LAUNCHER_DIR/tuide" <<EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/tuide" "\$@"
EOF
    chmod +x "$LAUNCHER_DIR/tuide"
    log "Installed launcher at $LAUNCHER_DIR/tuide"
}

print_path_hint() {
    case ":$PATH:" in
        *":$LAUNCHER_DIR:"*) ;;
        *)
            cat <<EOF

Add this to your shell profile if needed:

  export PATH="$LAUNCHER_DIR:\$PATH"
EOF
            ;;
    esac
}

print_finish() {
    if [ "$INSTALL_LAUNCHER" -eq 1 ]; then
        cat <<EOF

tuide install complete.

Launcher:

  $LAUNCHER_DIR/tuide

Recommended:

  tuide

Open a specific project:

  tuide /path/to/project

If you prefer using the virtual environment directly:

  source "$VENV_DIR/bin/activate"
  tuide

Version check:

  "$VENV_DIR/bin/python" -m tuide.main --version
EOF
        print_path_hint
        return
    fi

    cat <<EOF

tuide install complete.

Use the virtual environment directly:

  source "$VENV_DIR/bin/activate"
  tuide

Open a specific project:

  source "$VENV_DIR/bin/activate"
  tuide /path/to/project

Version check:

  "$VENV_DIR/bin/python" -m tuide.main --version
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --skip-system-deps)
            INSTALL_SYSTEM_DEPS=0
            ;;
        --no-terminal)
            INSTALL_LINUX_EXTRA=0
            ;;
        --venv-dir)
            shift
            if [ "$#" -eq 0 ]; then
                echo "--venv-dir requires a path"
                exit 1
            fi
            if [[ "$1" = /* ]]; then
                VENV_DIR="$1"
            else
                VENV_DIR="$ROOT_DIR/$1"
            fi
            ;;
        --python)
            shift
            if [ "$#" -eq 0 ]; then
                echo "--python requires an executable name or path"
                exit 1
            fi
            PYTHON_BIN="$1"
            ;;
        --launcher-dir)
            shift
            if [ "$#" -eq 0 ]; then
                echo "--launcher-dir requires a path"
                exit 1
            fi
            if [[ "$1" = /* ]]; then
                LAUNCHER_DIR="$1"
            else
                LAUNCHER_DIR="$ROOT_DIR/$1"
            fi
            ;;
        --no-launcher)
            INSTALL_LAUNCHER=0
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
ensure_repo_root
install_system_deps
ensure_python_version
create_venv
ensure_fd_alias
install_python_deps
install_launcher
print_finish
