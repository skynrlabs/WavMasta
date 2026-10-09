"""The songs list: one row per song with its name, status and a remove button.

Before and After live on the sound card, under the settings; the row of the song being heard
says so in its status."""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from .theme import THEME as T
from .theme import px

ROW_HEIGHT = 38
VISIBLE_ROWS = 4
STATUS_COLORS = {"muted": "muted", "busy": "accent_soft", "ok": "ok", "warn": "warn"}
# Pixel widths shared by the heading and every row so the columns line up: Song, Status, Remove.
# Song is sized to fit the longest name (see TracksTable._layout); Status takes the rest.
COLUMNS = [("Song", 200), ("Status", 0), ("", 96)]
SONG = 0  # index of the Song column
SONG_SHARE = 0.55  # the Song column may use up to this much of the room left after the buttons


def _columns(frame, song_width=None):
    for i, (_, width) in enumerate(COLUMNS):
        w = song_width if (i == SONG and song_width) else px(frame, width)
        frame.columnconfigure(i, minsize=w, weight=1 if width == 0 else 0)


def fit_text(font, text, width):
    """text, or as much of it as fits in width pixels followed by '…'."""
    if width <= 0 or font.measure(text) <= width:
        return text
    lo, hi = 0, len(text)
    while lo < hi:  # longest prefix that fits with the ellipsis
        mid = (lo + hi + 1) // 2
        if font.measure(text[:mid].rstrip() + "…") <= width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + "…"


class TracksTable(ttk.Frame):
    """Rows are rebuilt when songs are added or removed; selection and status update in place."""

    def __init__(self, parent, fonts, on_select, on_remove):
        super().__init__(parent, style="Inner.TFrame")
        self.F = fonts
        self.on_select, self.on_remove = on_select, on_remove
        self.rows = []
        self.selected = None
        self.enabled = True
        self.playing = None  # (row index, "before" or "after")
        self.columnconfigure(0, weight=1)
        self.name_font = tkfont.Font(font=fonts["btn"])
        self.status_font = tkfont.Font(font=fonts["body"])
        self.song_width = None
        self.status_width = None

        head = tk.Frame(self, bg=T["card"])
        self.head = head
        head.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        _columns(head)
        for i, (text, _) in enumerate(COLUMNS):
            tk.Label(head, text=text, bg=T["card"], fg=T["accent_soft"], font=fonts["small"], anchor="w").grid(
                row=0, column=i, sticky="w", padx=(14, 0) if i == SONG else 0
            )

        self.canvas = tk.Canvas(self, bg=T["field"], highlightthickness=0, height=px(self, ROW_HEIGHT) * 2)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.body = tk.Frame(self.canvas, bg=T["field"])
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: (self.canvas.itemconfigure(self._win, width=e.width), self._layout()))
        for w in (self.canvas, self.body):
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Button-4>", self._wheel)
            w.bind("<Button-5>", self._wheel)

        self.empty = tk.Label(
            self.canvas,
            text="Drop songs here, or click Add songs... (Ctrl+O).\nWAV, FLAC, MP3, AIFF, OGG or M4A.",
            justify="center",
            bg=T["field"],
            fg=T["muted"],
            font=fonts["body"],
        )

    # ---- building rows
    def set_tracks(self, tracks, selected):
        for row in self.rows:
            row["frame"].destroy()
        self.rows = [self._make_row(i, t) for i, t in enumerate(tracks)]
        self._layout()
        n = len(tracks)
        self.canvas.configure(height=px(self, ROW_HEIGHT) * min(max(n, 2), VISIBLE_ROWS))
        if n > VISIBLE_ROWS:
            self.scroll.grid(row=1, column=1, sticky="ns")
        else:
            self.scroll.grid_remove()
            self.canvas.yview_moveto(0)
        if n:
            self.empty.place_forget()
        else:
            self.empty.place(relx=0.5, rely=0.5, anchor="center")
        self.select(selected)
        self.set_enabled(self.enabled)
        p = self.playing
        self.set_playing(p if p is not None and p[0] < n else None)

    def _make_row(self, i, track):
        F = self.F
        frame = tk.Frame(self.body, bg=T["field"], height=px(self, ROW_HEIGHT))
        frame.pack(fill="x")
        frame.grid_propagate(False)
        frame.rowconfigure(0, weight=1)
        _columns(frame)
        name = tk.Label(frame, text=track.name, bg=T["field"], fg=T["text"], font=F["btn"], anchor="w")
        name.grid(row=0, column=0, sticky="ew", padx=(14, 0))
        status = tk.Label(frame, text=track.status, bg=T["field"], font=F["body"], anchor="w")
        status.grid(row=0, column=1, sticky="ew")
        remove = ttk.Button(frame, text="Remove", style="Small.TButton", command=lambda: self.on_remove(i))
        remove.grid(row=0, column=2, sticky="e", padx=(0, 8))
        row = {
            "frame": frame,
            "name": name,
            "status": status,
            "track": track,
            "remove": remove,
            "full_name": track.name,
            "full_status": track.status,
        }
        for w in (frame, name, status):
            w.bind("<Button-1>", lambda e: self.on_select(i) if self.enabled else None)
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Button-4>", self._wheel)
            w.bind("<Button-5>", self._wheel)
        self._paint_status(row, track)
        return row

    # ---- updating in place
    def select(self, index):
        self.selected = index
        for i, row in enumerate(self.rows):
            bg = T["sel"] if i == index else T["field"]
            for key in ("frame", "name", "status"):
                row[key].configure(bg=bg)
        if index is not None and index < len(self.rows):
            self._scroll_into_view(index)

    def update_status(self, index, track):
        if 0 <= index < len(self.rows):
            self._paint_status(self.rows[index], track)

    def _paint_status(self, row, track):
        row["track"] = track
        i = self.rows.index(row) if row in self.rows else len(self.rows)
        p = self.playing
        if p is not None and p[0] == i:  # the song being heard says so, until it stops
            row["full_status"] = f"▶  playing {p[1]}"
            color = T["accent2"]
        else:
            row["full_status"] = track.status
            color = T[STATUS_COLORS.get(track.status_kind, "muted")]
        text = fit_text(self.status_font, row["full_status"], self.status_width or 0)
        row["status"].configure(text=text, fg=color)

    def _layout(self):
        """Size the Song column to the longest name (within reason) and give Status the rest, so no
        text runs under the next column. Anything still too long ends in '…'."""
        width = self.canvas.winfo_width()
        if width <= 1:
            return
        fixed = sum(px(self, w) for (_, w) in COLUMNS if w and _ != "Song") + px(self, 22)
        room = max(0, width - fixed)
        gap = px(self, 16)
        longest = max((self.name_font.measure(r["full_name"]) for r in self.rows), default=0) + gap
        song = int(min(max(px(self, 200), longest), room * SONG_SHARE))
        self.song_width, self.status_width = song, max(0, room - song - gap)
        _columns(self.head, song)
        for r in self.rows:
            _columns(r["frame"], song)
            r["name"].configure(text=fit_text(self.name_font, r["full_name"], song - gap))
            r["status"].configure(text=fit_text(self.status_font, r["full_status"], self.status_width))

    def set_enabled(self, on):
        """on=False locks the rows: no selecting another song or removing one."""
        self.enabled = on
        for row in self.rows:
            row["remove"].state(["!disabled"] if on else ["disabled"])

    def set_playing(self, playing):
        """Mark the row being heard. playing: (row index, 'before' or 'after') or None."""
        self.playing = playing
        for row in self.rows:
            self._paint_status(row, row["track"])

    def set_drop_highlight(self, on):
        """Light up the list while files are dragged over the window."""
        self.canvas.configure(bg=T["sel"] if on else T["field"])
        self.empty.configure(bg=T["sel"] if on else T["field"])

    # ---- scrolling
    def _wheel(self, event):
        if len(self.rows) <= VISIBLE_ROWS:
            return
        step = -1 if (getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0) else 1
        self.canvas.yview_scroll(step, "units")

    def _scroll_into_view(self, index):
        n = len(self.rows)
        if n <= VISIBLE_ROWS:
            return
        top, bottom = self.canvas.yview()
        row_top, row_bottom = index / n, (index + 1) / n
        if row_top < top:
            self.canvas.yview_moveto(row_top)
        elif row_bottom > bottom:
            self.canvas.yview_moveto(row_bottom - (bottom - top))
