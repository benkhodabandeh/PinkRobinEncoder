# ui_runtime.py
"""Runtime safety helpers for Pink Robin Encoder.

This module is intentionally small and dependency-light. It patches only the
main App instance at startup so the existing GUI can become smoother without a
large rewrite.
"""

from __future__ import annotations

import logging
import platform
import queue
import signal
import time
import types
from collections import deque
from typing import Any

import config
import customtkinter as ctk

logger = logging.getLogger(__name__)

# Performance tuning constants
UI_QUEUE_BATCH_LIMIT = 24           # Bounded drain so repaints/input get time
UI_QUEUE_IDLE_TICK_MS = 33          # Calm idle cadence (~30fps, less repaint contention)
UI_QUEUE_BURST_TICK_MS = 16         # Burst cadence only when queue is deep
ESTIMATE_DEBOUNCE_MS = 180
ESTIMATE_DEBOUNCE_FAST_MS = 50      # Fast debounce for rapid changes
PREVIEW_DEBOUNCE_MS = 200
PREVIEW_DEBOUNCE_FAST_MS = 120      # Still calm during drag operations
PROCESS_CANCEL_GRACE_SEC = 2.5

# Adaptive performance tracking
MAX_QUEUE_HISTORY = 100
TARGET_FRAME_MS = 16.67             # 60fps target


def install_runtime_guards(app: Any) -> None:
    """Install smooth-UI helpers on an App instance."""
    app._ui_queue_batch_limit = UI_QUEUE_BATCH_LIMIT
    app._ui_queue_idle_tick_ms = UI_QUEUE_IDLE_TICK_MS
    app._ui_queue_burst_tick_ms = UI_QUEUE_BURST_TICK_MS
    app._estimate_after_id = None
    app._preview_after_id = None
    app._active_toast = None
    # Performance tracking
    app._ui_frame_times = deque(maxlen=MAX_QUEUE_HISTORY)
    app._last_ui_frame_time = time.perf_counter()
    app._adaptive_debounce = True

    app._process_ui_queue = types.MethodType(_process_ui_queue, app)
    app._request_estimate_update = types.MethodType(_request_estimate_update, app)
    app._request_preview_refresh = types.MethodType(_request_preview_refresh, app)
    app._show_toast = types.MethodType(_show_toast, app)
    app._terminate_process_tree = types.MethodType(_terminate_process_tree, app)
    app._get_performance_stats = types.MethodType(_get_performance_stats, app)


def _process_ui_queue(self: Any) -> None:
    """Drain a bounded number of callbacks per frame with adaptive performance.

    The bounded drain keeps the window responsive and lets Windows repaint/input
    events run between chunks. Adaptive batching adjusts based on frame time.
    """
    frame_start = time.perf_counter()
    processed = 0
    batch_limit = getattr(self, "_ui_queue_batch_limit", UI_QUEUE_BATCH_LIMIT)

    try:
        while processed < batch_limit:
            callback = self.ui_update_queue.get_nowait()
            if callable(callback):
                try:
                    callback()
                except Exception:
                    logger.exception("UI callback failed")
            processed += 1
    except queue.Empty:
        pass

    # Track frame time for adaptive performance
    frame_time_ms = (time.perf_counter() - frame_start) * 1000
    if hasattr(self, "_ui_frame_times"):
        self._ui_frame_times.append(frame_time_ms)

    # Adaptive batching: reduce batch limit if frames are slow
    if frame_time_ms > TARGET_FRAME_MS * 2 and batch_limit > 8:
        self._ui_queue_batch_limit = max(8, batch_limit - 4)
    elif frame_time_ms < TARGET_FRAME_MS * 0.5 and batch_limit < UI_QUEUE_BATCH_LIMIT:
        self._ui_queue_batch_limit = min(UI_QUEUE_BATCH_LIMIT, batch_limit + 2)

    # Schedule next frame with adaptive timing
    try:
        if not self.winfo_exists():
            return

        # Use burst mode for high queue depth, idle mode otherwise
        queue_depth = self.ui_update_queue.qsize()
        if queue_depth > 10:
            delay = getattr(self, "_ui_queue_burst_tick_ms", UI_QUEUE_BURST_TICK_MS)
        else:
            delay = getattr(self, "_ui_queue_idle_tick_ms", UI_QUEUE_IDLE_TICK_MS)

        # Adjust delay based on frame time
        if frame_time_ms > TARGET_FRAME_MS:
            delay = min(delay + 2, UI_QUEUE_IDLE_TICK_MS)

        self.after(delay, self._process_ui_queue)
    except Exception:
        logger.debug(
            "Stopped UI queue pump because the window is closing.", exc_info=False
        )


def _request_estimate_update(
    self: Any, delay_ms: int = ESTIMATE_DEBOUNCE_MS, fast: bool = False
) -> None:
    """Debounce expensive estimate recalculation during typing/slider moves.

    Args:
        delay_ms: Base debounce delay in milliseconds
        fast: If True, use fast debounce for rapid user interactions
    """
    try:
        if getattr(self, "_estimate_after_id", None):
            self.after_cancel(self._estimate_after_id)
    except Exception:
        logger.debug("Estimate debounce cancel raced timer completion.")

    # Adaptive debounce: use faster debounce for rapid changes
    if fast or getattr(self, "_adaptive_debounce", True):
        delay_ms = min(delay_ms, ESTIMATE_DEBOUNCE_FAST_MS)

    def _run() -> None:
        self._estimate_after_id = None
        if self.winfo_exists():
            self._update_estimates()

    self._estimate_after_id = self.after(delay_ms, _run)


def _request_preview_refresh(
    self: Any,
    image_path: str | None = None,
    delay_ms: int = PREVIEW_DEBOUNCE_MS,
    fast: bool = False,
) -> None:
    """Debounce preview redraws when crop fields/sliders change.

    Args:
        image_path: Path to the preview image
        delay_ms: Base debounce delay in milliseconds
        fast: If True, use fast debounce for drag operations
    """
    try:
        if getattr(self, "_preview_after_id", None):
            self.after_cancel(self._preview_after_id)
    except Exception:
        logger.debug("Preview debounce cancel raced timer completion.")

    # Adaptive debounce: use faster debounce for drag operations
    if fast or getattr(self, "_adaptive_debounce", True):
        delay_ms = min(delay_ms, PREVIEW_DEBOUNCE_FAST_MS)

    def _run() -> None:
        self._preview_after_id = None
        if not self.winfo_exists():
            return
        try:
            import gui_updaters

            gui_updaters.display_preview_image(self, image_path)
        except Exception:
            logger.exception("Preview refresh failed")

    self._preview_after_id = self.after(delay_ms, _run)


def _show_toast(self: Any, title: str, message: str, duration_ms: int = 2400) -> None:
    """Small non-blocking notification used for routine success messages."""
    try:
        if getattr(self, "_active_toast", None) and self._active_toast.winfo_exists():
            self._active_toast.destroy()
    except Exception:
        logger.debug("Previous toast was already destroyed.")

    try:
        toast = ctk.CTkToplevel(self)
        self._active_toast = toast
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(fg_color=config.Theme.BACKGROUND)
        frame = ctk.CTkFrame(
            toast,
            fg_color=config.Theme.SURFACE,
            corner_radius=config.Theme.CORNER_RADIUS + 6,
            border_width=1,
            border_color=config.Theme.PRIMARY,
        )
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        ctk.CTkLabel(
            frame, text=title, font=(config.Theme.FONT_FAMILY, 12, "bold"), text_color=config.Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=14, pady=(10, 0))
        ctk.CTkLabel(
            frame,
            text=message,
            font=(config.Theme.FONT_FAMILY, 11),
            text_color=config.Theme.TEXT_SECONDARY,
            wraplength=340,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(3, 10))
        self.update_idletasks()
        x = self.winfo_rootx() + max(24, self.winfo_width() - 430)
        y = self.winfo_rooty() + max(24, self.winfo_height() - 140)
        toast.geometry(f"400x92+{x}+{y}")
        toast.after(
            duration_ms, lambda: toast.destroy() if toast.winfo_exists() else None
        )
    except Exception:
        logger.info("Toast fallback: %s - %s", title, message)
        try:
            import gui_updaters

            gui_updaters.handle_status_update(self, f"{title}: {message}")
        except Exception:
            logger.debug("Toast status fallback failed; window is closing.")


def _terminate_process_tree(
    self: Any, process: Any, description: str = "process"
) -> None:
    """Terminate an FFmpeg process with Windows-aware escalation."""
    if not process or process.poll() is not None:
        return
    pid = getattr(process, "pid", "unknown")
    logger.info("Cancelling %s PID %s", description, pid)

    try:
        if platform.system() == "Windows":
            try:
                process.send_signal(signal.CTRL_BREAK_EVENT)
                logger.info("Sent CTRL_BREAK_EVENT to PID %s", pid)
            except Exception:
                process.terminate()
                logger.info("Sent terminate signal to PID %s", pid)
        else:
            process.terminate()
        try:
            process.wait(timeout=PROCESS_CANCEL_GRACE_SEC)
            return
        except Exception:
            logger.debug("Process ignored graceful terminate; escalating to kill.")
        if process.poll() is None:
            process.kill()
            logger.warning("Killed unresponsive %s PID %s", description, pid)
    except Exception:
        logger.exception("Failed to terminate %s PID %s", description, pid)


def _get_performance_stats(self: Any) -> dict[str, Any]:
    """Get current UI performance statistics for debugging/monitoring."""
    frame_times = list(getattr(self, "_ui_frame_times", []))
    if not frame_times:
        return {"status": "no_data"}

    avg_frame_ms = sum(frame_times) / len(frame_times)
    max_frame_ms = max(frame_times)
    fps = 1000 / avg_frame_ms if avg_frame_ms > 0 else 0

    return {
        "avg_frame_ms": round(avg_frame_ms, 2),
        "max_frame_ms": round(max_frame_ms, 2),
        "estimated_fps": round(fps, 1),
        "frame_samples": len(frame_times),
        "queue_depth": self.ui_update_queue.qsize(),
        "batch_limit": getattr(self, "_ui_queue_batch_limit", UI_QUEUE_BATCH_LIMIT),
        "adaptive_debounce": getattr(self, "_adaptive_debounce", True),
    }
