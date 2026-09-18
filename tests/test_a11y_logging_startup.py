"""Tests for a11y helpers, JSON logging, and the startup validation hook."""

import io
import json
import logging
import queue
from pathlib import Path

import pytest

import a11y
import config
from logger_setup import JsonFormatter


class _StubApp:
    """Minimal stand-in: announce() only needs ui_update_queue."""

    def __init__(self):
        self.ui_update_queue = queue.Queue()


def test_describe_action_known_and_unknown():
    assert a11y.describe_action("preset_on") == "Preset selected"
    assert a11y.describe_action("job_queued") == "Job added to the plan"
    assert a11y.describe_action("something-new") == "something-new"


def test_announce_queues_message():
    app = _StubApp()
    a11y.announce(app, "Hello")
    assert not app.ui_update_queue.empty()
    callback = app.ui_update_queue.get_nowait()
    assert callable(callback)


def test_announce_never_raises():
    a11y.announce(object(), "Hello")  # broken app stand-in: must not raise


def test_json_formatter_emits_parseable_json():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello %s", args=("world",), exc_info=None,
    )
    line = formatter.format(record)
    payload = json.loads(line)  # raises if not valid JSON
    assert payload["level"] == "INFO"
    assert payload["msg"] == "hello world"
    assert payload["logger"] == "test"
    assert "ts" in payload and "module" in payload


def test_json_formatter_includes_exception():
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname=__file__, lineno=1,
        msg="failed", args=(), exc_info=exc_info,
    )
    payload = json.loads(formatter.format(record))
    assert "ValueError: boom" in payload["exc"]


def test_validate_presets_negative():
    """Mutating a copy of a preset must trip the schema validator."""
    import copy

    bad = copy.deepcopy(config.STANDARD_PRESETS["THE_CAPO"])
    del bad["description"]
    with pytest.raises(ValueError, match="description"):
        _validate_single("THE_CAPO", bad)

    bad2 = copy.deepcopy(config.FAST_PRESETS["THE_HITMAN"])
    bad2["audio_codec"] = "aac"
    with pytest.raises(ValueError, match="libfdk_aac"):
        _validate_single("THE_HITMAN", bad2)


def _validate_single(pid, preset):
    """Reuse the real schema rules against one preset dict."""
    import config as cfg

    original = dict(cfg.STANDARD_PRESETS)
    try:
        cfg.STANDARD_PRESETS = {pid: preset}
        cfg_extra = dict(cfg.FAST_PRESETS)
        cfg_fast_backup, cfg_wf_backup = cfg.FAST_PRESETS, cfg.WORKFLOW_PRESETS
        cfg.FAST_PRESETS, cfg.WORKFLOW_PRESETS = {}, {}
        try:
            cfg.validate_presets()
        finally:
            cfg.FAST_PRESETS, cfg.WORKFLOW_PRESETS = cfg_fast_backup, cfg_wf_backup
    finally:
        cfg.STANDARD_PRESETS = original


def test_startup_hook_calls_validate_presets():
    """App startup must fail fast on bad presets (regression guard)."""
    app_src = Path(__file__).resolve().parent.parent / "src" / "app.py"
    text = app_src.read_text(encoding="utf-8")
    assert "validate_presets" in text, (
        "App startup must call config.validate_presets() - hook missing in app.py"
    )


def test_no_fallback_flags_in_source():
    """Required-dependency invariant: no HAS_* fallback branches may return."""
    src = Path(__file__).resolve().parent.parent / "src"
    for name in ("analysis.py", "encoding.py"):
        text = (src / name).read_text(encoding="utf-8")
        assert "HAS_PILLOW = False" not in text
        assert "HAS_PYSCENEDETECT = False" not in text
