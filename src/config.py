# config.py
"""
Configuration Constants for Pink Robin Encoder

This module defines:
  - Application metadata (name, version, copyright)
  - Default paths and filenames for logs, temporary files, and app settings.
  - Highly detailed, source-aware preset definitions for software encoding.
  - Constants for specialized workflows like "The Heist" and "The Job".
  - GUI appearance and other system settings.
"""

import logging
from datetime import datetime

# --- Application Information ---
APP_NAME = "Pink Robin Encoder"
APP_VERSION = "2026.7.7"
COPYRIGHT_TEXT = f"© 2018 - {datetime.now().year}"
UPDATE_URL = (
    "https://api.github.com/repos/benkhodabandeh/BKVideoEncoder/releases/latest"
)


# --- Quality Level Configuration ---
class Quality:
    """Encapsulates quality level settings."""

    LEVELS = ["Lean", "Standard", "Prime Cut"]
    DEFAULT_LEVEL = "Standard"


# --- UI Theme & Appearance (MATERIAL DESIGN-INSPIRED THEME) ---
class Theme:
    """A professional, modern theme inspired by Google's Material Design."""

    # Color Palette
    PRIMARY = "#DAB45B"  # Bright Cyan (Primary Action)
    PRIMARY_HOVER = "#F0CB70"
    SECONDARY = "#3E5268"  # Blue Grey (Secondary Action / Tonal Buttons)
    SECONDARY_HOVER = "#4F6A86"

    BACKGROUND = "#0E1117"  # Near-black for the main window
    SURFACE = "#151A22"  # Dark grey for panels and cards
    SURFACE_LIGHT = "#202837"  # Lighter grey for interactive surfaces

    TEXT_PRIMARY = "#F5F6F8"  # Soft white for primary text
    TEXT_SECONDARY = "#A9B4C0"  # Muted grey for hints and secondary info
    TEXT_ON_PRIMARY = "#0E1117"  # White text for primary buttons

    ERROR = "#CF6679"  # Material-compliant error color for dark themes
    SUCCESS = "#66BB6A"  # A clear, standard green

    # Typography
    FONT_FAMILY = "Segoe UI"
    FONT_H1 = (FONT_FAMILY, 24, "bold")
    FONT_H2 = (FONT_FAMILY, 16, "bold")
    FONT_SUBTITLE = (FONT_FAMILY, 14, "bold")
    FONT_BODY = (FONT_FAMILY, 14)
    FONT_BUTTON = (FONT_FAMILY, 14, "bold")
    FONT_SMALL = (FONT_FAMILY, 12)
    FONT_MONO = "Consolas"

    # Dimensions
    CORNER_RADIUS = 12  # Softer, more modern corners
    PADDING = 15
    PADDING_SMALL = 8


# --- File/Folder Structure & System Settings ---
LOG_FOLDER_NAME = "BKVideoEncoder_Logs"
APP_SETTINGS_FILENAME = "wge_settings.json"
TEMP_DIR_BASE = f"{APP_NAME.replace(' ', '_')}_Temp"
LOGO_FILENAME = "wgelogo.png"
PASSLOG_FILENAME_BASE = "wge_passlog"


# --- Logging Configuration ---
LOG_LEVEL = logging.INFO
LOG_FILE_RETENTION_DAYS = 7
LOG_FORMAT = (
    "%(asctime)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s"
)
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# --- Source Material Options ---
SOURCE_MATERIAL_OPTIONS = {
    "clean": "Clean",
    "modern": "Modern",
    "film": "Vintage",
    "animation": "Animation",
}
DEFAULT_SOURCE_MATERIAL = "modern"
SOURCE_COMPLEXITY_THRESHOLDS = {"clean": 0.08, "film": 0.20}
SCENEDETECT_THRESHOLDS = {
    "clean": 26.0,
    "modern": 27.5,
    "film": 30.0,
    "animation": 26.0,
}


# --- FFmpeg Executable Names ---
FFMPEG_EXE_BASE = "ffmpeg"
FFPROBE_EXE_BASE = "ffprobe"


def get_platform_exe_name(base_name: str) -> str:
    """Returns the executable name with a .exe extension on Windows."""
    return f"{base_name}.exe"


FFMPEG_EXE = get_platform_exe_name(FFMPEG_EXE_BASE)
FFPROBE_EXE = get_platform_exe_name(FFPROBE_EXE_BASE)


# --- Metadata Configuration ---
METADATA_USER_FIELDS = ["title", "artist", "year", "syndicate"]

# --- Analysis and Still Settings ---
CROP_DETECT_DURATION = 10
CROP_DETECT_OPTIONS = [
    "None",
    "Auto-Detect",
    "1.33 (4:3)",
    "1.66 (Gunnar)",
    "1.77 (16:9)",
    "1.85 (Theatrical)",
    "2.00",
    "2.35 (Anamorphic)",
    "2.39 (Anamorphic)",
    "Custom",
]
DEFAULT_CROP_MODE = "Auto-Detect"
NUM_PREVIEW_STILLS = 10
PREVIEW_STILL_EXTENSION = ".jpg"
PREVIEW_STILL_QUALITY = 4
FINAL_STILL_EXTENSION = ".png"  # Final stills are PNG for lossless quality
NUM_PALETTE_COLORS = 8
PALETTE_HEIGHT_RATIO = 0.08


# --- VMAF Configuration ---
VMAF_MODEL_FILENAME = "vmaf_v0.6.1.json"
VMAF_NUM_THREADS = 0  # 0 means auto-detect
VMAF_SCORE_GUIDE = {
    (95, 101): ("✅", "Prime Cut! (Looks just like the original)", Theme.SUCCESS),
    (90, 95): ("👍", "Good Stuff (Hard to tell the difference)", "#82C04F"),
    (80, 90): ("👌", "Decent (A bit rough around the edges)", "#A5D6A7"),
    (60, 80): ("🤔", "Rough (Needs some work)", "#FFB74D"),
    (0, 60): ("❌", "Forget About It! (A real mess)", Theme.ERROR),
}


# --- System & Filter Settings ---
AUDIO_RESAMPLE_FILTER = "aresample=resampler=soxr:out_sample_rate=48000"
SCALING_FILTER_FLAGS = "flags=lanczos+accurate_rnd+full_chroma_int"
FFMPEG_PROGRESS_INTERVAL_SEC = 0.25  # Reduced update frequency for less noise
PERFORMANCE_LOG_FILENAME = "wge_perf.json"


# =================================================================================
# ADVANCED ENCODING PRESETS
# =================================================================================

STANDARD_PRESETS = {
    # 'The Finisher' - High-quality, compatible, CRF-based master. Reasonably fast.
    "THE_CAPO": {
        "name": "The Capo",
        "output_name": "Theatrical",
        "description": "CRF-based high-quality theatrical master. Compatible with all players. "
            "Uses slow preset for best quality.",
        "container": ".mp4",
        "video_codec": "libx264",
        "rate_control_mode": "crf",
        "target_resolution_name": "FHD",
        "audio_codec": "libfdk_aac",
        "audio_options": "-vbr 5",
        "crf_levels": {"Lean": 20, "Standard": 18, "Prime Cut": 16},
        "base_options": {
            "preset": "slow",
            "profile:v": "high",
            "level": "4.2",
            "tune": "film",
        },
        "pix_fmt_8bit": "yuv420p",
        "source_material_tuning": {
            "common": "keyint=360:min-keyint=1",
            "clean": "-x264-params {common}:bframes=8:ref=8:aq-mode=1:psy-rd=0.8:0.1:deblock=-1,-1:"
                "mbtree=1:qcomp=0.9:merange=48",
            "modern": "-x264-params {common}:bframes=8:ref=8:aq-mode=1:aq-strength=1.1:psy-rd=1.0:"
                "0.15:deblock=-1,-1:mbtree=1:qcomp=0.9:merange=48",
            "film": "-x264-params {common}:bframes=8:ref=8:aq-mode=1:aq-strength=1.2:psy-rd=1.1:"
                "0.2:no-deblock=1:mbtree=1:qcomp=0.9:merange=48",
            "animation": "-x264-params {common}:bframes=10:ref=10:deblock=1,1:psy-rd=0.4:0.0:"
                "aq-mode=1:aq-strength=0.7:mbtree=1:qcomp=0.9:merange=48",
        },
    },
    # 'The Archivist' - Pushes x264 to its absolute limits for maximum quality/bitrate. VERY SLOW.
    "THE_SOLDIER": {
        "name": "The Soldier",
        "output_name": "Web.x264",
        "description": "2-pass ABR web encode with predictable size and quality. Pushes x264 to "
            "its limits for maximum quality/bitrate. VERY SLOW.",
        "container": ".mp4",
        "video_codec": "libx264",
        "rate_control_mode": "2pass_abr",
        "video_kbps_levels": {"Lean": 2500, "Standard": 3500, "Prime Cut": 5000},
        "bufsize_kb_multiplier": 2.0,
        "target_resolution_name": "FHD",
        "audio_codec": "libfdk_aac",
        "audio_options": "-vbr 4",
        "base_options": {"preset": "veryslow", "profile:v": "high"},
        "pix_fmt_8bit": "yuv420p",
        "size_denoise_filter": "nlmeans=s=1:p=3:r=5",
        "size_sharpen_filter": "cas=strength=0.1",
        "denoise_filter": "nlmeans=s=1:p=3:r=5",
        "sharpen_filter": "cas=strength=0.1",
        "source_material_tuning": {
            "common": "keyint=360:min-keyint=1:subme=11:merange=48:trellis=2:b-adapt=2:bframes=16:"
                "ref=16:rc-lookahead=60:qcomp=0.9:mbtree=1",
            "clean": "-tune fastdecode -x264-params {common}:aq-mode=3:psy-rd=1.0:0.15:"
                "deblock=-1,-1",
            "modern": "-tune fastdecode -x264-params {common}:aq-mode=3:aq-strength=1.1:psy-rd=1.0:"
                "0.15:deblock=-1,-1",
            "film": "-tune grain -x264-params {common}:aq-mode=3:aq-strength=1.3:psy-rd=1.2:0.2:"
                "no-deblock=1:ipratio=1.1",
            "animation": "-tune animation -x264-params {common}:aq-mode=2:deblock=1,1:psy-rd=0.4:"
                "0.0:aq-strength=0.7",
        },
    },
    # 'The Phantom' - Pushes x265 to its limits for maximum 10-bit quality/bitrate. VERY SLOW.
    "THE_GHOST": {
        "name": "The Ghost",
        "output_name": "Web.x265",
        "description": "Pushes x265 to its limits for maximum 10-bit quality/bitrate. VERY SLOW.",
        "container": ".mp4",
        "video_codec": "libx265",
        "rate_control_mode": "2pass_abr",
        "video_kbps_levels": {"Lean": 2500, "Standard": 3500, "Prime Cut": 5000},
        "vbv_bufsize_multiplier": 2.0,
        "target_resolution_name": "UHD",
        "audio_codec": "libfdk_aac",
        "audio_options": "-vbr 4",
        "base_options": {"preset": "slow", "threads": "0"},
        "pix_fmt_10bit": "yuv420p10le",
        "size_denoise_filter": "nlmeans=s=1:p=3:r=5",
        "size_sharpen_filter": "cas.strength=0.1",
        "denoise_filter": "nlmeans=s=1:p=3:r=5",
        "sharpen_filter": "cas.strength=0.1",
        "source_material_tuning": {
            # Re-tuned for stability and quality. Enabled slow-firstpass.
            "common_x265_params": "rd=4:rdoq-level=2:aq-mode=3:b-adapt=2:rc-lookahead=80:subme=5:"
                "keyint=360:slow-firstpass=1",
            "clean": "-tune fastdecode -x265-params {common}:psy-rd=1.5:psy-rdoq=1.0",
            "modern": "-tune fastdecode -x265-params {common}:psy-rd=2.0:psy-rdoq=1.5:"
                "aq-strength=1.1",
            "film": "-tune grain -x265-params {common}:psy-rd=2.0:psy-rdoq=1.0:aq-strength=1.2:"
                "deblock=-1,-1",
            "animation": "-tune animation -x265-params {common}:bframes=12:deblock=1,1:psy-rd=0.4:"
                "aq-strength=0.7",
        },
    },
}

# --- Fast Encoding Presets ---
FAST_PRESETS = {
    # CRF-based for fast, high-quality x264 encodes.
    "THE_HITMAN": {
        "name": "The Hitman",
        "output_name": "Fast.x264",
        "description": "CRF-based fast, high-quality x264 encode. Fast preset for quick exports.",
        "container": ".mp4",
        "video_codec": "libx264",
        "rate_control_mode": "crf",
        "target_resolution_name": "FHD",
        "audio_codec": "libfdk_aac",
        "audio_options": "-vbr 5",
        "crf_levels": {"Lean": 23, "Standard": 21, "Prime Cut": 19},
        "base_options": {
            "preset": "fast",
            "profile:v": "high",
            "level": "4.1",
            "tune": "fastdecode",
        },
        "pix_fmt_8bit": "yuv420p",
        "size_denoise_filter": "nlmeans=s=1:p=3:r=5",
        "size_sharpen_filter": "cas=strength=0.1",
        "source_material_tuning": {
            "common": "-x264-params keyint=360:min-keyint=1:bframes=3:ref=3:aq-mode=1:psy-rd=1.0:"
                "0.15:deblock=-1,-1:mbtree=1:qcomp=0.9:merange=48",
            "animation": "-x264-params keyint=360:min-keyint=1:bframes=6:ref=5:deblock=1,1:"
                "psy-rd=0.4:0.0:aq-mode=1:aq-strength=0.7:mbtree=1:qcomp=0.9:merange=48",
        },
    },
    # CRF-based for very fast, efficient 10-bit x265 encodes.
"THE_ROCKET": {
        "name": "The Rocket",
        "output_name": "Fast.x265",
        "description": "CRF-based very fast, efficient 10-bit x265 encode. Faster preset for "
            "efficient exports.",
        "container": ".mp4",
        "video_codec": "libx265",
        "rate_control_mode": "crf",
        "crf_levels": {"Lean": 25, "Standard": 23, "Prime Cut": 21},
        "target_resolution_name": "UHD",
        "audio_codec": "libfdk_aac",
        "audio_options": "-vbr 4",
        "base_options": {"preset": "faster", "tune": "fastdecode", "threads": "0"},
        "pix_fmt_10bit": "yuv420p10le",
        "size_denoise_filter": "nlmeans=s=1:p=3:r=5",
        "size_sharpen_filter": "cas.strength=0.1",
        "denoise_filter": "nlmeans=s=1:p=3:r=5",
        "sharpen_filter": "cas.strength=0.1",
        "source_material_tuning": {
            "common_x265_params": "rd=4:rdoq-level=1:aq-mode=3:qg-size=8:b-adapt=2:rc-lookahead=80:"
                "subme=5:keyint=360:hist-scenecut=1:scenecut-aware-qp=1:merange=64:aq-strength=1.2:"
                "slow-firstpass=0",
            "clean": "-x265-params {common}:psy-rd=1.2:psy-rdoq=1.0:ipratio=1.1",
            "modern": "-x265-params {common}:psy-rd=1.8:psy-rdoq=1.8:ipratio=1.1",
            "film": "-x265-params {common}:psy-rd=2.2:psy-rdoq=4.0:deblock=-2,-2:no-cutree=1:"
                "ipratio=1.1",
            "animation": "-x265-params {common}:bframes=10:deblock=1,1:psy-rd=0.4:aq-strength=0.7",
        },
    },
}

# --- Workflow Presets ---
WORKFLOW_PRESETS = {
    # CRF-based preset optimized for vertical social media (e.g., Instagram Reels).
"THE_HEIST": {
        "name": "The Heist",
        "output_name": "Social",
        "description": "CRF-based preset optimized for vertical social media (e.g., Instagram "
            "Reels). 1080p vertical output with slow preset for quality.",
        "container": ".mp4",
        "video_codec": "libx264",
        "rate_control_mode": "2pass_abr",
        "video_kbps_levels": {"Lean": 3500, "Standard": 6500, "Prime Cut": 10000},
        "bufsize_kb_multiplier": 2.0,
        "target_w_override": 1080,
        "pix_fmt_8bit": "yuv420p",
        "audio_codec": "libfdk_aac",
        "audio_options": "-b:a 192k",
        "base_options": {
            "preset": "slow",
            "profile:v": "high",
            "level": "4.2",
            "tune": "fastdecode",
        },
        "denoise_filter": "nlmeans=s=1:p=3:r=5",
        "sharpen_filter": "cas.strength=0.8",
        "source_material_tuning": {
            "common": "-x264-params bframes=3:b-adapt=2:ref=4:aq-mode=1:aq-strength=1.2:psy-rd=1.1:"
                "0.25:mbtree=1:qcomp=0.9:merange=48:keyint=360:min-keyint=1"
        },
    },
    # ABR-based preset for targeting a specific output file size.
"THE_JOB": {
        "name": "The Job",
        "output_name": "Target_MB",
        "description": "ABR-based preset for targeting a specific output file size. Exact "
            "target-size encodes with 2-pass ABR.",
        "container": ".mp4",
        "rate_control_mode": "2pass_abr",
        "default_target_mb": 199,
        "min_bitrate_kbps": 100,
        "max_bitrate_kbps": 50000,
        "target_resolution_name": "HD",
        "video_codec": "libx264",
        "base_options": {"preset": "slow", "tune": "fastdecode"},
        "pix_fmt_8bit": "yuv420p",
        "source_material_tuning": {"common": ""},
        "audio_codec": "libfdk_aac",
        "audio_options": "-b:a 128k",
        "audio_bitrate_kbps": 128,
        "size_denoise_filter": "nlmeans=s=1:p=3:r=5",
        "size_sharpen_filter": "cas.strength=0.1",
    },
}


# --- Audio Codec (Windows-only, libfdk_aac required) ---
# Since we ship a custom FFmpeg with libfdk-aac only, AUDIO_CODEC is always libfdk_aac
AUDIO_CODEC = "libfdk_aac"

# Map libfdk_aac VBR levels to native aac quality option syntax
_VBR_TO_QA = {"5": "2", "4": "1", "3": "1"}


def _translate_opts(opts: str) -> str:
    """Translate libfdk_aac VBR options to native aac quality options (if ever needed)."""
    import re

    opts = re.sub(
        r"-vbr\s+(\d)", lambda m: f"-q:a {_VBR_TO_QA.get(m.group(1), '2')}", opts
    )
    return opts


# Since AUDIO_CODEC is always libfdk_aac, no preset patching needed


# --- Resolution Definitions ---
RESOLUTIONS = {
    "HD": {"width": 1280, "height": 720},
    "FHD": {"width": 1920, "height": 1080},
    "UHD": {"width": 3840, "height": 2160},
    "FHD_PORTRAIT": {"width": 1080, "height": 1920},  # For vertical video
}


# --- Preset schema validation (stdlib, no extra dependency) ---
# Mirrors the contract in tests/test_config_presets.py so misconfiguration
# fails fast at startup/CI instead of mid-encode.
def validate_presets() -> None:
    """Validate every preset dict. Raises ValueError listing all problems."""
    problems: list = []
    seen: set = set()
    groups = (
        ("STANDARD", STANDARD_PRESETS),
        ("FAST", FAST_PRESETS),
        ("WORKFLOW", WORKFLOW_PRESETS),
    )
    for group_name, group in groups:
        for pid, preset in group.items():
            if pid in seen:
                problems.append(f"Duplicate preset id: {pid}")
            seen.add(pid)
            for key in ("name", "output_name", "description", "container",
                        "video_codec", "rate_control_mode", "audio_codec"):
                if not preset.get(key):
                    problems.append(f"{group_name}/{pid}: missing {key!r}")
            if preset.get("video_codec") not in ("libx264", "libx265"):
                problems.append(f"{group_name}/{pid}: unsupported video_codec")
            if preset.get("audio_codec") != "libfdk_aac":
                problems.append(f"{group_name}/{pid}: audio_codec must be libfdk_aac")
            mode = preset.get("rate_control_mode")
            if mode == "crf":
                if set(preset.get("crf_levels", {})) != set(Quality.LEVELS):
                    problems.append(f"{group_name}/{pid}: crf_levels must cover {Quality.LEVELS}")
            elif mode == "2pass_abr":
                if "video_kbps_levels" not in preset and pid != "THE_JOB":
                    problems.append(f"{group_name}/{pid}: 2pass_abr needs video_kbps_levels")
            else:
                problems.append(f"{group_name}/{pid}: unknown rate_control_mode {mode!r}")
            res = preset.get("target_resolution_name")
            if res is not None and res not in RESOLUTIONS:
                problems.append(f"{group_name}/{pid}: unknown resolution {res!r}")
    if AUDIO_CODEC != "libfdk_aac":
        problems.append("AUDIO_CODEC must be libfdk_aac (no fallback builds)")
    if problems:
        raise ValueError("Preset validation failed:\n- " + "\n- ".join(problems))
