"""Config persistence helpers."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

import tomli_w

from tuide.models import AppConfig
from tuide.paths import default_config_path


class ConfigStore:
    """Load and save app configuration."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or default_config_path()

    def load(self) -> AppConfig:
        """Load config from disk if it exists."""
        if not self.config_path.exists():
            return AppConfig()

        data = tomllib.loads(self.config_path.read_text(encoding="utf-8"))
        return AppConfig(
            workspace_width=int(data.get("workspace_width", 28)),
            terminal_width=int(data.get("terminal_width", 32)),
            default_workspace=str(data.get("default_workspace", "")),
        )

    def save(self, config: AppConfig) -> None:
        """Persist config to disk."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "workspace_width": config.workspace_width,
            "terminal_width": config.terminal_width,
            "default_workspace": config.default_workspace,
        }
        self.config_path.write_text(tomli_w.dumps(payload), encoding="utf-8")
