"""CLI entrypoint for tuide."""

from __future__ import annotations

from tuide.app import TuideApp


def main() -> None:
    """Run the Textual application."""
    app = TuideApp()
    app.run()


if __name__ == "__main__":
    main()

