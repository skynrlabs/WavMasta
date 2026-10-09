"""The bar across the top: brand, one tab per page, and Support / version on the right.
A violet-to-magenta line runs underneath, and the open tab is underlined in magenta."""

import tkinter as tk
import webbrowser

from .. import __version__
from ..config import SUPPORT_URL
from .theme import THEME as T
from .theme import GradientLine


class TopBar(tk.Frame):
    def __init__(self, parent, pages, on_select, fonts, logo=None):
        super().__init__(parent, bg=T["bar"])
        self.current = None
        self.items = {}
        self.columnconfigure(2, weight=1)

        brand = tk.Frame(self, bg=T["bar"])
        brand.grid(row=0, column=0, sticky="w", padx=(20, 28), pady=(10, 0))
        if logo is not None:
            tk.Label(brand, image=logo, bg=T["bar"]).pack(side="left", padx=(0, 10))
        tk.Label(brand, text="WavMasta", bg=T["bar"], fg=T["text"], font=fonts["brand"]).pack(side="left")

        tabs = tk.Frame(self, bg=T["bar"])
        tabs.grid(row=0, column=1, sticky="sw")
        for key, text in pages:
            tab = tk.Frame(tabs, bg=T["bar"], cursor="hand2")
            tab.pack(side="left", padx=(0, 4))
            label = tk.Label(
                tab, text=text, bg=T["bar"], fg=T["muted"], font=fonts["nav"], padx=14, pady=10, cursor="hand2"
            )
            label.pack()
            line = tk.Frame(tab, bg=T["bar"], height=3)
            line.pack(fill="x")
            self.items[key] = (line, label, tab)
            for w in (tab, label):
                w.bind("<Button-1>", lambda e, k=key: on_select(k))
                w.bind("<Enter>", lambda e, k=key: self._paint(k, hover=True))
                w.bind("<Leave>", lambda e, k=key: self._paint(k))

        right = tk.Frame(self, bg=T["bar"])
        right.grid(row=0, column=3, sticky="e", padx=(0, 20), pady=(10, 0))
        self.support = tk.Label(
            right, text="♥  Support WavMasta", bg=T["bar"], fg=T["accent2"], font=fonts["btn"], cursor="hand2"
        )
        self.support.pack(side="left", padx=(0, 16))
        self.support.bind("<Button-1>", lambda e: webbrowser.open(SUPPORT_URL))
        self.support.bind("<Enter>", lambda e: self.support.configure(fg=T["text"]))
        self.support.bind("<Leave>", lambda e: self.support.configure(fg=T["accent2"]))
        tk.Label(right, text=f"v{__version__} · Skynr Labs", bg=T["bar"], fg=T["muted"], font=fonts["small"]).pack(
            side="left"
        )

        GradientLine(self, height=2, bg=T["bar"]).grid(row=1, column=0, columnspan=4, sticky="ew")

    def _paint(self, key, hover=False):
        line, label, _ = self.items[key]
        active = self.current == key
        label.configure(fg=T["text"] if active or hover else T["muted"])
        line.configure(bg=T["accent2"] if active else T["line_hover"] if hover else T["bar"])

    def set_active(self, key):
        self.current = key
        for k in self.items:
            self._paint(k)

    def set_label(self, key, text):
        self.items[key][1].configure(text=text)
