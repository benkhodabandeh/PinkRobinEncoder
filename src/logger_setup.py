# logger_setup.py
"""
Configures application-wide logging for Pink Robin Encoder.

This module provides a centralized function to set up a robust logging system
that outputs to a fresh log file on each launch and to the console.
"""

import json
import logging
import logging.handlers
import os
import sys

import config

_logging_initialized = False


class JsonFormatter(logging.Formatter):
    """Single-line JSON formatter for machine-readable logs.

    Enable with PRE_JSON_LOGS=1. Used by CI log parsers and future
    OpenTelemetry shipping; the default human-readable format is unchanged.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, datefmt=config.LOG_DATE_FORMAT),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _make_formatter() -> logging.Formatter:
    if os.environ.get("PRE_JSON_LOGS") == "1":
        return JsonFormatter()
    return logging.Formatter(config.LOG_FORMAT, datefmt=config.LOG_DATE_FORMAT)


def setup_logging() -> None:
    """
    Sets up logging to a file that is overwritten on each application launch
    and to the console (stdout/stderr). Ensures this setup is performed only once.
    """
    global _logging_initialized
    if _logging_initialized:
        return

    # Create a formatter and the root logger
    formatter = _make_formatter()
    root_logger = logging.getLogger()
    root_logger.setLevel(config.LOG_LEVEL)

    # Clear any existing handlers to prevent duplicate logs in case of re-initialization
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # --- File Handler (with error handling and overwrite mode) ---
    log_dir = None
    log_filepath = "Disabled"
    try:
        # Prefer 'Documents' folder for user-accessibility
        documents_path = os.path.join(os.path.expanduser("~"), "Documents")
        log_dir = os.path.join(documents_path, config.LOG_FOLDER_NAME)
        log_filename = f"{config.APP_NAME.replace(' ', '_').lower()}.log"
        log_filepath = os.path.join(log_dir, log_filename)
        os.makedirs(log_dir, exist_ok=True)

        # Use a standard FileHandler in 'write' mode ('w') to overwrite the log on each run
        file_handler = logging.FileHandler(
            filename=log_filepath, mode="w", encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # Fallback to console if file logging fails, so logs are not lost
        print(f"CRITICAL: Could not set up file logging. Error: {e}", file=sys.stderr)

    # --- Console Handlers ---
    try:
        # Handler for INFO and WARNING to stdout
        class InfoFilter(logging.Filter):
            """Filters records to allow only INFO and WARNING levels."""

            def filter(self, record):
                return logging.INFO <= record.levelno <= logging.WARNING

        console_stdout = logging.StreamHandler(sys.stdout)
        console_stdout.addFilter(InfoFilter())
        console_stdout.setFormatter(formatter)
        root_logger.addHandler(console_stdout)

        # Handler for ERROR and CRITICAL to stderr
        console_stderr = logging.StreamHandler(sys.stderr)
        console_stderr.setLevel(logging.ERROR)
        console_stderr.setFormatter(formatter)
        root_logger.addHandler(console_stderr)
    except Exception as e:
        print(
            f"CRITICAL: Could not set up console logging. Error: {e}", file=sys.stderr
        )

    _logging_initialized = True

    # Log the initialization message
    init_logger = logging.getLogger(__name__)
    init_logger.info("=" * 60)
    init_logger.info(f"Logging initialized for {config.APP_NAME} v{config.APP_VERSION}")
    init_logger.info(f"Log file location: {log_filepath}")
    init_logger.info("=" * 60)
