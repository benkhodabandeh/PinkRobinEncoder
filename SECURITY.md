# Security Policy

## Supported versions

Security fixes should target the latest `main` branch and the newest public release.

## Reporting a vulnerability

Please do not open a public issue for security-sensitive reports. Use a private GitHub security advisory or contact the maintainer privately.

## Supply-chain expectations

Binary releases should verify and document:

- Exact FFmpeg source/build/version.
- SHA256 checksum for downloaded FFmpeg archives.
- Python dependency lock file or pinned release dependencies.
- Release checksums for every uploaded artifact.
- License notices for bundled components.

## Local processing model

BK Video Encoder is intended to process user-selected local media files. Avoid adding telemetry, upload, or network features unless they are explicitly documented and optional.
