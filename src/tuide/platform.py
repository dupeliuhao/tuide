"""Platform helpers with Linux-first defaults."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlatformInfo:
    """Resolved platform characteristics."""

    system: str
    is_linux: bool
    is_macos: bool
    is_windows: bool
    default_shell: str


def detect_platform() -> PlatformInfo:
    """Return current platform info with conservative shell defaults."""
    system = platform.system().lower()
    is_linux = system == "linux"
    is_macos = system == "darwin"
    is_windows = system == "windows"

    if is_linux or is_macos:
        default_shell = os.environ.get("SHELL", "/bin/bash")
    elif is_windows:
        default_shell = os.environ.get("COMSPEC", "powershell.exe")
    else:
        default_shell = os.environ.get("SHELL", "/bin/sh")

    return PlatformInfo(
        system=system,
        is_linux=is_linux,
        is_macos=is_macos,
        is_windows=is_windows,
        default_shell=default_shell,
    )

