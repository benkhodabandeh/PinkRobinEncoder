# Changelog

## v2026.7.7 (2026-07-07)
- Cross-platform: builds and runs on Windows, Linux, macOS
- Cross-platform: auto-detects FFmpeg audio codec (falls back from libfdk_aac → aac)
- CI: automated builds for all three platforms via GitHub Actions
- CI: release archives (7z) per platform, attached to tagged releases
- Licensing: GPLv3 with full third-party acknowledgments
- Build: cross-platform build.py, single source of truth
- Polish: Linux/macOS font fallback, cleaner build scripts
- Version bump to 2026.7.7

## v2025.8.14 (2025-08-14)
- Initial public release
- Preset-based encoding (The Capo, The Soldier, The Ghost, The Hitman, The Rocket, The Heist, The Job)
- VMAF quality control tool
- Preview still generation with color palette analysis
- Scene detection via PySceneDetect or FFmpeg
- UPX-compressed standalone .exe
