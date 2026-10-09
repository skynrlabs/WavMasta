"""Colours, fonts and ttk styles: 'Night violet', electric violet and magenta on deep navy."""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

THEME = {
    "bg": "#12121f",  # window
    "card": "#1c1c30",  # panels
    "field": "#0f0f1c",  # lists, inputs, sliders' tracks
    "line": "#2c2c48",  # borders and plain buttons
    "line_hover": "#3b3b60",
    "text": "#ececf6",
    "muted": "#9a9ab8",
    "accent": "#8b5cf6",  # violet: main buttons, active tab, slider thumbs
    "accent_hover": "#a07bff",
    "accent_soft": "#b9a2ff",  # violet for text on dark (easier to read than the full accent)
    "accent_text": "#ffffff",
    "accent2": "#ec4899",  # magenta: the far end of every gradient, highlights
    "ok": "#34d399",
    "warn": "#fbbf24",
    "sel": "#2a2350",  # selected row
    "bar": "#0d0d18",  # sidebar
    "bubble": "#241f45",  # Check results bubble: a violet tint over the panels
    "bubble_edge": "#4b3a8c",
    "bad": "#f87171",  # clipping: something mastering can't fix
}


def px(widget, n):
    """n pixels at 100% display scaling, grown to match Windows scaling (125%, 150%...),
    so fixed sizes keep pace with the text."""
    return int(round(n * float(widget.tk.call("tk", "scaling")) / (96 / 72)))


def blend(c1, c2, t):
    """Mix two #rrggbb colours: t=0 gives c1, t=1 gives c2."""
    a = [int(c1[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b, strict=True))


class GradientLine(tk.Canvas):
    """A thin violet-to-magenta stripe that stretches to fill its space."""

    def __init__(self, parent, height=2, vertical=False, bg=None, steps=64):
        super().__init__(parent, height=height, highlightthickness=0, bd=0, bg=bg or THEME["bg"])
        self.vertical, self.steps = vertical, steps
        if vertical:
            self.configure(width=height, height=18)
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        length = h if self.vertical else w
        n = max(1, min(self.steps, length))
        for i in range(n):
            color = blend(THEME["accent"], THEME["accent2"], i / max(1, n - 1))
            a, b = length * i / n, length * (i + 1) / n + 1
            if self.vertical:
                self.create_rectangle(0, a, w, b, fill=color, outline="")
            else:
                self.create_rectangle(a, 0, b, h, fill=color, outline="")


def make_fonts():
    families = set(tkfont.families())
    family = next(
        (f for f in ("Segoe UI", "Inter", "Helvetica Neue", "DejaVu Sans") if f in families),
        tkfont.nametofont("TkDefaultFont").actual("family"),
    )
    return {
        "title": (family, 20, "bold"),
        "brand": (family, 15, "bold"),
        "sub": (family, 10),
        "h": (family, 10, "bold"),
        "body": (family, 10),
        "small": (family, 9),
        "btn": (family, 10, "bold"),
        "big": (family, 12, "bold"),
        "status": (family, 13, "bold"),
        "nav": (family, 11, "bold"),
        "mono": ("Consolas" if "Consolas" in families else "DejaVu Sans Mono", 9),
    }


def apply_styles(root, F):
    T = THEME
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(
        ".",
        background=T["bg"],
        foreground=T["text"],
        font=F["body"],
        bordercolor=T["line"],
        lightcolor=T["line"],
        darkcolor=T["line"],
        troughcolor=T["field"],
        fieldbackground=T["field"],
        focuscolor=T["accent"],
        selectbackground=T["accent"],
        selectforeground=T["accent_text"],
        insertcolor=T["text"],
    )
    st.configure("TFrame", background=T["bg"])
    # panels: a hairline border instead of a flat block
    st.configure(
        "Card.TFrame",
        background=T["card"],
        relief="solid",
        borderwidth=1,
        bordercolor=T["line"],
        lightcolor=T["line"],
        darkcolor=T["line"],
    )
    st.configure("Inner.TFrame", background=T["card"], relief="flat", borderwidth=0)
    st.configure("TLabel", background=T["bg"], foreground=T["text"])
    st.configure("Card.TLabel", background=T["card"])
    st.configure("Muted.TLabel", background=T["card"], foreground=T["muted"], font=F["small"])
    st.configure("Head.TLabel", background=T["card"], foreground=T["text"], font=F["h"])
    st.configure("Lock.TLabel", background=T["card"], foreground=T["accent2"], font=F["small"])
    st.configure("Section.TLabel", background=T["card"], foreground=T["accent_soft"], font=F["small"])
    st.configure("Title.TLabel", font=F["title"])
    st.configure("Sub.TLabel", foreground=T["muted"], font=F["sub"])
    st.configure("Value.TLabel", background=T["card"], foreground=T["accent_soft"], font=F["btn"])
    st.configure(
        "TButton",
        background=T["line"],
        foreground=T["text"],
        font=F["btn"],
        borderwidth=0,
        padding=(12, 6),
        lightcolor=T["line"],
        darkcolor=T["line"],
    )
    st.map(
        "TButton",
        background=[("active", T["line_hover"]), ("disabled", T["card"])],
        foreground=[("disabled", T["muted"])],
    )
    st.configure("Small.TButton", font=F["small"], padding=(10, 3))
    st.configure(
        "Accent.TButton",
        background=T["accent"],
        foreground=T["accent_text"],
        font=F["big"],
        padding=(20, 10),
        lightcolor=T["accent"],
        darkcolor=T["accent"],
    )
    st.map(
        "Accent.TButton",
        background=[("active", T["accent_hover"]), ("disabled", T["line"])],
        foreground=[("disabled", T["muted"])],
    )
    st.configure(
        "Pink.TButton",
        background=T["accent2"],
        foreground=T["accent_text"],
        font=F["small"],
        padding=(10, 3),
        lightcolor=T["accent2"],
        darkcolor=T["accent2"],
    )
    st.map(
        "Pink.TButton",
        background=[("active", "#f472b6"), ("disabled", T["line"])],
        foreground=[("disabled", T["muted"])],
    )
    st.configure(
        "TCheckbutton",
        background=T["card"],
        foreground=T["text"],
        indicatorbackground=T["field"],
        indicatorforeground=T["accent_text"],
        indicatormargin=4,
    )
    st.configure("Card.TCheckbutton", font=F["btn"])
    st.map(
        "TCheckbutton",
        background=[("active", T["card"])],
        indicatorbackground=[("selected", T["accent"]), ("active", T["line"])],
        indicatorforeground=[("selected", T["accent_text"])],
    )
    for w in ("TCombobox", "TSpinbox", "TEntry"):
        st.configure(
            w,
            fieldbackground=T["field"],
            background=T["line"],
            foreground=T["text"],
            arrowcolor=T["accent_soft"],
            padding=5,
        )
        st.map(
            w,
            fieldbackground=[("disabled", T["card"]), ("readonly", T["field"])],  # disabled first: it wins
            foreground=[("disabled", T["muted"]), ("readonly", T["text"])],
            arrowcolor=[("disabled", T["line_hover"])],
            selectbackground=[("readonly", T["field"])],
            selectforeground=[("readonly", T["text"])],
        )
    st.configure("Horizontal.TProgressbar", background=T["accent2"], troughcolor=T["field"], thickness=6)
    for orient in ("Vertical", "Horizontal"):
        st.configure(
            f"{orient}.TScrollbar",
            background=T["line"],
            troughcolor=T["field"],
            bordercolor=T["field"],
            lightcolor=T["line"],
            darkcolor=T["line"],
            arrowcolor=T["muted"],
            gripcount=0,
            arrowsize=12,
        )
        st.map(f"{orient}.TScrollbar", background=[("active", T["line_hover"]), ("pressed", T["accent"])])
    # the Activity table
    st.configure(
        "Activity.Treeview",
        background=T["field"],
        fieldbackground=T["field"],
        foreground=T["text"],
        bordercolor=T["field"],
        lightcolor=T["field"],
        darkcolor=T["field"],
        rowheight=26,
        font=F["body"],
    )
    st.map("Activity.Treeview", background=[("selected", T["sel"])], foreground=[("selected", T["text"])])
    st.configure(
        "Activity.Treeview.Heading",
        background=T["card"],
        foreground=T["accent_soft"],
        font=F["small"],
        relief="flat",
        bordercolor=T["card"],
        lightcolor=T["card"],
        darkcolor=T["card"],
        padding=(6, 4),
    )
    st.map("Activity.Treeview.Heading", background=[("active", T["line"])])
    st.layout("Activity.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    root.option_add("*TCombobox*Listbox.background", T["field"])
    root.option_add("*TCombobox*Listbox.foreground", T["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", T["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", T["accent_text"])
    root.option_add("*TCombobox*Listbox.font", F["body"])
