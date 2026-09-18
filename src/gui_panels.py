# gui_panels.py
"""
Creates and organizes all the major UI panels for the Pink Robin Encoder application.
This module is responsible for the 'view' component of the application's layout,
placing widgets into parent frames provided by the main App class.
"""

import customtkinter as ctk
import weakref
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app import App

import a11y
import config
import gui_callbacks

logger = logging.getLogger(__name__)


# --- Helper to create a styled card ---
def _create_card_frame(parent: ctk.CTkFrame) -> ctk.CTkFrame:
    """Creates a standard styled frame for grouping settings."""
    frame = ctk.CTkFrame(
        parent, fg_color=config.Theme.SURFACE, corner_radius=config.Theme.CORNER_RADIUS
    )
    frame.pack(fill="x", padx=config.Theme.PADDING, pady=config.Theme.PADDING_SMALL)
    return frame


# --- Top Bar ---
def create_top_bar(app: "App", parent: ctk.CTkFrame):
    """Creates the top bar with load/destination buttons and QC Tool."""
    parent.grid_columnconfigure(1, weight=1)
    padding = config.Theme.PADDING

    load_button = ctk.CTkButton(
        parent,
        text="Load Evidence",
        width=160,
        height=40,
        command=lambda: gui_callbacks.load_video_callback(app),
        font=config.Theme.FONT_BUTTON,
        fg_color=config.Theme.PRIMARY,
        hover_color=config.Theme.PRIMARY_HOVER,
        corner_radius=config.Theme.CORNER_RADIUS,
    )
    load_button.grid(row=0, column=0, padx=(0, padding), pady=padding, sticky="w")
    app.widget_refs["load_button"] = weakref.ref(load_button)

    dest_button = ctk.CTkButton(
        parent,
        text="Set Drop-off",
        width=120,
        height=40,
        command=lambda: gui_callbacks.select_destination_callback(app),
        font=config.Theme.FONT_BUTTON,
        fg_color="transparent",
        hover_color=config.Theme.SURFACE_LIGHT,
        corner_radius=config.Theme.CORNER_RADIUS,
    )
    dest_button.grid(row=0, column=2, padx=padding, pady=padding, sticky="w")
    app.widget_refs["dest_button"] = weakref.ref(dest_button)

    dest_label = ctk.CTkLabel(
        parent,
        text="Drop-off: [Source Directory]",
        anchor="w",
        font=config.Theme.FONT_SMALL,
        text_color=config.Theme.TEXT_SECONDARY,
    )
    dest_label.grid(row=0, column=1, padx=padding, pady=padding, sticky="w")
    app.widget_refs["dest_label"] = weakref.ref(dest_label)

    qc_button = ctk.CTkButton(
        parent,
        text="QC Tool",
        width=120,
        height=40,
        command=lambda: gui_callbacks.open_qc_tool_callback(app),
        font=config.Theme.FONT_BUTTON,
        fg_color="transparent",
        border_width=2,
        border_color=config.Theme.SECONDARY,
        hover_color=config.Theme.SURFACE_LIGHT,
        corner_radius=config.Theme.CORNER_RADIUS,
    )
    qc_button.grid(row=0, column=3, padx=(padding, 0), pady=padding, sticky="e")
    app.widget_refs["qc_button"] = weakref.ref(qc_button)


# --- Left Panel ---
def create_settings_panel(app: "App", parent: ctk.CTkFrame):
    """Creates the main settings panel on the left."""
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    settings_container = ctk.CTkScrollableFrame(
        parent, fg_color="transparent", corner_radius=0
    )
    settings_container.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
    settings_container.grid_columnconfigure(0, weight=1)
    settings_container._scrollbar.configure(height=0)

    _create_metadata_panel(app, settings_container)
    _create_source_details_panel(app, settings_container)
    _create_preset_panel(
        app,
        settings_container,
        "Standard Operations",
        config.STANDARD_PRESETS,
        "preset_buttons",
    )
    _create_preset_panel(
        app,
        settings_container,
        "Fast Operations",
        config.FAST_PRESETS,
        "fast_preset_buttons",
    )
    _create_preset_panel(
        app,
        settings_container,
        "Special Workflows",
        config.WORKFLOW_PRESETS,
        "workflow_buttons",
    )
    _create_adjustments_panel(app, settings_container)
    _create_options_panel(app, settings_container)
    _create_special_ops_panel(app, settings_container)


def _create_metadata_panel(app: "App", parent: ctk.CTkFrame):
    meta_frame = _create_card_frame(parent)
    meta_frame.grid_columnconfigure(1, weight=1)
    padding = config.Theme.PADDING

    ctk.CTkLabel(meta_frame, text="Case File", font=config.Theme.FONT_H2).grid(
        row=0,
        column=0,
        columnspan=2,
        sticky="w",
        padx=padding,
        pady=(padding, padding - 5),
    )

    app.widget_refs["meta_entries"] = {}
    for i, field in enumerate(config.METADATA_USER_FIELDS):
        label = ctk.CTkLabel(
            meta_frame, text=field.title() + ":", font=config.Theme.FONT_BODY
        )
        label.grid(row=i + 1, column=0, sticky="w", padx=(padding, 10))
        entry = ctk.CTkEntry(
            meta_frame,
            textvariable=ctk.StringVar(value=""),
            corner_radius=config.Theme.CORNER_RADIUS,
            fg_color=config.Theme.BACKGROUND,
            border_color=config.Theme.SECONDARY,
        )
        entry.grid(row=i + 1, column=1, sticky="ew", pady=5, padx=(0, padding))
        entry.bind(
            "<KeyRelease>",
            lambda event, f=field: gui_callbacks.metadata_entry_callback(app, event, f),
        )
        app.widget_refs["meta_entries"][field] = weakref.ref(entry)


def _create_source_details_panel(app: "App", parent: ctk.CTkFrame):
    details_frame = _create_card_frame(parent)
    details_frame.grid_columnconfigure(0, weight=1)
    padding = config.Theme.PADDING

    ctk.CTkLabel(
        details_frame, text="Evidence Details", font=config.Theme.FONT_H2
    ).grid(row=0, column=0, sticky="w", padx=padding, pady=(padding, padding - 5))
    details_label = ctk.CTkLabel(
        details_frame,
        text="Load some evidence to see the details.",
        anchor="nw",
        justify="left",
        font=config.Theme.FONT_BODY,
        text_color=config.Theme.TEXT_SECONDARY,
    )
    details_label.grid(row=1, column=0, sticky="ew", padx=padding, pady=(0, padding))
    app.widget_refs["source_details_label"] = weakref.ref(details_label)


def _create_preset_panel(
    app: "App", parent: ctk.CTkFrame, title: str, presets: dict, widget_ref_key: str
):
    preset_frame = _create_card_frame(parent)
    padding = config.Theme.PADDING

    ctk.CTkLabel(preset_frame, text=title, font=config.Theme.FONT_H2).pack(
        anchor="w", padx=padding, pady=(padding, 5)
    )
    btn_container = ctk.CTkFrame(preset_frame, fg_color="transparent")
    btn_container.pack(fill="x", padx=padding - 5, pady=(0, padding - 5))

    cols = 3
    app.widget_refs[widget_ref_key] = {}
    for i, pid in enumerate(presets.keys()):
        btn_container.grid_columnconfigure(i % cols, weight=1)
        btn_kwargs = {
            "command": lambda p=pid: gui_callbacks.preset_button_callback(app, p),
            "font": config.Theme.FONT_BODY,
            "corner_radius": config.Theme.CORNER_RADIUS - 4,
        }
        desc = presets[pid].get("description", "")
        if desc:
            btn_kwargs["hover"] = True
        if presets[pid]["name"] == "The Job":
            button = ctk.CTkButton(
                btn_container, textvariable=app.target_mb_display_var, **btn_kwargs
            )
            button.bind(
                "<Button-3>",
                lambda event, p=pid: gui_callbacks.toggle_mb_entry_callback(app),
            )
        else:
            button = ctk.CTkButton(
                btn_container, text=presets[pid]["name"], **btn_kwargs
            )
        # Hover tooltip: update the shared hint label instead of overlaying
        # the grid (overlaying broke layout and crashed for tooltips).
        if desc:
            def _on_enter(event, d=desc):
                a11y.announce(app, d)

            button.bind("<Enter>", _on_enter, add="+")
        # Visible keyboard-focus indicator (WCAG 2.4.7).
        a11y.add_focus_ring(button)
        button.grid(
            row=i // cols, column=i % cols, sticky="ew", padx=5, pady=5, ipady=8
        )
        app.widget_refs[widget_ref_key][pid] = weakref.ref(button)


def _create_adjustments_panel(app: "App", parent: ctk.CTkFrame):
    adj_frame = _create_card_frame(parent)
    adj_frame.grid_columnconfigure(1, weight=1)
    padding = config.Theme.PADDING

    ctk.CTkLabel(adj_frame, text="Adjustments", font=config.Theme.FONT_H2).grid(
        row=0, column=0, columnspan=2, sticky="w", padx=padding, pady=(padding, 10)
    )
    _create_slider(
        app,
        adj_frame,
        "Source Material",
        list(config.SOURCE_MATERIAL_OPTIONS.items()),
        gui_callbacks.source_material_callback,
        "source_material_slider",
        "source_material_label",
        1,
    )
    _create_slider(
        app,
        adj_frame,
        "Quality",
        list(enumerate(config.Quality.LEVELS)),
        gui_callbacks.quality_slider_callback,
        "quality_level_slider",
        "quality_level_label",
        2,
    )


def _create_slider(
    app: "App",
    parent: ctk.CTkFrame,
    title: str,
    options: list,
    command: callable,
    slider_ref_key: str,
    label_ref_key: str,
    row: int,
):
    padding = config.Theme.PADDING
    ctk.CTkLabel(parent, text=title, font=config.Theme.FONT_SUBTITLE).grid(
        row=row * 2, column=0, columnspan=2, sticky="w", padx=padding, pady=(10, 2)
    )

    slider_frame = ctk.CTkFrame(parent, fg_color="transparent")
    slider_frame.grid(
        row=(row * 2) + 1,
        column=0,
        columnspan=2,
        sticky="ew",
        padx=padding,
        pady=(0, padding),
    )
    slider_frame.grid_columnconfigure(0, weight=1)

    slider = ctk.CTkSlider(
        slider_frame,
        from_=0,
        to=len(options) - 1,
        number_of_steps=len(options) - 1,
        command=lambda val, opts=options: command(app, opts[int(val)][0]),
        fg_color=config.Theme.SURFACE_LIGHT,
        progress_color=config.Theme.SECONDARY,
        button_color=config.Theme.PRIMARY,
        button_hover_color=config.Theme.PRIMARY_HOVER,
    )
    slider.grid(row=0, column=0, sticky="ew")
    app.widget_refs[slider_ref_key] = weakref.ref(slider)

    label = ctk.CTkLabel(
        slider_frame,
        text="",
        font=config.Theme.FONT_BODY,
        text_color=config.Theme.TEXT_SECONDARY,
        width=80,
        anchor="e",
    )
    label.grid(row=0, column=1, sticky="e", padx=(10, 0))
    app.widget_refs[label_ref_key] = weakref.ref(label)


def _create_options_panel(app: "App", parent: ctk.CTkFrame):
    options_frame = _create_card_frame(parent)
    padding = config.Theme.PADDING

    ctk.CTkLabel(options_frame, text="Options", font=config.Theme.FONT_H2).pack(
        anchor="w", padx=padding, pady=(padding, 5)
    )

    inner_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
    inner_frame.pack(fill="x", padx=padding, pady=(0, padding))
    inner_frame.grid_columnconfigure((0, 1), weight=1)

    # CROP
    crop_frame = ctk.CTkFrame(inner_frame, fg_color="transparent")
    crop_frame.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
    ctk.CTkLabel(crop_frame, text="Crop", font=config.Theme.FONT_SUBTITLE).pack(
        anchor="w"
    )
    crop_menu = ctk.CTkOptionMenu(
        crop_frame,
        variable=app.crop_mode_var,
        values=config.CROP_DETECT_OPTIONS,
        command=lambda choice: gui_callbacks.crop_mode_callback(app, choice),
        corner_radius=config.Theme.CORNER_RADIUS,
        fg_color=config.Theme.SURFACE_LIGHT,
        button_color=config.Theme.SECONDARY,
        button_hover_color=config.Theme.SECONDARY_HOVER,
        font=config.Theme.FONT_BODY,
        dropdown_font=config.Theme.FONT_BODY,
    )
    crop_menu.pack(fill="x", pady=(5, 0), ipady=4)
    app.widget_refs["crop_menu"] = weakref.ref(crop_menu)
    custom_crop_entry = ctk.CTkEntry(
        crop_frame,
        textvariable=app.custom_crop_var,
        placeholder_text="w:h:x:y",
        corner_radius=config.Theme.CORNER_RADIUS,
        fg_color=config.Theme.BACKGROUND,
        border_color=config.Theme.SECONDARY,
    )
    app.widget_refs["custom_crop_entry"] = weakref.ref(custom_crop_entry)
    custom_crop_entry.bind(
        "<KeyRelease>", lambda e: gui_callbacks.custom_crop_entry_callback(app)
    )

    # AUDIO & STILLS (using Checkboxes)
    checks_frame = ctk.CTkFrame(inner_frame, fg_color="transparent")
    checks_frame.grid(row=0, column=1, padx=10, sticky="nsew")
    ctk.CTkLabel(checks_frame, text="Extras", font=config.Theme.FONT_SUBTITLE).pack(
        anchor="w"
    )

    downmix_check = ctk.CTkCheckBox(
        checks_frame,
        text="Dual Audio Mixdown",
        variable=app.is_downmix_enabled,
        onvalue=True,
        offvalue=False,
        font=config.Theme.FONT_BODY,
        corner_radius=config.Theme.CORNER_RADIUS,
        fg_color=config.Theme.PRIMARY,
        hover_color=config.Theme.PRIMARY_HOVER,
    )
    downmix_check.pack(anchor="w", pady=(8, 4))
    app.widget_refs["downmix_check"] = weakref.ref(downmix_check)

    stills_check = ctk.CTkCheckBox(
        checks_frame,
        text="Generate Final Stills",
        variable=app.is_stills_enabled,
        onvalue=True,
        offvalue=False,
        font=config.Theme.FONT_BODY,
        corner_radius=config.Theme.CORNER_RADIUS,
        fg_color=config.Theme.PRIMARY,
        hover_color=config.Theme.PRIMARY_HOVER,
    )
    stills_check.pack(anchor="w", pady=4)
    app.widget_refs["stills_check"] = weakref.ref(stills_check)


def _create_special_ops_panel(app: "App", parent: ctk.CTkFrame):
    ops_frame = _create_card_frame(parent)
    padding = config.Theme.PADDING

    ctk.CTkLabel(ops_frame, text="Special Operations", font=config.Theme.FONT_H2).pack(
        anchor="w", padx=padding, pady=(padding, 5)
    )

    inner_frame = ctk.CTkFrame(ops_frame, fg_color="transparent")
    inner_frame.pack(fill="both", expand=True, padx=padding, pady=(0, padding))
    inner_frame.grid_columnconfigure(0, weight=1)

    btn_kwargs = {
        "corner_radius": config.Theme.CORNER_RADIUS,
        "font": config.Theme.FONT_BODY,
        "fg_color": "transparent",
        "border_width": 2,
        "border_color": config.Theme.SECONDARY,
        "hover_color": config.Theme.SURFACE_LIGHT,
    }

    mux_button = ctk.CTkButton(
        inner_frame,
        text="Mux Video/Audio...",
        command=lambda: gui_callbacks.mux_callback(app),
        **btn_kwargs,
    )
    mux_button.pack(fill="x", pady=4, ipady=5)
    app.widget_refs["mux_button"] = weakref.ref(mux_button)

    audio_button = ctk.CTkButton(
        inner_frame,
        text="Encode Audio Only...",
        command=lambda: gui_callbacks.audio_only_callback(app),
        **btn_kwargs,
    )
    audio_button.pack(fill="x", pady=4, ipady=5)
    app.widget_refs["audio_only_button"] = weakref.ref(audio_button)


# --- Right Panel ---
def create_preview_panel(app: "App", parent: ctk.CTkFrame):
    """Creates the preview area with canvas and a separate, professional control bar below it."""
    preview_container = ctk.CTkFrame(
        parent, fg_color=config.Theme.SURFACE, corner_radius=config.Theme.CORNER_RADIUS
    )
    preview_container.grid(
        row=0, column=0, sticky="nsew", pady=(0, config.Theme.PADDING)
    )
    preview_container.grid_rowconfigure(0, weight=1)
    preview_container.grid_columnconfigure(0, weight=1)

    canvas = ctk.CTkCanvas(
        preview_container, highlightthickness=0, background=config.Theme.BACKGROUND
    )
    canvas.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
    app.widget_refs["preview_canvas"] = weakref.ref(canvas)
    canvas.bind("<Configure>", lambda e: gui_callbacks.preview_resize_callback(app, e))

    preview_controls = ctk.CTkFrame(preview_container, fg_color="transparent")
    preview_controls.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
    preview_controls.grid_columnconfigure(1, weight=1)

    btn_kwargs = {
        "fg_color": "transparent",
        "text_color": config.Theme.TEXT_SECONDARY,
        "hover_color": config.Theme.SURFACE_LIGHT,
        "font": config.Theme.FONT_BODY,
        "corner_radius": config.Theme.CORNER_RADIUS,
    }

    prev_btn = ctk.CTkButton(
        preview_controls,
        text="◀ Previous Still",
        command=lambda: gui_callbacks.navigate_preview_callback(app, -1),
        **btn_kwargs,
    )
    prev_btn.grid(row=0, column=0, sticky="w", padx=5)
    app.widget_refs["prev_button"] = weakref.ref(prev_btn)

    reload_btn = ctk.CTkButton(
        preview_controls,
        text="Reload",
        command=lambda: gui_callbacks.reload_still_callback(app),
        fg_color=config.Theme.SECONDARY,
        hover_color=config.Theme.SECONDARY_HOVER,
        font=config.Theme.FONT_BODY,
        corner_radius=config.Theme.CORNER_RADIUS - 4,
        width=100,
    )
    reload_btn.grid(row=0, column=1, sticky="ew", padx=10)
    app.widget_refs["reload_button"] = weakref.ref(reload_btn)

    next_btn = ctk.CTkButton(
        preview_controls,
        text="Next Still ▶",
        command=lambda: gui_callbacks.navigate_preview_callback(app, 1),
        **btn_kwargs,
    )
    next_btn.grid(row=0, column=2, sticky="e", padx=5)
    app.widget_refs["next_button"] = weakref.ref(next_btn)


def create_control_panel(app: "App", parent: ctk.CTkFrame):
    control_frame = ctk.CTkFrame(parent, fg_color="transparent")
    control_frame.grid(row=1, column=0, sticky="ew", pady=(0, config.Theme.PADDING))
    control_frame.grid_columnconfigure(0, weight=1)
    padding = config.Theme.PADDING

    estimates_frame = ctk.CTkFrame(
        control_frame,
        fg_color=config.Theme.SURFACE,
        corner_radius=config.Theme.CORNER_RADIUS,
    )
    estimates_frame.pack(fill="x", pady=(0, padding), ipady=5)
    estimates_frame.grid_columnconfigure((0, 1, 2), weight=1)
    app.widget_refs["estimates_labels"] = {}

    size_label = ctk.CTkLabel(
        estimates_frame, text="Est. Size: --", font=config.Theme.FONT_BODY
    )
    size_label.grid(row=0, column=0, padx=padding)
    app.widget_refs["estimates_labels"]["size"] = weakref.ref(size_label)

    time_label = ctk.CTkLabel(
        estimates_frame, text="~Est. Time: --:--:--", font=config.Theme.FONT_BODY
    )
    time_label.grid(row=0, column=1, padx=padding)
    app.widget_refs["estimates_labels"]["time"] = weakref.ref(time_label)

    bitrate_label = ctk.CTkLabel(
        estimates_frame, text="Bitrate: --", font=config.Theme.FONT_BODY
    )
    bitrate_label.grid(row=0, column=2, padx=padding)
    app.widget_refs["estimates_labels"]["bitrate"] = weakref.ref(bitrate_label)

    action_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
    action_frame.pack(fill="x")
    action_frame.grid_columnconfigure(0, weight=2)
    action_frame.grid_columnconfigure((1, 2), weight=1)
    btn_h = 50

    develop_btn = ctk.CTkButton(
        action_frame,
        text="MAKE THE HIT",
        height=btn_h,
        font=config.Theme.FONT_BUTTON,
        command=lambda: gui_callbacks.develop_callback(app),
        corner_radius=config.Theme.CORNER_RADIUS,
        fg_color=config.Theme.PRIMARY,
        hover_color=config.Theme.PRIMARY_HOVER,
    )
    develop_btn.grid(row=0, column=0, sticky="ew", padx=(0, padding // 2))
    app.widget_refs["develop_button"] = weakref.ref(develop_btn)

    add_queue_btn = ctk.CTkButton(
        action_frame,
        text="Add to Plan",
        height=btn_h,
        command=lambda: gui_callbacks.add_to_queue_callback(app),
        font=config.Theme.FONT_BUTTON,
        fg_color=config.Theme.SECONDARY,
        hover_color=config.Theme.SECONDARY_HOVER,
        corner_radius=config.Theme.CORNER_RADIUS,
    )
    add_queue_btn.grid(row=0, column=1, sticky="ew", padx=padding // 2)
    app.widget_refs["add_queue_button"] = weakref.ref(add_queue_btn)

    cancel_btn = ctk.CTkButton(
        action_frame,
        text="CALL IT OFF",
        height=btn_h,
        command=lambda: gui_callbacks.cancel_callback(app),
        font=config.Theme.FONT_BUTTON,
        fg_color=config.Theme.ERROR,
        hover_color="#A55060",
        corner_radius=config.Theme.CORNER_RADIUS,
    )
    cancel_btn.grid(row=0, column=2, sticky="ew", padx=(padding // 2, 0))
    app.widget_refs["cancel_button"] = weakref.ref(cancel_btn)


def create_queue_panel(app: "App", parent: ctk.CTkFrame):
    queue_container = ctk.CTkFrame(
        parent, fg_color=config.Theme.SURFACE, corner_radius=config.Theme.CORNER_RADIUS
    )
    queue_container.grid(row=2, column=0, sticky="nsew")
    queue_container.grid_rowconfigure(1, weight=1)
    queue_container.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        queue_container, text="The Plan", font=config.Theme.FONT_H2, anchor="w"
    ).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=config.Theme.PADDING,
        pady=(config.Theme.PADDING, 5),
    )

    queue_frame = ctk.CTkScrollableFrame(
        queue_container, fg_color="transparent", corner_radius=0
    )
    queue_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
    queue_frame.grid_columnconfigure(0, weight=1)
    app.widget_refs["queue_frame"] = weakref.ref(queue_frame)


def update_queue_display(app: "App"):
    """Clears and redraws the batch queue UI."""
    if not (queue_frame := app._get_widget("queue_frame")):
        return
    for widget in queue_frame.winfo_children():
        widget.destroy()

    if not app.batch_queue:
        ctk.CTkLabel(
            queue_frame,
            text="The plan is empty.",
            text_color=config.Theme.TEXT_SECONDARY,
            font=config.Theme.FONT_BODY,
        ).pack(pady=20)
        return

    for i, job_item in enumerate(app.batch_queue):
        item_frame = ctk.CTkFrame(
            queue_frame,
            fg_color=config.Theme.SURFACE_LIGHT,
            corner_radius=config.Theme.CORNER_RADIUS - 4,
        )
        item_frame.pack(fill="x", padx=5, pady=4)
        item_frame.grid_columnconfigure(1, weight=1)

        title = job_item["metadata"].get("title") or os.path.basename(
            job_item["input_file"]
        )
        presets = ", ".join(
            sorted(
                [
                    p["name"]
                    for p_id, p in (
                        config.STANDARD_PRESETS
                        | config.FAST_PRESETS
                        | config.WORKFLOW_PRESETS
                    ).items()
                    if p_id
                    in (
                        job_item["selected_standard_presets"]
                        | job_item["selected_workflow_presets"]
                        | job_item["selected_fast_presets"]
                    )
                ]
            )
        )
        label_text = f"{title}"
        sub_text = f"› {presets or 'No Presets'}"

        info_frame = ctk.CTkFrame(item_frame, fg_color="transparent", cursor="hand2")
        info_frame.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        info_frame.bind(
            "<Button-1>",
            lambda e, j_id=job_item["job_id"]: gui_callbacks.reopen_job_callback(
                app, j_id
            ),
        )

        label = ctk.CTkLabel(
            info_frame, text=label_text, anchor="w", font=config.Theme.FONT_SUBTITLE
        )
        label.pack(fill="x")
        label.bind(
            "<Button-1>",
            lambda e, j_id=job_item["job_id"]: gui_callbacks.reopen_job_callback(
                app, j_id
            ),
        )

        sub_label = ctk.CTkLabel(
            info_frame,
            text=sub_text,
            anchor="w",
            font=config.Theme.FONT_SMALL,
            text_color=config.Theme.TEXT_SECONDARY,
        )
        sub_label.pack(fill="x")
        sub_label.bind(
            "<Button-1>",
            lambda e, j_id=job_item["job_id"]: gui_callbacks.reopen_job_callback(
                app, j_id
            ),
        )

        btn_kwargs = {
            "width": 30,
            "height": 30,
            "font": ("Arial", 16),
            "fg_color": "transparent",
            "hover_color": config.Theme.SURFACE,
            "text_color": config.Theme.TEXT_SECONDARY,
        }

        up_btn = ctk.CTkButton(
            item_frame,
            text="▲",
            command=lambda j_id=job_item["job_id"]: (
                gui_callbacks.move_queue_item_callback(app, j_id, -1)
            ),
            **btn_kwargs,
        )
        up_btn.grid(row=0, column=0, padx=(10, 0))
        if i == 0:
            up_btn.configure(state="disabled", text_color=config.Theme.SURFACE_LIGHT)

        down_btn = ctk.CTkButton(
            item_frame,
            text="▼",
            command=lambda j_id=job_item["job_id"]: (
                gui_callbacks.move_queue_item_callback(app, j_id, 1)
            ),
            **btn_kwargs,
        )
        down_btn.grid(row=1, column=0, padx=(10, 0))
        if i == len(app.batch_queue) - 1:
            down_btn.configure(state="disabled", text_color=config.Theme.SURFACE_LIGHT)

        remove_btn = ctk.CTkButton(
            item_frame,
            text="✕",
            width=35,
            height=35,
            fg_color="transparent",
            hover_color=config.Theme.ERROR,
            font=("Arial", 18),
            text_color=config.Theme.TEXT_SECONDARY,
            command=lambda j_id=job_item["job_id"]: (
                gui_callbacks.remove_from_queue_callback(app, j_id)
            ),
        )
        remove_btn.grid(row=0, rowspan=2, column=2, padx=10)


def create_status_bar(app: "App", parent: ctk.CTkFrame):
    """Creates the bottom status bar with message and progress."""
    parent.grid_columnconfigure(1, weight=1)
    parent.grid_columnconfigure(2, weight=1)
    padding = config.Theme.PADDING_SMALL

    version_label = ctk.CTkLabel(
        parent,
        text=f"v{config.APP_VERSION}",
        anchor="w",
        font=config.Theme.FONT_SMALL,
        text_color=config.Theme.TEXT_SECONDARY,
    )
    version_label.grid(row=0, column=0, sticky="w", padx=padding * 2)

    status_label = ctk.CTkLabel(
        parent,
        text="Waiting for orders...",
        anchor="w",
        font=config.Theme.FONT_SMALL,
        text_color=config.Theme.TEXT_SECONDARY,
    )
    status_label.grid(row=0, column=1, sticky="w", padx=padding, pady=2)
    app.widget_refs["status_label"] = weakref.ref(status_label)

    copyright_label = ctk.CTkLabel(
        parent,
        text=config.COPYRIGHT_TEXT,
        anchor="e",
        font=config.Theme.FONT_SMALL,
        text_color=config.Theme.TEXT_SECONDARY,
    )
    copyright_label.grid(row=0, column=2, sticky="e", padx=padding)

    progress_frame = ctk.CTkFrame(parent, fg_color="transparent")
    progress_frame.grid(row=0, column=3, sticky="e", padx=padding * 2, pady=2)

    app.widget_refs["progress_elapsed_label"] = ctk.CTkLabel(
        progress_frame,
        text="",
        font=config.Theme.FONT_SMALL,
        text_color=config.Theme.TEXT_SECONDARY,
    )
    app.widget_refs["progress_elapsed_label"].grid(row=0, column=0, padx=(0, 10))

    app.widget_refs["progress_eta_label"] = ctk.CTkLabel(
        progress_frame,
        text="",
        font=config.Theme.FONT_SMALL,
        text_color=config.Theme.TEXT_SECONDARY,
    )
    app.widget_refs["progress_eta_label"].grid(row=0, column=1, padx=(0, 10))

    progress_bar = ctk.CTkProgressBar(
        progress_frame,
        width=200,
        corner_radius=config.Theme.CORNER_RADIUS,
        fg_color=config.Theme.SURFACE_LIGHT,
        progress_color=config.Theme.PRIMARY,
    )
    progress_bar.set(0)
    progress_bar.grid(row=0, column=2, padx=(0, 10))
    app.widget_refs["progress_bar"] = weakref.ref(progress_bar)

    progress_text = ctk.CTkLabel(
        progress_frame,
        text="",
        width=40,
        font=config.Theme.FONT_SMALL,
        text_color=config.Theme.TEXT_SECONDARY,
    )
    progress_text.grid(row=0, column=3)
    app.widget_refs["progress_text_label"] = weakref.ref(progress_text)
