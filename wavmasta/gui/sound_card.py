"""The '<song> sound' card: how the song selected in the list will be mastered.

Left: the mastering itself (tone, loudness, glue, width, or matching a reference song).
Right: cleanup (noise, harsh highs, hum and whine), plus Check this song, which measures the
song and suggests cleanup settings.
"""

import os
import tkinter as tk
from tkinter import filedialog, ttk

from ..config import AUDIO_EXTENSIONS, LOUDNESS, TONE_HINTS, TONES
from .theme import THEME as T
from .widgets import slider

SLIDER = 140


def denoise_word(v):
    return "off" if v == 0 else "light" if v <= 35 else "medium" if v <= 65 else "strong"


def glue_word(v):
    return "off" if v == 0 else "gentle" if v <= 35 else "firm" if v <= 70 else "heavy"


def width_word(v):
    return "as mixed" if v == 100 else "mono" if v == 0 else "narrower" if v < 100 else "wider"


class SoundCard(ttk.Frame):
    def __init__(self, parent, fonts, on_apply_all, on_analyze, on_suggest, on_change=None):
        super().__init__(parent, style="Card.TFrame", padding=(16, 12))
        self.track = None
        self.on_change = on_change
        self._loading = False
        self.columnconfigure(0, weight=1)

        top = ttk.Frame(self, style="Card.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.title = tk.StringVar(value="Sound")
        ttk.Label(top, textvariable=self.title, style="Head.TLabel").pack(side="left")
        self.hint = tk.StringVar()
        ttk.Label(top, textvariable=self.hint, style="Muted.TLabel").pack(side="left", padx=(10, 0))
        self.apply_btn = ttk.Button(top, text="Apply to all songs", style="Small.TButton", command=on_apply_all)
        self.apply_btn.pack(side="right")

        self.body = ttk.Frame(self, style="Card.TFrame")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1, uniform="half")
        self.body.columnconfigure(1, weight=1, uniform="half")
        self.empty = ttk.Label(self, text="Add a song to choose how it's mastered.", style="Muted.TLabel")

        self._build_master(ttk.Frame(self.body, style="Card.TFrame"))
        self._build_cleanup(ttk.Frame(self.body, style="Card.TFrame"), fonts, on_analyze, on_suggest)
        self.show(None)

    # ---- layout helpers
    @staticmethod
    def _label(parent, r, text):
        ttk.Label(parent, text=text, style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=3, padx=(0, 12))

    @staticmethod
    def _section(parent, text):
        ttk.Label(parent, text=text, style="Muted.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

    def _slider_row(self, parent, r, label, var, lo, hi, step, text_var, on_move):
        self._label(parent, r, label)
        f = ttk.Frame(parent, style="Card.TFrame")
        f.grid(row=r, column=1, sticky="w")
        slider(f, var, lo, hi, step, on_move, length=SLIDER).pack(side="left")
        ttk.Label(f, textvariable=text_var, style="Value.TLabel").pack(side="left", padx=(10, 0))

    # ---- left: mastering
    def _build_master(self, f):
        f.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self._section(f, "MASTERING")
        self.tone_var = tk.StringVar(value="Neutral")
        self._label(f, 1, "Tone")
        tone = ttk.Frame(f, style="Card.TFrame")
        tone.grid(row=1, column=1, sticky="w")
        self.tone_box = ttk.Combobox(tone, textvariable=self.tone_var, values=list(TONES), state="readonly", width=14)
        self.tone_box.pack(side="left")
        self.tone_box.bind("<<ComboboxSelected>>", lambda e: self._store())
        self.tone_hint = tk.StringVar()
        ttk.Label(f, textvariable=self.tone_hint, style="Muted.TLabel").grid(row=2, column=1, sticky="w")

        self.loud_var = tk.StringVar()
        self._label(f, 3, "Loudness")
        self.loud_box = ttk.Combobox(f, textvariable=self.loud_var, values=list(LOUDNESS), state="readonly", width=22)
        self.loud_box.grid(row=3, column=1, sticky="w")
        self.loud_box.bind("<<ComboboxSelected>>", lambda e: self._store())

        self.glue_var, self.glue_text = tk.IntVar(value=30), tk.StringVar()
        self._slider_row(f, 4, "Glue", self.glue_var, 0, 100, 5, self.glue_text, lambda v: self._store())
        self.width_var, self.width_text = tk.IntVar(value=100), tk.StringVar()
        self._slider_row(f, 5, "Stereo width", self.width_var, 50, 150, 5, self.width_text, lambda v: self._store())

        self._label(f, 6, "Reference")
        ref = ttk.Frame(f, style="Card.TFrame")
        ref.grid(row=6, column=1, sticky="w")
        self.ref_btn = ttk.Button(ref, text="Choose...", style="Small.TButton", command=self.pick_reference)
        self.ref_btn.pack(side="left")
        self.ref_clear = ttk.Button(ref, text="Clear", style="Small.TButton", command=self.clear_reference)
        self.ref_text = tk.StringVar()
        ttk.Label(f, textvariable=self.ref_text, style="Muted.TLabel", wraplength=300, justify="left").grid(
            row=7, column=1, sticky="w"
        )

    # ---- right: cleanup and checking
    def _build_cleanup(self, f, fonts, on_analyze, on_suggest):
        f.grid(row=0, column=1, sticky="nsew")
        self._section(f, "CLEANUP")
        self.noise_var, self.noise_text = tk.IntVar(value=0), tk.StringVar()
        self._slider_row(f, 1, "Noise reduction", self.noise_var, 0, 100, 5, self.noise_text, lambda v: self._store())
        self.top_var, self.top_text = tk.DoubleVar(value=0.0), tk.StringVar()
        self._slider_row(f, 2, "Tame harsh highs", self.top_var, 0, 6, 0.5, self.top_text, lambda v: self._store())
        self.hum_var = tk.BooleanVar(value=True)
        self.hum_var.trace_add("write", lambda *_: self._store())
        ttk.Checkbutton(f, text="Remove steady hum and whine (found automatically)", variable=self.hum_var).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 6)
        )
        btns = ttk.Frame(f, style="Card.TFrame")
        btns.grid(row=4, column=0, columnspan=2, sticky="w", pady=(2, 4))
        self.check_btn = ttk.Button(btns, text="Check this song", style="Small.TButton", command=on_analyze)
        self.check_btn.pack(side="left")
        self.suggest_btn = ttk.Button(btns, text="Use suggestions", style="Small.TButton", command=on_suggest)
        self.findings = tk.Label(
            f, text="", bg=T["card"], fg=T["muted"], font=fonts["small"], justify="left", anchor="nw", wraplength=370
        )
        self.findings.grid(row=5, column=0, columnspan=2, sticky="nw")

    # ---- showing a song
    def show(self, track, count=0):
        """Load a song's settings into the card (or show the empty message when there's none)."""
        self.track = track
        if track is None:
            self.title.set("Sound")
            self.hint.set("")
            self.body.grid_remove()
            self.apply_btn.pack_forget()
            self.empty.grid(row=1, column=0, sticky="w")
            return
        self.empty.grid_remove()
        self.body.grid()
        self.title.set(f"{track.name}")
        self.hint.set("click another song to change its sound" if count > 1 else "")
        if count > 1:
            self.apply_btn.pack(side="right")
        else:
            self.apply_btn.pack_forget()
        self._loading = True
        self.tone_var.set(track.tone)
        self.loud_var.set(track.loudness)
        self.glue_var.set(track.glue)
        self.width_var.set(track.width)
        self.noise_var.set(track.denoise)
        self.top_var.set(track.tame_top)
        self.hum_var.set(track.fix_tones)
        self._loading = False
        self._refresh_texts()
        self.show_report(track.report)

    def show_report(self, report):
        if report is None:
            self.findings.configure(text="Check this song to measure it and find hiss, hum or harsh highs.")
            self.suggest_btn.pack_forget()
            return
        lines = [f"Now: {report.summary()}"] + ["• " + line for line in report.findings()]
        self.findings.configure(text="\n".join(lines))
        if self.track is not None and any(getattr(self.track, k) != v for k, v in report.suggested().items()):
            self.suggest_btn.pack(side="left", padx=(8, 0))
        else:
            self.suggest_btn.pack_forget()

    def _refresh_texts(self):
        t = self.track
        if t is None:
            return
        matched = bool(t.reference)
        self.tone_hint.set("matched to the reference" if matched else TONE_HINTS.get(t.tone, ""))
        for box in (self.tone_box, self.loud_box):
            box.state(["disabled"] if matched else ["!disabled", "readonly"])
        self.glue_text.set(f"{t.glue}% · {glue_word(t.glue)}")
        self.width_text.set(f"{t.width}% · {width_word(t.width)}")
        self.noise_text.set(f"{t.denoise}% · {denoise_word(t.denoise)}")
        self.top_text.set("off" if not t.tame_top else f"-{t.tame_top:g} dB")
        if matched:
            self.ref_text.set(f"Matching tone and loudness to {os.path.basename(t.reference)}")
            self.ref_clear.pack(side="left", padx=(6, 0))
        else:
            self.ref_text.set("Optional: a finished song whose tone and loudness to match")
            self.ref_clear.pack_forget()

    # ---- writing changes back to the song
    def _store(self):
        if self._loading or self.track is None:
            return
        t = self.track
        t.tone = self.tone_var.get()
        t.loudness = self.loud_var.get()
        t.glue = int(float(self.glue_var.get()))
        t.width = int(float(self.width_var.get()))
        t.denoise = int(float(self.noise_var.get()))
        t.tame_top = round(float(self.top_var.get()) * 2) / 2
        t.fix_tones = bool(self.hum_var.get())
        self._refresh_texts()
        self.show_report(t.report)
        if self.on_change:
            self.on_change()

    def pick_reference(self):
        if self.track is None:
            return
        exts = " ".join("*" + e for e in AUDIO_EXTENSIONS)
        path = filedialog.askopenfilename(
            title="Choose a finished song to match", filetypes=[("Audio", exts), ("All files", "*.*")]
        )
        if path:
            self.track.reference = path
            self._refresh_texts()
            if self.on_change:
                self.on_change()

    def clear_reference(self):
        if self.track is not None:
            self.track.reference = None
            self._refresh_texts()
            if self.on_change:
                self.on_change()

    def set_enabled(self, on):
        for b in (self.apply_btn, self.check_btn, self.suggest_btn, self.ref_btn, self.ref_clear):
            b.state(["!disabled"] if on else ["disabled"])
