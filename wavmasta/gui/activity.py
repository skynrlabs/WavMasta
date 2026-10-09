"""The Activity table on the History page: a short, readable history of what happened.

The journeys report results here (one entry per action, one line per song) instead of
showing the engine's step-by-step output, which is meant for the command line.
"""

import os
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from .theme import THEME as T
from .theme import px
from .tracks_table import fit_text


def describe(result):
    """One plain-English line about a mastered song, e.g. '-20.4 → -14.0 LUFS · notched 60 Hz'."""
    before, after = result["before"], result["after"]
    parts = [f"{before.lufs:.1f} → {after.lufs:.1f} LUFS", f"peak {after.true_peak:.1f} dBTP"]
    tones = result["info"].get("tones") or []
    if tones:
        parts.append("notched " + ", ".join(f"{f:,.0f} Hz" for f, _ in tones[:3]))
    return " · ".join(parts)


def _clock(seconds):
    return f"{int(seconds // 60)}:{int(round(seconds % 60)):02d}"


def master_report(result, settings, fmt, ceiling):
    """The breakdown shown under a mastered song: [(label, result, details, good), ...]."""
    before, after, info = result["before"], result["after"], result["info"]
    rows = []
    # clipping
    if after.clipped == 0:
        rows.append(("Clipping", "none ✓", "no samples hit full scale", True))
    else:
        rows.append(("Clipping", f"{after.clipped:,} samples", "try a lower Loudness or Peak ceiling", False))
    if before.clipped > 100:
        rows.append(("", "", f"your mix had {before.clipped:,} clipped samples: export it quieter", False))
    # peak and loudness
    safe = after.true_peak <= ceiling + 0.05
    rows.append(
        (
            "True peak",
            f"{after.true_peak:.1f} dBTP" + (" ✓" if safe else ""),
            f"under the {ceiling:g} dBTP ceiling, safe for streaming"
            if safe
            else f"above the {ceiling:g} dBTP ceiling",
            safe,
        )
    )
    change = after.lufs - before.lufs
    rows.append(
        (
            "Loudness",
            f"{after.lufs:.1f} LUFS",
            f"was {before.lufs:.1f} ({change:+.1f} dB) · target {info['target']:g}",
            abs(after.lufs - info["target"]) < 0.5,
        )
    )
    plr = after.true_peak - after.lufs
    if plr >= 9:
        feel = "open and punchy"
    elif plr >= 7:
        feel = "full, still punchy"
    else:
        feel = "dense: lower Loudness or Glue for more"
    rows.append(("Punch", f"{plr:.1f} dB", feel, plr >= 7))
    # cleanup
    if settings.denoise:
        if before.quiet_level is not None and after.quiet_level is not None:
            d = f"noise {-before.quiet_level:.0f} → {-after.quiet_level:.0f} dB under the music"
        else:
            d = "no quiet parts to measure it in"
        rows.append(("Hiss", f"reduced {settings.denoise}%", d, True))
    elif before.hiss:
        rows.append(("Hiss", "found, not reduced", "try Noise reduction around 40%", False))
    else:
        rows.append(("Hiss", "none found", "", True))
    tones = info.get("tones") or []
    if tones:
        what = ", ".join(f"{f:,.0f} Hz" for f, _ in tones)
        rows.append(("Hum and whine", f"removed {len(tones)}", what, True))
    elif settings.fix_tones:
        rows.append(("Hum and whine", "none found", "", True))
    else:
        rows.append(("Hum and whine", "not checked", "turned off for this song", True))
    if settings.tame_top:
        rows.append(("Harsh highs", f"softened -{settings.tame_top:g} dB", "above 11 kHz", True))
    elif before.fizzy:
        rows.append(("Harsh highs", "found, not softened", "try Tame harsh highs", False))
    # sound and file
    tone = f"matched to {os.path.basename(settings.reference)}" if settings.reference else settings.tone
    extra = f"glue {settings.glue}% · width {settings.width}%"
    rows.append(("Sound", tone, extra, True))
    rows.append(
        ("File", fmt, f"{after.sample_rate / 1000:g} kHz · {_clock(after.duration)} · original unchanged", True)
    )
    return rows


class ActivityLog:
    """A scrollable table: one expandable row per action, with a row per song underneath.

    The newest action is at the top and opened; older ones fold away so the table stays tidy.
    Double-click a mastered song to open the folder it was saved in.
    """

    COLUMNS = ("time", "result", "details", "saved")
    PLACEHOLDER = "Nothing here yet. Results from Check, Before/After and Master will show up here."

    def __init__(self, parent, fonts, on_open=None):
        self.on_open = on_open
        self.frame = tk.Frame(parent, bg=T["field"])
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(self.frame, columns=self.COLUMNS, style="Activity.Treeview", selectmode="browse")
        self.tree = tree
        tree.heading("#0", text="Action / song", anchor="w")
        tree.heading("time", text="Time", anchor="w")
        tree.heading("result", text="Result", anchor="w")
        tree.heading("details", text="Details", anchor="w")
        tree.heading("saved", text="Saved as", anchor="w")
        # Columns size themselves to their text (see _fit_columns), so nothing is ever cut off;
        # when they don't all fit, a sideways scrollbar appears instead.
        self.MIN = {"#0": 140, "time": 48, "result": 90, "details": 160, "saved": 110}
        for col, w in self.MIN.items():
            tree.column(col, width=px(tree, w), minwidth=px(tree, w), stretch=False)
        scroll = ttk.Scrollbar(self.frame, orient="vertical", command=tree.yview)
        self.xscroll = ttk.Scrollbar(self.frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scroll.set, xscrollcommand=self.xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.fonts = {k: tkfont.Font(font=fonts[k]) for k in ("body", "btn", "small")}
        self._fit_pending = False
        tree.bind("<Configure>", lambda e: self._schedule_fit())
        self._texts = {}  # row id -> (full text, full values); the table may show them shortened
        self.tip = tk.Label(
            self.frame, bg=T["card"], fg=T["text"], font=fonts["small"], padx=8, pady=4, relief="solid", bd=1
        )
        tree.bind("<Motion>", self._on_motion)
        tree.bind("<Leave>", lambda e: self.tip.place_forget())

        tree.tag_configure("action", font=fonts["btn"], foreground=T["text"])
        tree.tag_configure("song", foreground=T["text"])
        tree.tag_configure("problem", foreground=T["warn"])
        tree.tag_configure("summary", foreground=T["ok"])
        tree.tag_configure("summary_warn", foreground=T["warn"])
        tree.tag_configure("detail", foreground=T["muted"], font=fonts["small"])
        tree.tag_configure("detail_warn", foreground=T["warn"], font=fonts["small"])
        tree.bind("<Double-1>", self._on_double_click)

        self._saved = {}  # row id -> full path of the saved master
        self._current = None  # the action rows are being added under
        self.empty_note = tk.Label(self.frame, text=self.PLACEHOLDER, bg=T["field"], fg=T["muted"], font=fonts["body"])
        self._placeholder()

    def grid(self, **kw):
        self.frame.grid(**kw)

    def _placeholder(self):
        self.tree.delete(*self.tree.get_children())
        self._saved.clear()
        self._texts.clear()
        self._current = None
        self.empty_note.place(relx=0.5, rely=0.55, anchor="center")

    def clear(self):
        self._placeholder()

    # ---- entries
    def action(self, title, detail=""):
        """Start a new action at the top of the table, e.g. 'Master 3 songs' with its settings."""
        self.empty_note.place_forget()
        for item in self.tree.get_children():
            self.tree.item(item, open=False)  # fold older actions away
        self._current = self.tree.insert(
            "", 0, text=title, values=(time.strftime("%H:%M"), "", detail, ""), open=True, tags=("action",)
        )
        self.tree.see(self._current)
        self._schedule_fit()
        return self._current

    # ---- column widths that fit the text
    def _schedule_fit(self):
        if not self._fit_pending:
            self._fit_pending = True
            self.tree.after_idle(self._fit_columns)

    def _font_for(self, item):
        tags = self.tree.item(item, "tags")
        if "action" in tags:
            return self.fonts["btn"]
        if "detail" in tags or "detail_warn" in tags:
            return self.fonts["small"]
        return self.fonts["body"]

    def _full(self, item):
        """The row's full text and values (what's shown may be shortened to fit)."""
        if item not in self._texts:
            self._texts[item] = (self.tree.item(item, "text"), tuple(self.tree.item(item, "values")))
        return self._texts[item]

    def _fit_columns(self):
        """Widen each column to its longest text. If they don't all fit, the less important columns
        give way first (Saved as, then long song names) and their text ends in '…' (hovering shows
        it in full), so text never runs under the next column. A sideways scrollbar appears only if
        the window is very narrow."""
        self._fit_pending = False
        tree = self.tree
        pad, indent = px(tree, 18), px(tree, 20)
        head = self.fonts["small"]
        room = tree.winfo_width()
        if room <= 1:
            return
        items = []

        def walk(item, depth):
            items.append((item, depth))
            for child in tree.get_children(item):
                walk(child, depth + 1)

        for item in tree.get_children():
            walk(item, 0)
        need = {c: max(px(tree, m), head.measure(tree.heading(c, "text")) + pad) for c, m in self.MIN.items()}
        for item, depth in items:
            f = self._font_for(item)
            text, values = self._full(item)
            need["#0"] = max(need["#0"], indent * (depth + 1) + f.measure(text) + pad)
            for col, value in zip(self.COLUMNS, values, strict=False):
                if value:
                    need[col] = max(need[col], f.measure(str(value)) + pad)
        width = dict(need)
        spare = room - sum(width.values())
        if spare >= 0:
            width["details"] += spare  # everything fits: give the rest to Details
        else:
            # Too wide: give way in order of importance. Details (the readings) keeps its text longest;
            # long file names give way first and are shortened with "…" (hover shows them in full).
            over = -spare
            steps = [
                ("saved", px(tree, self.MIN["saved"])),
                ("#0", max(px(tree, self.MIN["#0"]), int(room * 0.26))),
                ("result", px(tree, self.MIN["result"])),
                ("details", px(tree, self.MIN["details"])),
                ("#0", px(tree, self.MIN["#0"])),
            ]
            for col, floor in steps:
                if over <= 0:
                    break
                take = max(0, min(over, width[col] - floor))
                width[col] -= take
                over -= take
        for col, w in width.items():
            tree.column(col, width=w)
        self._widths = width
        # shorten what doesn't fit, by pixel width, so it never overlaps the next column
        for item, depth in items:
            f = self._font_for(item)
            text, values = self._full(item)
            shown_text = fit_text(f, text, width["#0"] - indent * (depth + 1) - pad // 2)
            shown = tuple(
                fit_text(f, str(v), width[c] - pad // 2) if v else v for c, v in zip(self.COLUMNS, values, strict=False)
            )
            tree.item(item, text=shown_text, values=shown)
        if sum(width.values()) > room + 1:
            self.xscroll.grid(row=1, column=0, sticky="ew")
        else:
            self.xscroll.grid_remove()
            tree.xview_moveto(0)

    # ---- hovering over shortened text shows it in full
    def _on_motion(self, event):
        tree = self.tree
        item, col = tree.identify_row(event.y), tree.identify_column(event.x)
        text = ""
        if item and item in self._texts:
            full_text, values = self._texts[item]
            if col == "#0":
                text = full_text
            else:
                i = int(col[1:]) - 1
                text = str(values[i]) if 0 <= i < len(values) else ""
            shown = tree.item(item, "text") if col == "#0" else str(tree.item(item, "values")[int(col[1:]) - 1])
            if shown == text:
                text = ""  # not shortened: no need for a tip
        if text:
            self.tip.configure(text=text)
            x = min(event.x + 14, max(0, self.frame.winfo_width() - self.tip.winfo_reqwidth() - 4))
            self.tip.place(x=x, y=event.y + 18)
            self.tip.lift()
        else:
            self.tip.place_forget()

    def _child(self, text, values, tags):
        if self._current is None:
            self.action("Activity")
        row = self.tree.insert(self._current, "end", text=text, values=values, tags=tags)
        self.tree.see(row)
        self.tree.see(self._current)
        self._schedule_fit()
        return row

    def song(self, name, result, details="", saved=None):
        """A song that worked: what was found or done, and the file it was saved to (if any)."""
        row = self._child(name, ("", result, details, os.path.basename(saved) if saved else ""), ("song",))
        if saved:
            self._saved[row] = saved
        return row

    def details(self, row, items):
        """A breakdown under a song row: one line per (label, result, details, good)."""
        for label, result, details, good in items:
            self.tree.insert(
                row, "end", text=label, values=("", result, details, ""), tags=("detail" if good else "detail_warn",)
            )
        self.tree.item(row, open=True)
        self._schedule_fit()

    def problem(self, name, reason):
        return self._child(name, ("", reason, "", ""), ("problem",))

    def summary(self, label, result="", details="", good=True):
        return self._child(label, ("", result, details, ""), ("summary" if good else "summary_warn",))

    def _on_double_click(self, event):
        row = self.tree.identify_row(event.y)
        if row in self._saved and self.on_open:
            self.on_open(os.path.dirname(self._saved[row]))

    def as_text(self):
        """The table as plain text, top to bottom (for tests and copying)."""
        lines = []

        def walk(item, depth):
            text, values = self._full(item)
            values = [v for v in values if v]
            lines.append("  " * depth + " | ".join([text, *map(str, values)]))
            for child in self.tree.get_children(item):
                walk(child, depth + 1)

        for item in self.tree.get_children():
            walk(item, 0)
        return "\n".join(lines) or self.PLACEHOLDER


def short_path(path, keep=2):
    """Last couple of folders of a path, so messages don't wrap on long paths."""
    parts = os.path.normpath(path).split(os.sep)
    return path if len(parts) <= keep + 1 else os.sep.join(["..."] + parts[-keep:])
