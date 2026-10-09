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
