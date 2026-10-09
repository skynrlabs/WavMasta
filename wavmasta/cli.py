"""Command line: wavmasta "Song.wav" --tone country --loudness -14"""

import argparse
import os
import sys

from . import __version__
from .config import DEFAULT_CEILING, TONES
from .core import Settings, analyze, load, master_file
from .core import album as albums

TONE_KEYS = {name.lower().replace(" ", "-"): name for name in TONES}  # "roots-rock" -> "Roots rock"
FORMAT_KEYS = {"wav": "WAV 24-bit", "wav16": "WAV 16-bit (CD)", "flac": "FLAC 24-bit", "mp3": "MP3 320 kbps"}


def build_parser():
    ap = argparse.ArgumentParser(
        prog="wavmasta",
        description="Clean up and master songs. Saves '<song> - master.wav' next to each one.",
    )
    ap.add_argument("--version", action="version", version=f"WavMasta {__version__}")
    ap.add_argument("songs", nargs="+", help="audio files (wav, flac, mp3, aiff, ogg, m4a)")
    ap.add_argument("--check", action="store_true", help="only measure the songs and report problems; save nothing")
    ap.add_argument("--tone", default="neutral", choices=list(TONE_KEYS), help="EQ shape (default: neutral)")
    ap.add_argument("--loudness", type=float, default=-14.0, help="target loudness in LUFS (default: -14)")
    ap.add_argument("--ceiling", type=float, default=DEFAULT_CEILING, help="true-peak ceiling in dBTP (default: -1)")
    ap.add_argument("--denoise", type=int, default=0, help="noise reduction 0-100 (default: 0, off)")
    ap.add_argument("--no-hum-fix", action="store_true", help="don't notch out steady hum and whine")
    ap.add_argument("--tame-highs", type=float, default=0.0, help="cut harsh highs above 11 kHz, 0-6 dB")
    ap.add_argument("--glue", type=int, default=30, help="glue compression 0-100 (default: 30)")
    ap.add_argument("--width", type=int, default=100, help="stereo width 0-150 (default: 100)")
    ap.add_argument("--reference", help="a finished song to match tone and loudness to")
    ap.add_argument("--deess", type=int, default=0, help="tame sharp 's' sounds in vocals, 0-100 (default: 0, off)")
    ap.add_argument("--fade-out", type=float, default=0.0, help="fade the end over this many seconds, 0-10")
    ap.add_argument("--no-trim", action="store_true", help="keep silence at the start and end")
    ap.add_argument("--album", action="store_true", help="master the songs as one album: matched tone and loudness")
    ap.add_argument("--auto", action="store_true", help="use the cleanup settings Check suggests for each song")
    ap.add_argument("--format", default="wav", choices=list(FORMAT_KEYS), help="wav (24-bit), wav16, flac or mp3")
    ap.add_argument("--out", help="folder for the mastered files (default: next to each song)")
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    fmt = FORMAT_KEYS[a.format]
    failed = 0
    album = None
    if a.album and not a.check:
        found = [p for p in a.songs if os.path.isfile(p)]
        if len(found) >= 2:
            print(f"Listening to the album ({len(found)} songs) to match their tone...")
            album = albums.profile([(p, *load(p)) for p in found])
    for song in a.songs:
        if not os.path.isfile(song):
            print(f"Can't find {song}", file=sys.stderr)
            failed += 1
            continue
        if a.check:
            audio, sr = load(song)
            report = analyze(audio, sr)
            print(f"{os.path.basename(song)}: {report.summary()}")
            for line in report.findings():
                print(f"  - {line}")
            continue
        s = Settings(
            tone=TONE_KEYS[a.tone],
            target_lufs=a.loudness,
            ceiling=a.ceiling,
            denoise=a.denoise,
            fix_tones=not a.no_hum_fix,
            tame_top=a.tame_highs,
            glue=a.glue,
            width=a.width,
            reference=a.reference,
            deess=a.deess,
            fade_out=a.fade_out,
            trim=not a.no_trim,
        )
        if a.auto:
            audio, sr = load(song)
            for key, value in analyze(audio, sr).suggested().items():
                if (
                    (key == "denoise" and a.denoise)
                    or (key == "deess" and a.deess)
                    or (key == "fade_out" and a.fade_out)
                ):
                    continue  # an explicit setting wins
                setattr(s, key, value)
        err = s.check()
        if err:
            ap.error(err)
        try:
            result = master_file(song, s, a.out, fmt, album=album)
            if result is None:
                failed += 1
        except Exception as exc:
            print(f"  couldn't master {song}: {exc}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0
