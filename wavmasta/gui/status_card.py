"""The status card above the Master button: what's happening, in large type, with a colour to match.

Teal while working (with a progress bar), green when done, amber when something needs attention.
A second, smaller line adds detail such as where the files were saved.
"""

import tkinter as tk
from tkinter import ttk

from .theme import THEME as T

COLORS = {"muted": "text", "busy": "accent", "ok": "ok", "warn": "warn"}
EDGE = {"muted": "line", "busy": "accent", "ok": "ok", "warn": "warn"}


class StatusCard(tk.Frame):
    def __init__(self, parent, fonts):
        super().__init__(parent, bg=T["card"])
        self.columnconfigure(1, weight=1)
        self.edge = tk.Frame(self, bg=T["line"], width=5)
        self.edge.grid(row=0, column=0, rowspan=2, sticky="ns")
        self.status = tk.StringVar(value="Ready")
        self.detail = tk.StringVar(value="Drop your songs onto the window, pick a sound, then Master")
        self.kind = "muted"
        self.msg_lbl = tk.Label(
            self, textvariable=self.status, bg=T["card"], fg=T["text"], font=fonts["status"], anchor="w"
        )
        self.msg_lbl.grid(row=0, column=1, sticky="ew", padx=(14, 14), pady=(10, 0))
        self.detail_lbl = tk.Label(
            self, textvariable=self.detail, bg=T["card"], fg=T["muted"], font=fonts["body"], anchor="w"
        )
        self.detail_lbl.grid(row=1, column=1, sticky="ew", padx=(14, 14), pady=(2, 10))
        self.progress = ttk.Progressbar(self, mode="determinate", style="Horizontal.TProgressbar", length=260)

    def say(self, msg, kind="muted", detail=""):
        """Show a message. kind: muted (plain), busy, ok or warn."""
        self.kind = kind
        self.status.set(msg)
        self.detail.set(detail)
        self.msg_lbl.configure(fg=T[COLORS.get(kind, "text")])
        self.edge.configure(bg=T[EDGE.get(kind, "line")])
        if kind != "busy":
            self.stop_progress()

    # ---- progress (only visible while working)
    def start_progress(self, maximum):
        self.progress.configure(maximum=maximum, value=0)
        self.progress.grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 16))

    def set_progress(self, value):
        self.progress.configure(value=value)

    def stop_progress(self):
        self.progress.grid_remove()
