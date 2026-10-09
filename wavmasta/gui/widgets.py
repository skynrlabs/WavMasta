"""Small building blocks shared by the pages."""

import tkinter as tk
from tkinter import ttk

from .theme import THEME as T
from .theme import GradientLine


def title_row(parent, title, hint=None, upper=True):
    """A card's title: a short violet-to-magenta mark, the title, and an optional grey hint.
    Returns the row, so a page can add small buttons on the right."""
    top = ttk.Frame(parent, style="Inner.TFrame")
    GradientLine(top, height=4, vertical=True, bg=T["card"]).pack(side="left", padx=(0, 10))
    text = title.upper() if upper else title
    label = ttk.Label(top, text=text, style="Head.TLabel")
    label.pack(side="left")
    top.label = label
    if hint:
        ttk.Label(top, text=hint, style="Muted.TLabel").pack(side="left", padx=(12, 0))
    return top


def card(parent, row, title, hint=None, grow=False):
    """A bordered panel with a title row and an optional grey hint."""
    c = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
    c.grid(row=row, column=0, sticky="nsew", pady=(0, 12))
    if grow:
        parent.rowconfigure(row, weight=1)
    c.columnconfigure(1, weight=1)
    top = title_row(c, title, hint)
    top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
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
        activebackground=T["accent2"],
        troughcolor=T["field"],
        highlightthickness=0,
        bd=0,
        sliderrelief="flat",
        sliderlength=18,
        width=10,
    )
