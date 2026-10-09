"""History page: the Activity table of everything Check, Before/After and Master did."""

from tkinter import ttk

from ..activity import ActivityLog
from ..widgets import card


class HistoryPage(ttk.Frame):
    def __init__(self, parent, fonts):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        c = card(self, 0, "Activity", "double-click a saved file to open its folder", grow=True)
        c.rowconfigure(1, weight=1)
        self.activity = ActivityLog(c, fonts)
        self.activity.grid(row=1, column=0, columnspan=3, sticky="nsew")
        ttk.Button(c.top, text="Clear", style="Small.TButton", command=self.activity.clear).pack(side="right")
