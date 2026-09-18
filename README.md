<p align="center">
  <img src="https://raw.githubusercontent.com/benkhodabandeh/PinkRobinEncoder/main/.github/pinkrobinencoder.banner.png" alt="Pink Robin Encoder" width="760">
</p>

<p align="center">
  <strong>Cinema-grade FFmpeg encoding with a smooth workflow.</strong><br>
  Preset-driven x264/x265 encoding, batch development, scene-aware tuning, preview stills, crop tools, metadata, and VMAF QC.
</p>

<p align="center">
  <a href="https://github.com/benkhodabandeh/PinkRobinEncoder/releases"><img alt="Releases" src="https://img.shields.io/github/v/release/benkhodabandeh/PinkRobinEncoder?style=for-the-badge"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Windows 11" src="https://img.shields.io/badge/Windows_11-optimized-0078D4?style=for-the-badge&logo=windows11&logoColor=white">
  <img alt="License" src="https://img.shields.io/github/license/benkhodabandeh/PinkRobinEncoder?style=for-the-badge">
</p>

---

## Why Pink Robin Encoder

Pink Robin Encoder is a professional creator-focused encoder front-end. It removes repetitive command-line FFmpeg work while keeping the important creative controls visible: source type, target quality, crop, audio handling, metadata, batch queue, still generation, and VMAF comparison.

### Premium workflow highlights

| Area | What it does |
|---|---|
| Preset system | Curated workflows for theatrical masters, web encodes, HEVC compression, social vertical output, and target-size delivery. |
| Smooth UI | Background FFmpeg execution, debounced estimate/preview updates, bounded UI queue pumping, and non-blocking routine notifications. |
| Batch queue | Queue multiple jobs, reopen/edit queued jobs, reorder jobs, and process them as a development plan. |
| Video analysis | FFprobe metadata, source complexity suggestion, crop detection, scene detection, and preview stills. |
| Quality control | VMAF comparison tool for checking perceptual quality against the original. |
| Windows 11 polish | High-DPI awareness, bundled FFmpeg build support, refined dark theme, and professional icon/branding assets. |

---

## Quick start on Windows 11

### Portable release

1. Open the [Releases](https://github.com/benkhodabandeh/PinkRobinEncoder/releases) page.
2. Download the Windows archive.
3. Extract it to a normal user folder, for example `C:\Apps\PinkRobinEncoder`.
4. Run `PinkRobinEncoder\PinkRobinEncoder.exe`.

### Build from source

```powershell
git clone https://github.com/benkhodabandeh/PinkRobinEncoder.git
cd PinkRobinEncoder
py -3.12 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
python scripts\\fetch_ffmpeg_bundle.py
python build.py
```

> Builds are Nuitka-compiled, Windows-only. The custom FFmpeg bundle in
> `bin/` comes from `scripts/build_ffmpeg_windows.sh` (or the
> `ffmpeg-windows` CI artifact) — generic FFmpeg builds are not supported.

The portable build lands in `dist/`.

---

## Preset reference

| Preset | Codec | Mode | Best for |
|---|---|---|---|
| Studio H.264 | x264 | CRF | High-quality theatrical / compatibility master |
| Web H.264 | x264 | 2-pass ABR | Web distribution with predictable size and quality |
| Web H.265 | x265 | 2-pass ABR | Efficient HEVC compression |
| Express H.264 | x264 | CRF | Fast x264 export |
| Express H.265 | x265 | CRF | Fast HEVC export |
| Social Vertical | x264 | 2-pass ABR | Vertical 1080p / social delivery |
| Target Size | x264 | 2-pass ABR | Exact target-size encodes |

---

## Development quality checks

```powershell
pip install -r requirements-dev.txt
python scripts/dev_check.py
```

The development check compiles the source tree and optionally runs Ruff, Mypy, Bandit, and Pytest when installed.

---

## License and third-party components

The Pink Robin Encoder source code is licensed under the GNU GPL v3. Bundled FFmpeg builds and codec libraries are distributed under their own license terms. Review `LICENSE` before publishing binary releases.

---

## Author

Benyamin Khodabandeh — director, cinematographer, and creator of BAVE.
