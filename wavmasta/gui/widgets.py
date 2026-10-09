"""Small building blocks shared by the pages."""

import tkinter as tk
from tkinter import ttk

from .theme import THEME as T
from .theme import GradientLine, px


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
        length=px(parent, length),
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


class ScrollArea(ttk.Frame):
    """Holds the pages. When the window is too short for a page (small screens, or Windows display
    scaling at 125-150%), a scrollbar appears instead of the page being squashed or cut off.
    When there's room, pages fill the whole height as usual."""

    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, bg=T["bg"], highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.inner = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self._fit())
        self.inner.bind("<Configure>", lambda e: self._fit())
        self.scrolling = False
        self.page = None  # the page on screen; only its height matters

    def show(self, page):
        self.page = page
        self._fit()

    def needed_height(self):
        return (self.page or self.inner).winfo_reqheight()

    def _fit(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        need = self.needed_height()
        self.scrolling = need > h + 1
        height = need if self.scrolling else h
        self.canvas.itemconfigure(self._win, width=max(1, w), height=max(1, height))
        self.canvas.configure(scrollregion=(0, 0, w, height))
        if self.scrolling:
            self.scroll.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        else:
            self.scroll.grid_remove()
            self.canvas.yview_moveto(0)

    def wheel(self, event):
        """Scroll the page with the mouse wheel, unless the pointer is over something that scrolls itself."""
        if not self.scrolling:
            return
        w = event.widget
        try:
            if w.winfo_class() in ("Text", "Treeview", "Canvas") and w is not self.canvas:
                return
            if any(str(w).startswith(str(s)) for s in getattr(self, "skip", ())):
                return
        except (AttributeError, tk.TclError):
            return
        up = getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0
        self.canvas.yview_scroll(-3 if up else 3, "units")
