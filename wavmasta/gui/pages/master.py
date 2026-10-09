"""Master page: the songs (one row each) and the selected song's sound."""

import os
import tkinter as tk
from tkinter import filedialog, ttk

from ...config import AUDIO_EXTENSIONS
from ..model import Track
from ..sound_card import SoundCard
from ..tracks_table import TracksTable
from ..widgets import card

CHANGED = "changed · master again"


def audio_files(paths):
    """Expand dropped or picked paths: audio files as-is, folders to the audio files inside them.
    Files WavMasta made itself (' - master') are left out so they don't get mastered twice."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                full = os.path.join(p, name)
                if os.path.isfile(full) and name.lower().endswith(AUDIO_EXTENSIONS) and " - master" not in name:
                    out.append(full)
        elif p.lower().endswith(AUDIO_EXTENSIONS):
            out.append(p)
    return out


class MasterPage(ttk.Frame):
    def __init__(self, parent, fonts, settings_page, on_change, on_play, on_stop, on_analyze, on_suggest):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.settings_page = settings_page
        self.on_change = on_change
        self.on_play = on_play
        self.on_stop = on_stop
        self.tracks = []
        self.selected = None
        self._build_tracks(fonts)
        self.card = SoundCard(
            self,
            fonts,
            on_apply_all=self.apply_to_all,
            on_analyze=on_analyze,
            on_suggest=on_suggest,
            on_change=self.refresh_staleness,
        )
        self.card.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        self.rowconfigure(2, weight=1)
        # the save format, folder and ceiling also decide what a saved master contains
        for var in (settings_page.format_var, settings_page.ceiling_var, settings_page.out_text):
            var.trace_add("write", lambda *_: self.refresh_staleness())

    # ---- songs
    def _build_tracks(self, fonts):
        c = card(self, 0, "Songs")
        self.count_hint = tk.StringVar()
        ttk.Label(c.top, textvariable=self.count_hint, style="Muted.TLabel").pack(side="left", padx=(10, 0))
        self.clear_btn = ttk.Button(c.top, text="Clear all", style="Small.TButton", command=self.clear_tracks)
        self.clear_btn.pack(side="right")
        self.add_btn = ttk.Button(c.top, text="Add songs...", style="Small.TButton", command=self.add_files)
        self.add_btn.pack(side="right", padx=(0, 6))
        self.table = TracksTable(c, fonts, on_select=self.select, on_play=self._play, on_remove=self.remove)
        self.table.grid(row=1, column=0, columnspan=3, sticky="ew")

    def add_files(self):
        exts = " ".join("*" + e for e in AUDIO_EXTENSIONS)
        chosen = filedialog.askopenfilenames(title="Choose songs", filetypes=[("Audio", exts), ("All files", "*.*")])
        return self.add_paths(chosen)

    def add_paths(self, paths):
        """Add songs from file and folder paths (from Add songs... or drag and drop). Returns how many."""
        known = {os.path.normcase(os.path.abspath(t.path)) for t in self.tracks}
        new = []
        for f in audio_files(paths):
            key = os.path.normcase(os.path.abspath(f))
            if key not in known:
                known.add(key)
                new.append(Track(f))
        if new:
            if self.tracks:  # new songs start with the selected song's sound, like an album
                src = self.selected_track()
                for t in new:
                    t.copy_settings_from(src)
            self.tracks.extend(new)
            self.refresh(select=len(self.tracks) - len(new))
        return len(new)

    def remove(self, index):
        if not 0 <= index < len(self.tracks):
            return
        if self.table.playing and self.table.playing[0] == index:
            self.on_stop()
        self.tracks.pop(index)
        sel = self.selected or 0
        if index < sel:
            sel -= 1  # the selected song moved up one row
        self.refresh(select=min(sel, len(self.tracks) - 1) if self.tracks else None)

    def clear_tracks(self):
        if self.table.playing:
            self.on_stop()
        self.tracks.clear()
        self.refresh(select=None)

    def select(self, index):
        if index is None or not self.tracks:
            self.selected = None
            self.card.show(None)
        else:
            self.selected = index
            self.card.show(self.tracks[index], len(self.tracks))
        self.table.select(self.selected)
        self.on_change()

    def _play(self, index, which):
        """A row's Before/After button: plays that version, or stops it if it's the one playing."""
        if self.table.playing == (index, which):
            self.on_stop()
            return
        self.select(index)
        self.on_play(which)

    def set_playing(self, track, which=None):
        if track in self.tracks and which:
            self.table.set_playing((self.tracks.index(track), which))
        else:
            self.table.set_playing(None)

    def refresh(self, select=None):
        """Rebuild the rows after songs were added or removed."""
        if select is None and self.tracks:
            select = 0
        self.table.set_tracks(self.tracks, select)
        n = len(self.tracks)
        self.count_hint.set(f"{n} song{'s' if n != 1 else ''} · each with its own sound" if n else "")
        self.select(select if n else None)

    def selected_track(self):
        if self.selected is None or not self.tracks:
            return None
        return self.tracks[self.selected]

    def apply_to_all(self):
        src = self.selected_track()
        if src is None:
            return
        for t in self.tracks:
            if t is not src:
                t.copy_settings_from(src)
        self.refresh_staleness()
        self.on_change(f"Applied {src.name}'s sound to all {len(self.tracks)} songs")

    # ---- "changed since saved"
    def signature(self, track):
        """Everything that decides what a song's master contains."""
        sp = self.settings_page
        return (track.sound(), sp.format_var.get(), sp.ceiling_var.get(), sp.out_text.get())

    def mark_saved(self, track, sig):
        track.saved_sig = sig
        track.saved_status = track.status

    def refresh_staleness(self):
        """Saved songs whose settings changed since saving say so; changing back restores 'saved'."""
        for t in self.tracks:
            if t.saved_sig is None or t.status_kind == "busy":
                continue
            if self.signature(t) == t.saved_sig:
                t.status, t.status_kind = t.saved_status, "ok"
            else:
                t.status, t.status_kind = CHANGED, "warn"
            self.show_status(t)

    def show_status(self, track):
        if track in self.tracks:
            self.table.update_status(self.tracks.index(track), track)

    def set_enabled(self, on):
        self.table.set_enabled(on)
        self.card.set_enabled(on)
        for b in (self.add_btn, self.clear_btn):
            b.state(["!disabled"] if on else ["disabled"])

    def reset(self):
        for t in self.tracks:
            t.reset()
        self.select(self.selected)
        self.refresh_staleness()
