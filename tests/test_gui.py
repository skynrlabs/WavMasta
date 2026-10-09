"""Window smoke tests: open the real app, click through it, and check what the user would see.

Needs a display. On Linux CI these run under xvfb (a virtual screen); elsewhere they're
skipped automatically when no display is available.
"""

import os
import shutil
import time

import pytest

tk = pytest.importorskip("tkinter")

pytestmark = pytest.mark.gui


def _display_available():
    try:
        root = tk.Tk()
        root.destroy()
        return True
    except tk.TclError:
        return False


if not _display_available():
    pytest.skip("no display available", allow_module_level=True)

from wavmasta.gui import journeys  # noqa: E402
from wavmasta.gui.app import WavMastaApp  # noqa: E402
from wavmasta.gui.pages import PAGES  # noqa: E402


@pytest.fixture
def app(monkeypatch, tmp_path):
    played = []
    monkeypatch.setattr(journeys.Player, "play", lambda self, wav: played.append(wav))  # no speakers on CI
    monkeypatch.setattr(journeys, "PREVIEW_DIR", str(tmp_path))
    root = tk.Tk()
    a = WavMastaApp(root)
    a.played = played
    a.settings_page.out_dir = str(tmp_path / "out")
    root.update()
    yield a
    a.quit()


@pytest.fixture
def copies(songs, tmp_path):
    """Fresh copies of the test songs, so mastering writes next to them in this test's folder."""
    d = tmp_path / "in"
    d.mkdir()
    return {k: str(shutil.copy(v, d / os.path.basename(v))) for k, v in songs.items()}


def add(app, monkeypatch, paths):
    from tkinter import filedialog

    monkeypatch.setattr(filedialog, "askopenfilenames", lambda **kw: list(paths))
    app.master_page.add_files()
    app.root.update()


def wait(app, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        app.root.update()
        if not app.busy:
            return
        time.sleep(0.05)
    raise AssertionError("timed out waiting for the window")


def status(app):
    return app.status_card.status.get()


def page(app):
    return app.master_page


# ---- opening and navigating
def test_opens_on_master_page(app):
    assert app.page_title.get() == "Master"
    assert app.root.cget("menu") == ""
    assert status(app) == "Ready"
    assert "show up here" in app.activity.as_text()
    assert page(app).card.title.get() == "Sound"
    assert app.action.master_btn.cget("text") == "Master"
    assert "WAV 24-bit" in app.action.where.get()


def test_every_page_opens(app):
    for key, _, title, _ in PAGES:
        app.show_page(key)
        assert app.page_title.get() == title


def test_master_without_songs_says_so(app):
    app.masterer.start()
    assert "Add at least one song" in status(app)


# ---- adding and removing songs
def test_add_songs_and_folder(app, monkeypatch, copies, tmp_path):
    add(app, monkeypatch, [copies["clean"], copies["hum"]])
    assert len(page(app).tracks) == 2
    assert app.action.master_btn.cget("text") == "Master 2 songs"
    assert app.nav.items["master"][1].cget("text") == "Master  (2)"
    # adding the same file again does nothing; a folder adds what's new in it
    added = page(app).add_paths([copies["clean"], os.path.dirname(copies["clean"])])
    assert added == len(copies) - 2
    assert len(page(app).tracks) == len(copies)


def test_folder_skips_masters(app, copies):
    folder = os.path.dirname(copies["clean"])
    shutil.copy(copies["clean"], os.path.join(folder, "Clean Song - master.wav"))
    page(app).add_paths([folder])
    assert not any(" - master" in t.name for t in page(app).tracks)


def test_new_songs_start_with_the_selected_sound(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"]])
    t = page(app).tracks[0]
    t.tone, t.glue = "Country", 50
    page(app).add_paths([copies["hum"]])
    new = page(app).tracks[1]
    assert (new.tone, new.glue) == ("Country", 50)


def test_remove_and_clear(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"], copies["hum"], copies["whine"]])
    page(app).remove(0)
    assert [t.name for t in page(app).tracks] == ["Hum Song.wav", "Whine Song.wav"]
    page(app).clear_tracks()
    assert page(app).tracks == [] and page(app).card.title.get() == "Sound"


# ---- the sound card
def test_card_edits_the_selected_song(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"], copies["hum"]])
    card = page(app).card
    page(app).select(1)
    assert card.title.get() == "Hum Song.wav"
    card.tone_var.set("Roots rock")
    card._store()
    card.noise_var.set(45)
    card._store()
    t0, t1 = page(app).tracks
    assert (t1.tone, t1.denoise) == ("Roots rock", 45)
    assert (t0.tone, t0.denoise) == ("Neutral", 0)
    assert card.noise_text.get() == "45% · medium"
    page(app).select(0)
    assert card.tone_var.get() == "Neutral"


def test_apply_to_all(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"], copies["hum"], copies["whine"]])
    page(app).tracks[0].tone = "Warm"
    page(app).select(0)
    page(app).apply_to_all()
    assert {t.tone for t in page(app).tracks} == {"Warm"}
    assert "Applied" in status(app)


def test_reference_disables_tone_and_loudness(app, monkeypatch, copies):
    from tkinter import filedialog

    add(app, monkeypatch, [copies["clean"]])
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: copies["hum"])
    card = page(app).card
    card.pick_reference()
    assert page(app).tracks[0].reference == copies["hum"]
    assert "disabled" in card.tone_box.state()
    assert "Hum Song.wav" in card.ref_text.get()
    card.clear_reference()
    assert page(app).tracks[0].reference is None
    assert "disabled" not in card.tone_box.state()


# ---- check
def test_check_finds_problems_and_suggestions_apply(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["messy"]])
    app.checker.start()
    wait(app)
    t = page(app).tracks[0]
    assert t.report is not None
    text = page(app).card.findings.cget("text")
    assert "Hiss" in text and "7,400 Hz" in text
    assert "to fix" in status(app)
    assert page(app).card.suggest_btn.winfo_manager()  # Use suggestions is showing
    app.use_suggestions()
    assert t.denoise == 40
    assert "Suggestions applied" in status(app)
    assert not page(app).card.suggest_btn.winfo_manager()  # nothing left to suggest
    assert "Check Messy Song.wav" in app.activity.as_text()


def test_check_clean_song(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"]])
    app.checker.start()
    wait(app)
    assert "sounds clean" in status(app)


# ---- before / after
def test_before_and_after_play_level_matched_clips(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["whine"]])
    page(app)._play(0, "after")
    wait(app)
    assert app.played and "wavmasta_after_" in app.played[-1]
    assert page(app).table.rows[0]["after"].cget("text") == "Stop"
    assert status(app).startswith("After:")
    # Before reuses the same render (no second wait) and plays the original
    page(app)._play(0, "before")
    wait(app)
    assert "wavmasta_before_" in app.played[-1]
    assert page(app).table.rows[0]["before"].cget("text") == "Stop"
    assert page(app).table.rows[0]["after"].cget("text") == "After"
    # same loudness, so the comparison is fair
    from wavmasta.core import load
    from wavmasta.core.analysis import lufs

    b, sr = load(app.played[-1])
    a, _ = load(app.played[-2])
    assert lufs(b, sr) == pytest.approx(lufs(a, sr), abs=1.0)
    # pressing Stop stops
    page(app)._play(0, "before")
    assert page(app).table.playing is None and status(app) == "Stopped"


def test_preview_fills_in_the_report(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["hum"]])
    app.preview.start("after")
    wait(app)
    assert page(app).tracks[0].report is not None
    assert "Preview Hum Song.wav" in app.activity.as_text()


def test_silent_song_preview(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["silent"]])
    app.preview.start("after")
    wait(app)
    assert "silent" in status(app)


# ---- master
def test_master_saves_every_song(app, monkeypatch, copies, tmp_path):
    add(app, monkeypatch, [copies["clean"], copies["hum"], copies["silent"]])
    app.masterer.start()
    wait(app, 180)
    out = tmp_path / "out"
    assert sorted(os.listdir(out)) == ["Clean Song - master.wav", "Hum Song - master.wav"]
    t0, t1, t2 = page(app).tracks
    assert t0.status.startswith("saved · -14") and t0.status_kind == "ok"
    assert t2.status == "silent, skipped"
    assert status(app) == "Done: 2 of 3 mastered"
    assert "disabled" not in app.action.open_btn.state()
    feed = app.activity.as_text()
    assert "Master 3 songs" in feed and "2 of 3 saved" in feed and "60 Hz, 120 Hz" in feed


def test_master_reuses_the_preview_render(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"]])
    app.preview.start("after")
    wait(app)
    calls = []
    real = journeys.master_audio
    monkeypatch.setattr(journeys, "master_audio", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    app.masterer.start()
    wait(app)
    assert calls == []  # the song mastered for the preview was saved as-is


def test_changed_since_saved(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"]])
    app.masterer.start()
    wait(app)
    t = page(app).tracks[0]
    saved = t.status
    t.glue = 70
    page(app).refresh_staleness()
    assert t.status == "changed · master again" and t.status_kind == "warn"
    t.glue = 30
    page(app).refresh_staleness()
    assert t.status == saved
    app.settings_page.format_var.set("FLAC 24-bit")  # the format changes the file too
    app.root.update()
    assert t.status == "changed · master again"


def test_flac_and_folder_setting(app, monkeypatch, copies, tmp_path):
    add(app, monkeypatch, [copies["clean"]])
    app.settings_page.format_var.set("FLAC 24-bit")
    app.masterer.start()
    wait(app)
    assert os.listdir(tmp_path / "out") == ["Clean Song - master.flac"]
    assert "FLAC" in app.action.where.get()


def test_bad_ceiling_sends_you_to_settings(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"]])
    app.settings_page.ceiling_var.set("5")
    app.masterer.start()
    assert app.page_title.get() == "Settings"
    assert "ceiling" in status(app)


def test_reset_everything(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"]])
    t = page(app).tracks[0]
    t.tone, t.denoise = "Bright", 60
    app.settings_page.format_var.set("MP3 320 kbps")
    app.reset_settings()
    assert (t.tone, t.denoise) == ("Neutral", 0)
    assert app.settings_page.format_var.get() == "WAV 24-bit"


def test_settings_are_remembered(app):
    from wavmasta.config import load_settings

    app.settings_page.format_var.set("FLAC 24-bit")
    app.settings_page.ceiling_var.set("-2.0")
    assert load_settings()["format"] == "FLAC 24-bit"
    assert load_settings()["ceiling"] == -2.0


def test_shortcuts(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"]])
    app.root.event_generate("<F1>")
    app.root.update()
    assert app.page_title.get() == "Help"
    app.root.event_generate("<Control-Key-3>")
    app.root.update()
    assert app.page_title.get() == "Settings"


# ---- listening locks the sound settings
def test_playing_locks_the_sound_until_stopped(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"], copies["hum"]])
    page(app)._play(0, "after")
    wait(app)
    card, row = page(app).card, page(app).table.rows[0]
    # sound settings, adding/removing songs and Master are locked
    assert all(s.cget("state") == "disabled" for s in card.sliders)
    for w in (card.tone_box, card.loud_box, card.check_btn, card.ref_btn, card.hum_check, card.apply_btn):
        assert "disabled" in w.state()
    assert "disabled" in page(app).add_btn.state() and "disabled" in row["remove"].state()
    assert "disabled" in app.action.master_btn.state()
    assert "Stop" in card.hint.get()
    # ...but Before, After and Stop still work, on every row
    for r in page(app).table.rows:
        assert "disabled" not in r["before"].state() and "disabled" not in r["after"].state()
    # clicking another song's name doesn't move the card away from what's playing
    page(app).table.rows[1]["name"].event_generate("<Button-1>")
    app.root.update()
    assert page(app).selected == 0
    # shortcuts that change things say why they're waiting
    app.root.event_generate("<Control-Return>")
    app.root.update()
    assert status(app) == "Stop playback first"
    # Stop unlocks everything
    page(app)._play(0, "after")
    assert all(s.cget("state") == "normal" for s in card.sliders)
    assert "disabled" not in card.tone_box.state() and "disabled" not in app.action.master_btn.state()
    assert "disabled" not in row["remove"].state()
    assert "Stop" not in card.hint.get()


def test_switching_before_and_after_stays_locked(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"]])
    page(app)._play(0, "after")
    wait(app)
    page(app)._play(0, "before")
    wait(app)
    assert page(app).table.playing == (0, "before")
    assert "disabled" in page(app).card.tone_box.state()


def test_playback_ending_by_itself_unlocks(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"]])
    page(app)._play(0, "after")
    wait(app)
    app.preview._ended(app.preview.token)
    assert page(app).table.playing is None
    assert all(s.cget("state") == "normal" for s in page(app).card.sliders)


def test_reference_keeps_tone_off_after_unlock(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["clean"]])
    page(app).tracks[0].reference = copies["hum"]
    page(app).card.show(page(app).tracks[0], 1)
    page(app)._play(0, "after")
    wait(app)
    page(app)._play(0, "after")  # stop
    assert "disabled" in page(app).card.tone_box.state()  # still off: the reference sets the tone


def test_history_shows_a_breakdown_under_each_mastered_song(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["messy"]])
    page(app).tracks[0].denoise = 40
    app.masterer.start()
    wait(app, 120)
    feed = app.activity.as_text()
    for line in (
        "Clipping | none ✓",
        "True peak |",
        "under the -1 dBTP ceiling",
        "Loudness | -14",
        "Punch |",
        "Hiss | reduced 40%",
        "Hum and whine | removed",
        "7,400 Hz",
        "File | WAV 24-bit",
    ):
        assert line in feed, line
    # the breakdown sits under the song, which is opened to show it
    tree = app.activity.tree
    action = tree.get_children()[0]
    song = tree.get_children(action)[0]
    assert tree.item(song, "open") and len(tree.get_children(song)) >= 7


def test_breakdown_flags_what_was_found_but_not_fixed(app, monkeypatch, copies):
    add(app, monkeypatch, [copies["hiss"]])
    app.masterer.start()
    wait(app, 120)
    assert "Hiss | found, not reduced | try Noise reduction around 40%" in app.activity.as_text()


# ---- text is never clipped by the next column
def test_history_text_never_runs_under_the_next_column(app, monkeypatch, copies, tmp_path):
    long = tmp_path / "Burning Down The Back Roads Of Simcoe County (Acoustic Demo, Take 4).wav"
    shutil.copy(copies["messy"], long)
    add(app, monkeypatch, [str(long)])
    app.masterer.start()
    wait(app, 120)
    app.show_page("history")
    app.root.update()
    log = app.activity
    log._fit_columns()
    tree = log.tree
    shortened = 0

    def check(item, depth):
        nonlocal shortened
        font = log._font_for(item)
        assert font.measure(tree.item(item, "text")) + 20 * (depth + 1) <= tree.column("#0", "width") + 2
        for col, value in zip(log.COLUMNS, tree.item(item, "values"), strict=False):
            if value:
                assert font.measure(str(value)) <= tree.column(col, "width"), (col, value)
        full, _ = log._full(item)
        if tree.item(item, "text") != full:
            assert tree.item(item, "text").endswith("…")
            shortened += 1
        for child in tree.get_children(item):
            check(child, depth + 1)

    for item in tree.get_children():
        check(item, 0)
    assert shortened >= 1  # the long name was shortened to fit...
    assert long.name in log.as_text()  # ...but the full name is kept (hover shows it)
    assert not log.xscroll.winfo_ismapped()  # and the table still fits without scrolling sideways


def test_long_song_names_fit_or_end_in_an_ellipsis(app, monkeypatch, copies, tmp_path):
    long = tmp_path / ("A Very Long Song Title That Goes On And On - Final Mix Version Three (Remastered).wav")
    shutil.copy(copies["clean"], long)
    add(app, monkeypatch, [copies["clean"], str(long)])
    app.root.update()
    table = page(app).table
    for r in table.rows:
        shown = r["name"].cget("text")
        assert table.name_font.measure(shown) <= table.song_width
        assert shown == r["full_name"] or shown.endswith("…")
    assert table.rows[0]["name"].cget("text") == "Clean Song.wav"  # short names are never shortened
