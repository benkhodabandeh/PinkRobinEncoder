# validators.py
"""
Central input validation and security hardening for Pink Robin Encoder.

All user-supplied values that reach FFmpeg command lines, file paths, or
output filenames MUST pass through here first. FFmpeg is always invoked
with an argument list (never shell=True), so the residual risks are:
path traversal, control characters, overlong values, and malformed
numeric/crop inputs that would produce cryptic FFmpeg failures.

Every function returns (clean_value, error_message_or_None).
"""

from __future__ import annotations

import os
import re
from datetime import datetime

MAX_TEXT_LEN = 200
MAX_PATH_LEN = 260  # Windows MAX_PATH (classic); long-path aware code paths exist
_METADATA_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_CROP_RE = re.compile(r"^(\d+):(\d+):(\d+):(\d+)$")
_YEAR_RE = re.compile(r"^\d{4}$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _strip_controls(value: str) -> str:
    return _CONTROL_CHARS_RE.sub("", value)


def validate_title(value: object) -> tuple[str, str | None]:
    text = _strip_controls(str(value or "")).strip()
    if not text:
        return "", "Title is required."
    if len(text) > MAX_TEXT_LEN:
        return text[:MAX_TEXT_LEN], f"Title truncated to {MAX_TEXT_LEN} characters."
    return text, None


def validate_artist(value: object) -> tuple[str, str | None]:
    text = _strip_controls(str(value or "")).strip()
    if len(text) > MAX_TEXT_LEN:
        return text[:MAX_TEXT_LEN], f"Artist truncated to {MAX_TEXT_LEN} characters."
    return text, None


def validate_year(value: object) -> tuple[str, str | None]:
    text = _strip_controls(str(value or "")).strip()
    if not text:
        return "", "Year is required."
    if not _YEAR_RE.match(text):
        return "", "Year must be a 4-digit number (e.g. 2024)."
    year = int(text)
    current = datetime.now().year
    if not (1880 <= year <= current + 5):
        return "", f"Year must be between 1880 and {current + 5}."
    return text, None


def validate_syndicate(value: object) -> tuple[str, str | None]:
    text = _strip_controls(str(value or "")).strip()
    if len(text) > MAX_TEXT_LEN:
        return text[:MAX_TEXT_LEN], f"Syndicate truncated to {MAX_TEXT_LEN} characters."
    return text, None


def validate_metadata_dict(raw: dict[str, object]) -> tuple[dict[str, str], dict[str, str]]:
    """Validate the four user metadata fields. Returns (clean, errors)."""
    clean: dict[str, str] = {}
    errors: dict[str, str] = {}
    validators = {
        "title": validate_title,
        "artist": validate_artist,
        "year": validate_year,
        "syndicate": validate_syndicate,
    }
    for field, func in validators.items():
        value, err = func(raw.get(field, ""))
        clean[field] = value
        if err:
            errors[field] = err
    return clean, errors


def validate_metadata_key(key: str) -> bool:
    """FFmpeg -metadata keys must be safe identifiers."""
    return bool(_METADATA_KEY_RE.match(key or ""))


def validate_crop_string(value: object) -> tuple[str, str | None]:
    """Validate a custom crop string of the form w:h:x:y."""
    text = _strip_controls(str(value or "")).strip().removeprefix("crop=")
    if not text:
        return "", None  # empty = no custom crop, not an error
    match = _CROP_RE.match(text)
    if not match:
        return "", "Crop must be w:h:x:y with non-negative integers."
    w, h, x, y = (int(g) for g in match.groups())
    if w <= 0 or h <= 0:
        return "", "Crop width and height must be positive."
    if w > 16384 or h > 16384 or x > 16384 or y > 16384:
        return "", "Crop values are unrealistically large."
    if w % 2 or h % 2:
        return "", "Crop width and height should be even (chroma-safe)."
    return f"{w}:{h}:{x}:{y}", None


def validate_target_mb(value: object, default: float = 199.0) -> tuple[float, str | None]:
    try:
        number = float(str(value).strip())
    except (ValueError, TypeError, AttributeError):
        return default, f"Invalid target size; using default {default:.0f} MB."
    if number <= 0:
        return default, "Target size must be positive."
    if number > 100_000:
        return default, "Target size is unrealistically large."
    return round(number), None


def validate_input_video_path(path: object) -> tuple[str, str | None]:
    """Validate a user-selected source video path (guards path traversal)."""
    text = _strip_controls(str(path or "")).strip()
    if not text:
        return "", "No file selected."
    if "\x00" in str(path or ""):
        return "", "Invalid path (null byte)."
    norm = os.path.normpath(text)
    if len(norm) > MAX_PATH_LEN and not norm.startswith("\\\\?\\"):
        return "", "Path is too long for Windows file APIs."
    if not os.path.isabs(norm):
        return "", "Path must be absolute."
    allowed_exts = (".mp4", ".mkv", ".mov", ".avi")
    if os.path.splitext(norm)[1].lower() not in allowed_exts:
        return "", f"Unsupported video type. Allowed: {', '.join(allowed_exts)}."
    if not os.path.isfile(norm):
        return "", "File does not exist."
    return norm, None


def validate_destination_dir(path: object) -> tuple[str, str | None]:
    text = _strip_controls(str(path or "")).strip()
    if not text:
        return "", "No folder selected."
    norm = os.path.normpath(text)
    if not os.path.isabs(norm):
        return "", "Destination must be an absolute path."
    if not os.path.isdir(norm):
        return "", "Destination folder does not exist."
    return norm, None
