"""The bar along the bottom of every page: where files go, Open folder and Master.

Before and After live on each song's row (and turn into Stop while playing), so it's always
clear which song and which version you're hearing. Esc also stops playback.
"""

import tkinter as tk
from tkinter import ttk


class ActionBar(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Card.TFrame", padding=(16, 12))
        self.columnconfigure(0, weight=1)
        self.where = tk.StringVar()
        ttk.Label(self, textvariable=self.where, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.open_btn = ttk.Button(self, text="Open folder")
        self.open_btn.grid(row=0, column=1, sticky="e", padx=(0, 10))
        self.open_btn.state(["disabled"])
        self.master_btn = ttk.Button(self, text="Master", style="Accent.TButton")
        self.master_btn.grid(row=0, column=2, sticky="e")

    def set_master_label(self, tracks):
        """Say what Master will do: 'Master 4 songs' or 'Master My Song.wav'."""
        if len(tracks) == 1:
            name = tracks[0].name
            name = name if len(name) <= 26 else name[:23] + "..."
            text = f"Master {name}"
        elif tracks:
            text = f"Master {len(tracks)} songs"
        else:
            text = "Master"
        self.master_btn.configure(text=text)

    def set_where(self, fmt, folder_text):
        self.where.set(f"Saves {fmt} · {folder_text.lower() if folder_text.startswith('Same') else folder_text}")
