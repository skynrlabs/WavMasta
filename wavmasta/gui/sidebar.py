"""Left-hand navigation: brand, one entry per page, Support link and version at the bottom.
The open page gets a violet-to-magenta marker, and a thin gradient edge separates the sidebar
from the page."""

import tkinter as tk
import webbrowser

from .. import __version__
from ..config import SUPPORT_URL
from .theme import THEME as T
from .theme import GradientLine, px


class Sidebar(tk.Frame):
    def __init__(self, parent, pages, on_select, fonts, logo=None):
        super().__init__(parent, bg=T["bar"])
        self.current = None
        self.items = {}
        self.rowconfigure(0, weight=1)

        body = tk.Frame(self, bg=T["bar"], width=px(self, 200))
        body.grid(row=0, column=0, sticky="ns")
        body.pack_propagate(False)
        GradientLine(self, height=2, vertical=True, bg=T["bar"]).grid(row=0, column=1, sticky="ns")

        brand = tk.Frame(body, bg=T["bar"])
        brand.pack(fill="x", padx=18, pady=(20, 24))
        if logo is not None:
            tk.Label(brand, image=logo, bg=T["bar"]).pack(side="left", padx=(0, 10))
        tk.Label(brand, text="WavMasta", bg=T["bar"], fg=T["text"], font=fonts["brand"]).pack(side="left")

        for key, text in pages:
            row = tk.Frame(body, bg=T["bar"], cursor="hand2")
            row.pack(fill="x", padx=(10, 12), pady=1)
            marker = GradientLine(row, height=4, vertical=True, bg=T["bar"])
            marker.pack(side="left", fill="y")
            label = tk.Label(row, text=text, bg=T["bar"], fg=T["muted"], font=fonts["nav"], anchor="w", padx=14, pady=9)
            label.pack(side="left", fill="x", expand=True)
            self.items[key] = (marker, label, row)
            for w in (row, label):
                w.bind("<Button-1>", lambda e, k=key: on_select(k))
                w.bind("<Enter>", lambda e, k=key: self._paint(k, hover=True))
                w.bind("<Leave>", lambda e, k=key: self._paint(k))

        foot = tk.Frame(body, bg=T["bar"])
        foot.pack(side="bottom", fill="x", padx=18, pady=16)
        self.support = tk.Label(
            foot, text="♥  Support WavMasta", bg=T["bar"], fg=T["accent2"], font=fonts["btn"], cursor="hand2"
        )
        self.support.pack(anchor="w", pady=(0, 6))
        self.support.bind("<Button-1>", lambda e: webbrowser.open(SUPPORT_URL))
        self.support.bind("<Enter>", lambda e: self.support.configure(fg=T["text"]))
        self.support.bind("<Leave>", lambda e: self.support.configure(fg=T["accent2"]))
        tk.Label(
            foot,
            text="Free and open source.\nIf it saves you time,\nconsider chipping in.",
            bg=T["bar"],
            fg=T["muted"],
            font=fonts["small"],
            justify="left",
        ).pack(anchor="w", pady=(0, 10))
        tk.Label(foot, text=f"v{__version__}  ·  Skynr Labs", bg=T["bar"], fg=T["muted"], font=fonts["small"]).pack(
            anchor="w"
        )

    def _paint(self, key, hover=False):
        marker, label, row = self.items[key]
        active = self.current == key
        bg = T["sel"] if active else T["card"] if hover else T["bar"]
        for w in (row, label):
            w.configure(bg=bg)
        label.configure(fg=T["text"] if active or hover else T["muted"])
        if active:
            marker.pack(side="left", fill="y", before=label)
        else:
            marker.pack_forget()

    def set_active(self, key):
        self.current = key
        for k in self.items:
            self._paint(k)

    def set_label(self, key, text):
        self.items[key][1].configure(text=text)
