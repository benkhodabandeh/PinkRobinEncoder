# gui_tasks.py
"""
Contains functions that run in background threads for the Pink Robin Encoder.
These tasks perform long-running operations like video analysis, encoding,
and still generation, queuing UI updates to the main thread.
"""

import copy
import logging
import os
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app import App

import analysis
import config
import encoding
import gui_updaters
import utils
from gui_support import OperationCancelledError

logger = logging.getLogger(__name__)

# Removed: if analysis.HAS_PILLOW: pass  # No longer needed - Pillow is required


def _safe_ui_update(app: "App", callback: Callable[[], Any]) -> bool:
    """Safely queue a UI update, returning True if successful."""
    try:
        if app.winfo_exists():
            app.ui_update_queue.put(callback)
            return True
    except Exception as e:
        logger.debug(f"Failed to queue UI update: {e}")
    return False


def _check_cancel(app: "App") -> bool:
    """Check if cancellation was requested, raise OperationCancelledError if so."""
    if app.cancel_requested:
        raise OperationCancelledError()
    return False


def load_video_task(app: "App") -> None:
    """Task to analyze a video file, generate previews, and update the UI."""
    if not (filepath := app.input_file_original):
        logger.warning("load_video_task called with no filepath")
        return

    def _update_progress(val: int) -> None:
        _safe_ui_update(app, lambda: gui_updaters.handle_simple_progress_update(app, val))

    _update_progress(10)

    try:
        info = analysis.get_video_info(filepath)
    except Exception as e:
        logger.exception(f"Video analysis failed for {filepath}")
        # Eager message (not a closure over `e`): the except variable is
        # deleted after the block, and mypy cannot infer such lambdas.
        err_text = f"Analysis failed: {e}"

        def _report() -> None:
            gui_updaters.handle_error_message(app, ("File Error", err_text))

        _safe_ui_update(app, _report)
        return

    if not info:
        _safe_ui_update(app, lambda: gui_updaters.handle_error_message(
            app, ("File Error", f"Could not read info from:\n{os.path.basename(filepath)}")
        ))
        return

    if _check_cancel(app):
        return

    _update_progress(25)

    try:
        info["auto_crop_string"] = (
            analysis.detect_crop(filepath, info["duration"], info["width"], info["height"])
            or ""
        )
    except Exception as e:
        logger.warning(f"Crop detection failed for {filepath}: {e}")
        info["auto_crop_string"] = ""

    if _check_cancel(app):
        return

    _update_progress(40)

    try:
        suggested_material = analysis.analyze_source_complexity(info)
        parsed_meta = utils.parse_filename_for_metadata(filepath)
    except Exception as e:
        logger.warning(f"Metadata parsing failed: {e}")
        suggested_material = config.DEFAULT_SOURCE_MATERIAL
        parsed_meta = {}

    _safe_ui_update(app, lambda: gui_updaters.handle_set_video_info(app, info))
    _safe_ui_update(app, lambda: gui_updaters.handle_set_source_material(app, suggested_material))
    _safe_ui_update(app, lambda: gui_updaters.handle_set_metadata_from_filename(app, parsed_meta))
    app.ui_update_queue.put(
        lambda: gui_updaters.handle_set_source_material(app, suggested_material)
    )
    app.ui_update_queue.put(
        lambda: gui_updaters.handle_set_metadata_from_filename(app, parsed_meta)
    )
    app.ui_update_queue.put(lambda: gui_updaters.handle_simple_progress_update(app, 60))
    app.preview_stills_timestamps = analysis._get_random_timestamps(
        info["duration"], config.NUM_PREVIEW_STILLS
    )
    preview_stills = analysis.generate_stills_parallel(
        filepath,
        info["duration"],
        config.NUM_PREVIEW_STILLS,
        app.app_temp_dir,
        is_png=False,
        prefix="preview",
        cancel_flag_func=lambda: app.cancel_requested,
        timestamps_to_use=app.preview_stills_timestamps,
    )
    if app.cancel_requested:
        raise OperationCancelledError()
    app.ui_update_queue.put(
        lambda: gui_updaters.handle_set_preview_stills(app, (preview_stills, {}))
    )
    app.ui_update_queue.put(lambda: gui_updaters.handle_simple_progress_update(app, 80))
    colors_map = analysis.analyze_images_in_parallel(
        preview_stills, lambda: app.cancel_requested
    )
    if app.cancel_requested:
        raise OperationCancelledError()
    app.ui_update_queue.put(
        lambda: gui_updaters.handle_update_all_preview_colors(app, colors_map)
    )
    app.ui_update_queue.put(
        lambda: gui_updaters.handle_simple_progress_update(app, 100)
    )


def reload_single_preview_task(app: "App", index_to_replace: int):
    """Task to generate a new preview still and replace an existing one."""
    if result := analysis.generate_single_still(
        app.input_file_original,
        app.input_file_info["duration"],
        index_to_replace,
        app.app_temp_dir,
    ):
        new_path, new_timestamp = result
        app.preview_stills_timestamps[index_to_replace] = new_timestamp
        new_colors = analysis.analyze_image_colors(new_path, config.NUM_PALETTE_COLORS)
        app.ui_update_queue.put(
            lambda: gui_updaters.handle_update_single_preview(
                app, (index_to_replace, new_path, new_colors)
            )
        )


def _generate_final_stills(app: "App", job_item: dict[str, Any]) -> int:
    """Generates final, uncompressed stills from the source using preview timestamps."""
    if not (timestamps := app.preview_stills_timestamps):
        logger.warning("No preview timestamps available to generate final stills.")
        return 0
    job_output_dir = job_item.get("destination_path") or os.path.dirname(
        job_item["input_file"]
    )
    output_folder, _ = utils.generate_output_path(
        job_output_dir, job_item["metadata"], ".mp4"
    )
    if not output_folder:
        return 0
    stills_dir = utils.generate_stills_path(output_folder, job_item["metadata"])
    os.makedirs(stills_dir, exist_ok=True)

    title = utils.sanitize_filename_component(
        job_item["metadata"].get("title"), True, "Video"
    )
    artist = utils.sanitize_filename_component(
        job_item["metadata"].get("artist"), True, ""
    )
    year = job_item["metadata"].get("year", "")
    parts = [p for p in [title, artist, year, "Stills"] if p]
    filename_base = utils.sanitize_filename_component(
        " ".join(parts), True, "Final_Stills"
    )

    final_stills = analysis.generate_stills_parallel(
        job_item["input_file"],
        job_item["input_file_info"]["duration"],
        len(timestamps),
        stills_dir,
        is_png=True,
        prefix="final",
        cancel_flag_func=lambda: app.cancel_requested,
        output_filename_base=filename_base,
        timestamps_to_use=timestamps,
    )
    return len(final_stills)


def generate_final_stills_task(app: "App"):
    """Task for the 'Save Stills' button."""
    if not (job_item := create_job_item_from_current_state(app)):
        app.ui_update_queue.put(
            lambda: app._show_error(
                "Stills Error", "Cannot save stills, no video loaded."
            )
        )
        return

    num_saved = _generate_final_stills(app, job_item)
    if app.cancel_requested:
        app.ui_update_queue.put(
            lambda: gui_updaters.handle_status_update(app, "Still saving cancelled.")
        )
        return

    if num_saved > 0:
        job_output_dir = job_item.get("destination_path") or os.path.dirname(
            job_item["input_file"]
        )
        output_folder, _ = utils.generate_output_path(
            job_output_dir, job_item["metadata"], ".mp4"
        )
        stills_folder = utils.generate_stills_path(output_folder, job_item["metadata"])
        app.ui_update_queue.put(
            lambda: app._show_info(
                "Stills Saved",
                f"{num_saved} stills have been saved to:\n\n{stills_folder}",
            )
        )
    else:
        app.ui_update_queue.put(
            lambda: app._show_error("Stills Error", "Failed to save any final stills.")
        )


def read_ui_metadata(app: "App") -> dict[str, str]:
    """Reads the current metadata directly from the GUI entry widgets."""
    current_metadata = {}
    if meta_entries := app.widget_refs.get("meta_entries"):
        for field, entry_ref in meta_entries.items():
            if entry := app._get_widget(entry_ref):
                current_metadata[field] = entry.get()
    return current_metadata


def create_job_item_from_current_state(app: "App") -> dict[str, Any] | None:
    """
    Creates a job item by reading DIRECTLY from the UI widgets,
    making the UI the single source of truth and preventing override bugs.
    """
    if not app.is_video_loaded:
        return None
    if (
        not app.selected_standard_presets
        and not app.selected_workflow_presets
        and not app.selected_fast_presets
    ):
        return None

    current_metadata = read_ui_metadata(app)

    job_id = str(uuid.uuid4())
    return {
        "job_id": job_id,
        "input_file": app.input_file_original,
        "input_file_info": copy.deepcopy(app.input_file_info),
        "destination_path": app.destination_path,
        "metadata": current_metadata,
        "selected_standard_presets": copy.deepcopy(app.selected_standard_presets),
        "selected_fast_presets": copy.deepcopy(app.selected_fast_presets),
        "selected_workflow_presets": copy.deepcopy(app.selected_workflow_presets),
        "source_material": app.source_material_var.get(),
        "quality_level": app.quality_level_var.get(),
        "crop_mode": app.crop_mode_var.get(),
        "custom_crop_string": app.custom_crop_var.get()
        if app.crop_mode_var.get() == "Custom"
        else "",
        "is_downmix_enabled": app.is_downmix_enabled.get(),
        "is_stills_enabled": app.is_stills_enabled.get(),
        "target_mb_val": app.target_mb_var.get(),
    }


def run_development_batch_task(app: "App", jobs_to_process: list[dict[str, Any]]):
    """The main background task, now with robust, detailed progress tracking."""
    start_time_batch = time.monotonic()

    if not jobs_to_process:
        logger.warning(
            "run_development_batch_task was called with an empty list of jobs."
        )
        return

    # --- Pre-calculate total estimated time for accurate ETA ---
    total_estimated_time_s = 0
    all_encodes = []
    for job_item in jobs_to_process:
        all_presets_for_job = (
            list(job_item["selected_standard_presets"])
            + list(job_item["selected_workflow_presets"])
            + list(job_item["selected_fast_presets"])
        )
        for preset_id in all_presets_for_job:
            # Create a temporary job copy to calculate estimates
            job_for_preset = copy.deepcopy(job_item)
            preset_conf = (
                config.STANDARD_PRESETS.get(preset_id)
                or config.WORKFLOW_PRESETS.get(preset_id)
                or config.FAST_PRESETS.get(preset_id)
            )
            if not preset_conf:
                continue

            job_for_preset["preset_conf"] = preset_conf
            _, out_w, out_h = encoding.build_video_filter_chain(
                job_for_preset, preset_conf
            )
            time_for_preset = utils.get_time_estimate(job_for_preset, out_w, out_h)

            job_for_preset["estimated_time"] = time_for_preset
            job_for_preset["preset_id"] = preset_id
            all_encodes.append(job_for_preset)
            total_estimated_time_s += time_for_preset

    total_encodes = len(all_encodes)
    time_elapsed_so_far = 0
    num_stills_generated, total_outputs = 0, 0
    final_output_folder = None
    def cancel_flag_func():
        return app.cancel_requested

    for i, job_item in enumerate(all_encodes):
        if cancel_flag_func():
            raise OperationCancelledError("Batch cancelled by user.")

        job_start_time = time.monotonic()
        job_desc = job_item["metadata"].get("title") or os.path.basename(
            job_item["input_file"]
        )
        preset_conf = job_item["preset_conf"]
        app.current_encoding_job_description = (
            f"Job {i + 1}/{total_encodes}: {job_desc}"
        )

        job_output_dir = job_item.get("destination_path") or os.path.dirname(
            job_item["input_file"]
        )
        output_folder_path, _ = utils.generate_output_path(
            job_output_dir, job_item["metadata"], ".mp4"
        )
        if not output_folder_path:
            raise RuntimeError(
                f"Could not determine output folder for job '{job_desc}'."
            )
        if not final_output_folder:
            final_output_folder = output_folder_path

        if i == 0 and job_item.get("is_stills_enabled"):
            num_stills_generated += _generate_final_stills(app, job_item)

        job_item["job_num_str"] = f"{i + 1}/{total_encodes}"
        job_item["temp_dir"] = app.app_temp_dir

        # The progress callback now has much more context.
        # Loop variables are bound as defaults: the callback outlives the
        # iteration via run_process, so late binding would mix job ETAs.
        def progress_callback(
            progress_data,
            _i=i,
            _job_item=job_item,
            _job_start_time=job_start_time,
            _elapsed_so_far=time_elapsed_so_far,
            _preset_conf=preset_conf,
        ):
            # --- Overall Batch Progress Calculation ---
            progress_from_completed = (_i / total_encodes) * 100.0
            progress_this_job = (
                progress_data.get("overall_progress", 0.0) / total_encodes
            )
            total_batch_progress = progress_from_completed + progress_this_job

            # --- ETA Calculation ---
            time_for_this_job = _job_item.get("estimated_time", 0)
            progress_of_this_job = progress_data.get("overall_progress", 0.0) / 100.0
            time_elapsed_this_job = time.monotonic() - _job_start_time

            if progress_of_this_job > 0.01:  # Use real data once available
                estimated_total_time_this_job = (
                    time_elapsed_this_job / progress_of_this_job
                )
            else:  # Fallback to pre-calculated estimate
                estimated_total_time_this_job = time_for_this_job

            time_remaining_this_job = (
                estimated_total_time_this_job - time_elapsed_this_job
            )

            time_for_future_jobs = (
                total_estimated_time_s - _elapsed_so_far - time_for_this_job
            )
            total_eta_s = time_remaining_this_job + time_for_future_jobs

            # Pass all the rich data to the UI updater
            progress_data["total_eta_str"] = utils._format_eta(total_eta_s)
            progress_data["job_description"] = _preset_conf.get("output_name", "Encode")
            progress_data["job_num_str"] = f"({_i + 1}/{total_encodes})"

            # Use the new overall progress for the progress bar
            progress_data["overall_progress"] = total_batch_progress

            app.ui_update_queue.put(
                lambda p=progress_data: gui_updaters.handle_encoding_progress_update(
                    app, p
                )
            )

        # Calculate out_w and out_h inside the main loop to ensure they are correct for each job
        _, out_w, out_h = encoding.build_video_filter_chain(job_item, preset_conf)

        success, elapsed_time_actual = encoding.run_job(
            job_item, progress_callback, app.process_holder, cancel_flag_func
        )

        time_elapsed_so_far += job_item.get("estimated_time", elapsed_time_actual)

        if not success:
            if cancel_flag_func():
                raise OperationCancelledError("Encode cancelled.")
            raise RuntimeError(
                f"Encoding failed for job '{job_desc}' with preset "
                f"'{job_item['preset_id']}'. Check logs for details."
            )
        else:
            total_outputs += 1
            utils.write_perf_log(
                {
                    "timestamp": datetime.now().isoformat(),
                    "preset_id": job_item["preset_id"],
                    "encoder_preset": preset_conf.get("base_options", {}).get("preset"),
                    "pixels": out_w * out_h,
                    "duration": job_item["input_file_info"]["duration"],
                    "elapsed_time": elapsed_time_actual,
                    "time_per_second": elapsed_time_actual
                    / job_item["input_file_info"]["duration"],
                }
            )

    total_elapsed_time = time.monotonic() - start_time_batch
    if not app.cancel_requested and final_output_folder:
        app.ui_update_queue.put(
            lambda: gui_updaters.show_task_complete_summary(
                app,
                total_encodes,
                total_outputs,
                num_stills_generated,
                total_elapsed_time,
                total_estimated_time_s,
                final_output_folder,
            )
        )


def mux_task(app: "App", video_file: str, audio_file: str, output_file: str):
    """Task to mux video and audio files."""
    ffmpeg_path = utils.get_ffmpeg_path()
    if not ffmpeg_path:
        app.ui_update_queue.put(
            lambda: gui_updaters.handle_error_message(
                app, ("Muxing Error", "FFmpeg not found.")
            )
        )
        return

    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        video_file,
        "-i",
        audio_file,
        "-c",
        "copy",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        output_file,
    ]

    ret_code, _, stderr = utils.run_process(
        cmd,
        process_description="Muxing",
        process_holder=app.process_holder,
        cancel_flag_func=lambda: app.cancel_requested,
    )

    if app.cancel_requested:
        return
    if ret_code == 0:
        app.ui_update_queue.put(
            lambda: app._show_info(
                "Muxing Complete", f"Successfully muxed files to:\n\n{output_file}"
            )
        )
    else:
        app.ui_update_queue.put(
            lambda: gui_updaters.handle_error_message(
                app, ("Muxing Error", f"Muxing failed. FFmpeg output:\n\n{stderr}")
            )
        )


def audio_only_task(app: "App", input_file: str, output_file: str):
    """Task to encode audio only."""
    ffmpeg_path = utils.get_ffmpeg_path()
    if not ffmpeg_path:
        app.ui_update_queue.put(
            lambda: gui_updaters.handle_error_message(
                app, ("Audio Encoding Error", "FFmpeg not found.")
            )
        )
        return

    codec = config.AUDIO_CODEC
    quality_opts = ["-vbr", "5"] if codec == "libfdk_aac" else ["-q:a", "2"]
    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        input_file,
        "-vn",
        "-c:a",
        codec,
        *quality_opts,
        output_file,
    ]

    ret_code, _, stderr = utils.run_process(
        cmd,
        process_description="Audio Encoding",
        process_holder=app.process_holder,
        cancel_flag_func=lambda: app.cancel_requested,
    )

    if app.cancel_requested:
        return
    if ret_code == 0:
        app.ui_update_queue.put(
            lambda: app._show_info(
                "Audio Encoding Complete",
                f"Successfully encoded audio to:\n\n{output_file}",
            )
        )
    else:
        app.ui_update_queue.put(
            lambda: gui_updaters.handle_error_message(
                app,
                (
                    "Audio Encoding Error",
                    f"Audio encoding failed. FFmpeg output:\n\n{stderr}",
                ),
            )
        )
