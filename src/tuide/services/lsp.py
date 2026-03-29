"""Very early LSP capability detection and fallback plumbing."""

from __future__ import annotations

import shutil
from pathlib import Path


class LspService:
    """Detect language-server availability."""

    def pyright_available(self) -> bool:
        """Return whether pyright is available."""
        return shutil.which("pyright") is not None

    def metals_available(self) -> bool:
        """Return whether metals is available."""
        return shutil.which("metals") is not None

    def language_server_for(self, path: Path) -> str | None:
        """Return the preferred language server label for a file."""
        suffix = path.suffix.lower()
        if suffix == ".py":
            return "pyright"
        if suffix in {".scala", ".sc", ".sbt"}:
            return "metals"
        return None

    def available_for(self, path: Path) -> bool:
        """Return whether the preferred language server is available."""
        server = self.language_server_for(path)
        if server == "pyright":
            return self.pyright_available()
        if server == "metals":
            return self.metals_available()
        return False

    def status_label(self) -> str:
        """Return a summary capability label."""
        labels: list[str] = []
        labels.append("pyright" if self.pyright_available() else "no-pyright")
        labels.append("metals" if self.metals_available() else "no-metals")
        return ",".join(labels)
