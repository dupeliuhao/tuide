"""Filesystem paths for config and workspace state."""

from __future__ import annotations

from pathlib import Path

from platformdirs import PlatformDirs


APP_NAME = "tuide"
APP_AUTHOR = "tuide"


def get_dirs() -> PlatformDirs:
    """Return application directories."""
    return PlatformDirs(appname=APP_NAME, appauthor=APP_AUTHOR, roaming=True)


def config_dir() -> Path:
    """Return the configuration directory."""
    return Path(get_dirs().user_config_dir)


def data_dir() -> Path:
    """Return the application data directory."""
    return Path(get_dirs().user_data_dir)


def default_config_path() -> Path:
    """Return the default config file path."""
    return config_dir() / "config.toml"


def default_workspace_path() -> Path:
    """Return the default workspace file path."""
    return config_dir() / "workspace.toml"

