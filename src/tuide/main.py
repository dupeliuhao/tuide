"""CLI entrypoint for tuide."""

from __future__ import annotations

import argparse
from pathlib import Path

from tuide.app import TuideApp


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

    startup_path = Path(args.path).expanduser().resolve() if args.path else None
    app = TuideApp(startup_path=startup_path)
    app.run()


if __name__ == "__main__":
    main()
