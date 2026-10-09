"""The bar along the bottom of every page: where files go, Open folder and Master.

Before and After live on the sound card, under the settings (and turn into Stop while playing);
the song being heard says so in the songs list. Esc also stops playback.
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
        """Say what Master will do: 'Master 1 song' or 'Master 4 songs' (short, so it never gets cut off)."""
        n = len(tracks)
        text = f"Master {n} song{'s' if n != 1 else ''}" if n else "Master"
        self.master_btn.configure(text=text)

    def set_where(self, fmt, folder_text):
        self.where.set(f"Saves {fmt} · {folder_text.lower() if folder_text.startswith('Same') else folder_text}")
