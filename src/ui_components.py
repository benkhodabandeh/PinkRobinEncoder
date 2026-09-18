# ui_components.py
"""
Contains reusable, themed custom UI components (dialogs, etc.) for Pink Robin Encoder.
This helps to keep the main application logic and other GUI modules clean.
"""

import logging
import os
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

import config
import utils

logger = logging.getLogger(__name__)


class InputDialog(ctk.CTkToplevel):
    """A simple, themed dialog for getting user text input."""

    def __init__(self, parent, title: str, prompt: str, initial_value: str = ""):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title(title)
        self.result = None

        self.configure(fg_color=config.Theme.BACKGROUND)
        self.resizable(False, False)

        if hasattr(parent, "icon_path") and parent.icon_path:
            try:
                self.after(200, lambda: self.iconbitmap(parent.icon_path))
            except Exception:
                logger.debug("Dialog icon could not be set; continuing without it.")

        ctk.CTkLabel(self, text=prompt, font=config.Theme.FONT_BODY).pack(
            padx=20, pady=(20, 10)
        )
        self.entry = ctk.CTkEntry(
            self, font=config.Theme.FONT_BODY, corner_radius=config.Theme.CORNER_RADIUS
        )
        self.entry.pack(padx=20, pady=10, fill="x")
        self.entry.insert(0, initial_value)
        self.entry.focus()
        self.bind("<Return>", self._ok_event)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=20, pady=20)

        ok_button = ctk.CTkButton(
            btn_frame,
            text="OK",
            command=self._ok_event,
            fg_color=config.Theme.PRIMARY,
            hover_color=config.Theme.PRIMARY_HOVER,
        )
        ok_button.pack(side="left", padx=5)

        cancel_button = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self._cancel_event,
            fg_color=config.Theme.SECONDARY,
            hover_color=config.Theme.SECONDARY_HOVER,
        )
        cancel_button.pack(side="left", padx=5)

        self.after(100, self.lift)

    def _ok_event(self, event=None):
        self.result = self.entry.get()
        self.grab_release()
        self.destroy()

    def _cancel_event(self, event=None):
        self.result = None
        self.grab_release()
        self.destroy()

    @staticmethod
    def get_input(parent, title: str, prompt: str, initial_value: str = ""):
        dialog = InputDialog(parent, title, prompt, initial_value)
        parent.wait_window(dialog)
        return dialog.result


class CompletionDialog(ctk.CTkToplevel):
    """A themed dialog to show a professional summary upon task completion."""

    def __init__(
        self,
        parent,
        title_str: str,
        message_details: str,
        output_path: str,
        actual_time: float,
        estimated_time: float,
    ):
        super().__init__(parent)
        self.output_path = output_path
        self.transient(parent)
        self.grab_set()

        self.title(title_str)
        self.geometry("450x340")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close_dialog)
        self.configure(fg_color=config.Theme.BACKGROUND)
        self.attributes("-topmost", True)

        if hasattr(parent, "icon_path") and parent.icon_path:
            self.after(200, lambda: self.iconbitmap(parent.icon_path))

        padding = config.Theme.PADDING
        ctk.CTkLabel(self, text="Development Complete", font=config.Theme.FONT_H1).pack(
            pady=(padding, padding)
        )

        ctk.CTkLabel(
            self,
            text=message_details,
            wraplength=400,
            justify="left",
            anchor="w",
            font=config.Theme.FONT_BODY,
        ).pack(pady=(0, padding), padx=padding, anchor="w")

        time_frame = ctk.CTkFrame(
            self,
            fg_color=config.Theme.SURFACE,
            corner_radius=config.Theme.CORNER_RADIUS,
        )
        time_frame.pack(pady=5, padx=padding, fill="x")
        time_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            time_frame, text="Actual Time:", font=config.Theme.FONT_SUBTITLE
        ).grid(row=0, column=0, padx=padding, pady=(5, 0), sticky="w")
        ctk.CTkLabel(
            time_frame, text=utils._format_eta(actual_time), font=config.Theme.FONT_BODY
        ).grid(row=0, column=1, padx=padding, pady=(5, 0), sticky="e")
        ctk.CTkLabel(
            time_frame, text="Estimated Time:", font=config.Theme.FONT_SUBTITLE
        ).grid(row=1, column=0, padx=padding, pady=(0, 5), sticky="w")
        ctk.CTkLabel(
            time_frame,
            text=f"~{utils._format_eta(estimated_time)}",
            font=config.Theme.FONT_BODY,
        ).grid(row=1, column=1, padx=padding, pady=(0, 5), sticky="e")

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=padding, fill="x", side="bottom")
        button_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            button_frame,
            text="Open Output Folder",
            command=self.open_folder,
            font=config.Theme.FONT_BUTTON,
            fg_color=config.Theme.PRIMARY,
            hover_color=config.Theme.PRIMARY_HOVER,
        ).grid(
            row=0,
            column=0,
            padx=(padding, padding // 2),
            pady=padding,
            sticky="ew",
            ipady=4,
        )
        ctk.CTkButton(
            button_frame,
            text="OK",
            command=self.close_dialog,
            font=config.Theme.FONT_BUTTON,
            fg_color=config.Theme.SECONDARY,
            hover_color=config.Theme.SECONDARY_HOVER,
        ).grid(
            row=0,
            column=1,
            padx=(padding // 2, padding),
            pady=padding,
            sticky="ew",
            ipady=4,
        )

        self.after(100, self.lift)

    def open_folder(self):
        try:
            if os.path.exists(self.output_path):
                webbrowser.open(os.path.realpath(self.output_path))
            else:
                messagebox.showwarning(
                    "Path Not Found",
                    f"Could not find path: {self.output_path}",
                    parent=self,
                )
        except Exception as e:
            logger.error(f"Failed to open output folder: {e}")
        self.close_dialog()

    def close_dialog(self):
        self.grab_release()
        self.destroy()


class UpdateDialog(ctk.CTkToplevel):
    """A themed dialog to prompt the user about a new software version."""

    def __init__(self, parent, update_info: dict):
        super().__init__(parent)
        self.parent_app = parent
        self.update_info = update_info
        self.result = "remind"

        self.transient(parent)
        self.grab_set()
        self.title("Update Available")
        self.geometry("480x250")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close_dialog)
        self.configure(fg_color=config.Theme.BACKGROUND)
        self.attributes("-topmost", True)

        if hasattr(parent, "icon_path") and parent.icon_path:
            self.after(200, lambda: self.iconbitmap(parent.icon_path))

        padding = config.Theme.PADDING
        ctk.CTkLabel(
            self, text="🚀 New Version Available!", font=config.Theme.FONT_H1
        ).pack(pady=(padding, padding))

        message = (
            f"A new version of {config.APP_NAME} is ready for you.\n\n"
            f"  Your Version: {config.APP_VERSION}\n"
            f"  Latest Version: {self.update_info.get('latest_version', 'N/A')}"
        )
        ctk.CTkLabel(
            self,
            text=message,
            wraplength=420,
            justify="left",
            font=config.Theme.FONT_BODY,
        ).pack(pady=padding, padx=padding * 2)

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=padding, fill="x", side="bottom")
        button_frame.grid_columnconfigure((0, 1, 2), weight=1)

        dl_btn = ctk.CTkButton(
            button_frame,
            text="Download Now",
            command=self._download,
            font=config.Theme.FONT_BUTTON,
            fg_color=config.Theme.SUCCESS,
        )
        dl_btn.grid(
            row=0, column=0, padx=(padding, padding // 2), pady=padding, sticky="ew"
        )

        remind_btn = ctk.CTkButton(
            button_frame,
            text="Remind Me Later",
            command=self._remind,
            font=config.Theme.FONT_BUTTON,
            fg_color=config.Theme.SECONDARY,
            hover_color=config.Theme.SECONDARY_HOVER,
        )
        remind_btn.grid(row=0, column=1, padx=padding // 2, pady=padding, sticky="ew")

        skip_btn = ctk.CTkButton(
            button_frame,
            text="Skip This Version",
            command=self._skip,
            font=config.Theme.FONT_BODY,
            fg_color="transparent",
            text_color=config.Theme.TEXT_SECONDARY,
            hover=False,
        )
        skip_btn.grid(
            row=0, column=2, padx=(padding // 2, padding), pady=padding, sticky="ew"
        )

        self.after(100, self.lift)

    def _download(self):
        try:
            webbrowser.open(self.update_info.get("download_url"), new=2)
            self.result = "downloaded"
        except Exception as e:
            logger.error(f"Failed to open download URL: {e}")
        self.close_dialog()

    def _remind(self):
        self.result = "remind"
        self.close_dialog()

    def _skip(self):
        self.result = "skip"
        self.close_dialog()

    def close_dialog(self):
        self.grab_release()
        self.destroy()

    @staticmethod
    def show(parent, update_info: dict) -> str:
        """Shows the dialog and returns the user's choice."""
        dialog = UpdateDialog(parent, update_info)
        parent.wait_window(dialog)
        return dialog.result
