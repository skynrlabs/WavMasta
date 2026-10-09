"""Small building blocks shared by the pages."""

import tkinter as tk
from tkinter import ttk

from .theme import THEME as T


def card(parent, row, title, hint=None, grow=False):
    """A rounded-look panel with a bold title and an optional grey hint."""
    c = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
    c.grid(row=row, column=0, sticky="nsew", pady=(0, 12))
    if grow:
        parent.rowconfigure(row, weight=1)
    c.columnconfigure(1, weight=1)
    top = ttk.Frame(c, style="Card.TFrame")
    top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
    ttk.Label(top, text=title, style="Head.TLabel").pack(side="left")
    if hint:
        ttk.Label(top, text=hint, style="Muted.TLabel").pack(side="left", padx=(10, 0))
    c.top = top  # the title row, so a page can add a small button on the right
    return c


def slider(parent, var, lo, hi, step, command=None, length=260):
    return tk.Scale(
        parent,
        from_=lo,
        to=hi,
        resolution=step,
        variable=var,
        orient="horizontal",
        length=length,
        showvalue=False,
        command=command,
        bg=T["accent"],
        activebackground=T["accent_hover"],
        troughcolor=T["field"],
        highlightthickness=0,
        bd=0,
        sliderrelief="flat",
        sliderlength=18,
        width=10,
    )
