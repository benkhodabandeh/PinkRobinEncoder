# ADR 0002 — Minimal tailored FFmpeg build

Status: accepted.

## Context

Prebuilt FFmpeg distributions bundle dozens of external libraries the app
never invokes (ass, zimg, openjpeg, vpx, opus, ...), inflating the portable
archive and the attack surface, and making behavior depend on a third party.

## Decision

Build FFmpeg from source in MSYS2 MinGW64 (`scripts/build_ffmpeg_windows.sh`)
with exactly the audited feature set:
encoders {libx264, libx265, libfdk-aac, png, mjpeg, prores_ks},
filters {crop, cropdetect, scale, format, setpts, nlmeans, cas, aresample, libvmaf},
resampler soxr, demuxers/muxers for mp4/mov/mkv/avi/wav/aac/ac3/image2/null,
protocols file+pipe only, no network, no ffplay, native aac encoder disabled
to enforce libfdk-aac.

## Consequences

- `tests/test_ffmpeg_usage_contract.py` fails if `src/` gains a dependency
  the build lacks — update both together.
- Build takes 5–15 min; CI caches nothing by design (reproducibility first).
- Step 8 of the script verifies the tailored feature set and fails the
  build on any MISSING requirement.
