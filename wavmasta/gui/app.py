"""The main window: sidebar, page area and action bar, plus the shared plumbing the journeys use."""

import contextlib
import os
import queue
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from ..config import ASSETS_DIR
from .action_bar import ActionBar
from .dialogs import show_about
from .journeys import CheckJourney, MasterJourney, PreviewJourney, Renders
from .pages import PAGES, HelpPage, HistoryPage, MasterPage, SettingsPage
from .shortcuts import bind_shortcuts
from .sidebar import Sidebar
from .status_card import StatusCard
from .theme import THEME, apply_styles, make_fonts, px
from .widgets import ScrollArea

IS_WINDOWS = sys.platform.startswith("win")


class WavMastaApp:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.updates = queue.Queue()  # background threads -> window
        self.renders = Renders()
        self._setup_window()
        self.fonts = make_fonts()
        apply_styles(root, self.fonts)
        self.images = self._load_images()

        self.masterer = MasterJourney(self)
        self.preview = PreviewJourney(self)
        self.checker = CheckJourney(self)

        self._build_layout()
        self.dnd_enabled = self._enable_drag_and_drop()
        bind_shortcuts(self)
        self._wire_buttons()
        root.protocol("WM_DELETE_WINDOW", self.quit)

        self.master_page.on_lock = self._on_listening
        self.master_page.refresh()
        self.area.skip = [self.master_page.table]  # the songs list scrolls by itself
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            root.bind_all(seq, self.area.wheel, add="+")
        self._show_where()
        self.show_page("master")
        self._fit_window()
        self.say("Ready", detail="Drop your songs onto the window, pick a sound, then Master")
        self._poll()

    # ---- window setup
    def _setup_window(self):
        root = self.root
        root.title("WavMasta")
        root.configure(bg=THEME["bg"])
        ico = os.path.join(ASSETS_DIR, "wavmasta.ico")
        if IS_WINDOWS and os.path.exists(ico):
            with contextlib.suppress(tk.TclError):
                root.iconbitmap(default=ico)

    def _fit_window(self):
        """Open the window big enough for everything on the Master tab, at any display scaling,
        but never bigger than the screen (the page scrolls if the screen is too short)."""
        root = self.root
        card = self.master_page.card
        card.empty.grid_remove()  # measure with a song's Sound card showing, as it is in use,
        card.body.grid()  # including a few lines of Check findings
        card.findings.configure(text="\n".join(["Now: -20.0 LUFS · peak -4.0 dBTP"] + ["• finding"] * 5))
        for _ in range(3):  # sizes settle from the inside out, one layout pass per level
            root.update_idletasks()
        # ask for the full height once (plus a little room for long findings)
        self.area.canvas.configure(height=self.area.needed_height() + px(root, 24))
        for _ in range(3):
            root.update_idletasks()
        card.show(card.track)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        scale = float(root.tk.call("tk", "scaling")) / (96 / 72)  # 1.0 at 100% display scaling
        w = min(max(root.winfo_reqwidth(), int(1100 * scale)), sw - 40)
        h = min(root.winfo_reqheight(), sh - int(90 * scale))  # leave room for the taskbar and title bar
        self.area.canvas.configure(height=1)  # from now on the page area follows the window
        root.minsize(min(int(960 * scale), w), min(int(520 * scale), h))
        root.geometry(f"{w}x{h}")

    def _load_images(self):
        images = {}
        try:
            images["app"] = tk.PhotoImage(file=os.path.join(ASSETS_DIR, "icon.png"))
            images["small"] = tk.PhotoImage(file=os.path.join(ASSETS_DIR, "icon-32.png"))
            images["about"] = tk.PhotoImage(file=os.path.join(ASSETS_DIR, "icon-64.png"))
            if not IS_WINDOWS:  # Windows uses the .ico set above, which looks sharper in the title bar
                self.root.iconphoto(True, images["app"])
        except tk.TclError:
            pass
        return images

    def _enable_drag_and_drop(self):
        """Let people drop songs (or a folder of songs) from Explorer/Finder onto the window."""
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD

            TkinterDnD._require(self.root)
        except Exception:
            return False  # optional: Add songs... still works
        table = self.master_page.table
        targets = [self.main, self.master_page, table.canvas, table.body, table.empty]
        for w in targets:
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<DropEnter>>", lambda e: (table.set_drop_highlight(True), e.action)[1])
            w.dnd_bind("<<DropPosition>>", lambda e: e.action)
            w.dnd_bind("<<DropLeave>>", lambda e: (table.set_drop_highlight(False), e.action)[1])
            w.dnd_bind("<<Drop>>", self._on_drop)
        return True

    def _on_drop(self, event):
        self.master_page.table.set_drop_highlight(False)
        if self.busy or self.blocked_by_playback():
            return event.action
        paths = self.root.tk.splitlist(event.data)
        added = self.master_page.add_paths(paths)
        self.show_page("master")
        if added:
            self.say(f"Added {added} song{'s' if added != 1 else ''}", "ok")
        else:
            self.say("No new songs in what you dropped", "warn", "WavMasta reads WAV, FLAC, MP3, AIFF, OGG and M4A")
        return event.action

    def _build_layout(self):
        root = self.root
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        self.nav = Sidebar(
            root, [(k, label) for k, label, _, _ in PAGES], self.show_page, self.fonts, self.images.get("small")
        )
        self.nav.grid(row=0, column=0, sticky="ns")

        main = self.main = ttk.Frame(root, padding=(24, 16, 24, 14))
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.page_title = tk.StringVar()
        self.page_sub = tk.StringVar()
        ttk.Label(header, textvariable=self.page_title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, textvariable=self.page_sub, style="Sub.TLabel").pack(anchor="w")

        self.area = ScrollArea(main)
        self.area.grid(row=1, column=0, sticky="nsew")
        box = self.area.inner
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        self.settings_page = SettingsPage(box, on_reset=self.reset_settings)
        self.history_page = HistoryPage(box, self.fonts)
        self.master_page = MasterPage(
            box,
            self.fonts,
            self.settings_page,
            on_change=self._on_tracks_changed,
            on_play=lambda which: self.preview.start(which),
            on_stop=lambda: self.preview.stop(),
            on_analyze=lambda: self.checker.start(),
            on_suggest=self.use_suggestions,
        )
        self.help_page = HelpPage(box, self.fonts, self.about)
        self.pages = {
            "master": self.master_page,
            "history": self.history_page,
            "settings": self.settings_page,
            "help": self.help_page,
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        self.status_card = StatusCard(main, self.fonts)
        self.status_card.grid(row=2, column=0, sticky="ew", pady=(4, 10))
        self.action = ActionBar(main)
        self.action.grid(row=3, column=0, sticky="ew")

    def _wire_buttons(self):
        self.action.master_btn.configure(command=self.masterer.start)
        self.action.open_btn.configure(command=self.open_folder)
        self.activity.on_open = self.open_path
        sp = self.settings_page
        for var in (sp.format_var, sp.out_text):
            var.trace_add("write", lambda *_: self._show_where())

    def _show_where(self):
        self.action.set_where(self.settings_page.format_var.get(), self.settings_page.out_text.get())

    # ---- navigation
    def show_page(self, key):
        self.pages[key].tkraise()
        self.area.show(self.pages[key])
        for k, _, title, sub in PAGES:
            if k == key:
                self.page_title.set(title)
                self.page_sub.set(sub)
        self.nav.set_active(key)

    @property
    def activity(self):
        return self.history_page.activity

    def _on_tracks_changed(self, message=None):
        n = len(self.master_page.tracks)
        self.nav.set_label("master", f"Master  ({n})" if n else "Master")
        self.action.set_master_label(self.master_page.tracks)
        if message:
            self.say(message, "ok")

    # ---- plumbing shared by the journeys
    def post(self, fn):
        """Run fn on the window's thread (safe to call from a background thread)."""
        self.updates.put(fn)

    def say(self, msg, kind="muted", detail=""):
        """Show a message in the status card. kind: muted, busy, ok or warn."""
        self.status_card.say(msg, kind, detail)

    def set_busy(self, on):
        self.busy = on
        self.master_page.set_enabled(not on)
        self._update_master_btn()

    def _on_listening(self, playing):
        self._update_master_btn()

    def _update_master_btn(self):
        locked = self.busy or self.master_page.playing
        self.action.master_btn.state(["disabled"] if locked else ["!disabled"])

    def blocked_by_playback(self):
        """True (and says why) if a change is attempted while Before/After is playing."""
        if self.master_page.playing:
            self.say("Stop playback first", "warn", "Press Stop on the song, or Esc, then change its sound")
            return True
        return False

    def _poll(self):
        try:
            while True:
                self.updates.get_nowait()()
        except queue.Empty:
            pass
        self._poll_id = self.root.after(100, self._poll)

    # ---- commands
    def use_suggestions(self):
        if self.blocked_by_playback():
            return
        track = self.master_page.selected_track()
        if track is None or track.report is None:
            return
        changed = track.use_suggestions()
        self.master_page.card.show(track, len(self.master_page.tracks))
        self.master_page.refresh_staleness()
        if changed:
            names = {"denoise": "noise reduction", "fix_tones": "hum and whine", "tame_top": "harsh highs"}
            self.say(
                "Suggestions applied",
                "ok",
                "Changed " + ", ".join(names[c] for c in changed) + ". Press After to hear it",
            )

    def open_folder(self):
        d = self.masterer.last_out_dir or self.settings_page.out_dir
        if not d:
            self.say("Master something first, then Open folder", "warn")
            return
        self.open_path(d)

    def open_path(self, d):
        """Show a folder in Explorer / Finder / the file manager."""
        if IS_WINDOWS:
            os.startfile(d)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", d])
        else:
            subprocess.Popen(["xdg-open", d])

    def reset_settings(self):
        if self.blocked_by_playback():
            return
        self.settings_page.reset()
        self.master_page.reset()
        self.say("Settings reset to defaults", "ok")

    def about(self):
        show_about(self.root, self.fonts, self.images.get("about"))

    def quit(self):
        self.preview.player.stop()
        with contextlib.suppress(Exception):
            self.root.after_cancel(self._poll_id)
        self.root.destroy()


def run_gui():
    if IS_WINDOWS:
        try:  # show WavMasta's own icon on the taskbar instead of Python's
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SkynrLabs.WavMasta")
        except Exception:
            pass
    root = tk.Tk()
    WavMastaApp(root)
    root.mainloop()
