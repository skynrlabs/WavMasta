"""Help page: a scrolling quick guide plus links."""

import tkinter as tk
import webbrowser
from tkinter import ttk

from ...config import REPO_URL, SUPPORT_URL
from ..theme import THEME as T

HELP_TEXT = [
    ("h", "Quick start"),
    (
        "p",
        "1.  Drop your songs (or a folder of them) onto the window, or click Add songs... Use the final mix: "
        "a WAV or FLAC export, ideally peaking around -3 to -6 dB with no limiter on the master bus.",
    ),
    (
        "p",
        "2.  Click a song, then Check this song. WavMasta measures it and lists any hiss, hum, whine or harsh "
        "highs it finds. Use suggestions sets the cleanup for you.",
    ),
    (
        "p",
        "3.  Pick a Tone and a Loudness. Streaming (-14 LUFS) suits Spotify, YouTube and Apple Music, which turn "
        "louder songs down anyway. Apply to all songs gives an album the same sound.",
    ),
    (
        "p",
        "4.  Press After to hear the master, Before to hear the original. Both play the loudest 20 seconds, at "
        "the same loudness, so you hear the difference in sound, not just volume. Esc stops.",
    ),
    (
        "p",
        "5.  Click Master. Each song is saved as <name> - master.wav next to the original (change the folder and "
        "format in Settings). Change a setting afterwards and the row says 'changed · master again'.",
    ),
    ("h", "Mastering"),
    ("p", "Tone: a gentle EQ shape. Neutral changes nothing; the others stay within 2 dB."),
    (
        "p",
        "Loudness: how loud the finished song is, in LUFS. Louder isn't better on streaming: a -9 LUFS master "
        "is turned down to -14 and just sounds flatter than a -14 master.",
    ),
    ("p", "Glue: gentle compression that holds the mix together. 20-40% is natural; more gets punchy and dense."),
    ("p", "Stereo width: above 100% widens everything except the bass and kick, which stay centred."),
    (
        "p",
        "Reference: choose a finished, released song you like the sound of. WavMasta matches its tonal balance "
        "and loudness instead of using Tone and Loudness. Pick one in the same style as yours.",
    ),
    ("h", "Cleanup"),
    (
        "p",
        "Noise reduction: lowers steady hiss and noise. 30-50% is usually enough. Above about 70% it can "
        "start to sound watery or swirly, so check with After.",
    ),
    ("p", "Tame harsh highs: softens fizzy, brittle top end above 11 kHz, common in AI-generated songs."),
    (
        "p",
        "Remove steady hum and whine: finds tones that sit there for the whole song (mains hum at 50 or 60 Hz, "
        "a whine or ringing) and notches them out with very narrow filters. Notes in your music come and go, "
        "so they're left alone.",
    ),
    ("h", "Saving"),
    ("p", "WAV 24-bit is what distributors like DistroKid, CD Baby and TuneCore want. Upload that."),
    ("p", "Peak ceiling (Settings): -1.0 dBTP leaves room for streaming services to convert your song cleanly."),
    ("h", "Tips"),
    (
        "p",
        "Mastering polishes a good mix; it can't fix a bad one. If the vocal is buried or the bass is boomy, "
        "fix it in the mix first.",
    ),
    ("p", "Clipping in the original can't be undone. Export your mix quieter if Check reports clipping."),
    ("p", "Your original files are never changed."),
    ("h", "Keyboard shortcuts"),
    ("k", "Ctrl+O\tAdd songs"),
    ("k", "Ctrl+I\tCheck this song"),
    ("k", "Ctrl+B\tHear before"),
    ("k", "Ctrl+P\tHear after"),
    ("k", "Esc\tStop playback"),
    ("k", "Ctrl+Enter\tMaster"),
    ("k", "Ctrl+1 to 4\tSwitch pages"),
    ("k", "F1\tHelp"),
]


class HelpPage(ttk.Frame):
    def __init__(self, parent, fonts, on_about):
        super().__init__(parent)
        F = fonts
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        box = ttk.Frame(self, style="Card.TFrame", padding=(6, 6))
        box.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        text = tk.Text(
            box,
            bg=T["card"],
            fg=T["text"],
            relief="flat",
            highlightthickness=0,
            wrap="word",
            font=F["body"],
            padx=14,
            pady=8,
            cursor="arrow",
            spacing1=2,
            spacing3=4,
            tabs=("130p",),
        )
        scroll = ttk.Scrollbar(box, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        text.tag_configure("h", font=F["h"], foreground=T["accent"], spacing1=12, spacing3=4)
        text.tag_configure("p", foreground=T["text"], lmargin1=4, lmargin2=4)
        text.tag_configure("k", foreground=T["muted"], lmargin1=4, font=F["body"])
        for tag, line in HELP_TEXT:
            text.insert("end", line + "\n", tag)
        text.configure(state="disabled")

        links = ttk.Frame(self)
        links.grid(row=1, column=0, sticky="ew")
        ttk.Button(links, text="WavMasta on GitHub", command=lambda: webbrowser.open(REPO_URL)).pack(side="left")
        ttk.Button(links, text="Report a problem", command=lambda: webbrowser.open(REPO_URL + "/issues")).pack(
            side="left", padx=8
        )
        ttk.Button(links, text="About", command=on_about).pack(side="left")
        ttk.Button(links, text="Support WavMasta", command=lambda: webbrowser.open(SUPPORT_URL)).pack(side="right")
