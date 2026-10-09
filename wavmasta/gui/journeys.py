"""The three things a user does: check a song, hear it before and after, and master songs.

Each journey does its slow work on a background thread and reports back through
app.post(), because Tk widgets may only be touched from the main thread. Results go to
the Activity table as short, readable entries (see activity.py).
"""

import hashlib
import os
import tempfile
import threading

from ..core import Player, ab_clips, analyze, load, master_audio, output_path, save
from ..core.preview import write_wav16
from .activity import master_report, short_path

PREVIEW_DIR = tempfile.gettempdir()


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


class Renders:
    """Remembers the last mastered song, so hearing After and then clicking Master doesn't do the
    work twice. One song at a time: a full song in memory is about 40 MB a minute."""

    def __init__(self):
        self.key = None
        self.value = None
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            return self.value if key == self.key else None

    def put(self, key, value):
        with self.lock:
            self.key, self.value = key, value


def render(app, track, ceiling, log=lambda m: None):
    """Load, measure and master one song (or reuse the last result). Returns a dict."""
    key = (track.path, os.path.getmtime(track.path), track.sound(), ceiling)
    cached = app.renders.get(key)
    if cached:
        return cached
    audio, sr = load(track.path)
    before = analyze(audio, sr)
    if before.lufs == float("-inf"):  # silent: nothing to master
        return {"audio": audio, "mastered": audio, "sr": sr, "before": before, "info": {"tones": []}, "key": key}
    s = track.settings(ceiling)
    reference = load(s.reference) if s.reference else None
    mastered, info = master_audio(audio, sr, s, log=log, reference=reference, tones=before.tones)
    out = {"audio": audio, "mastered": mastered, "sr": sr, "before": before, "info": info, "key": key}
    app.renders.put(key, out)
    return out


class CheckJourney:
    """Measure the selected song and say what's wrong with it, with suggested cleanup settings."""

    def __init__(self, app):
        self.app = app

    def start(self):
        app = self.app
        if app.busy:
            return
        track = app.master_page.selected_track()
        if track is None:
            app.say("Add a song first, then Check it", "warn")
            app.show_page("master")
            return
        app.set_busy(True)
        app.say(f"Checking {track.name}...", "busy", "Measuring loudness, peaks, hiss, hum and harsh highs")
        threading.Thread(target=self._work, args=(track,), daemon=True).start()

    def _work(self, track):
        app = self.app
        try:
            audio, sr = load(track.path)
            report = analyze(audio, sr)
            app.post(lambda: self._done(track, report))
        except Exception as exc:
            msg = f"Couldn't check {track.name}: {exc}"
            app.post(lambda: (app.set_busy(False), app.say(msg, "warn")))

    def _done(self, track, report):
        app = self.app
        app.set_busy(False)
        track.report = report
        if app.master_page.selected_track() is track:
            app.master_page.card.show_report(report)
        findings = report.findings()
        problems = [f for f in findings if not f.startswith("No noise problems")]
        if problems:
            app.say(
                f"{track.name}: {plural(len(problems), 'thing')} to fix",
                "warn",
                "Use suggestions sets the cleanup for you, then press After to hear it",
            )
        else:
            app.say(f"{track.name} sounds clean", "ok", f"Now {report.summary()} · pick a tone and Master")
        feed = app.activity
        feed.action(f"Check {track.name}", report.summary())
        for line in findings:
            feed.song(track.name, line.split(".")[0], line)


class PreviewJourney:
    """Master the selected song in memory and play its loudest 20 seconds, before or after.

    Before is turned up or down to the same loudness as After, so you compare the sound itself:
    louder always seems better at first.
    """

    def __init__(self, app):
        self.app = app
        self.player = Player()
        self.clips = {}  # render key -> (before.wav, after.wav, start seconds, length seconds)
        self.token = None

    def start(self, which):
        app = self.app
        if app.busy:
            return
        track = app.master_page.selected_track()
        if track is None:
            app.say("Add a song first, then press Before or After", "warn")
            app.show_page("master")
            return
        ceiling, err = app.settings_page.ceiling()
        if err:
            app.say(err, "warn")
            app.show_page("settings")
            return
        self.player.stop()
        self.token = None
        app.master_page.set_playing(None)
        app.set_busy(True)
        app.say(f"Building the before/after preview of {track.name}...", "busy", "Mastering the song in memory first")
        threading.Thread(target=self._work, args=(track, which, ceiling), daemon=True).start()

    def _work(self, track, which, ceiling):
        app = self.app
        try:
            r = render(app, track, ceiling)
            if r["before"].lufs == float("-inf"):
                app.post(lambda: (app.set_busy(False), app.say(f"{track.name} is silent", "warn")))
                return
            if r["key"] not in self.clips:
                before, after, start = ab_clips(r["audio"], r["mastered"], r["sr"])
                tag = hashlib.md5(repr(r["key"]).encode()).hexdigest()[:10]
                b = write_wav16(os.path.join(PREVIEW_DIR, f"wavmasta_before_{tag}.wav"), before, r["sr"])
                a = write_wav16(os.path.join(PREVIEW_DIR, f"wavmasta_after_{tag}.wav"), after, r["sr"])
                self.clips = {r["key"]: (b, a, start, after.shape[1] / r["sr"])}  # only the latest song
                first = True
            else:
                first = False
            b, a, start, seconds = self.clips[r["key"]]
            app.post(lambda: self._play(track, which, b if which == "before" else a, start, seconds, r, first))
        except Exception as exc:
            msg = f"Preview failed: {exc}"
            app.post(lambda: (app.set_busy(False), app.say(msg, "warn")))

    def _play(self, track, which, wav, start, seconds, r, first):
        app = self.app
        app.set_busy(False)
        if track.report is None:
            track.report = r["before"]
            if app.master_page.selected_track() is track:
                app.master_page.card.show_report(track.report)
        if first:
            feed = app.activity
            feed.action(f"Preview {track.name}", track.settings(0).describe())
            feed.song(track.name, f"from {int(start // 60)}:{int(start % 60):02d}", describe_preview(r))
        try:
            self.player.play(wav)
        except Exception as exc:
            app.say("Couldn't play the preview", "warn", f"{exc}. It was saved to {wav}")
            return
        when = f"{int(start // 60)}:{int(start % 60):02d}"
        if which == "before":
            app.say(f"Before: {track.name}", "muted", f"The original from {when}, at the same loudness as After")
        else:
            app.say(
                f"After: {track.name}", "ok", f"The master from {when}. Happy with it? Stop, then Master to save it"
            )
        app.master_page.set_playing(track, which)
        self.token = token = object()
        app.root.after(int(seconds * 1000) + 300, lambda: self._ended(token))

    def _ended(self, token):
        if self.token is token:
            self.token = None
            self.app.master_page.set_playing(None)

    def stop(self):
        self.player.stop()
        self.token = None
        self.app.master_page.set_playing(None)
        self.app.say("Stopped", detail="Press Before or After on a song to hear it again")


def describe_preview(r):
    info = r["info"]
    parts = [f"{r['before'].lufs:.1f} → {info['target']:g} LUFS"]
    if info.get("tones"):
        parts.append("notched " + ", ".join(f"{f:,.0f} Hz" for f, _ in info["tones"][:3]))
    return " · ".join(parts)


class MasterJourney:
    """Master every song in the list and save the files."""

    def __init__(self, app):
        self.app = app
        self.last_out_dir = None

    def start(self):
        app = self.app
        if app.busy:
            return
        tracks = list(app.master_page.tracks)
        if not tracks:
            app.say("Add at least one song first", "warn")
            app.show_page("master")
            return
        ceiling, err = app.settings_page.ceiling()
        if err:
            app.say(err, "warn")
            app.show_page("settings")
            return
        for t in tracks:
            err = t.settings(ceiling).check()
            if err:
                app.say(f"{t.name}: {err}", "warn")
                return
        fmt = app.settings_page.format_var.get()
        out_dir = app.settings_page.out_dir
        app.activity.action(f"Master {plural(len(tracks), 'song')}", f"{fmt} · ceiling {ceiling:g} dBTP")
        self.sigs = {id(t): app.master_page.signature(t) for t in tracks}
        for t in tracks:
            t.saved_sig = None
            self._status(t, "waiting...", "muted")
        app.preview.player.stop()
        app.master_page.set_playing(None)
        app.set_busy(True)
        app.action.open_btn.state(["disabled"])
        app.say(f"Mastering {plural(len(tracks), 'song')}...", "busy", "Each row shows its result as it finishes")
        app.status_card.start_progress(len(tracks))
        args = (tracks, ceiling, fmt, out_dir)
        threading.Thread(target=self._work, args=args, daemon=True).start()

    def _status(self, track, text, kind, saved=None):
        """Update a song's status (call on the window's thread)."""
        track.status, track.status_kind = text, kind
        if saved:
            track.saved = saved
        self.app.master_page.show_status(track)

    def _work(self, tracks, ceiling, fmt, out_dir):
        app = self.app
        feed = app.activity
        ok = 0
        for i, t in enumerate(tracks):
            msg = f"Mastering {t.name}  ({i + 1} of {len(tracks)})"
            app.post(
                lambda m=msg, v=i, s=t: (
                    app.say(m, "busy", "Each row shows its result as it finishes"),
                    app.status_card.set_progress(v),
                    self._status(s, "mastering...", "busy"),
                )
            )
            try:
                r = render(app, t, ceiling)
                if r["before"].lufs == float("-inf"):
                    app.post(
                        lambda s=t: (
                            feed.problem(s.name, "silent, skipped"),
                            self._status(s, "silent, skipped", "warn"),
                        )
                    )
                    continue
                after = analyze(r["mastered"], r["sr"])
                dest = save(output_path(t.path, out_dir, fmt), r["mastered"], r["sr"], fmt)
                ok += 1
                self.last_out_dir = os.path.dirname(dest)
                result = {"before": r["before"], "after": after, "info": r["info"]}
                details = f"{after.lufs:.1f} LUFS · peak {after.true_peak:.1f} dBTP · details below"
                report = master_report(result, t.settings(ceiling), fmt, ceiling)
                done = f"saved · {after.lufs:.1f} LUFS"
                app.post(
                    lambda s=t, d=details, o=dest, x=done, rep=report: (
                        feed.details(feed.song(s.name, "mastered", d, saved=o), rep),
                        self._status(s, x, "ok", saved=o),
                        app.master_page.mark_saved(s, self.sigs[id(s)]),
                    )
                )
            except Exception as exc:  # keep going with the other songs
                err = f"couldn't master: {exc}"
                app.post(lambda s=t, e=err: (feed.problem(s.name, e), self._status(s, e, "warn")))
        if ok:
            summary = ("Done", f"{ok} of {len(tracks)} saved", f"in {short_path(self.last_out_dir)}")
        else:
            summary = ("Nothing was mastered", "", "")
        app.post(lambda: feed.summary(*summary, good=ok == len(tracks)))
        app.post(lambda: self._finish(ok, len(tracks)))

    def _finish(self, ok, total):
        app = self.app
        app.set_busy(False)
        app.status_card.set_progress(total)
        skipped = total - ok
        if ok:
            detail = f"Saved in {short_path(self.last_out_dir)}"
            if skipped:
                detail = f"{skipped} skipped (see the Songs list) · " + detail
        else:
            detail = "Check the Songs list for what went wrong"
        app.say(f"Done: {ok} of {total} mastered", "ok" if ok == total else "warn", detail)
        if self.last_out_dir:
            app.action.open_btn.state(["!disabled"])
            if app.settings_page.open_when_done.get() and ok:
                app.open_folder()
