# analysis.py
"""
Functions for video analysis for Pink Robin Encoder including:
  - Extracting video information using ffprobe.
  - Detecting crop parameters using FFmpeg's cropdetect.
  - Generating still images in parallel.
  - Analyzing image colors in parallel for palette display.
"""

import concurrent.futures
import json
import logging
import math
import os
import random
import re
from collections.abc import Callable
from typing import Any, cast

# Third-party imports - Pillow required
from PIL import Image, ImageDraw
from PIL import __version__ as PILLOW_VERSION

# Local imports
import config
import utils

HAS_PILLOW = True
logger = logging.getLogger(__name__)
logger.debug(
    f"Pillow library found (v{PILLOW_VERSION}). Palette and image features enabled."
)


# --- Helper Functions for Info Formatting ---


def _get_chroma_subsampling(pix_fmt: str) -> str:
    if not pix_fmt or not isinstance(pix_fmt, str):
        return "N/A"
    pix_fmt_l = pix_fmt.lower()
    if "444" in pix_fmt_l:
        return "4:4:4"
    if "422" in pix_fmt_l:
        return "4:2:2"
    if "420" in pix_fmt_l:
        return "4:2:0"
    if "411" in pix_fmt_l:
        return "4:1:1"
    if "gray" in pix_fmt_l or "mono" in pix_fmt_l:
        return "Grayscale"
    return "Unknown"


def _get_audio_bit_depth(sample_fmt: str) -> str:
    if not sample_fmt or not isinstance(sample_fmt, str):
        return "N/A"
    if match := re.search(r"s(\d+)", sample_fmt):
        return f"{match.group(1)}-bit"
    if "flt" in sample_fmt:
        return "32-bit float"
    if "dbl" in sample_fmt:
        return "64-bit float"
    return ""


def _get_video_bit_depth(video_stream: dict[str, Any]) -> int:
    if (bps := video_stream.get("bits_per_raw_sample")) and str(bps).isdigit():
        return int(bps)
    pix_fmt = video_stream.get("pix_fmt", "").lower()
    if any(s in pix_fmt for s in ["10", "p10", "xv30"]):
        return 10
    if any(s in pix_fmt for s in ["12", "p12", "xv36"]):
        return 12
    if any(s in pix_fmt for s in ["16", "p16"]):
        return 16
    return 8


def get_source_details_text(info: dict[str, Any]) -> str:
    if not info:
        return "No video loaded."
    v_stream, a_stream = info.get("video_stream", {}), info.get("audio_stream", {})
    v_codec = v_stream.get("codec_name", "n/a").upper()
    pix_fmt, color_transfer = (
        v_stream.get("pix_fmt", ""),
        v_stream.get("color_transfer", ""),
    )
    # ffprobe reports PQ as "smpte2084" and HLG as "arib-std-b67" — match
    # those too, otherwise HDR sources are mislabeled SDR in the UI.
    hdr_markers = ("pq", "hlg", "smpte2084", "smpte2086", "arib-std-b67")
    hdr_info = "HDR" if any(m in color_transfer for m in hdr_markers) else "SDR"
    video_part = (
        f"{v_codec} / {_get_chroma_subsampling(pix_fmt)} / "
        f"{_get_video_bit_depth(v_stream)}-bit ({hdr_info})"
    )
    audio_part = "No Audio"
    if a_stream:
        channels, sample_rate = (
            a_stream.get("channels", 0),
            int(a_stream.get("sample_rate", 0)),
        )
        channel_layout = a_stream.get(
            "channel_layout", f"{channels}ch" if channels else ""
        ).title()
        sample_rate_str = (
            f"{sample_rate / 1000:.1f}kHz".replace(".0", "")
            if sample_rate > 0
            else "N/A"
        )
        audio_part = (
            f"{a_stream.get('codec_name', 'n/a').upper()} / "
            f"{sample_rate_str} / {channel_layout}"
        )
    return f"Video: {video_part}\nAudio: {audio_part}"


# --- Core Analysis Functions ---


def get_video_info(filepath: str) -> dict[str, Any] | None:
    if not (probe_path := utils.get_ffprobe_path()):
        logger.error("ffprobe executable not found.")
        return None
    cmd = [
        probe_path,
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-print_format",
        "json",
        filepath,
    ]
    logger.info(f"Probing video info for: {os.path.basename(filepath)}")
    ret_code, stdout, stderr = utils.run_quick_process(cmd, "FFprobe Info")
    if ret_code != 0:
        logger.error(
            f"ffprobe failed for '{os.path.basename(filepath)}'. "
            f"Exit: {ret_code}.\n{stderr.strip()}"
        )
        return None
    try:
        data = json.loads(stdout)
        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"), None
        )
        if not video_stream:
            logger.error(f"No video stream in '{os.path.basename(filepath)}'.")
            return None
        width, height = (
            int(video_stream.get("width", 0)),
            int(video_stream.get("height", 0)),
        )
        duration = utils._parse_time_to_seconds(
            data.get("format", {}).get("duration")
        ) or utils._parse_time_to_seconds(video_stream.get("duration"))
        nb_frames = int(video_stream.get("nb_frames", 0))
        num, den = map(int, video_stream.get("r_frame_rate", "0/1").split("/"))
        frame_rate = (num / den) if den > 0 else 0
        if nb_frames <= 0 and duration > 0 and frame_rate > 0:
            nb_frames = math.ceil(duration * frame_rate)
        if any(x <= 0 for x in [width, height, duration, frame_rate]):
            logger.error(f"Invalid video parameters in '{os.path.basename(filepath)}'.")
            return None
        audio_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None
        )
        result = {
            "duration": duration,
            "width": width,
            "height": height,
            "nb_frames": nb_frames,
            "bit_rate": int(data.get("format", {}).get("bit_rate", 0)),
            "frame_rate": frame_rate,
            "has_audio": bool(audio_stream),
            "video_stream": video_stream,
            "audio_stream": audio_stream,
        }
        result["source_details_text"] = get_source_details_text(result)
        logger.info(
            f"Video Info: Duration={duration:.2f}s, Res={width}x{height}, Frames={nb_frames}"
        )
        return result
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(
            f"Error processing ffprobe JSON for {os.path.basename(filepath)}: {e}",
            exc_info=True,
        )
        return None


def detect_crop(
    filepath: str,
    duration: float,
    source_w: int,
    source_h: int,
    detect_duration: int = config.CROP_DETECT_DURATION,
) -> str | None:
    if not (ffmpeg_path := utils.get_ffmpeg_path()):
        return None
    analyze_time = min(duration - 0.1, float(detect_duration))
    if analyze_time <= 0:
        logger.warning("Video too short for crop detection.")
        return ""
    cmd = [
        ffmpeg_path,
        "-nostdin",
        "-hide_banner",
        "-i",
        filepath,
        "-t",
        f"{analyze_time:.3f}",
        "-vf",
        "cropdetect",
        "-f",
        "null",
        "-",
    ]
    logger.info(f"Starting crop detection for '{os.path.basename(filepath)}'...")
    ret_code, _, stderr = utils.run_quick_process(cmd, "Crop Detection")
    if ret_code != 0:
        logger.error(f"Crop detection failed for '{os.path.basename(filepath)}'.")
        return None

    crop_counts: dict[str, int] = {}
    crop_regex = re.compile(r"crop=(\d+:\d+:\d+:\d+)")
    for line in stderr.strip().splitlines():
        if match := crop_regex.search(line):
            param = match.group(1)
            crop_counts[param] = crop_counts.get(param, 0) + 1

    if not crop_counts:
        logger.info("No crop parameters detected.")
        return ""
    most_common_param = max(crop_counts, key=lambda name: crop_counts[name])
    w_str, h_str, _, _ = most_common_param.split(":")
    if (
        source_w > 0
        and source_h > 0
        and int(w_str) == source_w
        and int(h_str) == source_h
    ):
        logger.info(
            f"Detected crop '{most_common_param}' matches source resolution; no crop needed."
        )
        return ""
    logger.info(f"Most stable crop detected: crop={most_common_param}")
    return f"crop={most_common_param}"


def analyze_source_complexity(info: dict[str, Any]) -> str:
    pixels, framerate, bitrate = (
        info.get("width", 0) * info.get("height", 0),
        info.get("frame_rate", 0),
        info.get("bit_rate", 0),
    )
    if not all([pixels, framerate, bitrate]):
        logger.warning("Could not determine source complexity, defaulting to 'modern'.")
        return "modern"
    bpp = bitrate / (pixels * framerate) if (pixels * framerate) > 0 else 0
    if bpp <= config.SOURCE_COMPLEXITY_THRESHOLDS["clean"]:
        suggestion = "clean"
    elif bpp >= config.SOURCE_COMPLEXITY_THRESHOLDS["film"]:
        suggestion = "film"
    else:
        suggestion = "modern"
    logger.info(
        f"Source complexity analyzed (BPP: {bpp:.4f}). Suggested material: '{suggestion}'."
    )
    return suggestion


def _get_random_timestamps(duration: float, num_stills: int) -> list[float]:
    if duration <= 1.0:
        return [duration / 2.0] if num_stills > 0 else []
    margin = min(1.0, duration * 0.05)
    min_time, max_time = margin, duration - margin
    if max_time <= min_time:
        min_time, max_time = 0.1, duration - 0.1 if duration > 0.1 else duration
    timestamps: set[float] = set()
    for _ in range(num_stills * 30):
        if len(timestamps) >= num_stills:
            break
        # Preview still timestamps are decorative, never cryptographic.
        timestamps.add(random.uniform(min_time, max_time))  # nosec B311  # noqa: S311
    return sorted(timestamps)


def _extract_still(
    input_filepath: str, timestamp: float, output_filepath: str, is_png: bool
) -> bool:
    if not (ffmpeg_path := utils.get_ffmpeg_path()):
        return False
    logger.debug(
        f"Extracting still at {timestamp:.3f}s to {os.path.basename(output_filepath)}"
    )
    try:
        os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    except OSError as e:
        logger.error(f"Cannot create directory for still '{output_filepath}': {e}")
        return False
    cmd = [
        ffmpeg_path,
        "-nostdin",
        "-hide_banner",
        "-ss",
        f"{timestamp:.6f}",
        "-i",
        input_filepath,
        "-vframes",
        "1",
    ]
    # For truly uncompressed, pixel-perfect stills, use the PNG codec
    # without compression flags.
    if is_png:
        cmd.extend(["-c:v", "png"])
    else:
        cmd.extend(
            [
                "-c:v",
                "mjpeg",
                "-q:v",
                str(config.PREVIEW_STILL_QUALITY),
                "-pix_fmt",
                "yuvj420p",
            ]
        )
    cmd.extend(["-y", output_filepath])
    ret_code, _, _ = utils.run_quick_process(cmd, "Still Extraction")
    return (
        ret_code == 0
        and os.path.exists(output_filepath)
        and os.path.getsize(output_filepath) > 100
    )


def generate_stills_parallel(
    input_filepath: str,
    duration: float,
    num_stills: int,
    output_dir: str,
    is_png: bool,
    prefix: str,
    cancel_flag_func: Callable[[], bool],
    output_filename_base: str | None = None,
    timestamps_to_use: list[float] | None = None,
) -> list[str]:
    """Generates multiple still images in parallel, with optional custom naming and timestamps."""
    timestamps = (
        timestamps_to_use
        if timestamps_to_use is not None
        else _get_random_timestamps(duration, num_stills)
    )
    if not timestamps:
        logger.error("Failed to generate timestamps for still extraction.")
        return []
    generated_files: list[str | None] = [None] * len(timestamps)
    file_ext = (
        config.FINAL_STILL_EXTENSION if is_png else config.PREVIEW_STILL_EXTENSION
    )
    logger.info(f"Generating {len(timestamps)} {prefix} stills in parallel...")
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(4, max(1, (os.cpu_count() or 2) // 2))
    ) as executor:
        future_to_index: dict[concurrent.futures.Future, tuple[int, str]] = {}
        for i, ts in enumerate(timestamps):
            if cancel_flag_func():
                break
            filename = (
                f"{output_filename_base}_{i + 1:02d}{file_ext}"
                if output_filename_base
                else f"{prefix}_still_{i:02d}{file_ext}"
            )
            output_path = os.path.join(output_dir, filename)
            future = executor.submit(
                _extract_still, input_filepath, ts, output_path, is_png
            )
            future_to_index[future] = (i, output_path)
        for future in concurrent.futures.as_completed(future_to_index):
            if cancel_flag_func():
                break
            index, path = future_to_index[future]
            try:
                if future.result():
                    generated_files[index] = path
            except Exception as exc:
                logger.error(
                    f"Still extraction for {os.path.basename(path)} generated an exception: {exc}"
                )
    successful_files = [p for p in generated_files if p]
    logger.info(
        f"Successfully generated {len(successful_files)}/{len(timestamps)} stills."
    )
    return successful_files


def generate_single_still(
    input_filepath: str, duration: float, index_to_replace: int, output_dir: str
) -> tuple[str, float] | None:
    """Generates a single replacement preview still, returning its path and timestamp."""
    timestamps = _get_random_timestamps(duration, 1)
    if not timestamps:
        return None
    timestamp = timestamps[0]
    output_filepath = os.path.join(
        output_dir,
        f"preview_still_{index_to_replace:02d}{config.PREVIEW_STILL_EXTENSION}",
    )
    logger.info(f"Reloading still index {index_to_replace} at {timestamp:.3f}s")
    if _extract_still(input_filepath, timestamp, output_filepath, is_png=False):
        return output_filepath, timestamp
    return None


def analyze_image_colors(image_path: str, num_colors: int) -> list[str] | None:
    """Analyzes the dominant colors of an image using Pillow."""
    if not HAS_PILLOW or not os.path.exists(image_path):
        return None
    try:
        with Image.open(image_path) as img:
            img_rgb = img.convert("RGB")
            img_rgb.thumbnail((200, 200), Image.Resampling.LANCZOS)
            quantized_img = img_rgb.quantize(
                colors=num_colors, method=Image.Quantize.FASTOCTREE
            )
            palette_rgb_flat, color_counts = (
                quantized_img.getpalette(),
                quantized_img.getcolors(),
            )
            if not color_counts or not palette_rgb_flat:
                return None
            color_counts.sort(reverse=True, key=lambda item: item[0])
            dominant_colors_hex = []
            for _, color_index in color_counts[:num_colors]:
                # P-mode getcolors() yields palette indices (ints); the stub
                # types them loosely, so narrow explicitly.
                idx = cast(int, color_index) * 3
                channels = [int(v) for v in palette_rgb_flat[idx : idx + 3]]
                if len(channels) != 3:
                    return None
                r, g, b = channels[0], channels[1], channels[2]
                dominant_colors_hex.append(f"#{r:02x}{g:02x}{b:02x}")
            return dominant_colors_hex
    except Exception as e:
        logger.error(
            f"Error analyzing image colors in '{os.path.basename(image_path)}': {e}",
            exc_info=False,
        )
        return None


def analyze_images_in_parallel(
    image_paths: list[str], cancel_flag_func: Callable
) -> dict[str, list[str]]:
    """Analyzes colors for multiple images in parallel."""
    colors_map: dict[str, list[str]] = {}
    if not HAS_PILLOW:
        return colors_map
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(4, max(1, (os.cpu_count() or 2) // 2))
    ) as executor:
        future_to_path = {
            executor.submit(analyze_image_colors, path, config.NUM_PALETTE_COLORS): path
            for path in image_paths
        }
        for future in concurrent.futures.as_completed(future_to_path):
            if cancel_flag_func():
                break
            path = future_to_path[future]
            try:
                if colors := future.result():
                    colors_map[path] = colors
            except Exception as e:
                logger.error(f"Color analysis failed for {os.path.basename(path)}: {e}")
    return colors_map


def add_palette_to_still(
    image_or_path: Any, colors: list[str]
) -> Image.Image | None:
    """Appends a palette bar to an image, handling both path and Image object inputs."""
    if not HAS_PILLOW or not colors:
        return None
    try:
        img = (
            Image.open(image_or_path)
            if isinstance(image_or_path, str)
            else image_or_path
        )
        img_rgb = img.convert("RGB")
        img_w, img_h = img_rgb.size
        palette_h = max(10, int(img_h * config.PALETTE_HEIGHT_RATIO))
        palette_img = Image.new("RGB", (img_w, palette_h))
        draw = ImageDraw.Draw(palette_img)
        if (num_colors := len(colors)) == 0:
            return img_rgb
        block_w = img_w / num_colors
        for i, color_hex in enumerate(colors):
            draw.rectangle(
                [i * block_w, 0, (i + 1) * block_w, palette_h],
                fill=color_hex,
                outline=color_hex,
            )
        combined_img = Image.new("RGB", (img_w, img_h + palette_h))
        combined_img.paste(img_rgb, (0, 0))
        combined_img.paste(palette_img, (0, img_h))
        return combined_img
    except Exception as e:
        logger.error(f"Error adding palette to still: {e}", exc_info=True)
        return None
