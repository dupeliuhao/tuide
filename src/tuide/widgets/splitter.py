"""Resizable splitter widgets for panel dragging."""

from __future__ import annotations

from collections.abc import Callable

from textual import events
from textual.widgets import Static


class VerticalSplitter(Static):
    """Thin draggable divider that reports horizontal deltas."""

    DEFAULT_CLASSES = "panel-splitter"
    can_focus = False

    def __init__(
        self,
        on_drag_delta: Callable[[int], None],
        *,
        id: str | None = None,
    ) -> None:
        super().__init__("", id=id)
        self._on_drag_delta = on_drag_delta
        self._drag_origin_x: int | None = None

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Begin a resize drag."""
        self._drag_origin_x = event.screen_x
        self.capture_mouse()
        self.add_class("-dragging")
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Resize while dragging."""
        if self._drag_origin_x is None:
            return
        delta = event.screen_x - self._drag_origin_x
        if delta:
            self._on_drag_delta(delta)
            self._drag_origin_x = event.screen_x
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Finish a resize drag."""
        if self._drag_origin_x is None:
            return
        self._drag_origin_x = None
        self.release_mouse()
        self.remove_class("-dragging")
        event.stop()
