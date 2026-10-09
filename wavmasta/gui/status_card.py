"""The status card above the Master button: what's happening, in large type, with a glowing dot.

The dot and message are violet while working (with a magenta progress bar), green when done and
amber when something needs attention. A second, smaller line adds detail such as where files went.
"""

import tkinter as tk
from tkinter import ttk

from .theme import THEME as T
from .theme import blend, px

COLORS = {"muted": "text", "busy": "accent_soft", "ok": "ok", "warn": "warn"}
DOTS = {"muted": "muted", "busy": "accent", "ok": "ok", "warn": "warn"}
DOT = 14


class StatusCard(tk.Frame):
    def __init__(self, parent, fonts):
        super().__init__(parent, bg=T["card"], highlightthickness=1, highlightbackground=T["line"])
        self.columnconfigure(1, weight=1)
        self.dot = tk.Canvas(self, width=DOT + 8, height=DOT + 8, bg=T["card"], highlightthickness=0)
        self.dot.grid(row=0, column=0, rowspan=2, padx=(16, 0))
        self.status = tk.StringVar(value="Ready")
        self.detail = tk.StringVar(value="Drop your songs onto the window, pick a sound, then Master")
        self.kind = "muted"
        self.msg_lbl = tk.Label(
            self, textvariable=self.status, bg=T["card"], fg=T["text"], font=fonts["status"], anchor="w"
        )
        self.msg_lbl.grid(row=0, column=1, sticky="ew", padx=(12, 14), pady=(10, 0))
        self.detail_lbl = tk.Label(
            self, textvariable=self.detail, bg=T["card"], fg=T["muted"], font=fonts["body"], anchor="w"
        )
        self.detail_lbl.grid(row=1, column=1, sticky="ew", padx=(12, 14), pady=(2, 10))
        self.progress = ttk.Progressbar(
            self, mode="determinate", style="Horizontal.TProgressbar", length=px(parent, 260)
        )
        self._paint_dot()

    def _paint_dot(self):
        """A dot with a soft halo in the status colour."""
        c = T[DOTS.get(self.kind, "muted")]
        self.dot.delete("all")
        mid = (DOT + 8) / 2
        for r, t in ((DOT / 2 + 4, 0.75), (DOT / 2 + 2, 0.5), (DOT / 2, 0.0)):
            color = blend(c, T["card"], t)
            self.dot.create_oval(mid - r, mid - r, mid + r, mid + r, fill=color, outline="")

    def say(self, msg, kind="muted", detail=""):
        """Show a message. kind: muted (plain), busy, ok or warn."""
        self.kind = kind
        self.status.set(msg)
        self.detail.set(detail)
        self.msg_lbl.configure(fg=T[COLORS.get(kind, "text")])
        self._paint_dot()
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
