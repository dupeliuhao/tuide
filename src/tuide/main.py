"""CLI entrypoint for tuide."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from tuide.app import TuideApp


def _ensure_delta() -> None:
    """Install git-delta if it is not already on PATH."""
    if shutil.which("delta"):
        return

    print("git-delta not found — attempting to install…")

    # Try downloading the .deb directly (Ubuntu/Debian — not in default repos)
    if shutil.which("dpkg") and shutil.which("wget"):
        import platform
        machine = platform.machine()
        arch = "amd64" if machine == "x86_64" else ("arm64" if machine == "aarch64" else None)
        if arch:
            version = "0.18.2"
            url = f"https://github.com/dandavison/delta/releases/download/{version}/git-delta_{version}_{arch}.deb"
            deb = f"/tmp/git-delta_{version}_{arch}.deb"
            dl = subprocess.run(["wget", "-q", url, "-O", deb], capture_output=True)
            if dl.returncode == 0:
                if os.geteuid() == 0:
                    install_cmd = ["dpkg", "-i", deb]
                elif shutil.which("sudo"):
                    install_cmd = ["sudo", "-n", "dpkg", "-i", deb]
                else:
                    install_cmd = None
                if install_cmd:
                    result = subprocess.run(install_cmd, capture_output=True)
                    if result.returncode == 0 and shutil.which("delta"):
                        print("git-delta installed via .deb package.")
                        return

    # Try cargo
    if shutil.which("cargo"):
        result = subprocess.run(["cargo", "install", "git-delta"], capture_output=True)
        if result.returncode == 0 and shutil.which("delta"):
            print("git-delta installed via cargo.")
            return

    print(
        "Could not install git-delta automatically.\n"
        "Install it manually for enhanced diff view:\n"
        "  Ubuntu/Debian : sudo apt install git-delta\n"
        "  Rust/Cargo    : cargo install git-delta\n"
    )


def main() -> None:
    """Run the Textual application."""
    parser = argparse.ArgumentParser(prog="tuide", description="Terminal IDE")
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Directory to open as the workspace root (overrides persisted state)",
    )
    args = parser.parse_args()

    _ensure_delta()

    startup_path = Path(args.path).expanduser().resolve() if args.path else None
    app = TuideApp(startup_path=startup_path)
    app.run()


if __name__ == "__main__":
    main()
