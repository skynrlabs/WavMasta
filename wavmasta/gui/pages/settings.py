"""Settings page: where masters are saved, in what format, the peak ceiling and the soft clipper."""

import tkinter as tk
from tkinter import filedialog, ttk

from ...config import DEFAULT_CEILING, DEFAULT_FORMAT, FORMATS, OUTPUT_SUFFIX, load_settings, save_settings
from ...core.chain import SOFT_CLIP_MODES
from ..theme import px
from ..widgets import card

SAME_FOLDER = "Same folder as each song"
FORMAT_HINTS = {
    "WAV 24-bit": "best for uploading to a distributor (DistroKid, CD Baby, TuneCore...)",
    "WAV 16-bit (CD)": "for burning CDs; adds dither so fade-outs stay smooth",
    "FLAC 24-bit": "same quality as WAV 24-bit, about half the size",
    "MP3 320 kbps": "for sharing and quick listening, not for distributors",
}
SOFT_CLIP_HINTS = {
    "Auto": "only for masters louder than Streaming (-14 LUFS), so loud masters keep their punch",
    "Always": "for every master, Streaming ones too",
    "Off": "the limiter does all the work",
}
CEILING_HELP = (
    "The highest peak allowed, measured between samples too (dBTP). -1.0 leaves room for streaming services "
    "to convert your song without distortion. Use -2.0 if a very loud master still crackles after upload."
)


class SettingsPage(ttk.Frame):
    def __init__(self, parent, on_reset=None):
        super().__init__(parent)
        self.on_reset = on_reset
        self.columnconfigure(0, weight=1)
        saved = load_settings()
        self.out_dir = None
        self.out_text = tk.StringVar(value=SAME_FOLDER)
        self.open_when_done = tk.BooleanVar(value=bool(saved.get("open_when_done", False)))
        fmt = saved.get("format", DEFAULT_FORMAT)
        self.format_var = tk.StringVar(value=fmt if fmt in FORMATS else DEFAULT_FORMAT)
        self.ceiling_var = tk.StringVar(value=f"{float(saved.get('ceiling', DEFAULT_CEILING)):.1f}")
        clip = saved.get("soft_clip", "Auto")
        self.soft_clip_var = tk.StringVar(value=clip if clip in SOFT_CLIP_MODES else "Auto")
        self.soft_clip_hint = tk.StringVar()
        self.format_hint = tk.StringVar()
        self._build_output()
        self._build_ceiling()
        c = card(self, 2, "Start over", "every song's sound, save folder, format and ceiling")
        ttk.Button(c, text="Reset everything to defaults", command=lambda: self.on_reset and self.on_reset()).grid(
            row=1, column=0, sticky="w"
        )
        for var in (self.format_var, self.ceiling_var, self.open_when_done, self.soft_clip_var):
            var.trace_add("write", lambda *_: self._remember())
        self._show_format_hint()

    # ---- where and how files are saved
    def _build_output(self):
        c = card(self, 0, "Save masters to")
        ttk.Label(c, textvariable=self.out_text, style="Card.TLabel").grid(row=1, column=0, columnspan=2, sticky="w")
        btns = ttk.Frame(c, style="Inner.TFrame")
        btns.grid(row=1, column=2, sticky="e")
        ttk.Button(btns, text="Change...", command=self.pick_folder).pack(side="left")
        ttk.Button(btns, text="Reset", command=self.reset_folder).pack(side="left", padx=(6, 0))
        ttk.Label(
            c,
            text=f"Each song becomes  <song name>{OUTPUT_SUFFIX}.wav,  for example  My Song{OUTPUT_SUFFIX}.wav. "
            "Your original is never changed.",
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        row = ttk.Frame(c, style="Inner.TFrame")
        row.grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 0))
        ttk.Label(row, text="Format", style="Card.TLabel").pack(side="left", padx=(0, 16))
        box = ttk.Combobox(row, textvariable=self.format_var, values=list(FORMATS), state="readonly", width=18)
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", lambda e: self._show_format_hint())
        ttk.Label(row, textvariable=self.format_hint, style="Muted.TLabel").pack(side="left", padx=(12, 0))
        ttk.Checkbutton(c, text="Open the folder when mastering finishes", variable=self.open_when_done).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )

    def _build_ceiling(self):
        c = card(self, 1, "Peak ceiling", "the same for every song")
        row = ttk.Frame(c, style="Inner.TFrame")
        row.grid(row=1, column=0, columnspan=3, sticky="w")
        ttk.Spinbox(
            row, from_=-3.0, to=-0.1, increment=0.1, width=6, textvariable=self.ceiling_var, format="%.1f"
        ).pack(side="left")
        ttk.Label(row, text="dBTP", style="Card.TLabel").pack(side="left", padx=(8, 0))
        ttk.Label(c, text=CEILING_HELP, style="Muted.TLabel", justify="left", wraplength=px(c, 700)).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )
        clip = ttk.Frame(c, style="Inner.TFrame")
        clip.grid(row=3, column=0, columnspan=3, sticky="w", pady=(14, 0))
        ttk.Label(clip, text="Soft clip before the limiter", style="Card.TLabel").pack(side="left", padx=(0, 12))
        box = ttk.Combobox(
            clip, textvariable=self.soft_clip_var, values=list(SOFT_CLIP_MODES), state="readonly", width=8
        )
        box.pack(side="left")
        ttk.Label(clip, textvariable=self.soft_clip_hint, style="Muted.TLabel").pack(side="left", padx=(12, 0))
        self.soft_clip_var.trace_add("write", lambda *_: self._show_soft_clip_hint())
        self._show_soft_clip_hint()

    def _show_soft_clip_hint(self):
        self.soft_clip_hint.set(SOFT_CLIP_HINTS.get(self.soft_clip_var.get(), ""))

    def soft_clip(self):
        """Auto, Always or Off."""
        v = self.soft_clip_var.get()
        return v if v in SOFT_CLIP_MODES else "Auto"

    def _show_format_hint(self):
        self.format_hint.set(FORMAT_HINTS.get(self.format_var.get(), ""))

    def pick_folder(self):
        d = filedialog.askdirectory(title="Save masters to")
        if d:
            self.out_dir = d
            self.out_text.set(d)

    def reset_folder(self):
        self.out_dir = None
        self.out_text.set(SAME_FOLDER)

    def ceiling(self):
        """Returns (value, None) or (None, message explaining what's wrong)."""
        try:
            v = float(self.ceiling_var.get())
            if not -3.0 <= v <= -0.1:
                raise ValueError
        except ValueError:
            return None, "Peak ceiling should be between -3.0 and -0.1 dBTP (Settings)"
        return v, None

    def _remember(self):
        data = load_settings()
        data["format"] = self.format_var.get()
        data["open_when_done"] = bool(self.open_when_done.get())
        v, err = self.ceiling()
        if not err:
            data["ceiling"] = v
        data["soft_clip"] = self.soft_clip()
        save_settings(data)

    def reset(self):
        self.reset_folder()
        self.open_when_done.set(False)
        self.format_var.set(DEFAULT_FORMAT)
        self.ceiling_var.set(f"{DEFAULT_CEILING:.1f}")
        self.soft_clip_var.set("Auto")
        self._show_format_hint()
