"""Colours, fonts and ttk styles."""

import tkinter.font as tkfont
from tkinter import ttk

THEME = {
    "bg": "#1b1e22",
    "card": "#252a30",
    "field": "#14171a",
    "line": "#353b43",
    "text": "#e8eaed",
    "muted": "#9aa3ad",
    "accent": "#18c6cc",
    "accent_hover": "#3fd8dd",
    "accent_text": "#0d1013",
    "ok": "#4cd08a",
    "warn": "#f0b84a",
    "sel": "#243a40",
    "side": "#14171a",
    "side_hover": "#1f2328",
    "side_active": "#252a30",
}


def make_fonts():
    families = set(tkfont.families())
    family = next(
        (f for f in ("Segoe UI", "Inter", "Helvetica Neue", "DejaVu Sans") if f in families),
        tkfont.nametofont("TkDefaultFont").actual("family"),
    )
    return {
        "title": (family, 18, "bold"),
        "brand": (family, 14, "bold"),
        "sub": (family, 10),
        "h": (family, 11, "bold"),
        "body": (family, 10),
        "small": (family, 9),
        "btn": (family, 10, "bold"),
        "big": (family, 12, "bold"),
        "status": (family, 14, "bold"),
        "nav": (family, 11),
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
    st.configure("Card.TFrame", background=T["card"], relief="flat")
    st.configure("TLabel", background=T["bg"], foreground=T["text"])
    st.configure("Card.TLabel", background=T["card"])
    st.configure("Muted.TLabel", background=T["card"], foreground=T["muted"], font=F["small"])
    st.configure("Head.TLabel", background=T["card"], foreground=T["text"], font=F["h"])
    st.configure("Title.TLabel", font=F["title"])
    st.configure("Sub.TLabel", foreground=T["muted"], font=F["sub"])
    st.configure("Value.TLabel", background=T["card"], foreground=T["accent"], font=F["btn"])
    st.configure("TButton", background=T["line"], foreground=T["text"], font=F["btn"], borderwidth=0, padding=(12, 6))
    st.map(
        "TButton", background=[("active", "#434a53"), ("disabled", T["card"])], foreground=[("disabled", T["muted"])]
    )
    st.configure("Small.TButton", font=F["small"], padding=(10, 3))
    st.configure("Accent.TButton", background=T["accent"], foreground=T["accent_text"], font=F["big"], padding=(18, 10))
    st.map(
        "Accent.TButton",
        background=[("active", T["accent_hover"]), ("disabled", T["line"])],
        foreground=[("disabled", T["muted"])],
    )
    st.configure(
        "TCheckbutton",
        background=T["card"],
        foreground=T["text"],
        indicatorbackground=T["field"],
        indicatorforeground=T["accent"],
        indicatormargin=4,
    )
    st.map(
        "TCheckbutton",
        background=[("active", T["card"])],
        indicatorbackground=[("selected", T["accent"]), ("active", T["line"])],
        indicatorforeground=[("selected", T["accent_text"])],
    )
    for w in ("TCombobox", "TSpinbox", "TEntry"):
        st.configure(
            w, fieldbackground=T["field"], background=T["line"], foreground=T["text"], arrowcolor=T["text"], padding=5
        )
        st.map(
            w,
            fieldbackground=[("readonly", T["field"])],
            foreground=[("readonly", T["text"])],
            selectbackground=[("readonly", T["field"])],
            selectforeground=[("readonly", T["text"])],
        )
    st.configure("Horizontal.TProgressbar", background=T["accent"], troughcolor=T["field"], thickness=6)
    # Dark, flat scrollbars (the default clam look is a pale bar with a grip in the middle)
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
        st.map(f"{orient}.TScrollbar", background=[("active", "#4a525c"), ("pressed", T["accent"])])
    # The Activity table
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
    st.map(
        "Activity.Treeview",
        background=[("selected", "#243a40")],
        foreground=[("selected", T["text"])],
    )
    st.configure(
        "Activity.Treeview.Heading",
        background=T["card"],
        foreground=T["muted"],
        font=F["small"],
        relief="flat",
        bordercolor=T["card"],
        lightcolor=T["card"],
        darkcolor=T["card"],
        padding=(6, 4),
    )
    st.map("Activity.Treeview.Heading", background=[("active", T["line"])])
    st.layout("Activity.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])  # no inner border
    root.option_add("*TCombobox*Listbox.background", T["field"])
    root.option_add("*TCombobox*Listbox.foreground", T["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", T["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", T["accent_text"])
    root.option_add("*TCombobox*Listbox.font", F["body"])
