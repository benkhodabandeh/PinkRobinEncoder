@ECHO OFF
ECHO.
ECHO --- Pink Robin Encoder Build (Nuitka, Windows-only) ---
ECHO.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\make_windows_release.ps1"
ECHO.
ECHO --- Done ---
PAUSE
