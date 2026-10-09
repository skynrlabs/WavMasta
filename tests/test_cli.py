"""The command line: checking, mastering and error handling."""

import os

import pytest

from wavmasta.cli import main
from wavmasta.core import load
from wavmasta.core.analysis import lufs


def test_check_reports_problems_and_saves_nothing(songs, capsys):
    folder = os.path.dirname(songs["whine"])
    before = set(os.listdir(folder))
    assert main([songs["whine"], "--check"]) == 0
    out = capsys.readouterr().out
    assert "Whine Song.wav: " in out and "3,150 Hz" in out
    assert set(os.listdir(folder)) == before


def test_master_with_options(songs, tmp_path):
    assert (
        main([songs["hum"], "--tone", "roots-rock", "--loudness", "-11", "--format", "flac", "--out", str(tmp_path)])
        == 0
    )
    out = tmp_path / "Hum Song - master.flac"
    assert out.exists()
    y, sr = load(str(out))
    assert lufs(y, sr) == pytest.approx(-11, abs=0.3)


def test_auto_uses_suggestions(songs, tmp_path, capsys):
    assert main([songs["hiss"], "--auto", "--out", str(tmp_path)]) == 0
    assert "reducing hiss (40%)" in capsys.readouterr().out


def test_missing_file_fails(tmp_path, capsys):
    assert main([str(tmp_path / "nope.wav")]) == 1
    assert "Can't find" in capsys.readouterr().err


def test_bad_settings_are_rejected(songs):
    with pytest.raises(SystemExit):
        main([songs["clean"], "--loudness", "-2"])


def test_silent_song_fails(songs, tmp_path):
    assert main([songs["silent"], "--out", str(tmp_path)]) == 1


def test_album_masters_the_set_level_matched(songs, tmp_path, capsys):
    from wavmasta.core import album as albums

    files = [songs["clean"], songs["hum"], songs["hiss"]]
    assert main([*files, "--album", "--out", str(tmp_path)]) == 0
    assert "Listening to the album (3 songs)" in capsys.readouterr().out
    levels = [lufs(*load(str(p))) for p in sorted(tmp_path.iterdir())]
    assert len(levels) == 3 and albums.spread_db(levels) < 1.0


def test_trim_fade_and_deess_flags(songs, tmp_path):
    import numpy as np

    from . import synth

    padded = synth.write(tmp_path / "Padded.wav", np.pad(synth.song(), ((0, 0), (2 * synth.SR, 0))))
    out_a, out_b = tmp_path / "a", tmp_path / "b"
    assert main([padded, "--fade-out", "4", "--deess", "50", "--out", str(out_a)]) == 0
    assert main([padded, "--no-trim", "--out", str(out_b)]) == 0
    trimmed, sr = load(str(out_a / "Padded - master.wav"))
    kept, _ = load(str(out_b / "Padded - master.wav"))
    assert kept.shape[1] - trimmed.shape[1] > 1.9 * sr  # the 2 s of silence went
    assert np.max(np.abs(trimmed[:, -int(0.05 * sr) :])) < 1e-3  # and the fade ends in silence


def test_bad_release_settings_are_rejected(songs):
    for args in (["--deess", "150"], ["--fade-out", "30"]):
        with pytest.raises(SystemExit):
            main([songs["clean"], *args])
