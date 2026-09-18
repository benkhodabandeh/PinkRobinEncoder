# encoding.py
"""
Handles the construction and execution of all FFmpeg encoding commands for
Pink Robin Encoder. This module consolidates logic for standard presets and
specialized workflows into a single, robust system.
"""

import os
import logging
import subprocess
import config
import utils
import shlex
import time
import re
from typing import Dict, Any, Callable, List, Tuple, Optional
from gui_support import OperationCancelledError

logger = logging.getLogger(__name__)


# --- Optional PySceneDetect Import - required for scene detection ---
from scenedetect import open_video, SceneManager, SceneList
from scenedetect.detectors import ContentDetector

HAS_PYSCENEDETECT = True
logger.info("PySceneDetect library found. Advanced scene detection enabled.")


def get_scenecut_qp_filepath(
    job: Dict[str, Any], threshold: float, cancel_flag_func: Callable[[], bool]
) -> Optional[str]:
    """
    Uses PySceneDetect to find scene changes and generates a qpfile for FFmpeg.
    Returns the path to the generated qpfile.
    """
    if not HAS_PYSCENEDETECT:
        return None

    video_path = job["input_file"]
    job_id = job["job_id"]
    temp_dir = job["temp_dir"]

    try:
        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=threshold))

        logger.info(
            f"PySceneDetect: Analyzing '{os.path.basename(video_path)}' with threshold {threshold}..."
        )

        scene_manager.detect_scenes(video=video)

        if cancel_flag_func():
            raise OperationCancelledError("Cancelled during scene detection.")

        scene_list: SceneList = scene_manager.get_scene_list()

        if not scene_list:
            logger.warning("PySceneDetect found no scenes.")
            return None

        qp_filepath = os.path.join(temp_dir, f"scenecuts_{job_id}.qp")
        logger.info(
            f"PySceneDetect: Found {len(scene_list)} scenes. Saving QP file to {qp_filepath}"
        )

        with open(qp_filepath, "w") as qp_file:
            for i, scene in enumerate(scene_list):
                start_frame = scene[0].get_frames()
                if start_frame > 0:
                    qp_file.write(f"{start_frame} I -1\n")

        return qp_filepath
    except OperationCancelledError:
        raise
    except Exception as e:
        logger.error(
            f"PySceneDetect failed for '{os.path.basename(video_path)}': {e}",
            exc_info=True,
        )
        return None


def build_video_filter_chain(
    job: Dict[str, Any], preset_conf: Dict[str, Any]
) -> Tuple[str, int, int]:
    info = job["input_file_info"]
    source_w, source_h = info["width"], info["height"]
    v_filters = []
    quality_level = job.get("quality_level", config.Quality.DEFAULT_LEVEL)

    crop_mode = job.get("crop_mode", "None")
    crop_str_from_job = ""
    if crop_mode == "Custom":
        crop_str_from_job = job.get("custom_crop_string", "")
    elif crop_mode == "Auto-Detect":
        crop_str_from_job = info.get("auto_crop_string", "")

    if crop_str_from_job:
        try:
            full_crop_str = (
                crop_str_from_job
                if "crop=" in crop_str_from_job
                else f"crop={crop_str_from_job}"
            )
            if re.match(r"^crop=\d+:\d+:\d+:\d+$", full_crop_str):
                parts = full_crop_str.replace("crop=", "").split(":")
                v_filters.append(full_crop_str)
                source_w, source_h = int(parts[0]), int(parts[1])
        except (ValueError, IndexError) as e:
            logger.warning(
                f"Invalid or incomplete custom crop string '{crop_str_from_job}', ignoring. Error: {e}"
            )

    elif crop_mode not in ["None", "Custom", "Auto-Detect"]:
        crop_filter, new_w, new_h = utils.get_aspect_ratio_crop_filter(
            source_w, source_h, crop_mode
        )
        if crop_filter:
            v_filters.append(crop_filter)
            source_w, source_h = new_w, new_h

    target_res_name = preset_conf.get("target_resolution_name")
    target_w_override = preset_conf.get("target_w_override", 0)
    target_res = config.RESOLUTIONS.get(target_res_name, {}) if target_res_name else {}
    target_w = target_w_override or target_res.get("width", source_w)
    target_h = target_res.get("height", source_h) if target_res else source_h

    is_downscaling = (source_w > target_w) or (source_h > target_h)

    if is_downscaling:
        if quality_level != "Prime Cut":
            if denoise_filter := preset_conf.get(
                "size_denoise_filter"
            ) or preset_conf.get("denoise_filter"):
                v_filters.append(denoise_filter)
                logger.info(
                    f"Applying denoiser before scaling (downscaling detected): {denoise_filter}"
                )
            if sharpen_filter := preset_conf.get(
                "size_sharpen_filter"
            ) or preset_conf.get("sharpen_filter"):
                v_filters.append(sharpen_filter)
                logger.info(
                    f"Applying sharpener before scaling (downscaling detected): {sharpen_filter}"
                )
    else:
        logger.info(
            "No downscaling detected; filters will be applied after scaling if needed."
        )

    scale_filter, out_w, out_h = utils.get_aspect_aware_scale_filter(
        source_w, source_h, target_res_name, target_w_override
    )
    if scale_filter:
        v_filters.append(scale_filter)
    else:
        out_w, out_h = source_w, source_h

    if not is_downscaling:
        if quality_level != "Prime Cut":
            if denoise_filter := preset_conf.get("denoise_filter"):
                v_filters.append(denoise_filter)
                logger.info(f"Applying denoiser after scaling: {denoise_filter}")
            if sharpen_filter := preset_conf.get("sharpen_filter"):
                v_filters.append(sharpen_filter)
                logger.info(f"Applying sharpener after scaling: {sharpen_filter}")
    else:
        logger.info(
            "'Prime Cut' quality or downscaling handled; no additional post-scale filters applied."
        )

    pix_fmt = ""
    if preset_conf["video_codec"] == "libx264":
        pix_fmt = preset_conf.get("pix_fmt_8bit", "yuv420p")
    else:
        pix_fmt = preset_conf.get("pix_fmt_10bit", "yuv420p10le")
    if pix_fmt:
        v_filters.append(f"format={pix_fmt}")

    return ",".join(filter(None, v_filters)), out_w, out_h


def _build_audio_filter_chain(job: Dict[str, Any]) -> str:
    if (
        source_sr := job["input_file_info"]
        .get("audio_stream", {})
        .get("sample_rate", 0)
    ):
        if int(source_sr) != 48000:
            logger.info(f"Resampling audio from {source_sr}Hz to 48kHz.")
            return config.AUDIO_RESAMPLE_FILTER
    return ""


def _build_pass_command(
    job: Dict,
    pass_num: int,
    total_passes: int,
    video_opts: List[str],
    audio_opts: List[str],
    vf_str: str,
    af_str: str,
) -> List[str]:
    is_final_pass = pass_num == total_passes
    info = job["input_file_info"]

    cmd = [utils.get_ffmpeg_path(), "-y", "-hide_banner", "-i", job["input_file"]]

    cmd.extend(video_opts)
    if vf_str:
        cmd.extend(["-vf", vf_str])

    output_opts = []

    if is_final_pass:
        if v_stream := info.get("video_stream", {}):
            for key, flag in [
                ("color_space", "-colorspace"),
                ("color_primaries", "-color_primaries"),
                ("color_trc", "-color_transfer"),
            ]:
                if (value := v_stream.get(key)) and value != "unknown":
                    output_opts.extend([flag, value])

        if info.get("has_audio"):
            output_opts.extend(["-map", "0:v:0", "-map", "0:a:0?"])
            if job["preset_id"] in ["THE_HEIST", "THE_JOB"]:
                logger.info(
                    f"{job['preset_id']} preset: Forcing single stereo audio track."
                )
                output_opts.extend(audio_opts)
                output_opts.extend(["-ac", "2"])
                if af_str:
                    output_opts.extend(["-af", af_str])
            else:
                output_opts.extend(audio_opts)
                if af_str:
                    output_opts.extend(["-af:a:0", af_str])
                if (
                    job.get("is_downmix_enabled")
                    and info.get("audio_stream", {}).get("channels", 0) > 2
                ):
                    acodec = job["preset_conf"].get("audio_codec") or config.AUDIO_CODEC
                    downmix_opts = [
                        "-map",
                        "0:a:0?",
                        "-c:a:1",
                        acodec,
                        "-b:a:1",
                        "192k",
                        "-ac:1",
                        "2",
                    ]
                    if af_str:
                        downmix_opts.extend(["-af:a:1", af_str])
                    output_opts.extend(downmix_opts)
        else:
            output_opts.append("-an")
    else:
        output_opts.append("-an")

    cmd.extend(output_opts)

    if is_final_pass:
        cmd.extend(["-map_metadata", "-1", "-map_chapters", "-1"])
        for key, value in job.get("metadata", {}).items():
            if value:
                cmd.extend(["-metadata", f"{key}={value}"])
        if job["output_file"].lower().endswith(".mp4"):
            cmd.extend(["-movflags", "+faststart"])
        cmd.append(job["output_file"])
    else:
        cmd.extend(["-f", "null"])
        cmd.append("NUL" if os.name == "nt" else "/dev/null")

    return cmd


def _execute_encode(
    job: Dict[str, Any],
    total_passes: int,
    video_opts_base: List[str],
    audio_opts: List[str],
    vf_str: str,
    af_str: str,
    progress_callback: Callable[[Dict[str, Any]], None],
    process_holder: List[subprocess.Popen],
    cancel_flag_func: Callable[[], bool],
) -> Tuple[bool, float]:
    info = job.get("input_file_info", {})
    if not info:
        logger.error("Job missing input_file_info")
        return False, 0.0
    
    start_time = time.monotonic()

    ffmpeg_exe_path = utils.get_ffmpeg_path()
    if not ffmpeg_exe_path:
        logger.error("FFmpeg executable not found")
        return False, 0.0
        
    ffmpeg_cwd = os.path.dirname(ffmpeg_exe_path) if ffmpeg_exe_path else None

    for pass_num in range(1, total_passes + 1):
        if cancel_flag_func():
            raise OperationCancelledError(f"Cancelled before Pass {pass_num}.")

        video_opts = list(video_opts_base)  # Create a copy to modify for each pass
        job_name = job.get("job_description_short", "Job")
        pass_str = f" (Pass {pass_num}/{total_passes})" if total_passes > 1 else ""
        desc = f"({job.get('job_num_str', '')}) {job_name}{pass_str}"

        if total_passes > 1:
            passlogfile = os.path.join(
                job.get("temp_dir", ""), f"{config.PASSLOG_FILENAME_BASE}_{job.get('job_id', '')}"
            )
            preset_conf = job.get("preset_conf", {})
            if preset_conf.get("video_codec") == "libx265":
                escaped_logfile = utils.escape_ffmpeg_path_for_filter(passlogfile)
                stats_param = f":pass={pass_num}:stats={escaped_logfile}"
                param_string_found = False
                for i, opt in enumerate(video_opts):
                    if opt == "-x265-params":
                        video_opts[i + 1] += stats_param
                        param_string_found = True
                        break
                if not param_string_found:
                    video_opts.extend(["-x265-params", stats_param.lstrip(":")])
            else:
                video_opts.extend(["-pass", str(pass_num), "-passlogfile", passlogfile])

        logger.info(f"Starting: {desc}")
        cmd = _build_pass_command(
            job, pass_num, total_passes, video_opts, audio_opts, vf_str, af_str
        )

        def pass_progress_wrapper(p_data: Dict[str, Any]) -> None:
            base_prog = (100.0 / total_passes) * (pass_num - 1)
            range_prog = 100.0 / total_passes

            try:
                current_pass_progress = float(p_data.get("progress", 0.0))
            except (ValueError, TypeError):
                current_pass_progress = 0.0

            p_data["overall_progress"] = base_prog + (
                current_pass_progress * (range_prog / 100.0)
            )
            p_data["job_description"] = desc
            if callable(progress_callback):
                progress_callback(p_data)

        try:
            ret_code, _, stderr = utils.run_process(
                cmd=cmd,
                duration=info.get("duration"),
                total_frames=info.get("nb_frames"),
                progress_callback=pass_progress_wrapper,
                process_description=desc,
                process_holder=process_holder,
                cancel_flag_func=cancel_flag_func,
                cwd=ffmpeg_cwd,
            )
        except Exception as e:
            logger.exception(f"Process execution failed for {desc}")
            return False, 0.0

        if ret_code != 0:
            if cancel_flag_func():
                raise OperationCancelledError(f"Cancelled during Pass {pass_num}.")
            logger.error(f"Job '{desc}' failed on Pass {pass_num}. Stderr: {stderr}")
            return False, 0.0
        logger.info(f"Successfully completed: {desc}")

    elapsed_time = time.monotonic() - start_time
    if total_passes > 1:
        passlogfile_base = os.path.join(
            job.get("temp_dir", ""), f"{config.PASSLOG_FILENAME_BASE}_{job.get('job_id', '')}"
        )
        for suffix in ["", ".mbtree", "-0.log", "-0.log.mbtree"]:
            if os.path.exists(f := f"{passlogfile_base}{suffix}"):
                try:
                    os.remove(f)
                except OSError as e:
                    logger.warning(f"Could not remove passlog file {f}: {e}")
    return True, elapsed_time


def run_job(
    job: Dict,
    progress_callback: Callable,
    process_holder: List,
    cancel_flag_func: Callable,
) -> Tuple[bool, float]:
    preset_id = job.get("preset_id")
    preset_conf = (
        config.STANDARD_PRESETS.get(preset_id)
        or config.WORKFLOW_PRESETS.get(preset_id)
        or config.FAST_PRESETS.get(preset_id)
    )
    if not preset_conf:
        logger.error(f"Invalid preset config for job: {preset_id}")
        return False, 0.0

    job["preset_conf"] = preset_conf
    job["job_description_short"] = preset_conf.get("output_name", "Untitled")
    rate_control_mode = preset_conf.get("rate_control_mode")
    logger.info(
        f"--- Preparing Job: {job['job_description_short']} | Mode: {rate_control_mode.upper()} ---"
    )

    vf_str, out_w, out_h = build_video_filter_chain(job, preset_conf)
    af_str = _build_audio_filter_chain(job)

    output_dir = job.get("destination_path") or os.path.dirname(job["input_file"])
    meta = job["metadata"].copy()
    meta["output_name"], meta["resolution_name"] = (
        job["job_description_short"],
        utils.get_resolution_name(out_w, out_h),
    )
    _, job["output_file"] = utils.generate_output_path(
        output_dir, meta, preset_conf.get("container", ".mp4")
    )
    if not job["output_file"]:
        logger.error("Failed to generate a valid output file path.")
        return False, 0.0

    qp_filepath = None
    if preset_conf["video_codec"] == "libx264":
        logger.info("x264 encode detected, checking for scene cuts with PySceneDetect.")
        qp_filepath = get_scenecut_qp_filepath(
            job,
            config.SCENEDETECT_THRESHOLDS.get(job.get("source_material", "modern")),
            cancel_flag_func,
        )

    video_opts = ["-c:v", preset_conf["video_codec"]]
    audio_opts = ["-c:a", preset_conf["audio_codec"]]

    if audio_options_str := preset_conf.get("audio_options"):
        audio_opts.extend(shlex.split(audio_options_str))
    if base_opts := preset_conf.get("base_options"):
        video_opts.extend(utils.dict_to_cmd_list(base_opts))

    tuning_params = preset_conf.get("source_material_tuning", {})
    source_material = job.get("source_material", config.DEFAULT_SOURCE_MATERIAL)
    tuning_str = tuning_params.get(source_material) or tuning_params.get("common")
    if (
        source_material == "animation" and not tuning_str
    ):  # Fallback for presets without explicit animation tuning
        tuning_str = tuning_params.get("common")

    x_params_str = ""
    if tuning_str:
        if "{common}" in tuning_str:
            common_params = (
                tuning_params.get("common_x265_params", "")
                if preset_conf["video_codec"] == "libx265"
                else tuning_params.get("common", "")
            )
            tuning_str = tuning_str.format(common=common_params)

        params_list = shlex.split(tuning_str)

        # This part is a bit tricky; we need to separate the tune from the params
        # This logic is simplified for clarity, assuming '-tune' is not inside the params string.
        # It's better to move `-tune` to base_options or handle it more robustly if needed.
        if len(params_list) > 1 and params_list[0] in ["-x264-params", "-x265-params"]:
            x_params_str = params_list[1]
        else:
            # Handle cases where tune is part of the string, e.g., "-tune grain -x264-params ..."
            if "-tune" in params_list:
                try:
                    tune_index = params_list.index("-tune")
                    video_opts.extend(params_list[tune_index : tune_index + 2])
                except (ValueError, IndexError):
                    pass  # Ignore if format is unexpected
            if "-x264-params" in params_list:
                try:
                    params_index = params_list.index("-x264-params")
                    x_params_str = params_list[params_index + 1]
                except (ValueError, IndexError):
                    pass
            elif "-x265-params" in params_list:
                try:
                    params_index = params_list.index("-x265-params")
                    x_params_str = params_list[params_index + 1]
                except (ValueError, IndexError):
                    pass

    total_passes = 1

    # --- Rate Control Logic ---
    if rate_control_mode == "crf":
        total_passes = 1
        quality_level = job.get("quality_level", config.Quality.DEFAULT_LEVEL)
        crf_value = preset_conf.get("crf_levels", {}).get(quality_level, 20)
        video_opts.extend(["-crf", str(crf_value)])
        logger.info(
            f"CRF encode selected for '{preset_id}'. Quality: '{quality_level}', CRF Value: {crf_value}"
        )

    elif rate_control_mode == "2pass_abr":
        total_passes = 2
        quality_level = job.get("quality_level")
        video_kbps = preset_conf.get("video_kbps_levels", {}).get(quality_level, 2500)
        video_opts.extend(["-b:v", f"{video_kbps}k"])

        vbv_mult = preset_conf.get("vbv_bufsize_multiplier") or preset_conf.get(
            "bufsize_kb_multiplier", 2.0
        )
        maxrate_k = int(video_kbps * 1.20)
        bufsize_k = int(maxrate_k * vbv_mult)

        if preset_conf["video_codec"] == "libx264":
            video_opts.extend(
                ["-maxrate", f"{maxrate_k}k", "-bufsize", f"{bufsize_k}k"]
            )
            logger.info(
                f"Applying VBV to x264: maxrate {maxrate_k}k, bufsize {bufsize_k}k"
            )
        elif preset_conf["video_codec"] == "libx265":
            # *** FIX: Append VBV settings to the existing x_params_str ***
            vbv_params = f":vbv-maxrate={maxrate_k}:vbv-bufsize={bufsize_k}"
            x_params_str += vbv_params
            logger.info(
                f"Applying VBV to x265: maxrate {maxrate_k}k, bufsize {bufsize_k}k"
            )

        logger.info(f"Calculated ABR for {preset_id}: {video_kbps}k")

    else:
        logger.error(
            f"Unknown rate control mode '{rate_control_mode}' for preset '{preset_id}'."
        )
        return False, 0.0

    # --- Finalize x-params string with QP file if available ---
    if qp_filepath:
        if "keyint" in x_params_str:
            params = x_params_str.split(":")
            params_filtered = [p for p in params if not p.startswith("keyint=")]
            x_params_str = ":".join(params_filtered)
            logger.info(
                "QP file in use: Removed conflicting 'keyint' from encoder parameters."
            )

        # *** FIX: Append QP file settings to the existing x_params_str ***
        escaped_qp_path = utils.escape_ffmpeg_path_for_filter(qp_filepath)
        x_params_str += f":qpfile={escaped_qp_path}:scenecut=0"

    if x_params_str:
        # *** FIX: Add the single, consolidated params string to the command ***
        param_key = (
            "-x265-params"
            if preset_conf["video_codec"] == "libx265"
            else "-x264-params"
        )
        video_opts.extend([param_key, x_params_str.lstrip(":")])

    success, elapsed_time = _execute_encode(
        job,
        total_passes,
        video_opts,
        audio_opts,
        vf_str,
        af_str,
        progress_callback,
        process_holder,
        cancel_flag_func,
    )

    if success:
        logger.info(
            f"--- Finished Job: {job['job_description_short']} ({elapsed_time:.2f}s) ---"
        )
    else:
        logger.error(f"--- Job Failed: {job['job_description_short']} ---")

    return success, elapsed_time
