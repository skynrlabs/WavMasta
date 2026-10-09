"""Cleanup and the mastering chain: each fix removes its problem and leaves the music alone."""

import os

import numpy as np
import pytest

from wavmasta.core import Settings, analyze, chain, cleanup, load, master_audio, master_file, output_path, save
from wavmasta.core.analysis import lufs, true_peak_db

from . import synth
from .synth import SR, tone_level_db


def rel(x, freq):
    """A frequency's level relative to the song's loudness."""
    return tone_level_db(x, freq) - lufs(x, SR)


# ---- cleanup
def test_notch_removes_whine(audio):
    x = audio["whine"]
    y, info = master_audio(x, SR, Settings(glue=0), log=lambda m: None)
    assert [round(f) for f, _ in info["tones"]] == [3150]
    assert rel(y, 3150) < rel(x, 3150) - 25


def test_notch_removes_hum(audio):
    x = audio["hum"]
    y, _ = master_audio(x, SR, Settings(glue=0), log=lambda m: None)
    assert rel(y, 120) < rel(x, 120) - 10  # 60 Hz itself is masked by the bass notes around it


def test_hum_fix_can_be_turned_off(audio):
    _, info = master_audio(audio["hum"], SR, Settings(fix_tones=False), log=lambda m: None)
    assert info["tones"] == []


def test_denoise_lowers_hiss_and_leaves_the_low_end_alone(audio):
    from scipy.signal import butter, sosfiltfilt

    clean, x = synth.song(), audio["hiss"]  # the same song without the hiss
    y = cleanup.denoise(x, SR, 0.5)
    hp = butter(6, 5000, "highpass", fs=SR, output="sos")  # the synth music has nothing up here: pure hiss
    lp = butter(6, 800, "lowpass", fs=SR, output="sos")  # bass and the body of the chords

    def db(a):
        return 20 * np.log10(np.std(a) + 1e-12)

    assert db(sosfiltfilt(hp, y)) < db(sosfiltfilt(hp, x)) - 10  # hiss down by more than 10 dB
    low_change = db(sosfiltfilt(lp, y) - sosfiltfilt(lp, x)) - db(sosfiltfilt(lp, x))
    assert low_change < -60  # below 1 kHz nothing is touched
    assert lufs(y, SR) == pytest.approx(lufs(clean, SR), abs=0.3)


def test_stronger_denoise_removes_more(audio):
    from scipy.signal import butter, sosfiltfilt

    hp = butter(6, 5000, "highpass", fs=SR, output="sos")
    levels = [np.std(sosfiltfilt(hp, cleanup.denoise(audio["hiss"], SR, a))) for a in (0.2, 0.5, 0.9)]
    assert levels[0] > levels[1] > levels[2]


def test_denoise_off_changes_nothing(audio):
    x = audio["hiss"]
    assert cleanup.denoise(x, SR, 0) is x


def test_wider_stereo_keeps_the_bass_centred(audio):
    x = audio["clean"]
    y = chain.stereo_width(x, SR, 150)
    side_before = (x[0] - x[1]) / 2
    side_after = (y[0] - y[1]) / 2
    assert np.std(side_after) > np.std(side_before) * 1.2
    # synth bass and kick are dead centre, so the low end must stay mono
    assert tone_level_db(np.vstack([side_after, side_after]), 55.0) < tone_level_db(x, 55.0) - 40


def test_mono_width(audio):
    y = chain.stereo_width(audio["clean"], SR, 0)
    assert np.allclose(y[0], y[1], atol=1e-6)


# ---- loudness and peaks
@pytest.mark.parametrize("target", [-16.0, -14.0, -11.0])
def test_hits_loudness_target_under_the_ceiling(audio, target):
    y, info = master_audio(audio["clean"], SR, Settings(target_lufs=target), log=lambda m: None)
    assert lufs(y, SR) == pytest.approx(target, abs=0.3)
    assert true_peak_db(y) <= -1.0 + 0.05


def test_ceiling_is_respected_when_very_loud(audio):
    y, _ = master_audio(audio["clean"], SR, Settings(target_lufs=-9, ceiling=-2.0), log=lambda m: None)
    assert true_peak_db(y) <= -2.0 + 0.05


def test_every_tone_preset_runs(audio):
    from wavmasta.config import TONES

    for name in TONES:
        y, _ = master_audio(audio["clean"], SR, Settings(tone=name, glue=0), log=lambda m: None)
        assert lufs(y, SR) == pytest.approx(-14.0, abs=0.3)


def test_reference_moves_tone_toward_reference(audio):
    from scipy.signal import welch

    x = audio["clean"]
    bright = chain.apply_curve(x, SR, np.array([20, 3000, 6000, 22050]), np.array([0, 0, 6, 6]))

    def hi_mid(a):
        f, p = welch(a.mean(axis=0), SR, nperseg=8192)
        return 10 * np.log10(p[(f > 6000) & (f < 10000)].mean() / p[(f > 200) & (f < 2000)].mean())

    y, info = master_audio(x, SR, Settings(glue=0), log=lambda m: None, reference=(bright, SR))
    assert hi_mid(y) > hi_mid(x) + 2  # moved toward the brighter reference
    assert info["target"] == pytest.approx(np.clip(lufs(bright, SR), -20, -7), abs=0.01)


# ---- settings
def test_settings_are_checked():
    assert Settings().check() is None
    assert "Unknown tone" in Settings(tone="Dubstep").check()
    assert "Loudness" in Settings(target_lufs=-3).check()
    assert "reference" in Settings(reference="/nowhere/song.wav").check()
    assert "-14 LUFS" in Settings().describe()


# ---- files
def test_master_file_saves_next_to_song_and_leaves_original(songs, tmp_path):
    src = songs["messy"]
    from pathlib import Path

    before = Path(src).read_bytes()
    result = master_file(src, Settings(denoise=40), log=lambda m: None)
    assert result["saved"] == output_path(src)
    assert result["saved"].endswith("Messy Song - master.wav")
    assert Path(src).read_bytes() == before
    out, sr = load(result["saved"])
    assert sr == SR and lufs(out, sr) == pytest.approx(-14.0, abs=0.3)
    assert result["after"].tones == [] or all(ex < 15 for _, ex in result["after"].tones)
    os.remove(result["saved"])


def test_silent_song_is_skipped(songs):
    assert master_file(songs["silent"], Settings(), log=lambda m: None) is None


@pytest.mark.parametrize(
    "fmt, ext",
    [("WAV 24-bit", ".wav"), ("WAV 16-bit (CD)", ".wav"), ("FLAC 24-bit", ".flac"), ("MP3 320 kbps", ".mp3")],
)
def test_every_output_format(tmp_path, fmt, ext):
    x = synth.music(seconds=3)
    path = output_path(str(tmp_path / "Song.wav"), fmt=fmt)
    assert path.endswith("Song - master" + ext)
    save(path, x * 0.5, SR, fmt)
    y, sr = load(path)
    assert sr == SR and y.shape[0] == 2
    assert abs(lufs(y, SR) - lufs(x * 0.5, SR)) < 0.5


def test_output_never_overwrites_the_source(tmp_path):
    src = str(tmp_path / "Song - master.wav")
    assert output_path(src) != src


def test_mono_files_become_stereo(tmp_path):
    path = str(tmp_path / "mono.wav")
    save(path, synth.music(seconds=2)[:1], SR)
    y, _ = load(path)
    assert y.shape[0] == 2


def test_analyze_from_file_matches_memory(songs):
    x, sr = load(songs["whine"])
    assert [round(f) for f, _ in analyze(x, sr).tones] == [3150]


def test_hum_and_its_harmonic_are_both_reduced():
    h = synth.song(hum=0.006)
    y, _ = master_audio(h, SR, Settings(glue=0), log=lambda m: None)
    for f in (60, 120):
        assert rel(y, f) < rel(h, f) - 10
