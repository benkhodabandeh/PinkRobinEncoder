#!/usr/bin/env python3
"""DEPRECATED: use scripts/fetch_ffmpeg_bundle.py instead.

This module previously downloaded third-party BtbN FFmpeg builds (Windows /
Linux) or Homebrew FFmpeg (macOS). That violates two project requirements:

  1. Windows-only — Linux/macOS builds were removed.
  2. Custom minimal FFmpeg — releases must bundle the tailored build from
     scripts/build_ffmpeg_windows.sh, fetched via scripts/fetch_ffmpeg_bundle.py.

Kept as a thin shim so old docs/CI references fail with a clear message
instead of silently fetching the wrong binaries. Scheduled for deletion
once the first CI-built bundle is published (see ADR 0003).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    print(
        "download_ffmpeg.py is DEPRECATED and refuses to fetch third-party builds.\n"
        "Use instead:\n"
        "  python scripts/fetch_ffmpeg_bundle.py   # CI artifact (Windows)\n"
        "  bash scripts/build_ffmpeg_windows.sh    # local build (MSYS2 MinGW64)",
        file=sys.stderr,
    )
    fetcher = Path(__file__).resolve().parent / "fetch_ffmpeg_bundle.py"
    # Fixed interpreter + fixed in-repo script path; no user input, no shell.
    return subprocess.call([sys.executable, str(fetcher)])  # nosec B603 - fixed argv  # noqa: S603


if __name__ == "__main__":
    sys.exit(main())
