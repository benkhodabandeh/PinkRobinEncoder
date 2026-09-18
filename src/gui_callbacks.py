# gui_callbacks.py
"""
Contains callback functions for all GUI events in Pink Robin Encoder.
These functions are triggered by user interactions (button clicks, etc.)
and are responsible for initiating application logic in response.
"""

import logging
import os
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

if TYPE_CHECKING:
    from app import App

import a11y
import config
import gui_panels
import gui_tasks
import gui_updaters
import ui_components

logger = logging.getLogger(__name__)


# --- Top Bar Callbacks ---


def load_video_callback(app: "App"):
    """Handles the 'Load Video' button click."""
    filepath = filedialog.askopenfilename(
        title="Select a video file",
        filetypes=(("Video Files", "*.mp4 *.mkv *.mov *.avi"), ("All files", "*.*")),
    )
    if not filepath:
        return
    app.reset_to_load_state(os.path.normpath(filepath))
    app._update_destination_label()
    app._start_processing_task(
        description=f"Loading {os.path.basename(filepath)}",
        task_func=gui_tasks.load_video_task,
        is_develop_task=True,
    )


def select_destination_callback(app: "App"):
    """Handles the 'Set Destination' button click."""
    initial_dir = (
        os.path.dirname(app.input_file_original)
        if app.input_file_original
        else os.path.expanduser("~")
    )
    dir_path = filedialog.askdirectory(
        title="Select Destination Folder", initialdir=initial_dir
    )
    if dir_path:
        app.destination_path = os.path.normpath(dir_path)
        app._update_destination_label()


def open_qc_tool_callback(app: "App"):
    """Opens the QC Tool window."""
    if app.qc_window is None or not app.qc_window.winfo_exists():
        from qc_tool import QCToolWindow

        app.qc_window = QCToolWindow(app)
        app.qc_window.focus()
    else:
        app.qc_window.lift()
        app.qc_window.focus()


# --- Settings Panel Callbacks ---


def metadata_entry_callback(app: "App", event: Any, field: str):
    """Updates metadata dictionary and refreshes UI estimates and state."""
    if isinstance(widget := event.widget, ctk.CTkEntry):
        app.metadata[field] = widget.get()
        getattr(app, "_request_estimate_update", app._update_estimates)()
        app._update_ui_state()


def preset_button_callback(app: "App", preset_id: str):
    """Handles clicks on any preset or workflow button."""
    is_standard = preset_id in config.STANDARD_PRESETS
    is_fast = preset_id in config.FAST_PRESETS
    target_set = app.selected_standard_presets
    if is_fast:
        target_set = app.selected_fast_presets
    elif not is_standard:
        target_set = app.selected_workflow_presets

    if preset_id in target_set:
        target_set.remove(preset_id)
        state = "deselected"
    else:
        target_set.add(preset_id)
        state = "selected"

    gui_updaters.update_preset_button_styles(app)
    app._update_ui_state()
    getattr(app, "_request_estimate_update", app._update_estimates)()
    preset_name = (
        config.STANDARD_PRESETS.get(preset_id)
        or config.FAST_PRESETS.get(preset_id)
        or config.WORKFLOW_PRESETS.get(preset_id, {})
    ).get("name", preset_id)
    a11y.announce(app, f"{preset_name} {state}.")


def toggle_mb_entry_callback(app: "App"):
    """Handles right-click on the 'MB' button to set a new target size."""
    if not app.is_video_loaded:
        return
    current_val = app.target_mb_var.get()
    new_val = ui_components.InputDialog.get_input(
        app, "Target Size", "Enter new target size in MB:", initial_value=current_val
    )
    if new_val is not None:
        import validators

        clean_mb, err = validators.validate_target_mb(new_val)
        if err and clean_mb == config.WORKFLOW_PRESETS["THE_JOB"]["default_target_mb"]:
            app._show_error("Invalid Input", f"'{new_val}' is not valid. {err}")
            return
        app.target_mb_var.set(str(int(clean_mb)))
        gui_updaters.update_mb_button_display(app)
        if err:  # clamped to a sane value: inform, don't block
            app._show_warning("Target Size Adjusted", err)
        if "THE_JOB" in app.selected_workflow_presets:
            getattr(app, "_request_estimate_update", app._update_estimates)()


def source_material_callback(app: "App", source_key: str):
    app.source_material_var.set(source_key)
    gui_updaters.update_source_slider(app)
    getattr(app, "_request_estimate_update", app._update_estimates)()


def quality_slider_callback(app: "App", level_index: int):
    level_key = config.Quality.LEVELS[level_index]
    if level_key in config.Quality.LEVELS:
        app.quality_level_var.set(level_key)
        gui_updaters.update_quality_slider(app)
        getattr(app, "_request_estimate_update", app._update_estimates)()


def crop_mode_callback(app: "App", choice: str):
    """Handles selection from the crop mode dropdown, showing/hiding the custom entry."""
    logger.info(f"Crop mode changed to: {choice}")
    if custom_entry := app._get_widget("custom_crop_entry"):
        if choice == "Custom":
            custom_entry.pack(fill="x", pady=(8, 0))
        else:
            custom_entry.pack_forget()
    getattr(app, "_request_estimate_update", app._update_estimates)()
    getattr(
        app,
        "_request_preview_refresh",
        lambda path=None: gui_updaters.display_preview_image(app, path),
    )(
        app.preview_stills_paths[app.current_preview_index]
        if app.current_preview_index != -1
        else None
    )


def custom_crop_entry_callback(app: "App"):
    """Handles typing in the custom crop entry field."""
    getattr(app, "_request_estimate_update", app._update_estimates)()
    getattr(
        app,
        "_request_preview_refresh",
        lambda path=None: gui_updaters.display_preview_image(app, path),
    )(
        app.preview_stills_paths[app.current_preview_index]
        if app.current_preview_index != -1
        else None
    )


# --- Special Operations Callbacks ---


def mux_callback(app: "App"):
    """Handles the 'Mux Video/Audio' button click."""
    video_file = filedialog.askopenfilename(
        title="Select Video File",
        filetypes=(("Video Files", "*.mp4 *.mkv"), ("All files", "*.*")),
        parent=app,
    )
    if not video_file:
        return
    audio_file = filedialog.askopenfilename(
        title="Select Audio File",
        filetypes=(("Audio Files", "*.m4a *.aac *.ac3 *.wav"), ("All files", "*.*")),
        parent=app,
    )
    if not audio_file:
        return
    output_file = filedialog.asksaveasfilename(
        title="Save Muxed File",
        defaultextension=".mp4",
        filetypes=(("MP4 Container", "*.mp4"),),
        parent=app,
    )
    if not output_file:
        return

    app._start_processing_task(
        description="Muxing files...",
        task_func=gui_tasks.mux_task,
        args_for_task=(video_file, audio_file, output_file),
    )


def audio_only_callback(app: "App"):
    """Handles the 'Encode Audio Only' button click."""
    input_file = filedialog.askopenfilename(
        title="Select Input File", filetypes=(("All files", "*.*"),), parent=app
    )
    if not input_file:
        return
    output_file = filedialog.asksaveasfilename(
        title="Save Audio File",
        defaultextension=".m4a",
        filetypes=(("AAC Audio", "*.m4a"),),
        parent=app,
    )
    if not output_file:
        return

    app._start_processing_task(
        description="Encoding audio...",
        task_func=gui_tasks.audio_only_task,
        args_for_task=(input_file, output_file),
    )


# --- Main Control Callbacks ---


def add_to_queue_callback(app: "App"):
    """Creates a job from the current settings and adds it to the batch queue."""
    if not app.is_video_loaded:
        app._show_warning("Not Ready", "Please load a video file first.")
        return

    job_item = gui_tasks.create_job_item_from_current_state(app)
    if not job_item:
        app._show_error(
            "Preset Error", "Please select at least one preset or workflow."
        )
        return

    app.batch_queue.append(job_item)
    job_title = job_item["metadata"].get("title", "Untitled")
    logger.info(f"Added job '{job_title}' to queue. Queue size: {len(app.batch_queue)}")
    gui_panels.update_queue_display(app)

    app._reset_ui_for_new_job()
    getattr(app, "_show_toast", app._show_info)(
        "Job Queued",
        f"'{job_item['metadata'].get('title', 'Untitled')}' was added to The Plan.",
    )


def develop_callback(app: "App"):
    jobs_to_run = []

    if app.batch_queue:
        logger.info(f"Develop started with {len(app.batch_queue)} jobs in the queue.")
        jobs_to_run = list(app.batch_queue)
        app.batch_queue.clear()
        gui_panels.update_queue_display(app)
    elif app.is_video_loaded:
        logger.info(
            "Develop started with no jobs in queue. Creating a single job from UI."
        )
        if single_job := gui_tasks.create_job_item_from_current_state(app):
            jobs_to_run.append(single_job)
        else:
            app._show_error(
                "Not Ready", "Please select at least one preset before developing."
            )
            return
    else:
        app._show_error(
            "Not Ready", "Please load a video and select presets to develop."
        )
        return

    if not app._pre_flight_checks(jobs_to_run):
        app.batch_queue = jobs_to_run  # Restore queue if checks fail
        gui_panels.update_queue_display(app)
        return

    app.is_develop_run = True
    app._start_processing_task(
        description=f"Developing {len(jobs_to_run)} job(s)",
        task_func=gui_tasks.run_development_batch_task,
        args_for_task=(jobs_to_run,),
    )


def save_stills_callback(app: "App"):
    if not app.is_video_loaded:
        app._show_warning("Not Ready", "Please load a video file first.")
        return
    app._start_processing_task(
        description="Generating Final Stills",
        task_func=gui_tasks.generate_final_stills_task,
    )


def cancel_callback(app: "App"):
    if not app.is_processing or app.cancel_requested:
        return
    if not messagebox.askyesno(
        "Confirm Cancellation",
        "Are you sure you want to cancel the current process?",
        parent=app,
        icon="warning",
    ):
        return

    logger.info("Cancel button pressed. Requesting task cancellation.")
    app.cancel_requested = True
    if app.process_holder:
        for p in app.process_holder:
            try:
                if p and p.poll() is None:
                    getattr(
                        app,
                        "_terminate_process_tree",
                        lambda proc, description="process": proc.terminate(),
                    )(p, "active FFmpeg process")
                    logger.info(f"Cancellation requested for process PID {p.pid}")
            except Exception as e:
                logger.error(f"Error terminating process PID {p.pid}: {e}")

    if cancel_btn := app._get_widget("cancel_button"):
        cancel_btn.configure(state="disabled", text="CANCELLING...")


# --- Queue Management Callbacks ---


def remove_from_queue_callback(app: "App", job_id: str):
    app.batch_queue = [job for job in app.batch_queue if job.get("job_id") != job_id]
    logger.info(
        f"Removed job ID {job_id} from queue. Remaining: {len(app.batch_queue)}"
    )
    gui_panels.update_queue_display(app)
    app._update_ui_state()


def move_queue_item_callback(app: "App", job_id: str, direction: int):
    try:
        index = next(
            i for i, job in enumerate(app.batch_queue) if job.get("job_id") == job_id
        )
        new_index = index + direction
        if 0 <= new_index < len(app.batch_queue):
            app.batch_queue.insert(new_index, app.batch_queue.pop(index))
            gui_panels.update_queue_display(app)
    except StopIteration:
        logger.warning(f"Could not find job ID {job_id} to move it.")


def reopen_job_callback(app: "App", job_id: str):
    job_to_load = next(
        (job for job in app.batch_queue if job.get("job_id") == job_id), None
    )
    if not job_to_load:
        return
    if app.is_processing:
        app._show_warning(
            "Busy", "Cannot edit a queued job while processing is active."
        )
        return
    if app.is_video_loaded and app.input_file_original != job_to_load["input_file"]:
        if not messagebox.askyesno(
            "Load Different Video?",
            "This job is for a different video file. Loading it will replace "
            "the currently loaded video and its settings. Continue?",
            parent=app,
        ):
            return

    app.reset_to_load_state(job_to_load["input_file"])
    app.after(
        50, lambda: _load_job_data(app, job_to_load)
    )  # Defer to allow UI to reset
    remove_from_queue_callback(app, job_id)
    app._show_info(
        "Job Loaded",
        "The selected job's settings have been loaded for editing.\n"
        "It has been removed from The Plan.",
    )


def _load_job_data(app: "App", job_to_load: dict):
    """Helper to populate UI with job data after a short delay."""
    gui_updaters.handle_set_video_info(app, job_to_load["input_file_info"])
    gui_updaters.handle_set_metadata_from_dict(app, job_to_load["metadata"])

    app.source_material_var.set(job_to_load["source_material"])
    gui_updaters.update_source_slider(app)

    app.quality_level_var.set(job_to_load["quality_level"])
    gui_updaters.update_quality_slider(app)

    app.crop_mode_var.set(job_to_load["crop_mode"])
    app.custom_crop_var.set(job_to_load.get("custom_crop_string", ""))
    crop_mode_callback(app, app.crop_mode_var.get())

    app.is_downmix_enabled.set(job_to_load["is_downmix_enabled"])
    app.is_stills_enabled.set(job_to_load["is_stills_enabled"])
    app.target_mb_var.set(job_to_load["target_mb_val"])
    gui_updaters.update_mb_button_display(app)

    app.selected_standard_presets = job_to_load["selected_standard_presets"].copy()
    app.selected_fast_presets = job_to_load["selected_fast_presets"].copy()
    app.selected_workflow_presets = job_to_load["selected_workflow_presets"].copy()
    gui_updaters.update_preset_button_styles(app)

    getattr(app, "_request_estimate_update", app._update_estimates)()


# --- Preview Panel Callbacks ---


def navigate_preview_callback(app: "App", direction: int):
    """Cycles through the generated preview stills."""
    num_stills = len(app.preview_stills_paths)
    if num_stills <= 1:
        return
    app.current_preview_index = (app.current_preview_index + direction) % num_stills
    gui_updaters.display_preview_image(
        app, app.preview_stills_paths[app.current_preview_index]
    )
    gui_updaters.handle_status_update(
        app, f"Preview: {app.current_preview_index + 1} of {num_stills}"
    )


def reload_still_callback(app: "App"):
    """Generates a new random still to replace the currently viewed one."""
    if not app.is_video_loaded or app.current_preview_index < 0:
        return
    app._start_processing_task(
        description="Reloading preview still...",
        task_func=gui_tasks.reload_single_preview_task,
        args_for_task=(app.current_preview_index,),
        is_develop_task=False,
    )


def preview_resize_callback(app: "App", event: Any):
    """Handles the canvas resize event to redraw the preview image."""
    if app.resize_job_id:
        app.after_cancel(app.resize_job_id)
    app.resize_job_id = app.after(150, lambda: _perform_resize_actions(app))


def _perform_resize_actions(app: "App"):
    """Redraws the preview area after a resize event."""
    app.resize_job_id = None
    if not app.winfo_exists():
        return
    if app.current_preview_index != -1 and app.preview_stills_paths:
        gui_updaters.display_preview_image(
            app, app.preview_stills_paths[app.current_preview_index]
        )
    elif not app.is_video_loaded:
        gui_updaters.display_welcome_screen(app)
