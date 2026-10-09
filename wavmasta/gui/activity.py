"""The Activity table on the History page: a short, readable history of what happened.

The journeys report results here (one entry per action, one line per song) instead of
showing the engine's step-by-step output, which is meant for the command line.
"""

import os
import time
import tkinter as tk
from tkinter import ttk

from .theme import THEME as T
from .theme import px


def describe(result):
    """One plain-English line about a mastered song, e.g. '-20.4 → -14.0 LUFS · notched 60 Hz'."""
    before, after = result["before"], result["after"]
    parts = [f"{before.lufs:.1f} → {after.lufs:.1f} LUFS", f"peak {after.true_peak:.1f} dBTP"]
    tones = result["info"].get("tones") or []
    if tones:
        parts.append("notched " + ", ".join(f"{f:,.0f} Hz" for f, _ in tones[:3]))
    return " · ".join(parts)


class ActivityLog:
    """A scrollable table: one expandable row per action, with a row per song underneath.

    The newest action is at the top and opened; older ones fold away so the table stays tidy.
    Double-click a mastered song to open the folder it was saved in.
    """

    COLUMNS = ("time", "result", "details", "saved")
    PLACEHOLDER = "Nothing here yet. Results from Check, Before/After and Master will show up here."

    def __init__(self, parent, fonts, on_open=None):
        self.on_open = on_open
        self.frame = tk.Frame(parent, bg=T["field"])
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(self.frame, columns=self.COLUMNS, style="Activity.Treeview", selectmode="browse")
        self.tree = tree
        tree.heading("#0", text="Action / song", anchor="w")
        tree.heading("time", text="Time", anchor="w")
        tree.heading("result", text="Result", anchor="w")
        tree.heading("details", text="Details", anchor="w")
        tree.heading("saved", text="Saved as", anchor="w")
        tree.column("#0", width=px(tree, 210), minwidth=px(tree, 140), stretch=False)
        tree.column("time", width=px(tree, 52), minwidth=px(tree, 48), stretch=False)
        tree.column("result", width=px(tree, 150), minwidth=px(tree, 110), stretch=False)
        tree.column("details", width=px(tree, 240), minwidth=px(tree, 120), stretch=True)
        tree.column("saved", width=px(tree, 170), minwidth=px(tree, 110), stretch=True)
        scroll = ttk.Scrollbar(self.frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        tree.tag_configure("action", font=fonts["btn"], foreground=T["text"])
        tree.tag_configure("song", foreground=T["text"])
        tree.tag_configure("problem", foreground=T["warn"])
        tree.tag_configure("summary", foreground=T["ok"])
        tree.tag_configure("summary_warn", foreground=T["warn"])
        tree.bind("<Double-1>", self._on_double_click)

        self._saved = {}  # row id -> full path of the saved master
        self._current = None  # the action rows are being added under
        self.empty_note = tk.Label(self.frame, text=self.PLACEHOLDER, bg=T["field"], fg=T["muted"], font=fonts["body"])
        self._placeholder()

    def grid(self, **kw):
        self.frame.grid(**kw)

    def _placeholder(self):
        self.tree.delete(*self.tree.get_children())
        self._saved.clear()
        self._current = None
        self.empty_note.place(relx=0.5, rely=0.55, anchor="center")

    def clear(self):
        self._placeholder()

    # ---- entries
    def action(self, title, detail=""):
        """Start a new action at the top of the table, e.g. 'Master 3 songs' with its settings."""
        self.empty_note.place_forget()
        for item in self.tree.get_children():
            self.tree.item(item, open=False)  # fold older actions away
        self._current = self.tree.insert(
            "", 0, text=title, values=(time.strftime("%H:%M"), "", detail, ""), open=True, tags=("action",)
        )
        self.tree.see(self._current)
        return self._current

    def _child(self, text, values, tags):
        if self._current is None:
            self.action("Activity")
        row = self.tree.insert(self._current, "end", text=text, values=values, tags=tags)
        self.tree.see(row)
        self.tree.see(self._current)
        return row

    def song(self, name, result, details="", saved=None):
        """A song that worked: what was found or done, and the file it was saved to (if any)."""
        row = self._child(name, ("", result, details, os.path.basename(saved) if saved else ""), ("song",))
        if saved:
            self._saved[row] = saved
        return row

    def problem(self, name, reason):
        return self._child(name, ("", reason, "", ""), ("problem",))

    def summary(self, label, result="", details="", good=True):
        return self._child(label, ("", result, details, ""), ("summary" if good else "summary_warn",))

    def _on_double_click(self, event):
        row = self.tree.identify_row(event.y)
        if row in self._saved and self.on_open:
            self.on_open(os.path.dirname(self._saved[row]))

    def as_text(self):
        """The table as plain text, top to bottom (for tests and copying)."""
        lines = []

        def walk(item, depth):
            values = [v for v in self.tree.item(item, "values") if v]
            lines.append("  " * depth + " | ".join([self.tree.item(item, "text"), *map(str, values)]))
            for child in self.tree.get_children(item):
                walk(child, depth + 1)

        for item in self.tree.get_children():
            walk(item, 0)
        return "\n".join(lines) or self.PLACEHOLDER


def short_path(path, keep=2):
    """Last couple of folders of a path, so messages don't wrap on long paths."""
    parts = os.path.normpath(path).split(os.sep)
    return path if len(parts) <= keep + 1 else os.sep.join(["..."] + parts[-keep:])
