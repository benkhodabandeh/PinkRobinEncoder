# app.py
"""
Main application class and entry point for the Pink Robin Encoder GUI.
Manages the main window, core application state, UI queue, and background
task execution, orchestrating all other modules.
"""

import copy
import logging
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import weakref
from collections.abc import Callable
from tkinter import messagebox
from typing import Any

import analysis

# Local module imports
import config
import customtkinter as ctk
import encoding
import gui_callbacks
import gui_panels
import gui_updaters
import logger_setup
import ui_components
import ui_runtime
import utils
from gui_support import OperationCancelledError

if analysis.HAS_PILLOW:
    from PIL import ImageTk

logger = logging.getLogger(__name__)


class App(ctk.CTk):
    """Main application class for the Pink Robin Encoder GUI."""

    def __init__(self):
        super().__init__()
        self._initialize_state()
        ui_runtime.install_runtime_guards(self)
        self._setup_logging()
        self._validate_configuration()
        self._check_essential_dependencies()
        self._load_assets()
        self._configure_window()
        self._create_layout()
        self._setup_keyboard_shortcuts()
        self.after(50, self._initialize_async)
        self.after(100, self._process_ui_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._update_ui_state()
        gui_updaters.update_source_slider(self)
        gui_updaters.update_quality_slider(self)
        gui_updaters.update_mb_button_display(self)
        logger.info(f"{config.APP_NAME} GUI Initialized.")

    def _initialize_state(self):
        """Initializes all state variables for the application."""
        self.input_file_original: str | None = None
        self.input_file_info: dict[str, Any] = {}
        self.destination_path: str | None = None
        self.app_temp_dir: str | None = None
        self.metadata: dict[str, str] = dict.fromkeys(config.METADATA_USER_FIELDS, "")
        self.is_video_loaded: bool = False
        self.selected_standard_presets: set = set()
        self.selected_fast_presets: set = set()
        self.selected_workflow_presets: set = set()
        self.source_material_var = ctk.StringVar(value=config.DEFAULT_SOURCE_MATERIAL)
        self.quality_level_var = ctk.StringVar(value=config.Quality.DEFAULT_LEVEL)
        self.crop_mode_var = ctk.StringVar(value=config.CROP_DETECT_OPTIONS[0])
        self.custom_crop_var = ctk.StringVar(value="")
        self.is_downmix_enabled = ctk.BooleanVar(value=False)
        self.is_stills_enabled = ctk.BooleanVar(value=True)
        self.target_mb_var = ctk.StringVar(
            value=str(config.WORKFLOW_PRESETS["THE_JOB"]["default_target_mb"])
        )
        self.target_mb_display_var = ctk.StringVar(value="The Job")
        self.preview_stills_paths: list[str] = []
        self.preview_stills_timestamps: list[float] = []
        self.preview_stills_colors: dict[str, list[str]] = {}
        self.current_preview_index: int = -1
        self._preview_photo_image_ref: Any | None = None
        self.logo_photo_image: Any | None = None
        self.resize_job_id: str | None = None
        self.batch_queue: list[dict[str, Any]] = []
        self.ui_update_queue = queue.Queue()
        self.is_processing: bool = False
        self.is_preparing: bool = False
        self.cancel_requested: bool = False
        self.process_holder: list[subprocess.Popen] = []
        self.processing_task_description: str = ""
        self.current_encoding_job_description: str = ""
        self.last_known_progress: float = 0.0
        self.busy_animation_job_id: str | None = None
        self.app_settings: dict[str, Any] = {}
        self.active_bitrate_kbits: float = 0.0
        self.estimated_size_mb: float = 0.0
        self.estimated_time_s: float = 0.0
        self.qc_window: tk.Toplevel | None = None
        self.widget_refs: dict[str, Any] = {}
        self.is_develop_run: bool = False

    def _setup_logging(self):
        logger_setup.setup_logging()

    def _validate_configuration(self):
        """Fail fast on preset schema violations (misconfig never reaches encode)."""
        try:
            config.validate_presets()
        except ValueError as e:
            self._show_critical_error_and_exit("Configuration Error", str(e))

    def _check_essential_dependencies(self):
        if not utils.get_ffmpeg_path() or not utils.get_ffprobe_path():
            missing = [
                name
                for name, path in [
                    (config.FFMPEG_EXE, utils.get_ffmpeg_path()),
                    (config.FFPROBE_EXE, utils.get_ffprobe_path()),
                ]
                if not path
            ]
            missing_str = " and ".join(missing)
            self._show_critical_error_and_exit(
                "Dependency Error",
                "Critical Error: Cannot find "
                f"{missing_str}.\n\nPlease ensure FFmpeg is in a 'bin' folder "
                "next to the application or in the system PATH.\n\n"
                "Application will now exit.",
            )

    def _load_assets(self):
        try:
            self.icon_path = utils.find_resource_path("icon.ico")
            if not self.icon_path:
                logger.warning("Could not find application icon 'icon.ico'.")
        except Exception as e:
            self.icon_path = None
            logger.warning(f"Could not load application icon: {e}")
        if analysis.HAS_PILLOW and (
            logo_path := utils.find_resource_path(config.LOGO_FILENAME)
        ):
            if os.path.exists(logo_path):
                try:
                    with analysis.Image.open(logo_path) as logo_img:
                        logo_img.thumbnail(
                            (200, 200), analysis.Image.Resampling.LANCZOS
                        )
                        self.logo_photo_image = ImageTk.PhotoImage(logo_img)
                except Exception as e:
                    logger.warning(f"Could not load or process logo image: {e}")

    def _configure_window(self):
        self.title(config.APP_NAME)
        self.geometry("1200x800")
        self.minsize(1100, 750)
        self.configure(fg_color=config.Theme.BACKGROUND)
        if self.icon_path:
            try:
                self.iconbitmap(default=self.icon_path)
            except tk.TclError:
                logger.warning(f"Failed to set window icon from path: {self.icon_path}")

    def _create_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        padding = config.Theme.PADDING
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, padx=padding, pady=(0, 0), sticky="ew")
        gui_panels.create_top_bar(self, top_frame)

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=2, minsize=400)
        main_frame.grid_columnconfigure(1, weight=3)
        main_frame.grid_rowconfigure(0, weight=1)

        left_panel_container = ctk.CTkFrame(
            main_frame, fg_color=config.Theme.BACKGROUND
        )
        left_panel_container.grid(
            row=0,
            column=0,
            padx=(padding, padding // 2),
            pady=(0, padding),
            sticky="nsew",
        )
        gui_panels.create_settings_panel(self, left_panel_container)

        right_panel = ctk.CTkFrame(main_frame, fg_color="transparent")
        right_panel.grid(
            row=0,
            column=1,
            padx=(padding // 2, padding),
            pady=(0, padding),
            sticky="nsew",
        )
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(0, weight=1)
        right_panel.grid_rowconfigure(2, weight=1)

        gui_panels.create_preview_panel(self, right_panel)
        gui_panels.create_control_panel(self, right_panel)
        gui_panels.create_queue_panel(self, right_panel)

        status_frame = ctk.CTkFrame(
            self, fg_color=config.Theme.SURFACE, corner_radius=0, height=40
        )
        status_frame.grid(row=2, column=0, sticky="ew")
        gui_panels.create_status_bar(self, status_frame)

    def _setup_keyboard_shortcuts(self):
        """Setup global keyboard shortcuts for the application."""
        # Ctrl+O: Load video
        self.bind("<Control-o>", lambda e: gui_callbacks.load_video_callback(self))
        self.bind("<Control-O>", lambda e: gui_callbacks.load_video_callback(self))

        # Ctrl+S: Develop/encode
        self.bind("<Control-s>", lambda e: gui_callbacks.develop_callback(self))
        self.bind("<Control-S>", lambda e: gui_callbacks.develop_callback(self))

        # Ctrl+Q: QC Tool
        self.bind("<Control-q>", lambda e: gui_callbacks.open_qc_tool_callback(self))
        self.bind("<Control-Q>", lambda e: gui_callbacks.open_qc_tool_callback(self))

        # Escape: Cancel current operation
        self.bind("<Escape>", lambda e: gui_callbacks.cancel_callback(self))

        # Delete: Remove selected queue item
        self.bind("<Delete>", lambda e: self._remove_selected_queue_item())

        # Arrow keys for queue navigation
        self.bind("<Up>", lambda e: self._move_queue_item(-1))
        self.bind("<Down>", lambda e: self._move_queue_item(1))

        # F5: Reload preview
        self.bind("<F5>", lambda e: gui_callbacks.reload_still_callback(self))

        # Number keys 1-9: Quick select preset
        for i in range(1, 10):
            self.bind(f"<Key-{i}>", lambda e, idx=i-1: self._select_preset_by_index(idx))

    def _remove_selected_queue_item(self):
        """Remove the selected item from the queue (placeholder for future implementation)."""
        pass

    def _move_queue_item(self, direction: int):
        """Move selected queue item up/down (placeholder for future implementation)."""
        pass

    def _select_preset_by_index(self, index: int):
        """Select a preset by numeric index (placeholder for future implementation)."""
        pass

    def _initialize_async(self):
        self.app_temp_dir = utils.create_temp_directory()
        if not self.app_temp_dir:
            self._show_critical_error_and_exit(
                "Critical Error", "Could not create a temporary directory."
            )
        self.app_settings = utils.load_app_settings()
        threading.Thread(target=self._run_update_check, daemon=True).start()
        self.ui_update_queue.put(lambda: gui_updaters.display_welcome_screen(self))

    def _run_update_check(self):
        if update_info := utils.check_for_updates(
            config.APP_VERSION, self.app_settings
        ):
            self.ui_update_queue.put(lambda: self._show_update_prompt(update_info))

    def _process_ui_queue(self):
        try:
            while not self.ui_update_queue.empty():
                if callable(callback := self.ui_update_queue.get_nowait()):
                    callback()
        except queue.Empty:
            pass
        self.after(50, self._process_ui_queue)

    def _start_processing_task(
        self,
        description: str,
        task_func: Callable,
        args_for_task: tuple = (),
        is_develop_task: bool = False,
    ):
        if self.is_processing:
            self._show_warning(
                "Busy", f"Already processing: {self.processing_task_description}"
            )
            return
        (
            self.is_processing,
            self.is_preparing,
            self.processing_task_description,
            self.cancel_requested,
        ) = True, is_develop_task, description, False
        self.process_holder.clear()
        self._update_ui_state()
        gui_updaters.handle_status_update(self, f"{description}...")
        if self.is_preparing:
            gui_updaters.start_busy_animation(self)

        def task_wrapper(app_ref, *task_args):
            app_instance = app_ref()
            try:
                if app_instance:
                    task_func(app_instance, *task_args)
            except OperationCancelledError as e:
                logger.info(f"Task '{description}' cancelled by user. {e}")
                if app_instance:
                    app_instance.ui_update_queue.put(
                        lambda: gui_updaters.handle_status_update(
                            app_instance, f"Task Cancelled: {description}"
                        )
                    )
            except Exception as e:
                logger.exception(
                    f"Unhandled exception in background task '{description}':"
                )
                if app_instance:
                    app_instance.ui_update_queue.put(
                        lambda err=e: app_instance._show_error(
                            f"Task Error: {description}",
                            f"Task failed unexpectedly:\n\n{err}",
                        )
                    )
            finally:
                if app_instance and app_instance.winfo_exists():
                    app_instance.ui_update_queue.put(
                        app_instance._finish_processing_task
                    )

        threading.Thread(
            target=task_wrapper, args=(weakref.ref(self), *args_for_task), daemon=True
        ).start()

    def _finish_processing_task(self):
        was_cancelled = self.cancel_requested

        self.is_processing = False
        self.is_preparing = False
        self.is_develop_run = False
        self.processing_task_description = ""
        self.current_encoding_job_description = ""
        self.process_holder.clear()

        gui_updaters.stop_busy_animation(self)
        gui_updaters.handle_encoding_progress_update(self, {"overall_progress": 0})

        if progress_text := self._get_widget("progress_text_label"):
            progress_text.configure(text="")

        self._update_ui_state()

        if was_cancelled:
            gui_updaters.handle_status_update(self, "Task Cancelled.")
        else:
            gui_updaters.handle_status_update(self, "Ready.")

    def reset_to_load_state(self, filepath: str | None = None):
        logger.debug("Performing hard reset of UI state.")
        self.input_file_original = filepath
        self.input_file_info = {}
        self.is_video_loaded = False
        self.batch_queue.clear()

        self.metadata = dict.fromkeys(config.METADATA_USER_FIELDS, "")
        if meta_entries := self.widget_refs.get("meta_entries"):
            for entry_ref in meta_entries.values():
                if entry := self._get_widget(entry_ref):
                    entry.delete(0, "end")

        self._reset_ui_for_new_job()

        gui_panels.update_queue_display(self)
        self._update_ui_state()

    def _reset_ui_for_new_job(self):
        logger.debug("Performing soft reset of UI for next job (presets/sliders only).")
        self.selected_standard_presets.clear()
        self.selected_fast_presets.clear()
        self.selected_workflow_presets.clear()
        gui_updaters.update_preset_button_styles(self)

        self.quality_level_var.set(config.Quality.DEFAULT_LEVEL)
        gui_updaters.update_quality_slider(self)

        self._update_estimates()
        self._update_ui_state()

    def _update_ui_state(self):
        is_idle, is_loaded = not self.is_processing, self.is_video_loaded
        can_interact = is_idle and is_loaded
        has_presets = bool(
            self.selected_standard_presets
            or self.selected_workflow_presets
            or self.selected_fast_presets
        )

        can_add_to_queue = can_interact and has_presets
        can_develop = is_idle and (
            bool(self.batch_queue) or (can_interact and has_presets)
        )

        states = {
            "load_button": "normal" if is_idle else "disabled",
            "dest_button": "normal" if is_idle else "disabled",
            "qc_button": "normal" if is_idle else "disabled",
            "add_queue_button": "normal" if can_add_to_queue else "disabled",
            "develop_button": "normal" if can_develop else "disabled",
            "cancel_button": "normal"
            if not is_idle and not self.cancel_requested
            else "disabled",
            "prev_button": "normal"
            if is_loaded and len(self.preview_stills_paths) > 1
            else "disabled",
            "next_button": "normal"
            if is_loaded and len(self.preview_stills_paths) > 1
            else "disabled",
            "reload_button": "normal" if is_loaded and is_idle else "disabled",
            "mux_button": "normal" if is_idle else "disabled",
            "audio_only_button": "normal" if is_idle else "disabled",
        }
        for name, state in states.items():
            self._set_widget_state(name, state)

        for panel_key in [
            "meta_entries",
            "preset_buttons",
            "workflow_buttons",
            "fast_preset_buttons",
            "source_material_slider",
            "quality_level_slider",
            "downmix_check",
            "stills_check",
            "crop_menu",
            "custom_crop_entry",
        ]:
            widget_or_dict = self.widget_refs.get(panel_key, {})
            state_to_set = "normal" if can_interact else "disabled"
            if isinstance(widget_or_dict, dict):
                [
                    self._set_widget_state(w, state_to_set)
                    for w in widget_or_dict.values()
                ]
            else:
                self._set_widget_state(widget_or_dict, state_to_set)

        if not self.is_processing and not can_interact:
            self.ui_update_queue.put(
                lambda: gui_updaters.update_estimates_display(self, 0, 0, 0, None)
            )

    def _update_destination_label(self):
        if dest_label := self._get_widget("dest_label"):
            path = self.destination_path or (
                os.path.dirname(self.input_file_original)
                if self.input_file_original
                else "[Source Directory]"
            )
            dest_label.configure(text=f"Drop-off: {path}")

    def _update_estimates(self):
        if not self.is_video_loaded or not (
            self.selected_standard_presets
            or self.selected_workflow_presets
            or self.selected_fast_presets
        ):
            gui_updaters.update_estimates_display(self, 0, 0, 0, None)
            return

        base_job_item = {
            "input_file_info": self.input_file_info,
            "crop_mode": self.crop_mode_var.get(),
            "custom_crop_string": self.custom_crop_var.get(),
            "quality_level": self.quality_level_var.get(),
            "target_mb_val": self.target_mb_var.get(),
            "metadata": self.metadata,
        }

        total_bitrate, total_size, total_time, is_crf, crf_val = 0, 0, 0, False, None
        all_presets = (
            list(self.selected_standard_presets)
            + list(self.selected_workflow_presets)
            + list(self.selected_fast_presets)
        )

        crf_presets_selected = [
            pid
            for pid in all_presets
            if (
                p := (
                    config.STANDARD_PRESETS.get(pid)
                    or config.WORKFLOW_PRESETS.get(pid)
                    or config.FAST_PRESETS.get(pid)
                )
            )
            and "crf" in p.get("rate_control_mode")
        ]
        if len(crf_presets_selected) == 1 and len(all_presets) == 1:
            pid = crf_presets_selected[0]
            preset_conf = (
                config.STANDARD_PRESETS.get(pid)
                or config.WORKFLOW_PRESETS.get(pid)
                or config.FAST_PRESETS.get(pid)
            )
            crf_val = preset_conf.get("crf_levels", {}).get(
                self.quality_level_var.get()
            )

        # Parallel estimate calculation for multiple presets
        import concurrent.futures

        def calculate_preset_estimate(pid: str) -> tuple:
            """Calculate estimate for a single preset."""
            preset_conf = (
                config.STANDARD_PRESETS.get(pid)
                or config.WORKFLOW_PRESETS.get(pid)
                or config.FAST_PRESETS.get(pid)
            )
            if not preset_conf:
                return (pid, 0, 0, 0, False, None)

            # Use a deep copy to prevent state pollution
            job_item = copy.deepcopy(base_job_item)
            job_item["preset_id"], job_item["preset_conf"] = pid, preset_conf

            _, out_w, out_h = encoding.build_video_filter_chain(job_item, preset_conf)
            time_est = utils.get_time_estimate(job_item, out_w, out_h)

            is_crf_local = "crf" in preset_conf.get("rate_control_mode", "")
            if is_crf_local:
                crf_here = preset_conf.get("crf_levels", {}).get(
                    self.quality_level_var.get()
                )
                return (pid, 0, 0, time_est, True, crf_here)

            video_kbps = utils.calculate_video_bitrate(
                pid, preset_conf, self.input_file_info, job_item, out_w, out_h
            )

            if pid == "THE_JOB":
                try:
                    size_est = float(self.target_mb_var.get())
                except (ValueError, TypeError):
                    size_est = config.WORKFLOW_PRESETS["THE_JOB"]["default_target_mb"]
            else:
                audio_kbps = preset_conf.get(
                    "audio_bitrate_kbps",
                    utils.get_audio_bitrate_from_options(
                        preset_conf.get("audio_options", ""), 128
                    ),
                )
                duration = self.input_file_info.get("duration", 0)
                size_est = ((video_kbps + audio_kbps) * duration) / 8 / 1024

            return (pid, video_kbps, size_est, time_est, False, None)

        # Use ThreadPoolExecutor for I/O-bound estimate calculations
        # Use min of preset count or CPU count for optimal parallelism
        max_workers = min(len(all_presets), os.cpu_count() or 4)

        total_bitrate, total_size, total_time, is_crf, crf_val = 0, 0, 0, False, None

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_pid = {
                executor.submit(calculate_preset_estimate, pid): pid
                for pid in all_presets
            }

            for future in concurrent.futures.as_completed(future_to_pid):
                try:
                    pid, bitrate, size, time_est, is_crf_local, crf = future.result()
                    total_bitrate += bitrate
                    total_size += size
                    total_time += time_est

                    if is_crf_local:
                        is_crf = True
                        if crf and crf_val is None:
                            crf_val = crf
                except Exception as e:
                    logger.warning(f"Estimate calculation failed for {pid}: {e}")

        if is_crf:
            total_size = -2 if total_size > 0 else -1

        self.active_bitrate_kbits, self.estimated_size_mb, self.estimated_time_s = (
            total_bitrate,
            total_size,
            total_time,
        )
        gui_updaters.update_estimates_display(
            self,
            self.active_bitrate_kbits,
            self.estimated_size_mb,
            self.estimated_time_s,
            crf_val,
        )

    def _pre_flight_checks(self, job_list: list[dict[str, Any]]) -> bool:
        if not job_list:
            self._show_error(
                "Queue Empty", "There are no jobs in the queue to develop."
            )
            return False

        for job in job_list:
            job_metadata, job_title = (
                job.get("metadata", {}),
                job.get("metadata", {}).get("title")
                or os.path.basename(job.get("input_file", "...")),
            )
            if not job_metadata.get("title") or not job_metadata.get("year"):
                if not messagebox.askyesno(
                    "Missing Metadata",
                    f"The job for '{job_title}' has a missing Title "
                    "and/or Year.\n\nProceed anyway?",
                    icon="question",
                    parent=self,
                ):
                    return False
            import validators

            _, year_err = validators.validate_year(job_metadata.get("year", ""))
            if job_metadata.get("year") and year_err:
                self._show_error("Invalid Metadata", f"The job for '{job_title}': {year_err}")
                return False
        return True

    def on_closing(self):
        if self.is_processing and not messagebox.askyesno(
            "Confirm Exit",
            "A task is running. Are you sure you want to exit?",
            icon="warning",
            parent=self,
        ):
            return
        if self.is_processing:
            self.cancel_requested = True
        self._cleanup_before_exit()
        self.destroy()

    def _cleanup_before_exit(self):
        if self.qc_window and self.qc_window.winfo_exists():
            self.qc_window.destroy()
        if self.app_temp_dir:
            utils.cleanup_temp_directory(self.app_temp_dir)
        utils.save_app_settings(self.app_settings)
        logger.info(f"--- {config.APP_NAME} Application Closed ---")

    def _get_widget(self, ref: Any) -> ctk.CTkBaseClass | None:
        widget = (
            ref()
            if isinstance(ref, weakref.ReferenceType)
            else self.widget_refs.get(ref)
            if isinstance(ref, str)
            else ref
        )
        widget = widget() if isinstance(widget, weakref.ReferenceType) else widget
        if isinstance(widget, (ctk.CTkBaseClass, tk.Widget)) and widget.winfo_exists():
            return widget
        return None

    def _set_widget_state(self, ref: Any, state: str):
        if (
            (widget := self._get_widget(ref))
            and hasattr(widget, "configure")
            and widget.cget("state") != state
        ):
            widget.configure(state=state)

    def _show_error(self, title, message):
        logger.error(f"UI_ERROR: [{title}] {message.replace(os.linesep, ' ')}")
        messagebox.showerror(title, message, parent=self)

    def _show_warning(self, title, message):
        logger.warning(f"UI_WARN: [{title}] {message.replace(os.linesep, ' ')}")
        messagebox.showwarning(title, message, parent=self)

    def _show_info(self, title, message):
        logger.info(f"UI_INFO: [{title}] {message.replace(os.linesep, ' ')}")
        messagebox.showinfo(title, message, parent=self)

    def _show_critical_error_and_exit(self, title, message):
        logger.critical(f"CRITICAL ERROR: {title} - {message}")
        try:
            self.withdraw()
            messagebox.showerror(title, message, parent=self)
        except Exception:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(title, message, parent=None)
        sys.exit(1)

    def _show_update_prompt(self, update_info: dict[str, Any]):
        choice = ui_components.UpdateDialog.show(self, update_info)
        if choice == "skip":
            self.app_settings["update_skipped_version"] = update_info.get(
                "latest_version"
            )
        utils.save_app_settings(self.app_settings)


if __name__ == "__main__":
    if "--version" in sys.argv:
        # Lightweight startup probe (used by the frozen-build smoke test):
        # proves the bundle imports cleanly without creating any GUI.
        print(f"{config.APP_NAME} {config.APP_VERSION}")
        sys.exit(0)
    try:
        # DPI awareness - Windows only, safe to attempt on all platforms
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(2)
    except (ImportError, AttributeError):
        logger.warning("Could not set high DPI awareness.")

    try:
        app = App()
        app.mainloop()
    except Exception as e:
        logging.basicConfig(
            level=logging.CRITICAL, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        logging.critical(
            "A fatal error occurred during application startup.", exc_info=True
        )
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Fatal Error",
            "A critical error occurred and the application must close.\n\n"
            f"Please check logs for details.\n\nError: {e}",
        )
