"""The Waveform card: the selected song before and after mastering, on the same scale.

The original is drawn as a light outline, the master as violet-to-magenta bars, so you can see
what changed: how much louder it got, where the limiter flattened the peaks (against the dashed
ceiling lines), what was trimmed off the ends and how the fade-out tails away. The stretch the
Before/After preview plays is shaded.
"""

import tkinter as tk
from tkinter import ttk

import numpy as np

from .theme import THEME as T
from .theme import blend, px
from .widgets import card

HEIGHT = 74  # px at 100% display scaling


def _clock(seconds):
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


class WaveformCard:
    def __init__(self, parent, row, fonts):
        self.fonts = fonts
        self.card = card(parent, row, "Waveform")
        top = self.card.top
        legend = tk.Frame(top, bg=T["card"])
        legend.pack(side="right")
        self._key(legend, T["text"], "original")
        self._key(legend, T["accent2"], "master", solid=True)
        self._key(legend, T["line_hover"], "preview stretch", solid=True)
        self.hint = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.hint, style="Muted.TLabel").pack(side="left", padx=(12, 0))
        self.canvas = tk.Canvas(
            self.card, height=px(parent, HEIGHT), bg=T["field"], highlightthickness=0, bd=0, cursor="arrow"
        )
        self.canvas.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.data = None

    def _key(self, parent, color, text, solid=False):
        sw = tk.Canvas(parent, width=px(parent, 16), height=px(parent, 10), bg=T["card"], highlightthickness=0)
        if solid:
            sw.create_rectangle(1, 1, px(parent, 15), px(parent, 9), fill=color, outline="")
        else:
            sw.create_line(1, px(parent, 5), px(parent, 15), px(parent, 5), fill=color, width=2)
        sw.pack(side="left", padx=(12, 4))
        tk.Label(parent, text=text, bg=T["card"], fg=T["muted"], font=self.fonts["small"]).pack(side="left")

    # ---- what to show
    def show(self, data):
        """data: None (nothing selected), or a dict with
        before: envelope of the original; seconds: its length;
        after: envelope of the master, or None; after_start/after_seconds: where it sits on the
        original's timeline (it starts later and is shorter when silence was trimmed);
        ceiling: the peak ceiling as a 0-1 level; window: (start, length) seconds of the preview
        on the master's timeline, or None; stale: True when the settings changed since;
        note: a line to show instead of the master (e.g. while loading)."""
        self.data = data
        if data is None:
            self.hint.set("")
        elif data.get("after") is None:
            self.hint.set(data.get("note") or "press After to see the master over the original")
        elif data.get("stale"):
            self.hint.set("settings changed since · press After to update")
        else:
            self.hint.set(f"{_clock(data['seconds'])} long · master shown over the original")
        self.redraw()

    # ---- drawing
    def redraw(self):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 4 or h < 4:
            return
        mid, half = h / 2, h / 2 - px(c, 6)
        d = self.data
        c.create_line(0, mid, w, mid, fill=T["line"])
        if d is None or d.get("before") is None:
            text = (d or {}).get("note") or "Select a song to see its waveform"
            c.create_text(w / 2, mid, text=text, fill=T["muted"], font=self.fonts["small"])
            return
        total = max(d["seconds"], 1e-6)

        def x_of(seconds):
            return seconds / total * w

        def resample(env, x0, x1):
            """The envelope stretched over pixel columns x0..x1: one peak per column."""
            n = max(1, int(round(x1 - x0)))
            idx = (np.arange(n) * len(env) / n).astype(int)
            ends = np.minimum(len(env), ((np.arange(n) + 1) * len(env) / n).astype(int) + 1)
            return [
                float(env[a:b].max()) if b > a else float(env[min(a, len(env) - 1)])
                for a, b in zip(idx, ends, strict=True)
            ]

        after, stale = d.get("after"), d.get("stale")
        label = None
        # the stretch the preview plays
        if after is not None and d.get("window"):
            start, length = d["window"]
            a = x_of(d.get("after_start", 0.0) + start)
            c.create_rectangle(a, 0, a + x_of(length), h, fill=blend(T["field"], T["line_hover"], 0.55), outline="")
        # master: gradient bars
        if after is not None:
            x0 = x_of(d.get("after_start", 0.0))
            x1 = x0 + x_of(d.get("after_seconds", total))
            peaks = resample(after, x0, x1)
            n = len(peaks)
            for i, p in enumerate(peaks):
                color = blend(T["accent"], T["accent2"], i / max(1, n - 1))
                if stale:
                    color = blend(color, T["field"], 0.6)
                x = x0 + i
                c.create_line(x, mid - p * half, x, mid + p * half + 1, fill=color)
            if d.get("ceiling"):
                y = d["ceiling"] * half
                for yy in (mid - y, mid + y):
                    c.create_line(0, yy, w, yy, fill=T["text"], dash=(3, 4))
                label = (px(c, 6), mid - y + px(c, 3))
        # original: a light outline on top
        peaks = resample(d["before"], 0, w)
        top = []
        bottom = []
        for i, p in enumerate(peaks):
            top += [i, mid - p * half]
            bottom += [i, mid + p * half]
        if len(top) >= 4:
            outline = T["text"] if after is not None else T["muted"]
            c.create_line(*top, fill=outline, width=1)
            c.create_line(*bottom, fill=outline, width=1)
        if label:  # on a small dark tag, drawn last so the waveform never hides it
            tag = c.create_text(*label, text="ceiling", anchor="nw", fill=T["muted"], font=self.fonts["small"])
            x0, y0, x1, y1 = c.bbox(tag)
            back = c.create_rectangle(x0 - 3, y0 - 1, x1 + 3, y1 + 1, fill=T["field"], outline=T["line"])
            c.tag_lower(back, tag)
        if after is None:
            c.create_text(
                w / 2, px(c, 10), text=d.get("note") or "press After to draw the master", fill=T["muted"],
                font=self.fonts["small"],
            )  # fmt: skip

    def as_text(self):
        """What the card shows, in words (for tests)."""
        return self.hint.get()
