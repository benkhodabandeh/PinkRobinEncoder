# ADR 0001 — No fallbacks: required dependencies, fail fast

Status: accepted.

## Context

The codebase historically probed for optional libraries at runtime
(`HAS_PILLOW`, `HAS_PYSCENEDETECT`, `libfdk_aac`-vs-`aac`) and silently
degraded. Degraded paths were untested, produced worse output, and hid
broken installs until mid-encode.

## Decision

Ship an all-in-one portable bundle with everything included; treat
Pillow, PySceneDetect, and libfdk-aac as REQUIRED. Missing pieces fail
fast at startup with a clear message instead of degrading.

## Consequences

- Simpler code: no `HAS_*` branches, one tested path.
- `scripts/build_ffmpeg_windows.sh` must provide libfdk-aac/soxr/vmaf;
  `tests/test_ffmpeg_usage_contract.py` guards the invariant.
- Users cannot run a partial install — acceptable for a portable release.
