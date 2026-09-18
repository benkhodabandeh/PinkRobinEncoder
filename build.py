#!/usr/bin/env python3
"""Windows-only Nuitka build for Pink Robin Encoder.

Produces a single all-in-one executable (Nuitka onefile):
    dist/PinkRobinEncoder.exe
The custom FFmpeg bundle (bin/ffmpeg.exe, bin/ffprobe.exe + DLLs) and
app data files (icon, logo, VMAF model) are embedded inside the exe and
unpacked to a cache dir automatically at first launch.

Prerequisites (Windows):
    py -3.12 -m venv .venv
    .\\.venv\\Scripts\\Activate.ps1
    pip install -r requirements.txt -r requirements-dev.txt
    # Provide the custom FFmpeg bundle first:
    #   Option A (CI): download the ffmpeg-windows artifact into ./bin
    #   Option B (local): bash scripts/build_ffmpeg_windows.sh (MSYS2 MinGW64)

Usage:
    python build.py [--skip-tests]
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
SRC = ROOT / "src"
DIST = ROOT / "dist"
BIN = ROOT / "bin"
VER = "V1.0"
# Nuitka requires a fully-numeric version for its VERSIONINFO resource.
NUITKA_VERSION = "1.0.0.0"
NAME = "PinkRobinEncoder"

REQUIRED_BIN_FILES = (
    "ffmpeg.exe",
    "ffprobe.exe",
    "libx265.dll",
    "libsoxr.dll",
    "libvmaf.dll",
)
# Versioned DLL names change with upstream releases (e.g. libx264-164.dll ->
# libx264-165.dll), so match those by glob instead of a hardcoded name.
REQUIRED_BIN_GLOBS = ("libx264-*.dll", "libfdk-aac-*.dll")


def run(cmd: list[str]) -> None:
    print("> " + " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(ROOT))


def check_windows() -> None:
    if platform.system() != "Windows":
        print("ERROR: Pink Robin Encoder builds Windows-only. Aborting.", file=sys.stderr)
        sys.exit(1)


def check_ffmpeg_bundle() -> None:
    missing = [f for f in REQUIRED_BIN_FILES if not (BIN / f).is_file()]
    for pattern in REQUIRED_BIN_GLOBS:
        if not any(BIN.glob(pattern)):
            missing.append(pattern)
    if missing:
        print("ERROR: custom FFmpeg bundle incomplete in ./bin.", file=sys.stderr)
        print(f"  Missing: {', '.join(missing)}", file=sys.stderr)
        print("  Build it with:  bash scripts/build_ffmpeg_windows.sh  (MSYS2 MinGW64)", file=sys.stderr)
        print("  ...or download the ffmpeg-windows CI artifact into ./bin", file=sys.stderr)
        sys.exit(1)
    print(f"FFmpeg bundle OK: {', '.join(REQUIRED_BIN_FILES)} present.")


def main() -> None:
    check_windows()
    skip_tests = "--skip-tests" in sys.argv

    # Clean previous artifacts (keep ./bin - the FFmpeg bundle is expensive).
    for p in [ROOT / "build", DIST]:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    DIST.mkdir(parents=True, exist_ok=True)

    if not skip_tests:
        run([sys.executable, "scripts/dev_check.py"])
    check_ffmpeg_bundle()

    # Pre-bundle check: the FFmpeg binaries must actually execute before we
    # embed them (guards a corrupt/incomplete ./bin download).
    subprocess.check_call([str(BIN / "ffmpeg.exe"), "-version"], stdout=subprocess.DEVNULL)
    subprocess.check_call([str(BIN / "ffprobe.exe"), "-version"], stdout=subprocess.DEVNULL)
    print("FFmpeg bundle executes OK.")

    # ---- Nuitka compile (onefile: single all-in-one exe) ----
    # Every file in ./bin (ffmpeg.exe, ffprobe.exe + all DLLs) is embedded
    # via explicit --include-data-files entries (Nuitka filters .exe/.dll
    # out of --include-data-dir, which only covers the VMAF model JSON) and
    # unpacked to a cache dir at first launch.
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--onefile",
        "--windows-console-mode=disable",
        f"--windows-icon-from-ico={SRC / 'icon.ico'}",
        "--company-name=Pink Robin Encoder",
        f"--product-name={NAME}",
        f"--file-version={NUITKA_VERSION}",
        f"--product-version={NUITKA_VERSION}",
        f"--output-dir={DIST}",
        "--enable-plugin=tk-inter",
        f"--include-data-files={SRC / 'icon.ico'}=icon.ico",
        f"--include-data-files={SRC / 'pink_robin_logo.png'}=pink_robin_logo.png",
        # The FFmpeg binaries and all DLLs must be embedded explicitly
        # (Nuitka filters .exe/.dll out of --include-data-dir).
        # find_resource_path resolves them from sys._MEIPASS/bin/ at runtime.
        *[f"--include-data-files={f}=bin/{f.name}" for f in sorted(BIN.iterdir()) if f.is_file()],
        f"--include-data-dir={BIN}=bin",
        "--include-package-data=scenedetect",
        "--nofollow-import-to=tests,pytest",
        "--assume-yes-for-downloads",
        "--show-progress",
        str(SRC / "app.py"),
    ]
    run(cmd)

    # Onefile mode emits a single app.exe directly in DIST - rename it.
    src_exe = DIST / "app.exe"
    dst_exe = DIST / f"{NAME}.exe"
    if dst_exe.is_file():
        dst_exe.unlink()
    if not src_exe.is_file():
        print(f"ERROR: expected Nuitka onefile output missing: {src_exe}", file=sys.stderr)
        sys.exit(1)
    src_exe.rename(dst_exe)

    # Smoke test: frozen exe must start and report its version (exit 0).
    # This guards broken DLL/module bundling that previously made the
    # released exe exit silently with code 1.
    subprocess.check_call([str(dst_exe), "--version"])
    print("Smoke test OK: frozen exe launches and reports version.")

    # Archive the single exe (no wrapper folder - it is fully self-contained).
    archive_path = DIST / f"{NAME}.{VER}.windows.7z"
    _7z = shutil.which("7z") or shutil.which("7za") or shutil.which("7zz") or r"C:\Program Files\7-Zip\7z.exe"
    subprocess.check_call([_7z, "a", "-mx=9", str(archive_path), dst_exe.name], cwd=str(DIST))

    print(f"Release: {archive_path}")


if __name__ == "__main__":
    main()
