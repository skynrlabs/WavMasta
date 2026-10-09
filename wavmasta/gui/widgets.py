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
        self._last_need = None
        self._watch()

    def show(self, page):
        self.page = page
        self._fit()

    def _watch(self):
        """Pages grow and shrink (a song added, Check results shown); Tk doesn't announce that for a
        page held at a fixed size, so look a few times a second and re-fit when it changes."""
        try:
            need = self.needed_height()
            if need != self._last_need:
                self._last_need = need
                self._fit()
            self.after(250, self._watch)
        except tk.TclError:
            pass  # the window was closed

    def needed_height(self):
        return (self.page or self.inner).winfo_reqheight()

    def _fit(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        need = self.needed_height()
        self.scrolling = need > h + 1
        height = need if self.scrolling else h
        # the scrollbar floats over the right edge, and the page narrows only while it shows
        bar = self.scroll.winfo_reqwidth() + px(self, 6) if self.scrolling else 0
        self.canvas.itemconfigure(self._win, width=max(1, w - bar), height=max(1, height))
        self.canvas.configure(scrollregion=(0, 0, w, height))
        if self.scrolling:
            self.scroll.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")
        else:
            self.scroll.place_forget()
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


def rounded_rect(canvas, x0, y0, x1, y1, r, **kw):
    """A rounded rectangle on a canvas (a smoothed polygon with doubled corner points)."""
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]  # fmt: skip
    return canvas.create_polygon(pts, smooth=True, splinesteps=24, **kw)


class Bubble(tk.Canvas):
    """A card with rounded corners, a tinted fill and a soft violet outline. Put widgets in .inner;
    the bubble grows and shrinks to fit them."""

    def __init__(self, parent, fill=None, outline=None, radius=12, pad=(14, 10), bg=None):
        super().__init__(parent, highlightthickness=0, bd=0, bg=bg or T["card"], height=10, width=10)
        self.fill, self.outline = fill or T["bubble"], outline or T["bubble_edge"]
        self.radius, self.pad = px(self, radius), (px(self, pad[0]), px(self, pad[1]))
        self.inner = tk.Frame(self, bg=self.fill)
        self._win = self.create_window(self.pad[0], self.pad[1], window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.refit())
        self.bind("<Configure>", lambda e: self._draw())

    def refit(self):
        """Resize to the contents once Tk has laid them out (call after changing what's inside)."""
        self.after_idle(self._fit)

    def _fit(self):
        self.inner.update_idletasks()
        w = self.inner.winfo_reqwidth() + 2 * self.pad[0]
        h = self.inner.winfo_reqheight() + 2 * self.pad[1]
        self.configure(width=w, height=h)
        self._draw()

    def _draw(self):
        self.delete("shape")
        w, h = self.winfo_width(), self.winfo_height()
        if w > 2 and h > 2:
            rounded_rect(
                self, 1, 1, w - 2, h - 2, self.radius, fill=self.fill, outline=self.outline, width=1, tags="shape"
            )
            self.tag_lower("shape")
