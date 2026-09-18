param(
    [string]$Python = "py -3.11",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Write-Host "Creating Pink Robin Encoder Windows release (Nuitka)..." -ForegroundColor Cyan

if ($env:OS -ne "Windows_NT") {
    Write-Error "Pink Robin Encoder builds Windows-only. Aborting."
    exit 1
}

if (!(Test-Path ".venv")) {
    Invoke-Expression "$Python -m venv .venv"
}
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
python scripts\dev_check.py
python scripts\fetch_ffmpeg_bundle.py
if ($SkipTests) {
    python build.py --skip-tests
} else {
    python build.py
}

Write-Host "Build completed. Check dist/." -ForegroundColor Green
