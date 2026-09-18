# qc_tool.py
"""
Quality Control Tool window for Pink Robin Encoder.
Provides a themed interface for multi-threaded VMAF score calculation
with real-time progress metrics and a final compression report.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import subprocess
import threading
import os
import re
import logging
import uuid
import shlex
from typing import Optional, Dict, TYPE_CHECKING, List, Any

if TYPE_CHECKING:
    from app import App

import config
import utils
import analysis
from gui_support import OperationCancelledError

logger = logging.getLogger(__name__)

_libvmaf_support_cache: Optional[bool] = None


def _check_libvmaf_support() -> bool:
    """
    Performs a one-time check to see if the available FFmpeg build includes
    the necessary libvmaf filter. Caches the result for efficiency.
    """
    global _libvmaf_support_cache
    if _libvmaf_support_cache is not None:
        return _libvmaf_support_cache

    logger.info("Performing one-time check for libvmaf filter support in FFmpeg...")
    ffmpeg_path = utils.get_ffmpeg_path()
    if not ffmpeg_path:
        logger.critical("Cannot check filter support: FFmpeg path not found.")
        _libvmaf_support_cache = False
        return False

    cmd = [ffmpeg_path, "-hide_banner", "-filters"]
    ret_code, stdout, _ = utils.run_quick_process(cmd, "VMAF Filter Check")

    if ret_code == 0:
        _libvmaf_support_cache = "libvmaf" in stdout
        if _libvmaf_support_cache:
            logger.info("FFmpeg build confirmed to support the 'libvmaf' filter.")
        else:
            logger.critical(
                "FFmpeg build does NOT support the required 'libvmaf' filter."
            )
    else:
        _libvmaf_support_cache = False
        logger.error(
            "Failed to execute `ffmpeg -filters` to check for libvmaf support."
        )

    return _libvmaf_support_cache


class QCToolWindow(ctk.CTkToplevel):
    """The main window for the Quality Control tool."""

    def __init__(self, parent: "App"):
        super().__init__(parent)
        self.parent_app = parent

        self.title(f"QC Tool - {config.APP_NAME}")
        self.geometry("640x700")
        self.minsize(600, 550)
        self.configure(fg_color=config.Theme.BACKGROUND)

        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        if parent.icon_path and os.path.exists(parent.icon_path):
            try:
                self.after(200, lambda: self.iconbitmap(parent.icon_path))
            except Exception as e:
                logger.warning(f"QC Tool: Failed to set window icon: {e}")

        self.lift()
        self.attributes("-topmost", True)
        self.after(100, lambda: self.attributes("-topmost", False))
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.is_calculating: bool = False
        self.cancel_requested: bool = False
        self.process_holder: List[subprocess.Popen] = []
        self.vmaf_model_path: Optional[str] = None
        self.ffmpeg_path: Optional[str] = None
        self.temp_upscaled_file: Optional[str] = None

        self._create_widgets()
        self._check_prerequisites()
        logger.info("QC Tool Window initialized.")

    def _create_widgets(self):
        padding = config.Theme.PADDING

        input_frame = ctk.CTkFrame(
            self,
            fg_color=config.Theme.SURFACE,
            corner_radius=config.Theme.CORNER_RADIUS,
        )
        input_frame.grid(
            row=0, column=0, padx=padding * 2, pady=(padding * 2, padding), sticky="ew"
        )
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            input_frame, text="Quality Control", font=config.Theme.FONT_H1
        ).grid(row=0, column=0, columnspan=3, padx=padding, pady=padding, sticky="ew")

        btn_kwargs = {
            "width": 90,
            "corner_radius": config.Theme.CORNER_RADIUS,
            "font": config.Theme.FONT_BUTTON,
            "fg_color": config.Theme.SECONDARY,
            "hover_color": config.Theme.SECONDARY_HOVER,
        }
        entry_kwargs = {
            "corner_radius": config.Theme.CORNER_RADIUS,
            "border_color": config.Theme.SECONDARY,
            "fg_color": config.Theme.BACKGROUND,
            "font": config.Theme.FONT_BODY,
        }
        label_kwargs = {"font": config.Theme.FONT_BODY}

        ctk.CTkLabel(input_frame, text="Reference Video:", **label_kwargs).grid(
            row=1, column=0, padx=padding, pady=5, sticky="w"
        )
        self.entry_ref = ctk.CTkEntry(
            input_frame,
            placeholder_text="Select original reference video...",
            **entry_kwargs,
        )
        self.entry_ref.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(
            input_frame,
            text="Browse...",
            command=lambda: self._select_file(self.entry_ref),
            **btn_kwargs,
        ).grid(row=1, column=2, padx=(5, padding), pady=5)

        ctk.CTkLabel(input_frame, text="Encoded Video:", **label_kwargs).grid(
            row=2, column=0, padx=padding, pady=5, sticky="w"
        )
        self.entry_dist = ctk.CTkEntry(
            input_frame,
            placeholder_text="Select encoded/distorted video...",
            **entry_kwargs,
        )
        self.entry_dist.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(
            input_frame,
            text="Browse...",
            command=lambda: self._select_file(self.entry_dist),
            **btn_kwargs,
        ).grid(row=2, column=2, padx=(5, padding), pady=5, sticky="s")

        self.btn_calculate = ctk.CTkButton(
            self,
            text="REVIEW",
            command=self._start_vmaf_thread,
            height=40,
            corner_radius=config.Theme.CORNER_RADIUS,
            fg_color=config.Theme.PRIMARY,
            hover_color=config.Theme.PRIMARY_HOVER,
            font=config.Theme.FONT_BUTTON,
        )
        self.btn_calculate.grid(
            row=1, column=0, pady=padding, padx=padding * 2, sticky="ew"
        )

        self.results_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.results_frame.grid(
            row=2, column=0, padx=padding * 2, pady=padding, sticky="ew"
        )
        self.results_frame.grid_columnconfigure((0, 1), weight=1)

        vmaf_panel = self._create_metric_panel(self.results_frame, "VMAF SCORE")
        vmaf_panel.grid(row=0, column=0, padx=(0, padding / 2), sticky="nsew")
        self.lbl_score_value = self._create_metric_value_label(vmaf_panel)
        self.lbl_score_sub = self._create_metric_sub_label(
            vmaf_panel, "Load videos and click REVIEW"
        )

        comp_panel = self._create_metric_panel(self.results_frame, "COMPRESSION")
        comp_panel.grid(row=0, column=1, padx=(padding / 2, 0), sticky="nsew")
        self.lbl_compression_percent = self._create_metric_value_label(
            comp_panel, "- -.-- %"
        )
        self.lbl_ref_size = self._create_metric_sub_label(comp_panel, "Original: N/A")
        self.lbl_dist_size = self._create_metric_sub_label(comp_panel, "Encoded: N/A")
        self.lbl_dist_size.pack_configure(pady=(0, 8))

        self._create_progress_log_frame()
        self.progress_log_frame.grid_remove()

    def _create_metric_panel(self, parent: ctk.CTkFrame, title: str) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(
            parent,
            fg_color=config.Theme.SURFACE,
            corner_radius=config.Theme.CORNER_RADIUS,
        )
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel,
            text=title,
            font=config.Theme.FONT_SUBTITLE,
            text_color=config.Theme.TEXT_SECONDARY,
        ).pack(pady=(8, 0))
        return panel

    def _create_metric_value_label(
        self, parent: ctk.CTkFrame, text: str = "--.--"
    ) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(family=config.Theme.FONT_FAMILY, size=36, weight="bold"),
        )
        label.pack(pady=5, padx=10, expand=True)
        return label

    def _create_metric_sub_label(self, parent: ctk.CTkFrame, text: str) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            parent,
            text=text,
            font=config.Theme.FONT_SMALL,
            wraplength=250,
            text_color=config.Theme.TEXT_SECONDARY,
        )
        label.pack(padx=10)
        return label

    def _create_progress_log_frame(self):
        padding = config.Theme.PADDING
        self.progress_log_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.progress_log_frame.grid(
            row=3,
            column=0,
            padx=padding * 2,
            pady=(padding, padding * 2),
            sticky="nsew",
        )
        self.progress_log_frame.grid_rowconfigure(2, weight=1)
        self.progress_log_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_log_frame,
            mode="determinate",
            fg_color=config.Theme.SURFACE_LIGHT,
            progress_color=config.Theme.PRIMARY,
        )
        self.progress_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.progress_bar.set(0)

        metrics_dashboard = ctk.CTkFrame(
            self.progress_log_frame, fg_color="transparent"
        )
        metrics_dashboard.grid(row=1, column=0, sticky="ew")
        metrics_dashboard.grid_columnconfigure((0, 10), weight=1)

        val_font = config.Theme.FONT_SUBTITLE
        sep_kwargs = {
            "text": "|",
            "font": val_font,
            "text_color": config.Theme.SECONDARY,
        }

        ctk.CTkLabel(
            metrics_dashboard, text="Progress:", font=config.Theme.FONT_BODY
        ).grid(row=0, column=1, sticky="e", padx=(0, 5))
        self.lbl_progress_val = ctk.CTkLabel(
            metrics_dashboard, text="0/0 (0.0%)", font=val_font, anchor="w"
        )
        self.lbl_progress_val.grid(row=0, column=2, sticky="w")
        ctk.CTkLabel(metrics_dashboard, **sep_kwargs).grid(row=0, column=3, padx=15)
        ctk.CTkLabel(
            metrics_dashboard, text="Speed:", font=config.Theme.FONT_BODY
        ).grid(row=0, column=4, sticky="e", padx=(0, 5))
        self.lbl_speed_val = ctk.CTkLabel(
            metrics_dashboard, text="--x", font=val_font, anchor="w"
        )
        self.lbl_speed_val.grid(row=0, column=5, sticky="w")
        ctk.CTkLabel(metrics_dashboard, **sep_kwargs).grid(row=0, column=6, padx=15)
        ctk.CTkLabel(metrics_dashboard, text="ETA:", font=config.Theme.FONT_BODY).grid(
            row=0, column=7, sticky="e", padx=(0, 5)
        )
        self.lbl_time_val = ctk.CTkLabel(
            metrics_dashboard, text="--:--:--", font=val_font, anchor="w"
        )
        self.lbl_time_val.grid(row=0, column=8, sticky="w")

        self.txt_output = ctk.CTkTextbox(
            self.progress_log_frame,
            font=(config.Theme.FONT_MONO, 11),
            wrap="word",
            state="disabled",
            fg_color=config.Theme.SURFACE,
            border_color=config.Theme.SECONDARY,
            border_width=1,
        )
        self.txt_output.grid(row=2, column=0, pady=(10, 0), sticky="nsew")

    def _update_progress_ui(self, progress_data: Dict[str, Any]):
        if not self.winfo_exists():
            return
        progress_val = progress_data.get("progress", 0.0) / 100.0
        self.progress_bar.set(progress_val)
        self.lbl_progress_val.configure(text=progress_data.get("progress_text", "..."))
        self.lbl_speed_val.configure(text=progress_data.get("speed", "..."))
        self.lbl_time_val.configure(text=progress_data.get("eta_str", "..."))

    def _ui_toggle_calculating(
        self, is_calculating: bool, status_text: str = "Calculating..."
    ):
        self.is_calculating = is_calculating
        if is_calculating:
            self.btn_calculate.configure(
                state="normal",
                text="CANCEL",
                fg_color=config.Theme.ERROR,
                hover_color="#A55060",
                command=self._cancel_task,
            )
            self._log_message(f"\n--- {status_text} ---")
            self.results_frame.grid_remove()
            self.progress_log_frame.grid()
        else:
            self.btn_calculate.configure(
                state="normal",
                text="REVIEW",
                fg_color=config.Theme.PRIMARY,
                hover_color=config.Theme.PRIMARY_HOVER,
                command=self._start_vmaf_thread,
            )
            self.progress_log_frame.grid_remove()
            self.results_frame.grid()

    def _clear_results_ui(self):
        self.update_score_indicator(None, "Calculating VMAF score...")
        self.lbl_compression_percent.configure(
            text="- -.-- %", text_color=config.Theme.TEXT_PRIMARY
        )
        self.lbl_ref_size.configure(text="Original: N/A")
        self.lbl_dist_size.configure(text="Encoded: N/A")

    def _update_compression_report_ui(self, ref_size: int, dist_size: int):
        self.lbl_ref_size.configure(text=f"Original: {utils._format_bytes(ref_size)}")
        self.lbl_dist_size.configure(text=f"Encoded: {utils._format_bytes(dist_size)}")
        if ref_size > 0 and dist_size >= 0:
            compression_ratio = 1 - (dist_size / ref_size)
            sign = "-" if compression_ratio >= 0 else "+"
            color = (
                config.Theme.SUCCESS if compression_ratio >= 0 else config.Theme.ERROR
            )
            self.lbl_compression_percent.configure(
                text=f"{sign}{abs(compression_ratio):.1%}", text_color=color
            )
        else:
            self.lbl_compression_percent.configure(
                text="N/A", text_color=config.Theme.TEXT_PRIMARY
            )

    def _check_prerequisites(self):
        self._log_message("--- System Check ---", clear=True)
        self.ffmpeg_path = utils.get_ffmpeg_path()
        self.vmaf_model_path = utils.find_resource_path(config.VMAF_MODEL_FILENAME)

        libvmaf_supported = _check_libvmaf_support()
        ffmpeg_ok = self.ffmpeg_path and os.path.exists(self.ffmpeg_path)
        model_ok = self.vmaf_model_path and os.path.exists(self.vmaf_model_path)

        if ffmpeg_ok:
            self._log_message(f"✅ FFmpeg found: {os.path.basename(self.ffmpeg_path)}")
        else:
            self._log_message(
                f"❌ ERROR: FFmpeg executable ('{config.FFMPEG_EXE}') not found."
            )

        if libvmaf_supported:
            self._log_message("✅ FFmpeg build supports libvmaf filter.")
        else:
            self._log_message(
                "❌ ERROR: Your FFmpeg build does NOT support the libvmaf filter."
            )

        if model_ok:
            self._log_message(
                f"✅ VMAF model found: {os.path.basename(self.vmaf_model_path)}"
            )
        else:
            self._log_message(
                f"❌ ERROR: VMAF model ('{config.VMAF_MODEL_FILENAME}') not found."
            )

        if ffmpeg_ok and model_ok and libvmaf_supported:
            self._log_message("✅ Prerequisites met. Ready for QC.\n" + "-" * 35)
            self.btn_calculate.configure(state="normal")
        else:
            self._log_message(
                "❌ Prerequisites missing! Calculation disabled.\n" + "-" * 35
            )
            self.btn_calculate.configure(state="disabled")

    def _select_file(self, entry_widget: ctk.CTkEntry):
        filepath = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=(
                ("Video Files", "*.mp4 *.mkv *.avi *.mov"),
                ("All Files", "*.*"),
            ),
            parent=self,
        )
        if filepath:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, os.path.normpath(filepath))

    def _log_message(self, message: str, clear: bool = False):
        if not self.winfo_exists():
            return
        self.txt_output.configure(state="normal")
        if clear:
            self.txt_output.delete("1.0", tk.END)
        self.txt_output.insert(tk.END, str(message) + "\n")
        self.txt_output.see(tk.END)
        self.txt_output.configure(state="disabled")

    def update_score_indicator(
        self, score: Optional[float], subtitle: Optional[str] = None
    ):
        text_color, emoji = config.Theme.TEXT_PRIMARY, "🤔"
        sub_text = subtitle if subtitle is not None else "Load videos and click REVIEW"
        score_val_text = f"{score:.2f}" if score is not None else "--.--"

        if score is not None:
            for score_range, (emo, text, color_name) in config.VMAF_SCORE_GUIDE.items():
                if score_range[0] <= score < score_range[1]:
                    emoji, sub_text, text_color = emo, text, color_name
                    break

        self.lbl_score_value.configure(text=score_val_text, text_color=text_color)
        self.lbl_score_sub.configure(text=f"{emoji} {sub_text}")

    def _start_vmaf_thread(self):
        if self.is_calculating:
            return
        self.cancel_requested = False
        self.process_holder.clear()
        self._clear_results_ui()
        self._log_message("\n--- Starting VMAF Calculation ---", clear=True)
        threading.Thread(target=self._vmaf_precheck_and_run, daemon=True).start()

    def _cancel_task(self):
        if not self.is_calculating:
            return
        self.cancel_requested = True
        self._log_message("\n--- CANCEL REQUESTED ---")
        self.btn_calculate.configure(state="disabled", text="CANCELLING...")

    def _vmaf_precheck_and_run(self):
        ref_path, dist_path = self.entry_ref.get(), self.entry_dist.get()
        if not all(
            [ref_path, dist_path, os.path.exists(ref_path), os.path.exists(dist_path)]
        ):
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Input Error",
                    "Please select valid Reference and Encoded video files.",
                    parent=self,
                ),
            )
            return

        try:
            self._log_message("Probing video files for comparison...")
            ref_info = analysis.get_video_info(ref_path)
            dist_info = analysis.get_video_info(dist_path)

            if not ref_info or not dist_info:
                raise ValueError("Could not get properties for one or both videos.")
            if abs(ref_info["duration"] - dist_info["duration"]) > 0.1:
                self._log_message(
                    "⚠️ WARNING: Video durations differ significantly. Results may be inaccurate."
                )

            if (
                ref_info["width"] != dist_info["width"]
                or ref_info["height"] != dist_info["height"]
            ):
                self._log_message("Resolution mismatch detected.")
                msg = (
                    f"Resolutions do not match:\n  Reference: {ref_info['width']}x{ref_info['height']}\n  Encoded:   {dist_info['width']}x{dist_info['height']}\n\n"
                    f"For an accurate VMAF score, the encoded video must be upscaled to match the reference. This will create a temporary, high-quality file.\n\nDo you want to proceed?"
                )
                if messagebox.askyesno("Resolution Mismatch", msg, parent=self):
                    self._run_upscale_task(dist_path, ref_path, ref_info)
                else:
                    self._log_message(
                        "❌ Calculation cancelled by user due to resolution mismatch."
                    )
                    self.after(0, lambda: self._ui_toggle_calculating(False))
            else:
                self._log_message(
                    "✅ Resolutions match. Proceeding with VMAF calculation."
                )
                self._run_vmaf_task(ref_path, dist_path, ref_info)
        except Exception as e:
            logger.error(f"Error during VMAF pre-check: {e}", exc_info=True)
            self._log_message(f"❌ An unexpected error occurred during pre-check: {e}")
            self.after(0, lambda: self._ui_toggle_calculating(False))

    def _run_upscale_task(self, dist_path, ref_path, ref_info):
        self.after(
            0, lambda: self._ui_toggle_calculating(True, "Upscaling for VMAF...")
        )
        try:
            target_w, target_h = ref_info["width"], ref_info["height"]
            self.temp_upscaled_file = os.path.join(
                self.parent_app.app_temp_dir,
                f"temp_vmaf_upscale_{uuid.uuid4().hex}.mov",
            )
            self._log_message(
                f"Creating temporary upscaled file at {target_w}x{target_h}..."
            )
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-i",
                dist_path,
                "-c:v",
                "prores_ks",
                "-profile:v",
                "3",
                "-vf",
                f"scale={target_w}:{target_h}",
                self.temp_upscaled_file,
            ]

            ret, _, stderr = utils.run_process(
                cmd=cmd,
                duration=ref_info["duration"],
                total_frames=ref_info["nb_frames"],
                progress_callback=lambda p: self.after(0, self._update_progress_ui, p),
                process_description="VMAF Upscaling",
                process_holder=self.process_holder,
                cancel_flag_func=lambda: self.cancel_requested,
            )
            if self.cancel_requested:
                raise OperationCancelledError()
            if ret != 0:
                raise RuntimeError(f"Upscaling failed. FFmpeg stderr:\n{stderr}")

            self._log_message("✅ Upscaling complete.")
            self._run_vmaf_task(ref_path, self.temp_upscaled_file, ref_info)
        except Exception as e:
            logger.error(f"Error during upscale task: {e}", exc_info=True)
            self._log_message(f"❌ Upscaling failed: {e}")
            self.after(0, lambda: self._ui_toggle_calculating(False))

    def _run_vmaf_task(self, ref_path: str, dist_path: str, ref_info: Dict[str, Any]):
        self.after(0, lambda: self._ui_toggle_calculating(True, "Calculating VMAF..."))
        vmaf_score, stderr_output = None, ""
        try:
            if not self.ffmpeg_path or not self.vmaf_model_path:
                raise RuntimeError("FFmpeg or VMAF model path not set.")

            ffmpeg_dir, model_filename = (
                os.path.dirname(self.ffmpeg_path),
                os.path.basename(self.vmaf_model_path),
            )
            vmaf_log_path = os.path.join(
                self.parent_app.app_temp_dir, f"vmaf_log_{uuid.uuid4().hex}.json"
            )
            escaped_log_path = utils.escape_ffmpeg_path_for_filter(vmaf_log_path)

            # *** FIX: Changed 'model_path=' to the correct 'model=path=' syntax ***
            libvmaf_options = f"model=path='{model_filename}':log_path={escaped_log_path}:log_fmt=json:n_threads={config.VMAF_NUM_THREADS}"

            filter_string = f"[0:v]setpts=PTS-STARTPTS[dist];[1:v]setpts=PTS-STARTPTS[ref];[dist][ref]libvmaf={libvmaf_options}"
            command = [
                self.ffmpeg_path,
                "-hide_banner",
                "-progress",
                "pipe:1",
                "-i",
                dist_path,
                "-i",
                ref_path,
                "-filter_complex",
                filter_string,
                "-f",
                "null",
                "-",
            ]

            logger.info(f"Executing VMAF command with CWD set to: {ffmpeg_dir}")
            logger.info(
                f"Full command for debugging: {' '.join(shlex.quote(c) for c in command)}"
            )
            self._log_message(
                f"Using {config.VMAF_NUM_THREADS or 'auto'} threads. Executing from: {ffmpeg_dir}"
            )

            ret_code, _, stderr_output = utils.run_process(
                cmd=command,
                duration=ref_info["duration"],
                total_frames=ref_info["nb_frames"],
                progress_callback=lambda p: self.after(0, self._update_progress_ui, p),
                process_description="VMAF Calculation",
                process_holder=self.process_holder,
                cancel_flag_func=lambda: self.cancel_requested,
                cwd=ffmpeg_dir,
            )

            if self.cancel_requested:
                raise OperationCancelledError()
            if ret_code != 0:
                raise ValueError(f"FFmpeg process failed with code {ret_code}.")

            score_match = re.search(r"VMAF score\s*:\s*([\d\.]+)", stderr_output)
            if score_match:
                vmaf_score = float(score_match.group(1))
                self._log_message(f"\n✅ VMAF Score Found: {vmaf_score:.4f}")
                try:
                    ref_size, dist_size = (
                        os.path.getsize(ref_path),
                        os.path.getsize(self.entry_dist.get()),
                    )
                    self.after(
                        0,
                        lambda rs=ref_size, ds=dist_size: (
                            self._update_compression_report_ui(rs, ds)
                        ),
                    )
                except FileNotFoundError:
                    self._log_message(
                        "⚠️ Could not get file sizes for compression report."
                    )
            else:
                raise ValueError("Could not parse VMAF score from FFmpeg output.")
        except OperationCancelledError:
            self._log_message("❌ Calculation cancelled by user.")
        except Exception as e:
            logger.error(f"Error during VMAF task: {e}", exc_info=True)
            self._log_message(f"❌ An unexpected error occurred: {e}")
            if stderr_output:
                self._log_message(
                    f"\n--- Full FFmpeg Output ---\n{stderr_output.strip()}"
                )
        finally:
            self.after(0, lambda s=vmaf_score: self.update_score_indicator(s))
            if (
                hasattr(self, "progress_bar")
                and self.progress_bar.cget("mode") == "indeterminate"
            ):
                self.after(0, self.progress_bar.stop)
            self.after(0, lambda: self.progress_bar.set(0))
            self.after(0, lambda: self._ui_toggle_calculating(False))

    def on_closing(self):
        if self.is_calculating:
            if messagebox.askyesno(
                "Confirm Close",
                "Calculation is in progress. Are you sure you want to close?",
                parent=self,
            ):
                self._cancel_task()
                self.destroy()
        else:
            self.destroy()

        if self.temp_upscaled_file and os.path.exists(self.temp_upscaled_file):
            try:
                os.remove(self.temp_upscaled_file)
                logger.info(
                    f"Cleaned up temporary upscale file: {self.temp_upscaled_file}"
                )
            except OSError as e:
                logger.warning(f"Could not remove temporary upscale file: {e}")
