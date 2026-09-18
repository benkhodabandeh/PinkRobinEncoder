#!/usr/bin/env python3
"""Fetch the custom Pink Robin Encoder FFmpeg bundle (Windows-only).

The bundle is built by scripts/build_ffmpeg_windows.sh (MSYS2 MinGW64) and
published as the `ffmpeg-windows` artifact of the `build-ffmpeg` GitHub
Actions workflow. This script downloads and verifies it into ./bin.

Usage (CI or local):
    python scripts/fetch_ffmpeg_bundle.py [--repo OWNER/REPO]

Requires: GitHub CLI (gh) for artifact download. Falls back to a clear error
telling the user to build locally with scripts/build_ffmpeg_windows.sh.

This script intentionally supports Windows ONLY. Linux/macOS builds were
removed per project requirements.
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"

REQUIRED_FILES = (
    "ffmpeg.exe",
    "ffprobe.exe",
    "libx265.dll",
    "libsoxr.dll",
    "libvmaf.dll",
)

# Versioned DLL names change with upstream releases (e.g. libx264-164.dll ->
# libx264-165.dll), so match those by glob instead of a hardcoded name.
REQUIRED_GLOBS = ("libx264-*.dll", "libfdk-aac-*.dll")


def _has_dll(pattern: str) -> bool:
    """Check for a versioned DLL by glob pattern."""
    return any(BIN.glob(pattern))


def bundle_complete() -> list[str]:
    BIN.mkdir(exist_ok=True)
    missing = [f for f in REQUIRED_FILES if not (BIN / f).is_file()]
    missing.extend(p for p in REQUIRED_GLOBS if not _has_dll(p))
    return missing


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
    repo = _repo_arg()
    run_id = _find_successful_run_id(gh, repo)
    if not run_id:
        print(
            "ERROR: no successful build-ffmpeg run found. Build FFmpeg first:\n"
            "  bash scripts/build_ffmpeg_windows.sh  (MSYS2 MinGW64)",
            file=sys.stderr,
        )
        return 1

    print(f"Downloading ffmpeg-windows artifact (run {run_id}) via gh ...")
    if not _download_artifact_with_retry(gh, run_id, repo):
        print(
            "ERROR: artifact download failed after retries. Build locally instead:\n"
            "  bash scripts/build_ffmpeg_windows.sh  (MSYS2 MinGW64)",
            file=sys.stderr,
        )
        return 1

    tmp_zip = ROOT / "ffmpeg-windows.zip"
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
    git_exe = shutil.which("git")
    if git_exe is not None:
        try:
            url = subprocess.check_output(  # nosec B603  # noqa: S603
                [git_exe, "remote", "get-url", "origin"],
                cwd=str(ROOT),
                text=True,
            ).strip()
            path = url.split("github.com", 1)[1].lstrip("/:").removesuffix(".git")
            if path.count("/") == 1:
                return path
        except Exception:
            logger.debug("git remote detection failed; using default repo.")
    return "benkhodabandeh/PinkRobinEncoder"


def _find_successful_run_id(gh: str, repo: str) -> str | None:
    """Find the databaseId of the latest successful build-ffmpeg run."""
    for _ in range(30):  # Retry up to ~5 minutes
        try:
            out = subprocess.check_output(  # nosec B603  # noqa: S603
                [
                    gh, "run", "list", "--workflow", "build-ffmpeg.yml",
                    "--status", "success", "--limit", "1",
                    "--json", "databaseId", "--jq", ".[0].databaseId",
                    "--repo", repo,
                ],
                cwd=str(ROOT), text=True,
            ).strip()
            if out and out.isdigit():
                return out
        except subprocess.CalledProcessError:
            pass
        time.sleep(10)
    return None


def _download_artifact_with_retry(gh: str, run_id: str, repo: str) -> bool:
    """Download the ffmpeg-windows artifact, retrying if the artifact isn't ready."""
    for attempt in range(5):
        try:
            subprocess.check_call(  # nosec B603  # noqa: S603
                [
                    gh, "run", "download", run_id, "--name", "ffmpeg-windows",
                    "--dir", str(ROOT), "--repo", repo,
                ],
                cwd=str(ROOT),
            )
            return True
        except subprocess.CalledProcessError:
            if attempt < 4:
                print(f"Artifact not ready yet, retrying in 15s (attempt {attempt + 1}/5)...")
                time.sleep(15)
            else:
                return False
    return False


if __name__ == "__main__":
    sys.exit(main())
