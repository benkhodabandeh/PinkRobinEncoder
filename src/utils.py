# utils.py
"""
General utility functions for Pink Robin Encoder including path management,
process execution, filename parsing, and other helper tasks.
"""

import json
import logging
import os
import platform
import queue
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import config

logger = logging.getLogger(__name__)


# --- Process Safety Helpers ---
def _prepare_long_running_cmd(cmd: list[str]) -> list[str]:
    """Return a safer FFmpeg/FFprobe command.

    FFmpeg can read from stdin by default. In GUI apps that can cause rare hangs,
    especially when packaged on Windows. Add -nostdin automatically when the
    executable appears to be FFmpeg/FFprobe and the caller did not already add it.
    """
    prepared = list(cmd or [])
    if not prepared:
        return prepared
    exe_name = os.path.basename(str(prepared[0])).lower()
    if ("ffmpeg" in exe_name or "ffprobe" in exe_name) and "-nostdin" not in prepared:
        prepared.insert(1, "-nostdin")
    return prepared


# --- Path and Settings Management ---


def find_resource_path(resource_name: str) -> str | None:
    """Finds a resource file in bundled or local development environments."""
    search_paths = []
    if hasattr(sys, "_MEIPASS"):
        search_paths.append(os.path.join(sys._MEIPASS, "bin", resource_name))
        search_paths.append(os.path.join(sys._MEIPASS, resource_name))

    try:
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        project_root = os.path.dirname(script_dir)

        search_paths.append(os.path.join(project_root, "bin", resource_name))
        search_paths.append(os.path.join(project_root, "src", resource_name))
        search_paths.append(os.path.join(project_root, resource_name))
    except Exception:
        logger.debug("argv-based resource lookup unavailable; using PATH only.")

    for path in search_paths:
        if os.path.exists(path):
            logger.debug(f"Found '{resource_name}' at: {path}")
            return os.path.normpath(path)

    if path_in_sys := shutil.which(resource_name):
        logger.debug(f"Found '{resource_name}' in system PATH: {path_in_sys}")
        return os.path.normpath(path_in_sys)

    logger.warning(
        f"Resource '{resource_name}' could not be found in standard locations or system PATH."
    )
    return None


def get_executable_path(exe_base_name: str) -> str | None:
    """Caches and returns the full path to an executable to avoid repeated searches."""
    exe_name = config.get_platform_exe_name(exe_base_name)
    cache_key = f"_{exe_name}_path_cache"
    if hasattr(sys, cache_key) and getattr(sys, cache_key) is not None:
        return getattr(sys, cache_key)
    found_path = find_resource_path(exe_name)
    setattr(sys, cache_key, found_path)
    return found_path


def get_ffmpeg_path() -> str | None:
    """Gets the full path to the FFmpeg executable."""
    return get_executable_path(config.FFMPEG_EXE_BASE)


def get_ffprobe_path() -> str | None:
    """Gets the full path to the FFprobe executable."""
    return get_executable_path(config.FFPROBE_EXE_BASE)


def escape_ffmpeg_path_for_filter(path: str) -> str:
    """Correctly escapes a path for use inside an FFmpeg filter string."""
    if not isinstance(path, str):
        return ""
    if platform.system() == "Windows":
        return path.replace("\\", "\\\\").replace(":", "\\:")
    else:
        return path.replace("'", "'\\''")


def get_app_settings_path() -> str:
    """Returns the path to the application's persistent settings file."""
    documents_path = os.path.join(
        os.path.expanduser("~"), "Documents", config.LOG_FOLDER_NAME
    )
    os.makedirs(documents_path, exist_ok=True)
    return os.path.join(documents_path, config.APP_SETTINGS_FILENAME)


def load_app_settings() -> dict[str, Any]:
    """Loads application settings from a JSON file."""
    settings_path = get_app_settings_path()
    try:
        if os.path.exists(settings_path):
            with open(settings_path, encoding="utf-8") as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Could not load settings file at {settings_path}: {e}")
    return {}


def save_app_settings(settings: dict[str, Any]):
    """Saves application settings to a JSON file."""
    settings_path = get_app_settings_path()
    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
    except OSError as e:
        logger.error(f"Could not save settings file to {settings_path}: {e}")


# --- Filename and Path Generation ---


def sanitize_filename_component(
    name: str, allow_spaces: bool = True, fallback: str = "Untitled"
) -> str:
    """Removes illegal characters from a string for use in a filename or directory."""
    if not name or not isinstance(name, str):
        return fallback
    sanitized = name.strip()
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", sanitized)
    sanitized = re.sub(r"[\s_]+", " " if allow_spaces else "_", sanitized)
    return sanitized.strip() or fallback


def generate_output_path(
    base_dir: str, meta: dict[str, str], container: str
) -> tuple[str | None, str | None]:
    """
    Generates the output folder and full video filepath based on metadata.
    """
    try:
        title = sanitize_filename_component(meta.get("title"), True, "Video")
        artist = sanitize_filename_component(meta.get("artist"), True, "")
        year = meta.get("year", "")
        syndicate = meta.get("syndicate", "")

        folder_parts = [p for p in [title, artist, year] if p]
        if syndicate:
            folder_parts.append(f"©{syndicate}")

        folder_name = " ".join(folder_parts)
        sanitized_folder_name = sanitize_filename_component(
            folder_name, True, "Output_Folder"
        )
        output_folder_path = os.path.join(base_dir, sanitized_folder_name)

        res_name = meta.get("resolution_name", "")
        preset_name = meta.get("output_name", "")

        file_parts = [p for p in [title, artist, year] if p]
        base_filename_str = " ".join(file_parts)

        detail_parts = [p for p in [res_name, preset_name] if p]
        if detail_parts:
            base_filename_str += " - " + " - ".join(detail_parts)

        sanitized_filename = sanitize_filename_component(
            base_filename_str, True, "Output_Video"
        )
        final_video_filename = sanitized_filename + container
        full_video_filepath = os.path.join(output_folder_path, final_video_filename)

        os.makedirs(output_folder_path, exist_ok=True)

        return output_folder_path, full_video_filepath

    except (OSError, TypeError) as e:
        logger.error(f"Failed to generate output path in '{base_dir}': {e}")
        return None, None


def get_resolution_name(width: int, height: int) -> str:
    if not width or not height:
        return ""
    if width >= 3800:
        return "UHD"
    if width >= 1900:
        return "FHD"
    if width >= 1200:
        return "HD"
    return f"{height}p"


def generate_stills_path(base_dir: str, meta: dict[str, str]) -> str:
    title = sanitize_filename_component(meta.get("title"), True, "Video")
    artist = sanitize_filename_component(meta.get("artist"), True, "")
    year = meta.get("year", "")
    parts = [p for p in [title, artist, year] if p]
    parts.append("Stills")
    folder_name = " ".join(parts)
    sanitized_folder_name = sanitize_filename_component(
        folder_name, True, "Stills_Folder"
    )
    return os.path.join(base_dir, sanitized_folder_name)


def parse_filename_for_metadata(filepath: str) -> dict[str, str]:
    if not filepath:
        return {"title": "", "year": ""}
    filename = os.path.splitext(os.path.basename(filepath))[0]
    meta = {"title": "", "year": ""}
    year_match = re.search(r"[.(_\s](\d{4})[.)_\s]?", filename)
    title_candidate = filename
    if year_match:
        year = int(year_match.group(1))
        current_year = datetime.now().year
        if 1880 < year <= current_year + 5:
            meta["year"] = str(year)
            title_candidate = filename[: year_match.start()]
    tags_pattern = (
        r"(?i)[\s._-](1080p|720p|2160p|4k|uhd|fhd|hd|bluray|web-dl|webrip"
        r"|x264|x265|h265|hevc|aac|dts|ac3|5\.1|7\.1)[\s._-]"
    )
    title_candidate = re.sub(tags_pattern, " ", title_candidate, flags=re.VERBOSE)
    title = " ".join(title_candidate.replace(".", " ").replace("_", " ").split())
    meta["title"] = title.strip() or "Untitled"
    return meta


def dict_to_cmd_list(options: dict[str, str]) -> list[str]:
    cmd_list = []
    for key, value in options.items():
        cmd_list.extend([f"-{key}", str(value)])
    return cmd_list


def get_audio_bitrate_from_options(options_str: str, fallback_kbps: int) -> int:
    if not isinstance(options_str, str):
        return fallback_kbps
    cbr_match = re.search(r"-b:a\s+(\d+)k", options_str)
    if cbr_match:
        return int(cbr_match.group(1))
    vbr_match = re.search(r"-vbr\s+(\d)", options_str)
    if vbr_match:
        vbr_level = int(vbr_match.group(1))
        vbr_map = {1: 96, 2: 128, 3: 160, 4: 192, 5: 256}
        return vbr_map.get(vbr_level, fallback_kbps)
    return fallback_kbps


def _format_eta(seconds: float) -> str:
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "--:--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _parse_time_to_seconds(time_str: Any | None) -> float:
    if not time_str:
        return 0.0
    try:
        if isinstance(time_str, str) and ":" in time_str:
            parts = time_str.split(":")
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return float(time_str)
    except (ValueError, IndexError, TypeError):
        return 0.0


def _format_bytes(size_bytes: int) -> str:
    if size_bytes is None or size_bytes < 0:
        return "N/A"
    if size_bytes == 0:
        return "0 B"
    power = 1024
    n = 0
    power_labels = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size_bytes >= power and n < len(power_labels) - 1:
        size_bytes /= power
        n += 1
    return f"{size_bytes:.1f} {power_labels[n]}"


def get_aspect_aware_scale_filter(
    source_w: int, source_h: int, target_res_name: str, target_w_override: int = 0
) -> tuple[str, int, int]:
    if not all(isinstance(val, int) and val > 0 for val in [source_w, source_h]):
        return "", source_w, source_h
    if target_w_override > 0:
        target_w, target_h = (
            target_w_override,
            int(target_w_override / (source_w / source_h)),
        )
    else:
        target_res = config.RESOLUTIONS.get(target_res_name)
        if not target_res:
            return "", source_w, source_h
        target_w, target_h = target_res["width"], target_res["height"]
    if not target_w_override and (source_w <= target_w and source_h <= target_h):
        logger.info(
            f"Output resolution target ({target_res_name}) is not smaller "
            "than source. No scaling will be applied."
        )
        return "", source_w, source_h
    w_ratio, h_ratio = target_w / source_w, target_h / source_h
    if target_w_override > 0 or w_ratio < h_ratio:
        out_w, out_h = target_w, round(source_h * w_ratio / 4) * 4
    else:
        out_h, out_w = target_h, round(source_w * h_ratio / 4) * 4
    display_target = target_res_name or f"{target_w_override}px width"
    logger.info(
        f"Aspect-aware scale: {source_w}x{source_h} -> {out_w}x{out_h} (Target: {display_target})"
    )
    return f"scale={out_w}:{out_h}:{config.SCALING_FILTER_FLAGS}", out_w, out_h


def get_aspect_ratio_crop_filter(
    source_w: int, source_h: int, aspect_ratio_str: str
) -> tuple[str, int, int]:
    try:
        target_ar = float(aspect_ratio_str.split(" ")[0])
    except (ValueError, IndexError):
        return "", source_w, source_h
    source_ar = source_w / source_h
    if abs(source_ar - target_ar) < 0.01:
        return "", source_w, source_h
    if source_ar > target_ar:
        new_w, new_h, crop_x, crop_y = (
            int(source_h * target_ar),
            source_h,
            (source_w - int(source_h * target_ar)) // 2,
            0,
        )
    else:
        new_w, new_h, crop_x, crop_y = (
            source_w,
            int(source_w / target_ar),
            0,
            (source_h - int(source_w / target_ar)) // 2,
        )
    crop_filter = f"crop={new_w}:{new_h}:{crop_x}:{crop_y}"
    logger.info(f"Calculated crop for {aspect_ratio_str} AR: {crop_filter}")
    return crop_filter, new_w, new_h


def calculate_video_bitrate(
    pid: str,
    preset_config: dict,
    source_info: dict,
    job_item: dict,
    out_w: int,
    out_h: int,
) -> int:
    quality_level = job_item.get("quality_level", config.Quality.DEFAULT_LEVEL)
    if pid == "THE_JOB":
        try:
            target_size_mb = float(job_item["target_mb_val"])
        except (ValueError, TypeError):
            target_size_mb = config.WORKFLOW_PRESETS["THE_JOB"]["default_target_mb"]
        duration_s, audio_bitrate_kbps = (
            source_info.get("duration", 1),
            preset_config.get("audio_bitrate_kbps", 128),
        )
        target_bits, audio_bits = (
            target_size_mb * 1024 * 1024 * 8,
            audio_bitrate_kbps * 1000 * duration_s,
        )
        video_kbps = max(0, (target_bits - audio_bits)) / (duration_s * 1000)
        return int(
            max(
                preset_config.get("min_bitrate_kbps", 100),
                min(video_kbps, preset_config.get("max_bitrate_kbps", 50000)),
            )
        )

    # *** FIX: Use the correct key 'video_kbps_levels' instead of 'bitrate_levels_kbps' ***
    base_kbps = preset_config.get("video_kbps_levels", {}).get(quality_level, 2500)

    if pid == "THE_GHOST":
        # Scale bitrate based on resolution relative to UHD
        base_res_pixels = (
            config.RESOLUTIONS["UHD"]["width"] * config.RESOLUTIONS["UHD"]["height"]
        )
        output_pixels = out_w * out_h
        res_factor = output_pixels / base_res_pixels
        # Use a power curve (e.g., ^0.75) for more natural scaling
        return int(base_kbps * (res_factor**0.75))

    return int(base_kbps)


def run_quick_process(cmd: list[str], process_description: str) -> tuple[int, str, str]:
    """Runs a short-lived subprocess and captures its output."""
    cmd = _prepare_long_running_cmd(cmd)
    cmd_str = " ".join(shlex.quote(c) for c in cmd)
    logger.debug(f"Running quick process '{process_description}': {cmd_str}")
    try:
        startupinfo = None
        creationflags = 0
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )

        # cmd is an internally built arg list (fixed ffmpeg path + validated
        # options); shell is never used.
        process = subprocess.run(  # nosec B603 - internal argv, no shell  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        return process.returncode, process.stdout, process.stderr
    except FileNotFoundError:
        logger.error(f"{process_description} failed: Command '{cmd[0]}' not found.")
        return -1, "", f"Error: Command '{cmd[0]}' not found."
    except Exception as e:
        logger.error(f"An unexpected error in run_quick_process: {e}", exc_info=True)
        return -1, "", f"Python Exception: {e}"


def run_process(
    cmd: list[str],
    duration: float | None = None,
    total_frames: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    process_description: str = "FFmpeg Process",
    process_holder: list[subprocess.Popen] | None = None,
    cancel_flag_func: Callable[[], bool] | None = None,
    cwd: str | None = None,
) -> tuple[int, str, str]:
    cmd = _prepare_long_running_cmd(cmd)
    cmd_str, progress_cmd = " ".join(shlex.quote(c) for c in cmd), cmd
    logger.info(f"Running ({process_description}): {cmd_str}")
    if cwd:
        logger.info(f"Setting CWD for process: {cwd}")
    if "-progress" not in cmd:
        progress_cmd = cmd[:1] + ["-progress", "pipe:1"] + cmd[1:]

    start_time = time.monotonic()

    output_queue, process = queue.Queue(), None

    def reader_thread(stream, q):
        try:
            for line in iter(stream.readline, ""):
                q.put(line)
        except (OSError, ValueError):
            pass
        finally:
            if stream and not stream.closed:
                stream.close()
            q.put(None)

    try:
        startupinfo, creationflags = None, 0
        if platform.system() == "Windows":
            startupinfo, creationflags = (
                subprocess.STARTUPINFO(),
                subprocess.CREATE_NO_WINDOW,
            )
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        # progress_cmd is derived from the internally built cmd list
        # (fixed ffmpeg path + validated options); shell is never used.
        process = subprocess.Popen(  # nosec B603 - internal argv, no shell  # noqa: S603
            progress_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            creationflags=creationflags,
            cwd=cwd,
            bufsize=1,
        )
        if process_holder is not None:
            process_holder.append(process)

        stdout_thread = threading.Thread(
            target=reader_thread, args=(process.stdout, output_queue), daemon=True
        )
        stderr_thread = threading.Thread(
            target=reader_thread, args=(process.stderr, output_queue), daemon=True
        )
        stdout_thread.start()
        stderr_thread.start()

        full_stderr, progress_data, last_update_time, finished_streams = [], {}, 0, 0

        while finished_streams < 2:
            if cancel_flag_func and cancel_flag_func():
                if process.poll() is None:
                    logger.warning(
                        f"Cancellation received for '{process_description}'. Terminating..."
                    )
                    try:
                        if platform.system() == "Windows":
                            process.send_signal(signal.CTRL_BREAK_EVENT)
                        else:
                            process.terminate()
                    except Exception:
                        process.terminate()
                    break

            try:
                line = output_queue.get_nowait()
                if line is None:
                    finished_streams += 1
                    continue
                if "=" in line:
                    progress_data.update([line.strip().split("=", 1)])
                else:
                    full_stderr.append(line)
            except queue.Empty:
                pass
            current_time = time.monotonic()
            if progress_callback and (
                current_time - last_update_time > config.FFMPEG_PROGRESS_INTERVAL_SEC
            ):
                last_update_time = current_time

                try:
                    frame = int(progress_data.get("frame", 0))
                except (ValueError, TypeError):
                    frame = 0

                if "out_time_us" in progress_data:
                    out_time_s = (
                        _parse_time_to_seconds(progress_data.get("out_time_us"))
                        / 1_000_000.0
                    )
                else:
                    out_time_s = _parse_time_to_seconds(progress_data.get("out_time"))

                if (
                    frame == 0
                    and out_time_s > 0
                    and duration
                    and duration > 0
                    and total_frames
                    and total_frames > 0
                ):
                    frame = int(total_frames * (out_time_s / duration))

                progress_percent, progress_text = 0.0, "..."
                if total_frames and total_frames > 0:
                    progress_percent = (
                        min(100.0, (frame / total_frames) * 100) if frame > 0 else 0.0
                    )
                    progress_text = f"{frame}/{total_frames} ({progress_percent:.1f}%)"
                elif duration and duration > 0:
                    progress_percent = (
                        min(100.0, (out_time_s / duration) * 100)
                        if out_time_s > 0
                        else 0.0
                    )
                    progress_text = f"{progress_percent:.1f}%"

                try:
                    speed_val = float(
                        progress_data.get("speed", "0.0x").replace("x", "")
                    )
                except (ValueError, TypeError):
                    speed_val = 0.0

                eta = (
                    (duration - out_time_s) / speed_val
                    if speed_val > 0 and duration and out_time_s > 0
                    else 0
                )

                elapsed = current_time - start_time

                progress_callback(
                    {
                        "progress": progress_percent,
                        "progress_text": progress_text,
                        "eta_str": _format_eta(eta),
                        "speed": f"{speed_val:.2f}x",
                        "overall_progress": progress_percent,
                        "elapsed_str": _format_eta(elapsed),
                    }
                )

            time.sleep(0.01)

        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)
        while not output_queue.empty():
            line = output_queue.get_nowait()
            if line and "=" not in line:
                full_stderr.append(line)
        return_code = process.wait()
        stderr_str = "".join(full_stderr)
        if return_code != 0 and not (cancel_flag_func and cancel_flag_func()):
            logger.error(
                f"Process '{process_description}' failed with exit code "
                f"{return_code}. Stderr: {stderr_str.strip()}"
            )
        return return_code, "", stderr_str
    except Exception as e:
        logger.error(f"An unexpected error in run_process: {e}", exc_info=True)
        raise e
    finally:
        if process and process.poll() is None:
            try:
                process.kill()
                process.wait()
            except Exception:
                logger.debug("Force-kill during cleanup raced process exit.")
        if process_holder is not None and process in process_holder:
            try:
                process_holder.remove(process)
            except ValueError:
                pass


def create_temp_directory() -> str | None:
    try:
        base_temp_dir = os.path.join(tempfile.gettempdir(), config.TEMP_DIR_BASE)
        session_id = (
            f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
        )
        session_dir = os.path.join(base_temp_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)
        logger.info(f"Created temporary session directory: {session_dir}")
        return session_dir
    except Exception as e:
        logger.critical(f"Failed to create temporary directory: {e}", exc_info=True)
        return None


def cleanup_temp_directory(temp_dir: str | None):
    if temp_dir and os.path.isdir(temp_dir):
        logger.info(f"Cleaning up temporary directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)


def check_for_updates(
    current_version: str, settings: dict[str, Any]
) -> dict[str, Any] | None:
    from packaging.version import parse as parse_version

    now_iso, last_check = (
        datetime.now().isoformat(),
        settings.get("update_last_check", "2000-01-01"),
    )
    if (
        datetime.fromisoformat(now_iso) - datetime.fromisoformat(last_check)
    ) < timedelta(days=7):
        logger.info("Update check skipped, last check was less than 7 days ago.")
        return None
    settings["update_last_check"] = now_iso
    logger.info(f"Checking for updates. Current version: {current_version}")
    if not config.UPDATE_URL.startswith("https://"):
        logger.warning("Refusing update check: UPDATE_URL is not https.")
        save_app_settings(settings)
        return None
    try:
        # UPDATE_URL is a hardcoded https constant (config.py), asserted above.
        req = urllib.request.Request(  # nosec B310 - fixed https URL  # noqa: S310
            config.UPDATE_URL,
            headers={"User-Agent": f"{config.APP_NAME}/{current_version}"},
        )
        with urllib.request.urlopen(req, timeout=5) as response:  # nosec B310 - fixed https URL  # noqa: S310
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                latest_version = data.get("tag_name", "").lstrip("v")
                data["download_url"] = data.get("html_url", "")
                if latest_version:
                    skipped_version = settings.get("update_skipped_version", "")
                    if (
                        parse_version(latest_version) > parse_version(current_version)
                        and latest_version != skipped_version
                    ):
                        logger.info(f"Update found! New version: {latest_version}")
                        return data
                    else:
                        logger.info(
                            f"Application is up to date or version {latest_version} was skipped."
                        )
            else:
                logger.warning(
                    f"Update check failed with status code: {response.status}"
                )
    except urllib.error.URLError as e:
        logger.warning(
            f"Could not check for updates due to a network error. Details: {e.reason}"
        )
    except Exception as e:
        logger.warning(f"An unexpected error occurred during update check: {e}")
    save_app_settings(settings)
    return None


def get_perf_log_path() -> str:
    doc_path = os.path.join(
        os.path.expanduser("~"), "Documents", config.LOG_FOLDER_NAME
    )
    os.makedirs(doc_path, exist_ok=True)
    return os.path.join(doc_path, config.PERFORMANCE_LOG_FILENAME)


def read_perf_log() -> list[dict[str, Any]]:
    log_path = get_perf_log_path()
    if not os.path.exists(log_path):
        return []
    try:
        with open(log_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def write_perf_log(perf_data: dict[str, Any]):
    records = read_perf_log()
    records.append(perf_data)
    if len(records) > 100:
        records = records[-100:]
        logger.info(f"Performance log has been capped to {len(records)} entries.")
    try:
        with open(get_perf_log_path(), "w", encoding="utf-8") as f:
            json.dump(records, f, indent=4)
    except OSError as e:
        logger.error(f"Failed to write to performance log: {e}")


def get_time_estimate(job_item: dict[str, Any], out_w: int, out_h: int) -> float:
    records = read_perf_log()
    if not records:
        return 0.0
    duration, pixels = job_item["input_file_info"]["duration"], out_w * out_h
    preset_conf = job_item["preset_conf"]
    preset_id = job_item.get("preset_id")
    encoder_preset = preset_conf.get("base_options", {}).get("preset", "default")
    matches = []
    for rec in records:
        if (
            rec.get("preset_id") == preset_id
            and rec.get("encoder_preset") == encoder_preset
        ):
            diff = abs(rec.get("pixels", 0) - pixels)
            matches.append({"diff": diff, "record": rec})
    if not matches:
        logger.warning(
            f"No performance history found for preset '{preset_id}' with speed '{encoder_preset}'."
        )
        return 0.0
    matches.sort(key=lambda x: x["diff"])
    top_matches = matches[:5]
    average_time_per_second = sum(
        m["record"]["time_per_second"] for m in top_matches
    ) / len(top_matches)
    estimated_time = average_time_per_second * duration
    logger.info(
        f"Found {len(top_matches)} similar past encodes. Averaged estimate: {estimated_time:.1f}s"
    )
    return estimated_time
