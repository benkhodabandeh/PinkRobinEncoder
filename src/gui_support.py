# gui_support.py
"""
Contains helper classes and functions that support the GUI layer,
separating them from core application logic.
"""


class OperationCancelledError(Exception):
    """Custom exception to signal user cancellation of a background task."""

    pass
