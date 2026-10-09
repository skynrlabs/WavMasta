"""Left-hand navigation: brand, one entry per page, version footer."""

import tkinter as tk
import webbrowser

from .. import __version__
from ..config import SUPPORT_URL
from .theme import THEME as T


class Sidebar(tk.Frame):
    def __init__(self, parent, pages, on_select, fonts, logo=None):
        super().__init__(parent, bg=T["side"], width=196)
        self.grid_propagate(False)
        self.pack_propagate(False)
        self.current = None
        self.items = {}

        brand = tk.Frame(self, bg=T["side"])
        brand.pack(fill="x", padx=18, pady=(18, 22))
        if logo is not None:
            tk.Label(brand, image=logo, bg=T["side"]).pack(side="left", padx=(0, 10))
        tk.Label(brand, text="WavMasta", bg=T["side"], fg=T["text"], font=fonts["brand"]).pack(side="left")

        for key, text in pages:
            frame = tk.Frame(self, bg=T["side"], cursor="hand2")
            frame.pack(fill="x")
            bar = tk.Frame(frame, bg=T["side"], width=4)
            bar.pack(side="left", fill="y")
            label = tk.Label(
                frame,
                text=text,
                bg=T["side"],
                fg=T["muted"],
                font=fonts["nav"],
                anchor="w",
                padx=18,
                pady=10,
                cursor="hand2",
            )
            label.pack(side="left", fill="x", expand=True)
            self.items[key] = (bar, label, frame)
            for w in (frame, label):
                w.bind("<Button-1>", lambda e, k=key: on_select(k))
                w.bind("<Enter>", lambda e, k=key: self._paint(k, hover=True))
                w.bind("<Leave>", lambda e, k=key: self._paint(k))

        foot = tk.Frame(self, bg=T["side"])
        foot.pack(side="bottom", fill="x", padx=18, pady=14)
        self.support = tk.Label(
            foot, text="Support WavMasta", bg=T["side"], fg=T["accent"], font=fonts["btn"], cursor="hand2"
        )
        self.support.pack(anchor="w", pady=(0, 6))
        self.support.bind("<Button-1>", lambda e: webbrowser.open(SUPPORT_URL))
        self.support.bind("<Enter>", lambda e: self.support.configure(fg=T["accent_hover"]))
        self.support.bind("<Leave>", lambda e: self.support.configure(fg=T["accent"]))
        tk.Label(
            foot,
            text="Free and open source.\nIf it saves you time,\nconsider chipping in.",
            bg=T["side"],
            fg=T["muted"],
            font=fonts["small"],
            justify="left",
        ).pack(anchor="w", pady=(0, 10))
        tk.Label(foot, text=f"v{__version__}  ·  Skynr Labs", bg=T["side"], fg=T["muted"], font=fonts["small"]).pack(
            anchor="w"
        )

    def _paint(self, key, hover=False):
        bar, label, frame = self.items[key]
        active = self.current == key
        bg = T["side_active"] if active else T["side_hover"] if hover else T["side"]
        frame.configure(bg=bg)
        label.configure(bg=bg, fg=T["text"] if active or hover else T["muted"])
        bar.configure(bg=T["accent"] if active else bg)

    def set_active(self, key):
        self.current = key
        for k in self.items:
            self._paint(k)

    def set_label(self, key, text):
        self.items[key][1].configure(text=text)
