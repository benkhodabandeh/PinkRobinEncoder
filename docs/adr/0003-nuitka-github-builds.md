# ADR 0003 — Nuitka builds, all artifacts from GitHub Actions

Status: accepted.

## Context

PyInstaller one-dir bundles were large, slow to start, and trivially
reversible. Developers also built FFmpeg locally with no provenance, so
releases were not reproducible.

## Decision

- Compile with Nuitka (`python build.py`, standalone onedir) for faster
  startup and harder reverse-engineering.
- Build BOTH the custom FFmpeg and the app on GitHub Actions
  (`.github/workflows/build-ffmpeg.yml`, `build-app.yml`); releases ship
  only CI-built artifacts plus an SBOM.
- `scripts/fetch_ffmpeg_bundle.py` downloads the CI artifact; local
  `scripts/build_ffmpeg_windows.sh` remains for developers without `gh`.

## Consequences

- Windows-only CI (one runner family, less matrix complexity).
- Nuitka first builds are slow (~10–20 min); acceptable for release cadence.
- `scripts/download_ffmpeg.py` (BtbN/brew fetcher) is superseded and will
  be removed once the first CI-built bundle is published.
