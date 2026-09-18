# a11y.py
"""
Accessibility helpers for Pink Robin Encoder (WCAG 2.1 AA effort).

Tkinter/customtkinter has limited native screen-reader support, so this
module focuses on what the toolkit CAN do well:
  - visible keyboard-focus indicators on interactive controls,
  - single-key/Alt accelerators for primary actions,
  - status-bar announcements for state changes (preset toggles, queue ops),
  - a documented list of known limitations (see docs/ACCESSIBILITY.md).

Honest scope: this does not make customtkinter fully screen-reader
compatible (NVDA/JAWS narration of custom-drawn widgets remains limited).
It makes the app fully keyboard-operable with visible focus and
announced feedback, which is the achievable AA bar for this stack.
"""

from __future__ import annotations

import logging
from typing import Any

import config

logger = logging.getLogger(__name__)

FOCUS_RING_COLOR = "#F0CB70"
FOCUS_RING_WIDTH = 2


def announce(app: Any, message: str) -> None:
    """Announce a state change via the status bar (and log it)."""
    try:
        # Queue only - the gui_updaters import happens lazily on the main
        # thread when the callback runs (importing it here would break
        # headless/test contexts and couple this helper to the GUI layer).
        app.ui_update_queue.put(lambda: _deliver(app, message))
    except Exception:
        logger.debug("a11y announce failed: %s", message)


def _deliver(app: Any, message: str) -> None:
    """Main-thread delivery of a queued announcement."""
    try:
        import gui_updaters

        gui_updaters.handle_status_update(app, message)
    except Exception:
        logger.debug("a11y delivery failed: %s", message)


def add_focus_ring(widget: Any, ring_color: str = FOCUS_RING_COLOR) -> None:
    """Add a visible focus indicator to a button-like widget."""
    try:
        normal_border = {"border_width": 0}

        def _on_focus_in(_event=None, w=widget):
            try:
                w.configure(border_width=FOCUS_RING_WIDTH, border_color=ring_color)
            except Exception:
                logger.debug("Focus ring could not be drawn on this widget.")

        def _on_focus_out(_event=None, w=widget):
            try:
                w.configure(**normal_border, border_color=config.Theme.SURFACE_LIGHT)
            except Exception:
                logger.debug("Focus ring could not be cleared on this widget.")

        widget.bind("<FocusIn>", _on_focus_in, add="+")
        widget.bind("<FocusOut>", _on_focus_out, add="+")
    except Exception:
        logger.debug("a11y focus ring setup failed", exc_info=False)


def describe_action(action: str) -> str:
    """Human-readable descriptions for status announcements."""
    descriptions = {
        "preset_on": "Preset selected",
        "preset_off": "Preset deselected",
        "job_queued": "Job added to the plan",
        "job_removed": "Job removed from the plan",
        "queue_moved": "Plan item moved",
        "cancelled": "Operation cancelled",
        "develop_started": "Development started",
        "develop_done": "Development complete",
    }
    return descriptions.get(action, action)
