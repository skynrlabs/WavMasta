"""About dialog."""

import tkinter as tk
import webbrowser
from tkinter import ttk

from .. import __version__
from ..config import REPO_URL, SUPPORT_URL
from .theme import THEME as T


def show_about(root, fonts, logo=None):
    F = fonts
    win = tk.Toplevel(root)
    win.title("About WavMasta")
    win.configure(bg=T["card"])
    win.resizable(False, False)
    win.transient(root)
    box = tk.Frame(win, bg=T["card"], padx=28, pady=22)
    box.pack()
    if logo is not None:
        tk.Label(box, image=logo, bg=T["card"]).pack()
    tk.Label(box, text="WavMasta", bg=T["card"], fg=T["text"], font=F["title"]).pack(pady=(10, 0))
    tk.Label(box, text=f"Version {__version__}", bg=T["card"], fg=T["muted"], font=F["body"]).pack()
    tk.Label(
        box, text="Clean up and master your songs, ready for release.", bg=T["card"], fg=T["text"], font=F["body"]
    ).pack(pady=(12, 0))
    tk.Label(box, text="© 2026 Skynr Labs  ·  MIT License", bg=T["card"], fg=T["muted"], font=F["small"]).pack(
        pady=(4, 14)
    )
    row = tk.Frame(box, bg=T["card"])
    row.pack()
    support = ttk.Button(
        row, text="Support WavMasta", style="Accent.TButton", command=lambda: webbrowser.open(SUPPORT_URL)
    )
    support.pack(side="left", padx=4)
    ttk.Button(row, text="GitHub", command=lambda: webbrowser.open(REPO_URL)).pack(side="left", padx=4)
    ttk.Button(row, text="Close", command=win.destroy).pack(side="left", padx=4)
    win.bind("<Escape>", lambda e: win.destroy())
    win.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - win.winfo_width()) // 2
    y = root.winfo_rooty() + (root.winfo_height() - win.winfo_height()) // 3
    win.geometry(f"+{x}+{y}")
    win.grab_set()
    return win
