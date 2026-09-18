#!/usr/bin/env python3
"""Windows-only Nuitka build for Pink Robin Encoder.

Produces a standalone portable folder:
    dist/PinkRobinEncoder/
        PinkRobinEncoder.exe
        bin/ffmpeg.exe, bin/ffprobe.exe + required DLLs
        licenses/, README.md

Prerequisites (Windows):
    py -3.11 -m venv .venv
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
VER = "2026.7.7"
NAME = "PinkRobinEncoder"

REQUIRED_BIN_FILES = ("ffmpeg.exe", "ffprobe.exe", "libvmaf.dll", "libsoxr.dll")


def run(cmd: list[str]) -> None:
    print("> " + " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(ROOT))


def check_windows() -> None:
    if platform.system() != "Windows":
        print("ERROR: Pink Robin Encoder builds Windows-only. Aborting.", file=sys.stderr)
        sys.exit(1)


def check_ffmpeg_bundle() -> None:
    missing = [f for f in REQUIRED_BIN_FILES if not (BIN / f).is_file()]
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

    # ---- Nuitka compile (standalone onedir: fast startup, easy bin/ bundling) ----
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--windows-console-mode=disable",
        f"--windows-icon-from-ico={SRC / 'icon.ico'}",
        f"--company-name=Pink Robin Encoder",
        f"--product-name={NAME}",
        f"--file-version={VER}",
        f"--product-version={VER}",
        f"--output-dir={DIST}",
        f"--include-data-files={SRC / 'icon.ico'}=icon.ico",
        f"--include-data-files={SRC / 'wgelogo.png'}=wgelogo.png",
        f"--include-data-files={SRC / 'vmaf_v0.6.1.json'}=vmaf_v0.6.1.json",
        "--include-package-data=scenedetect",
        "--nofollow-import-to=tests,pytest",
        "--assume-yes-for-downloads",
        "--show-progress",
        str(SRC / "app.py"),
    ]
    run(cmd)

    # Nuitka names the output folder app.dist - rename to PinkRobinEncoder.
    compiled = DIST / "app.dist"
    out_dir = DIST / NAME
    if out_dir.is_dir():
        shutil.rmtree(out_dir, ignore_errors=True)
    if not compiled.is_dir():
        print(f"ERROR: expected Nuitka output folder missing: {compiled}", file=sys.stderr)
        sys.exit(1)
    compiled.rename(out_dir)

    # Rename app.exe -> PinkRobinEncoder.exe
    src_exe = out_dir / "app.exe"
    dst_exe = out_dir / f"{NAME}.exe"
    if src_exe.is_file():
        src_exe.rename(dst_exe)
    elif not dst_exe.is_file():
        print(f"ERROR: expected executable missing in {out_dir}", file=sys.stderr)
        sys.exit(1)

    # ---- Assemble portable release ----
    shutil.copytree(BIN, out_dir / "bin", dirs_exist_ok=True)
    for item in ["licenses", "README.md", "CHANGELOG.md"]:
        src = ROOT / item
        if src.is_dir():
            shutil.copytree(src, out_dir / item, dirs_exist_ok=True)
        elif src.is_file():
            shutil.copy2(src, out_dir / item)

    # Smoke test: version flag must exit 0 (guards broken DLL bundling).
    ffmpeg = out_dir / "bin" / "ffmpeg.exe"
    subprocess.check_call([str(ffmpeg), "-version"], stdout=subprocess.DEVNULL)
    subprocess.check_call([str(out_dir / "bin" / "ffprobe.exe"), "-version"], stdout=subprocess.DEVNULL)
    print("Smoke test OK: bundled ffmpeg/ffprobe execute.")

    # Archive
    archive_path = DIST / f"{NAME}.{VER}.windows.7z"
    _7z = shutil.which("7z") or shutil.which("7za") or shutil.which("7zz") or r"C:\Program Files\7-Zip\7z.exe"
    subprocess.check_call([_7z, "a", "-mx=9", str(archive_path), out_dir.name], cwd=str(DIST))

    print(f"Release: {archive_path}")


if __name__ == "__main__":
    main()
