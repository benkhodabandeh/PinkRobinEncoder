# Contributing

Thanks for improving BK Video Encoder.

## Development setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
python scripts/dev_check.py
```

## Pull request checklist

- Keep UI work off the Tk main thread.
- Use the existing UI queue for cross-thread UI updates.
- Avoid blocking modal dialogs for routine success messages.
- Test FFmpeg command generation with at least one tiny sample before release.
- Update README/docs when user-facing behavior changes.
- Do not commit bundled FFmpeg archives or large generated videos.

## Coding style

- Prefer small functions with explicit names.
- Keep FFmpeg command construction deterministic and easy to test.
- Use `pathlib` for new filesystem code when possible.
- Log actionable errors without dumping private file paths into public reports.
