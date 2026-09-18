# gui_updaters.py
"""
Functions for updating GUI elements in the Pink Robin Encoder application.
These functions are intended to be called from the main UI thread,
typically via the application's UI update queue. They are responsible
for all visual changes in response to application state.
"""

import os
import logging
from typing import TYPE_CHECKING, Dict, Any, Optional, List, Tuple

if TYPE_CHECKING:
    from app import App

import config
import analysis
import utils
import ui_components
import gui_callbacks

if analysis.HAS_PILLOW:
    from PIL import Image, ImageTk

logger = logging.getLogger(__name__)

# --- Status & Progress Updaters ---


def handle_status_update(app: "App", message: str) -> None:
    if status_label := app._get_widget("status_label"):
        max_len = 150
        display_message = (
            message if len(message) <= max_len else f"{message[: max_len - 3]}..."
        )
        status_label.configure(text=display_message)


def handle_encoding_progress_update(app: "App", progress_data: Dict[str, Any]) -> None:
    if app.is_preparing:
        return

    overall_progress = progress_data.get("overall_progress", 0.0)
    eta_str = progress_data.get("total_eta_str", "--:--:--")
    elapsed_str = progress_data.get("elapsed_str", "--:--:--")
    speed_str = progress_data.get("speed", "--x")
    job_desc = progress_data.get("job_description", "...")
    job_num_str = progress_data.get("job_num_str", "")
    progress_text_str = progress_data.get("progress_text", "")

    status_text = (
        f"Processing {job_num_str}: {job_desc} @ {speed_str} [{progress_text_str}]"
    )
    handle_status_update(app, status_text)

    if progress_bar := app._get_widget("progress_bar"):
        if progress_bar.cget("mode") == "indeterminate":
            progress_bar.configure(mode="determinate")
        progress_bar.set(overall_progress / 100.0)

    if progress_text := app._get_widget("progress_text_label"):
        progress_text.configure(text=f"{int(overall_progress)}%")

    if progress_eta := app._get_widget("progress_eta_label"):
        progress_eta.configure(text=f"ETA: {eta_str}")

    if progress_elapsed := app._get_widget("progress_elapsed_label"):
        progress_elapsed.configure(text=f"Elapsed: {elapsed_str}")


def handle_simple_progress_update(app: "App", value: float) -> None:
    if progress_bar := app._get_widget("progress_bar"):
        if progress_bar.cget("mode") == "indeterminate":
            progress_bar.configure(mode="determinate")
        progress_ui_val = max(0.0, min(1.0, value / 100.0))
        progress_bar.set(progress_ui_val)
    if progress_text := app._get_widget("progress_text_label"):
        progress_text.configure(text=f"{int(value)}%" if value > 0 else "")


def start_busy_animation(app: "App", message: str = "Gearing up..."):
    handle_status_update(app, message)
    if progress_bar := app._get_widget("progress_bar"):
        progress_bar.configure(mode="indeterminate")
        progress_bar.start()


def stop_busy_animation(app: "App"):
    if progress_bar := app._get_widget("progress_bar"):
        progress_bar.stop()
        progress_bar.configure(mode="determinate")


# --- Preview & Welcome Screen ---


def display_welcome_screen(app: "App") -> None:
    if not (preview_canvas := app._get_widget("preview_canvas")):
        return
    preview_canvas.delete("all")
    app._preview_photo_image_ref = None
    canvas_w, canvas_h = preview_canvas.winfo_width(), preview_canvas.winfo_height()
    if canvas_w < 2 or canvas_h < 2:
        return

    y_pos = canvas_h / 2 - 40
    if app.logo_photo_image:
        preview_canvas.create_image(
            canvas_w / 2, y_pos, anchor="center", image=app.logo_photo_image
        )
        y_pos += app.logo_photo_image.height() / 2 + 30
    else:
        preview_canvas.create_text(
            canvas_w / 2,
            y_pos,
            text=config.APP_NAME,
            fill=config.Theme.TEXT_PRIMARY,
            font=config.Theme.FONT_H1,
            anchor="center",
        )
        y_pos += 40

    preview_canvas.create_text(
        canvas_w / 2,
        y_pos,
        text="Load evidence to begin.",
        fill=config.Theme.TEXT_SECONDARY,
        font=config.Theme.FONT_BODY,
        anchor="center",
    )


def display_preview_image(app: "App", image_path: Optional[str]) -> None:
    if not (preview_canvas := app._get_widget("preview_canvas")):
        return
    preview_canvas.delete("all")
    app._preview_photo_image_ref = None

    if not image_path or not os.path.exists(image_path) or not analysis.HAS_PILLOW:
        display_welcome_screen(app)
        return

    try:
        canvas_w, canvas_h = preview_canvas.winfo_width(), preview_canvas.winfo_height()
        if canvas_w < 2 or canvas_h < 2:
            return

        with Image.open(image_path) as pil_image:
            info, crop_mode = app.input_file_info, app.crop_mode_var.get()
            crop_filter_str = None
            if crop_mode == "Auto-Detect":
                crop_filter_str = info.get("auto_crop_string")
            elif crop_mode == "Custom":
                crop_filter_str = app.custom_crop_var.get()
            elif crop_mode != "None":
                crop_filter_str, _, _ = utils.get_aspect_ratio_crop_filter(
                    pil_image.width, pil_image.height, crop_mode
                )

            img_to_display = pil_image
            if crop_filter_str and "crop=" in crop_filter_str:
                try:
                    parts = crop_filter_str.replace("crop=", "").split(":")
                    w, h, x, y = [int(p) for p in parts]
                    img_to_display = pil_image.crop((x, y, x + w, y + h))
                except (ValueError, IndexError) as e:
                    logger.warning(
                        f"Invalid crop string for preview '{crop_filter_str}': {e}"
                    )

            if colors := app.preview_stills_colors.get(image_path):
                if img_with_palette := analysis.add_palette_to_still(
                    img_to_display, colors
                ):
                    img_to_display = img_with_palette

            img_w, img_h = img_to_display.size
            if img_w <= 0 or img_h <= 0:
                return

            scale = min(
                (canvas_w - config.Theme.PADDING * 2) / img_w,
                (canvas_h - config.Theme.PADDING * 2) / img_h,
            )
            new_w, new_h = int(img_w * scale), int(img_h * scale)

            if new_w > 0 and new_h > 0:
                resized_img = img_to_display.resize(
                    (new_w, new_h), Image.Resampling.LANCZOS
                )
                photo_image = ImageTk.PhotoImage(resized_img)
                app._preview_photo_image_ref = photo_image
                img_x, img_y = (canvas_w - new_w) / 2, (canvas_h - new_h) / 2
                preview_canvas.create_image(
                    img_x, img_y, anchor="nw", image=photo_image
                )

    except Exception as e:
        logger.exception(f"Error displaying preview image '{image_path}': {e}")


# --- UI State & Style Updaters ---


def update_preset_button_styles(app: "App") -> None:
    """Uses a filled/tonal style for active/inactive presets."""
    preset_sets_map = {
        "preset_buttons": app.selected_standard_presets,
        "fast_preset_buttons": app.selected_fast_presets,
        "workflow_buttons": app.selected_workflow_presets,
    }

    for button_key, preset_set in preset_sets_map.items():
        for pid, button_ref in app.widget_refs.get(button_key, {}).items():
            if button := app._get_widget(button_ref):
                is_active = pid in preset_set
                if is_active:
                    button.configure(
                        fg_color=config.Theme.SECONDARY,
                        hover_color=config.Theme.SECONDARY_HOVER,
                        text_color=config.Theme.TEXT_PRIMARY,
                    )
                else:
                    button.configure(
                        fg_color=config.Theme.SURFACE_LIGHT,
                        hover_color=config.Theme.SECONDARY,
                        text_color=config.Theme.TEXT_SECONDARY,
                    )


def update_mb_button_display(app: "App"):
    try:
        mb_val = float(app.target_mb_var.get())
        display_text = f"{mb_val:.0f} MB"
    except (ValueError, TypeError):
        display_text = "The Job"
    app.target_mb_display_var.set(display_text)


def _update_slider_widgets(
    app: "App", slider_key: str, label_key: str, options: list, current_value: Any
):
    if slider := app._get_widget(slider_key):
        try:
            # Find the index of the current value in the options list
            current_index = [opt[0] for opt in options].index(current_value)
            slider.set(current_index)
        except (ValueError, IndexError):
            pass  # Value not in options, slider remains as is

    if label := app._get_widget(label_key):
        try:
            # Find the display text for the current value
            display_text = next(opt[1] for opt in options if opt[0] == current_value)
            label.configure(text=display_text)
        except StopIteration:
            pass


def update_source_slider(app: "App"):
    options = list(config.SOURCE_MATERIAL_OPTIONS.items())
    current_val = app.source_material_var.get()
    _update_slider_widgets(
        app, "source_material_slider", "source_material_label", options, current_val
    )


def update_quality_slider(app: "App"):
    options = list(enumerate(config.Quality.LEVELS))
    current_val = app.quality_level_var.get()
    try:
        current_idx = config.Quality.LEVELS.index(current_val)
        _update_slider_widgets(
            app, "quality_level_slider", "quality_level_label", options, current_idx
        )
    except ValueError:
        pass


# --- Data Display Updaters ---


def handle_set_video_info(app: "App", video_info: Optional[Dict[str, Any]]) -> None:
    app.is_video_loaded = bool(video_info)
    if video_info:
        app.input_file_info = video_info
        if load_btn := app._get_widget("load_button"):
            load_btn.configure(
                fg_color=config.Theme.SUCCESS, text="Evidence Loaded"
            )  # Use success color
        if details_label := app._get_widget("source_details_label"):
            details_label.configure(
                text=video_info.get("source_details_text", "N/A"),
                text_color=config.Theme.TEXT_PRIMARY,
            )
        if crop_menu := app._get_widget("crop_menu"):
            crop_menu.set(config.DEFAULT_CROP_MODE)
        if downmix_check := app._get_widget("downmix_check"):
            is_multichannel = video_info.get("audio_stream", {}).get("channels", 0) > 2
            downmix_check.configure(state="normal" if is_multichannel else "disabled")
            if not is_multichannel:
                app.is_downmix_enabled.set(False)
    else:
        app.reset_to_load_state(None)
        if load_btn := app._get_widget("load_button"):
            load_btn.configure(fg_color=config.Theme.PRIMARY, text="Load Evidence")
    app._update_ui_state()
    app._update_estimates()


def handle_set_source_material(app: "App", source_material: str) -> None:
    app.source_material_var.set(source_material)
    update_source_slider(app)


def handle_set_metadata_from_dict(app: "App", meta_dict: Dict[str, str]):
    app.metadata = meta_dict.copy()
    for field, value in meta_dict.items():
        if entry_ref := app.widget_refs.get("meta_entries", {}).get(field):
            if entry := app._get_widget(entry_ref):
                entry.delete(0, "end")
                entry.insert(0, value)


def handle_set_metadata_from_filename(app: "App", parsed_meta: Dict[str, str]):
    for field, value in parsed_meta.items():
        if entry_ref := app.widget_refs.get("meta_entries", {}).get(field):
            if entry := app._get_widget(entry_ref):
                if not entry.get():
                    entry.insert(0, value)
                    app.metadata[field] = value
    logger.info(f"Pre-filled metadata from filename: {parsed_meta}")
    app._update_estimates()


def handle_set_preview_stills(
    app: "App", paths_colors_tuple: Tuple[List[str], Dict[str, List[str]]]
) -> None:
    app.preview_stills_paths, app.preview_stills_colors = paths_colors_tuple
    if app.preview_stills_paths:
        app.current_preview_index = 0
        display_preview_image(app, app.preview_stills_paths[0])
        handle_status_update(app, f"Preview: 1 of {len(app.preview_stills_paths)}")
    else:
        app.current_preview_index = -1
        display_welcome_screen(app)
    app._update_ui_state()
    gui_callbacks.preview_resize_callback(app, None)


def handle_update_single_preview(
    app: "App", index_path_colors_tuple: Tuple[int, str, Optional[List[str]]]
) -> None:
    index, new_path, new_colors = index_path_colors_tuple
    if 0 <= index < len(app.preview_stills_paths):
        if old_path := app.preview_stills_paths[index]:
            if old_path in app.preview_stills_colors:
                del app.preview_stills_colors[old_path]
        app.preview_stills_paths[index] = new_path
        if new_colors:
            app.preview_stills_colors[new_path] = new_colors
        if index == app.current_preview_index:
            display_preview_image(app, new_path)
    app._update_ui_state()


def handle_update_all_preview_colors(app: "App", colors_map: Dict[str, List[str]]):
    logger.info("Applying color palettes to preview stills.")
    app.preview_stills_colors = colors_map
    if (
        app.current_preview_index >= 0
        and len(app.preview_stills_paths) > app.current_preview_index
    ):
        display_preview_image(app, app.preview_stills_paths[app.current_preview_index])


def show_task_complete_summary(
    app: "App",
    jobs: int,
    outputs: int,
    stills: int,
    elapsed_time: float,
    estimated_time: float,
    output_path: str,
):
    details = f"• Outputs Created: {outputs} video file(s), {stills} still image(s)."
    if app.winfo_exists():
        ui_components.CompletionDialog(
            app, "The Job is Done", details, output_path, elapsed_time, estimated_time
        )


def update_estimates_display(
    app: "App",
    bitrate_kbits: float,
    size_mb: float,
    time_s: float,
    crf_val: Optional[str],
):
    labels = app.widget_refs.get("estimates_labels", {})
    if size_label := app._get_widget(labels.get("size")):
        if size_mb == -1:
            size_text = "Est. Size: N/A (CRF)"
        elif size_mb == -2:
            size_text = "Est. Size: N/A (Mixed)"
        elif size_mb > 0:
            size_text = f"Est. Size: {size_mb:.1f} MB"
        else:
            size_text = "Est. Size: --"
        size_label.configure(text=size_text)
    if bitrate_label := app._get_widget(labels.get("bitrate")):
        if crf_val:
            bitrate_text = f"Quality: CRF {crf_val}"
        elif size_mb == -2:
            bitrate_text = "Bitrate: N/A (Mixed)"
        elif bitrate_kbits > 0:
            bitrate_text = f"Bitrate: {bitrate_kbits:.0f} kbps"
        else:
            bitrate_text = "Bitrate: --"
        bitrate_label.configure(text=bitrate_text)
    if time_label := app._get_widget(labels.get("time")):
        time_text = (
            f"~Est. Time: {utils._format_eta(time_s)}"
            if time_s > 0
            else "~Est. Time: --:--:--"
        )
        time_label.configure(text=time_text)


def handle_error_message(app: "App", title_message_tuple: Tuple[str, str]):
    app._show_error(title_message_tuple[0], title_message_tuple[1])


def handle_warning_message(app: "App", title_message_tuple: Tuple[str, str]):
    app._show_warning(title_message_tuple[0], title_message_tuple[1])
