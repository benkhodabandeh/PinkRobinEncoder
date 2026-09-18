#!/usr/bin/env python3
"""Fetch the custom Pink Robin Encoder FFmpeg bundle (Windows-only).

The bundle is built by scripts/build_ffmpeg_windows.sh (MSYS2 MinGW64) and
published as the `ffmpeg-windows` artifact of the `build-ffmpeg` GitHub
Actions workflow. This script downloads and verifies it into ./bin.

Usage (CI or local):
    python scripts/fetch_ffmpeg_bundle.py [--release-tag v2026.7.7] [--repo OWNER/REPO]

Requires: GitHub CLI (gh) for artifact download. Falls back to a clear error
telling the user to build locally with scripts/build_ffmpeg_windows.sh.

This script intentionally supports Windows ONLY. Linux/macOS builds were
removed per project requirements.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"

REQUIRED_FILES = (
    "ffmpeg.exe",
    "ffprobe.exe",
    "libvmaf.dll",
    "libsoxr.dll",
    "libx264-164.dll",
)


def bundle_complete() -> list[str]:
    BIN.mkdir(exist_ok=True)
    return [f for f in REQUIRED_FILES if not (BIN / f).is_file()]


def main() -> int:
    if platform.system() != "Windows":
        print("ERROR: Pink Robin Encoder is Windows-only. Aborting.", file=sys.stderr)
        return 1

    missing = bundle_complete()
    if not missing:
        print("Custom FFmpeg bundle already complete in ./bin.")
        return 0

    print(f"Bundle incomplete, missing: {', '.join(missing)}")
    gh = shutil.which("gh")
    if not gh:
        print(
            "ERROR: GitHub CLI (gh) not found and ./bin is incomplete.\n"
            "  Build locally instead:  bash scripts/build_ffmpeg_windows.sh  (MSYS2 MinGW64)",
            file=sys.stderr,
        )
        return 1

    # Download the ffmpeg-windows artifact from the latest successful
    # build-ffmpeg workflow run (explicit run ID: `gh run download` without
    # one is interactive and fails in CI).
    print("Downloading ffmpeg-windows artifact via gh ...")
    tmp_zip = ROOT / "ffmpeg-windows.zip"
    try:
        repo = _repo_arg()
        run_id = subprocess.check_output(
            [
                gh, "run", "list", "--workflow", "build-ffmpeg.yml",
                "--status", "success", "--limit", "1",
                "--json", "databaseId", "--jq", ".[0].databaseId",
                "--repo", repo,
            ],
            cwd=str(ROOT),
            text=True,
        ).strip()
        if not run_id:
            raise subprocess.CalledProcessError(1, [gh, "run", "list"])
        subprocess.check_call(
            [
                gh, "run", "download", run_id, "--name", "ffmpeg-windows",
                "--dir", str(ROOT), "--repo", repo,
            ],
            cwd=str(ROOT),
        )
    except subprocess.CalledProcessError:
        print(
            "ERROR: artifact download failed. Build locally instead:\n"
            "  bash scripts/build_ffmpeg_windows.sh  (MSYS2 MinGW64)",
            file=sys.stderr,
        )
        return 1

    if tmp_zip.is_file():
        with zipfile.ZipFile(tmp_zip) as z:
            z.extractall(path=BIN)
        tmp_zip.unlink()

    missing = bundle_complete()
    if missing:
        print(f"ERROR: bundle still incomplete: {', '.join(missing)}", file=sys.stderr)
        return 1
    print("Custom FFmpeg bundle ready in ./bin.")
    return 0


def _repo_arg() -> str:
    for i, arg in enumerate(sys.argv):
        if arg == "--repo" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    # Auto-detect from git remote so forks/renames work with no flags.
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=str(ROOT),
            text=True,
        ).strip()
        # Supports https://github.com/OWNER/REPO(.git) and git@github.com:OWNER/REPO(.git)
        path = url.split("github.com", 1)[1].lstrip("/:").removesuffix(".git")
        if path.count("/") == 1:
            return path
    except Exception:
        pass
    return "benkhodabandeh/BKVideoEncoder"


if __name__ == "__main__":
    sys.exit(main())
