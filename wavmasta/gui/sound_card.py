"""The '<song> sound' card: how the song selected in the list will be mastered.

Left: the mastering itself (tone, loudness, glue, width, or matching a reference song), the
song's ending (fade-out, trimming silence), and Before/After, so you can hear each change
without going back up to the songs list.
Right: cleanup (noise, harsh highs, sharp 's' sounds, hum and whine), plus Check this song, which
measures the song and suggests settings.
"""

import os
import tkinter as tk
from tkinter import filedialog, ttk

from ..config import AUDIO_EXTENSIONS, LOUDNESS, TONE_HINTS, TONES
from .theme import THEME as T
from .theme import px
from .widgets import Bubble, slider, title_row

SLIDER = 140


def denoise_word(v):
    return "off" if v == 0 else "light" if v <= 35 else "medium" if v <= 65 else "strong"


def glue_word(v):
    return "off" if v == 0 else "gentle" if v <= 35 else "firm" if v <= 70 else "heavy"


def deess_word(v):
    return "off" if v == 0 else "light" if v <= 35 else "medium" if v <= 65 else "strong"


def fade_word(v):
    return "none" if v == 0 else f"{v:g} s"


def width_word(v):
    return "as mixed" if v == 100 else "mono" if v == 0 else "narrower" if v < 100 else "wider"


class SoundCard(ttk.Frame):
    def __init__(self, parent, fonts, on_apply_all, on_analyze, on_suggest, on_change=None, on_play=None):
        super().__init__(parent, style="Card.TFrame", padding=(16, 12))
        self.track = None
        self.on_play = on_play  # called with "before" or "after" (plays it, or stops it if it's playing)
        self.on_change = on_change
        self._loading = False
        self.locked = False
        self.lock_note = ""
        self.sliders = []
        self.columnconfigure(0, weight=1)

        top = title_row(self, "Sound", upper=False)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.title = tk.StringVar(value="Sound")
        top.label.configure(textvariable=self.title)
        self.hint = tk.StringVar()
        self.hint_label = ttk.Label(top, textvariable=self.hint, style="Muted.TLabel")
        self.hint_label.pack(side="left", padx=(10, 0))
        self.apply_btn = ttk.Button(top, text="Apply to all songs", style="Small.TButton", command=on_apply_all)
        self.apply_btn.pack(side="right")

        self.body = ttk.Frame(self, style="Inner.TFrame")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1, uniform="half")
        self.body.columnconfigure(1, weight=1, uniform="half")
        self.empty = ttk.Label(self, text="Add a song to choose how it's mastered.", style="Muted.TLabel")

        self._build_master(ttk.Frame(self.body, style="Inner.TFrame"))
        self._build_cleanup(ttk.Frame(self.body, style="Inner.TFrame"), fonts, on_analyze, on_suggest)
        self.show(None)

    # ---- layout helpers
    @staticmethod
    def _label(parent, r, text):
        ttk.Label(parent, text=text, style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=3, padx=(0, 12))

    @staticmethod
    def _section(parent, text):
        ttk.Label(parent, text=text, style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )

    def _slider_row(self, parent, r, label, var, lo, hi, step, text_var, on_move):
        self._label(parent, r, label)
        f = ttk.Frame(parent, style="Inner.TFrame")
        f.grid(row=r, column=1, sticky="w")
        s = slider(f, var, lo, hi, step, on_move, length=SLIDER)
        s.pack(side="left")
        self.sliders.append(s)
        ttk.Label(f, textvariable=text_var, style="Value.TLabel").pack(side="left", padx=(10, 0))

    # ---- left: mastering
    def _build_master(self, f):
        f.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self._section(f, "MASTERING")
        self.tone_var = tk.StringVar(value="Neutral")
        self._label(f, 1, "Tone")
        tone = ttk.Frame(f, style="Inner.TFrame")
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
        ref = ttk.Frame(f, style="Inner.TFrame")
        ref.grid(row=6, column=1, sticky="w")
        self.ref_btn = ttk.Button(ref, text="Choose...", style="Small.TButton", command=self.pick_reference)
        self.ref_btn.pack(side="left")
        self.ref_clear = ttk.Button(ref, text="Clear", style="Small.TButton", command=self.clear_reference)
        self.ref_text = tk.StringVar()
        ttk.Label(f, textvariable=self.ref_text, style="Muted.TLabel", wraplength=px(f, 300), justify="left").grid(
            row=7, column=1, sticky="w"
        )
        self.fade_var, self.fade_text = tk.DoubleVar(value=0.0), tk.StringVar()
        self._slider_row(f, 8, "Fade-out", self.fade_var, 0, 10, 0.5, self.fade_text, lambda v: self._store())
        self.trim_var = tk.BooleanVar(value=True)
        self.trim_var.trace_add("write", lambda *_: self._store())
        self.trim_check = ttk.Checkbutton(f, text="Trim silence from the start and end", variable=self.trim_var)
        self.trim_check.grid(row=9, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # hear the change right here: the same Before/After as the song's row in the list
        ttk.Separator(f).grid(row=10, column=0, columnspan=2, sticky="ew", pady=(10, 8))
        self._label(f, 11, "Hear")
        hear = ttk.Frame(f, style="Inner.TFrame")
        hear.grid(row=11, column=1, sticky="w")
        self.hear = {}
        for which in ("before", "after"):
            b = ttk.Button(hear, text=which.capitalize(), style="Small.TButton", width=8,
                           command=lambda w=which: self.on_play and self.on_play(w))  # fmt: skip
            b.pack(side="left", padx=(0, 6))
            self.hear[which] = b
        self.hear_text = tk.StringVar()
        self.hear_label = ttk.Label(f, textvariable=self.hear_text, style="Muted.TLabel")
        self.hear_label.grid(row=12, column=1, sticky="w")

    # ---- right: cleanup and checking
    def _build_cleanup(self, f, fonts, on_analyze, on_suggest):
        f.grid(row=0, column=1, sticky="nsew")
        self._section(f, "CLEANUP")
        self.noise_var, self.noise_text = tk.IntVar(value=0), tk.StringVar()
        self._slider_row(f, 1, "Noise reduction", self.noise_var, 0, 100, 5, self.noise_text, lambda v: self._store())
        self.top_var, self.top_text = tk.DoubleVar(value=0.0), tk.StringVar()
        self._slider_row(f, 2, "Tame harsh highs", self.top_var, 0, 6, 0.5, self.top_text, lambda v: self._store())
        self.deess_var, self.deess_text = tk.IntVar(value=0), tk.StringVar()
        self._slider_row(f, 3, "De-ess", self.deess_var, 0, 100, 5, self.deess_text, lambda v: self._store())
        self.hum_var = tk.BooleanVar(value=True)
        self.hum_var.trace_add("write", lambda *_: self._store())
        self.hum_check = ttk.Checkbutton(f, text="Remove hum and whine, if Check finds any", variable=self.hum_var)
        self.hum_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 6))
        btns = ttk.Frame(f, style="Inner.TFrame")
        btns.grid(row=5, column=0, columnspan=2, sticky="w", pady=(2, 4))
        self.check_btn = ttk.Button(btns, text="Check this song", style="Small.TButton", command=on_analyze)
        self.check_btn.pack(side="left")
        self.suggest_btn = ttk.Button(btns, text="✦ Use suggestions", style="Pink.TButton", command=on_suggest)
        # Check results: a rounded bubble under the buttons, one coloured line per finding
        self.fonts = fonts
        self.bubble = Bubble(f)
        self.bubble.grid(row=6, column=0, columnspan=2, sticky="nw", pady=(6, 0))

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
        self.count = count
        self._show_hint()
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
        self.deess_var.set(track.deess)
        self.fade_var.set(track.fade_out)
        self.trim_var.set(track.trim)
        self._loading = False
        self._refresh_texts()
        self.show_report(track.report)

    def show_report(self, report):
        """Fill the Check results bubble: a heading with the song's loudness and peak, then a line per
        finding with a coloured dot (red: can't be fixed, amber: worth fixing, green: all clear) and
        the tip in violet."""
        box = self.bubble.inner
        for w in box.winfo_children():
            w.destroy()
        F, fill, wrap = self.fonts, self.bubble.fill, px(box, 330)
        box.columnconfigure(0, weight=0)
        box.columnconfigure(1, weight=1)  # a wide heading widens the text column, not the dots
        if report is None:
            tk.Label(box, text="✦", bg=fill, fg=T["accent_soft"], font=F["btn"]).grid(row=0, column=0, sticky="nw")
            tk.Label(
                box,
                text="Check this song to measure it and find hiss, hum or harsh highs.",
                bg=fill, fg=T["muted"], font=F["small"], justify="left", wraplength=wrap,
            ).grid(row=0, column=1, sticky="w", padx=(8, 0))  # fmt: skip
            self.suggest_btn.pack_forget()
            self.bubble._fit()
            self.bubble.refit()
            return
        head = tk.Frame(box, bg=fill)
        head.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        tk.Label(head, text="CHECK RESULTS", bg=fill, fg=T["accent_soft"], font=F["small"]).pack(side="left")
        tk.Label(head, text=f"  {report.lufs:.1f} LUFS", bg=fill, fg=T["text"], font=F["btn"]).pack(side="left")
        tk.Label(head, text=f"  ·  peak {report.true_peak:.1f} dBTP", bg=fill, fg=T["text"], font=F["small"]).pack(
            side="left"
        )
        for i, line in enumerate(report.findings(), start=1):
            if line.startswith("No noise problems"):
                color = T["ok"]
            elif line.startswith("Clipping"):
                color = T["bad"]
            else:
                color = T["warn"]
            what, _, tip = line.partition(". ")
            tk.Label(box, text="●", bg=fill, fg=color, font=F["small"]).grid(row=i, column=0, sticky="nw", pady=(1, 0))
            cell = tk.Frame(box, bg=fill)
            cell.grid(row=i, column=1, sticky="w", padx=(8, 0), pady=(0, 3))
            tk.Label(
                cell, text=what + ("." if tip else ""), bg=fill, fg=T["text"], font=F["small"], justify="left",
                wraplength=wrap,
            ).pack(anchor="w")  # fmt: skip
            if tip:
                tk.Label(
                    cell, text=tip, bg=fill, fg=T["accent_soft"], font=F["small"], justify="left", wraplength=wrap
                ).pack(anchor="w")
        if self.track is not None and any(getattr(self.track, k) != v for k, v in report.suggested().items()):
            self.suggest_btn.pack(side="left", padx=(8, 0))
        else:
            self.suggest_btn.pack_forget()
        self.bubble._fit()
        self.bubble.refit()

    def findings_text(self):
        """Everything the Check results bubble says, as plain text (for tests and copying)."""
        out = []

        def walk(w):
            for c in w.winfo_children():
                if isinstance(c, tk.Label) and c.cget("text") not in ("●", "✦"):
                    out.append(c.cget("text"))
                walk(c)

        walk(self.bubble.inner)
        return "\n".join(out)

    def _refresh_texts(self):
        t = self.track
        if t is None:
            return
        matched = bool(t.reference)
        self.tone_hint.set("matched to the reference" if matched else TONE_HINTS.get(t.tone, ""))
        for box in (self.tone_box, self.loud_box):
            box.state(["disabled"] if matched or self.locked else ["!disabled", "readonly"])
        self.glue_text.set(f"{t.glue}% · {glue_word(t.glue)}")
        self.width_text.set(f"{t.width}% · {width_word(t.width)}")
        self.noise_text.set(f"{t.denoise}% · {denoise_word(t.denoise)}")
        self.top_text.set("off" if not t.tame_top else f"-{t.tame_top:g} dB")
        self.deess_text.set(f"{t.deess}% · {deess_word(t.deess)}")
        self.fade_text.set(fade_word(t.fade_out))
        if matched:
            self.ref_text.set(f"Matching tone and loudness to {os.path.basename(t.reference)}")
            self.ref_clear.pack(side="left", padx=(6, 0))
        else:
            self.ref_text.set("Optional: match a finished song's tone and loudness")
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
        t.deess = int(float(self.deess_var.get()))
        t.fade_out = round(float(self.fade_var.get()) * 2) / 2
        t.trim = bool(self.trim_var.get())
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

    def _show_hint(self):
        if self.track is None:
            return
        if self.locked and self.lock_note:
            self.hint.set(self.lock_note)
        else:
            self.hint.set("click another song to change its sound" if getattr(self, "count", 0) > 1 else "")
        self.hint_label.configure(style="Lock.TLabel" if self.locked and self.lock_note else "Muted.TLabel")

    # ---- Before / After on the card
    def set_playing(self, which):
        """The version being heard says Stop. which: 'before', 'after' or None."""
        for w, b in self.hear.items():
            b.configure(text="Stop" if w == which else w.capitalize())

    def set_heard(self, state):
        """The note under Before/After. state: 'new' (not heard yet), 'changed' (settings changed
        since you last listened) or 'current' (what you heard matches the settings)."""
        text, style = {
            "new": ("hear what these settings do", "Muted.TLabel"),
            "changed": ("settings changed · press After to hear them", "Lock.TLabel"),
            "current": ("✓ you've heard these settings", "Muted.TLabel"),
        }.get(state, ("", "Muted.TLabel"))
        self.hear_text.set(text)
        self.hear_label.configure(style=style)

    def set_enabled(self, on, note="", listening=False):
        """Lock or unlock every control on the card. note: shown beside the title while locked.
        listening: locked because a version is playing, so Before/After/Stop keep working."""
        self.locked = not on
        self.lock_note = note if not on else ""
        for b in self.hear.values():
            b.state(["!disabled"] if on or listening else ["disabled"])
        for b in (
            self.apply_btn, self.check_btn, self.suggest_btn, self.ref_btn, self.ref_clear, self.hum_check,
            self.trim_check,
        ):  # fmt: skip
            b.state(["!disabled"] if on else ["disabled"])
        for s in self.sliders:
            s.configure(
                state="normal" if on else "disabled",
                bg=T["accent"] if on else T["line_hover"],
                cursor="" if on else "arrow",
            )
        if self.track is not None:
            self._refresh_texts()  # restores the tone and loudness boxes (they stay off with a reference)
        else:
            for box in (self.tone_box, self.loud_box):
                box.state(["!disabled", "readonly"] if on else ["disabled"])
        self._show_hint()
