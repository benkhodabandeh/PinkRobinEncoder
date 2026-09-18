"""FFmpeg usage contract: the minimal custom build must cover src/ usage.

This test scans src/*.py as text and enforces two invariants:
1. REQUIRED tokens (codecs/filters/options the app depends on) are present.
2. BANNED tokens (libraries the minimal build deliberately excludes) are NOT
   referenced in any FFmpeg command context.

If a developer adds e.g. a `zscale` filter, this test fails with a message
telling them to update scripts/build_ffmpeg_windows.sh first.
"""

from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

# Tokens the custom build MUST provide (verified in build script step 8).
REQUIRED_TOKENS = [
    "libx264",
    "libx265",
    "libfdk_aac",
    "libvmaf",
    "resampler=soxr",
    "prores_ks",
    "nlmeans",
    "cas=",
    "cropdetect",
    "mjpeg",
]

# External libraries/filters deliberately excluded from the minimal build.
# NOTE: matched against FFmpeg-command context, not GUI font strings.
BANNED_TOKENS = [
    "libvpx",
    "libmp3lame",
    "libopus",
    "libvorbis",
    "libtheora",
    "-filter_complex ass=",
    "subtitles=",
    "drawtext=",
    "zscale=",
    "tonemap=",
    "libopenjpeg",
    "libwebp",
    "libbluray",
    "libdav1d",
    "libsvtav1",
    "librav1e",
]


def _src_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in SRC.glob("*.py"))


def test_required_ffmpeg_tokens_present():
    text = _src_text()
    for token in REQUIRED_TOKENS:
        assert token in text, (
            f"Required FFmpeg token {token!r} not found in src/ - "
            "did someone remove a feature the custom build relies on?"
        )


def test_banned_ffmpeg_tokens_absent():
    text = _src_text()
    for token in BANNED_TOKENS:
        assert token not in text, (
            f"Banned FFmpeg token {token!r} found in src/ - "
            "either remove the usage or update scripts/build_ffmpeg_windows.sh "
            "to bundle the library first."
        )


def test_qpfile_scenecut_path_uses_x264_only():
    # get_scenecut_qp_filepath is x264-only by design (qpfile + scenecut=0).
    text = (SRC / "encoding.py").read_text(encoding="utf-8")
    assert "qpfile=" in text
    assert "scenecut=0" in text


def test_audio_resample_filter_requires_soxr():
    import config

    assert "soxr" in config.AUDIO_RESAMPLE_FILTER
