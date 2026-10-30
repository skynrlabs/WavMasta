"""About dialog, and the open-source licenses window it opens."""

import tkinter as tk
import webbrowser
from tkinter import ttk

from .. import __version__, licenses
from ..config import REPO_URL
from .theme import THEME as T
from .theme import px


def _centre(win, root, third=True):
    win.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - win.winfo_width()) // 2
    y = root.winfo_rooty() + (root.winfo_height() - win.winfo_height()) // (3 if third else 2)
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")


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
        pady=(4, 0)
    )
    tk.Label(
        box,
        text="The Windows app includes pedalboard (GPL v3), so it's shared under the GPL v3.",
        bg=T["card"],
        fg=T["muted"],
        font=F["small"],
    ).pack(pady=(0, 14))
    row = tk.Frame(box, bg=T["card"])
    row.pack()
    ttk.Button(row, text="GitHub", command=lambda: webbrowser.open(REPO_URL)).pack(side="left", padx=4)
    ttk.Button(row, text="Open-source licenses", command=lambda: show_licenses(win, fonts)).pack(side="left", padx=4)
    ttk.Button(row, text="Close", command=win.destroy).pack(side="left", padx=4)
    win.bind("<Escape>", lambda e: win.destroy())
    _centre(win, root)
    win.grab_set()
    return win


def show_licenses(parent, fonts):
    """The libraries WavMasta is built on and their licenses, in a scrollable window."""
    win = tk.Toplevel(parent)
    win.title("Open-source licenses")
    win.configure(bg=T["card"])
    win.transient(parent)
    win.minsize(px(win, 420), px(win, 300))
    box = tk.Frame(win, bg=T["card"], padx=16, pady=14)
    box.pack(fill="both", expand=True)
    box.columnconfigure(0, weight=1)
    box.rowconfigure(0, weight=1)
    text = tk.Text(
        box,
        bg=T["field"],
        fg=T["text"],
        relief="flat",
        highlightthickness=0,
        wrap="word",
        font="TkFixedFont",
        width=100,
        height=30,
        padx=12,
        pady=8,
        insertbackground=T["text"],
        selectbackground=T["sel"],
    )
    scroll = ttk.Scrollbar(box, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")
    text.insert("1.0", licenses.dialog_text())
    text.configure(state="disabled")  # read-only, but text can still be selected and copied
    had_grab = parent.grab_current() is parent

    def close():
        win.destroy()
        if had_grab and parent.winfo_exists():
            parent.grab_set()  # back to the About box, which keeps the main window waiting

    ttk.Button(box, text="Close", command=close).grid(row=1, column=0, columnspan=2, sticky="e", pady=(12, 0))
    win.protocol("WM_DELETE_WINDOW", close)
    win.bind("<Escape>", lambda e: close())
    _centre(win, parent, third=False)
    win.grab_set()
    win.text = text  # for the tests
    return win
