"""Trim and fade, the de-esser, album mode, the true-peak limiter and the waveform envelope."""

import numpy as np
import pytest

from wavmasta.core import Settings, analyze, chain, edges, envelope, master_audio
from wavmasta.core import album as albums
from wavmasta.core.analysis import lufs, true_peak_db
from wavmasta.core.deess import deess, sibilance_db, suggested_amount

from . import synth
from .synth import SR


# ---- trim and fade
def test_trim_cuts_silence_but_keeps_the_attack():
    x = synth.song(pad=(2.0, 3.0))
    lead, tail = edges.silence_at_edges(x, SR)
    assert lead == pytest.approx(2.0, abs=0.02) and tail >= 3.0  # the last note rings into the pad
    y, start, end = edges.trim(x, SR)
    assert start == pytest.approx(lead - edges.KEEP_BEFORE, abs=0.02)
    assert end == pytest.approx(tail - edges.KEEP_AFTER, abs=0.02)
    assert y.shape[1] == x.shape[1] - round(start * SR) - round(end * SR)
    assert abs(y[:, 0]).max() == 0.0  # starts in the kept bit of silence, so no click


def test_nothing_to_trim_leaves_audio_alone():
    x = synth.song()
    y, start, end = edges.trim(x, SR)
    assert (start, end) == (0.0, 0.0) and y is x


def test_fade_out_reaches_silence_smoothly():
    x = synth.song()
    y = edges.fade_out(x, SR, 3)
    assert np.all(y[:, -1] == 0)
    assert np.array_equal(y[:, : -3 * SR], x[:, : -3 * SR])  # nothing before the fade changes
    a, b = x[0, -3 * SR :], y[0, -3 * SR :]
    loud = np.abs(a) > 1e-3
    gain = b[loud] / a[loud]
    assert gain[0] == pytest.approx(1.0, abs=0.01)
    assert np.all(np.diff(gain) <= 1e-6)  # the volume only ever goes down


def test_abrupt_endings_are_spotted():
    x = synth.song()
    assert edges.ends_abruptly(x, SR)
    assert not edges.ends_abruptly(edges.fade_out(x, SR, 3), SR)


def test_check_suggests_trim_and_fade():
    r = analyze(synth.song(pad=(2.0, 0)), SR)
    s = r.suggested()
    assert s["trim"] is True and s["fade_out"] == 3.0
    text = " ".join(r.findings())
    assert "2.0 s at the start" in text and "fade-out" in text


def test_faded_master_still_hits_loudness():
    x = synth.song(pad=(1.5, 2))
    y, info = master_audio(x, SR, Settings(fade_out=4), log=lambda m: None)
    assert lufs(y, SR) == pytest.approx(-14, abs=0.2)
    assert info["trim"][0] > 1.0 and info["fade"] == 4
    assert y.shape[1] < x.shape[1]


# ---- de-esser
def _band(a, mask=None):
    from scipy.signal import butter, sosfiltfilt

    b = sosfiltfilt(butter(6, [5000, 9000], "bandpass", fs=SR, output="sos"), a.mean(axis=0))
    if mask is not None:
        b = b[mask]
    return 10 * np.log10(np.mean(b**2) + 1e-20)


def test_deess_leaves_a_song_without_s_sounds_alone():
    clean = synth.mix(sibilance=0)
    assert abs(_band(deess(clean, SR, 0.8)) - _band(clean)) < 0.3


def test_deess_turns_s_sounds_down_and_only_them():
    from scipy.signal import butter, sosfiltfilt

    harsh, clean = synth.mix(sibilance=0.06), synth.mix(sibilance=0)
    s_only = (harsh - clean).mean(axis=0)
    mask = np.abs(sosfiltfilt(butter(2, 30, fs=SR, output="sos"), np.abs(s_only))) > 0.002
    y = deess(harsh, SR, 0.5)
    assert _band(y, mask) < _band(harsh, mask) - 3  # the 's' moments come down
    assert abs(_band(y, ~mask) - _band(harsh, ~mask)) < 0.3  # the rest doesn't
    lp = butter(6, 3000, fs=SR, output="sos")
    change = sosfiltfilt(lp, (y - harsh).mean(axis=0))
    body = sosfiltfilt(lp, harsh.mean(axis=0))
    assert 20 * np.log10(np.std(change) / np.std(body)) < -50  # below 3 kHz: untouched


def test_stronger_deess_removes_more():
    harsh = synth.mix(sibilance=0.06)
    levels = [sibilance_db(deess(harsh, SR, a), SR) for a in (0.2, 0.5, 0.9)]
    assert levels[0] > levels[1] > levels[2]


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_sibilance_check(seed):
    assert suggested_amount(sibilance_db(synth.mix(sibilance=0, seed=seed), SR)) == 0
    assert suggested_amount(sibilance_db(synth.mix(sibilance=0.06, seed=seed), SR)) >= 50
    assert analyze(synth.mix(sibilance=0.06, seed=seed), SR).suggested()["deess"] >= 50


def test_no_vocal_no_deess_suggestion():
    for x in (synth.song(), synth.song(hiss=0.004), synth.song(fizz=0.3)):
        assert "deess" not in analyze(x, SR).suggested()


# ---- album mode
def _album_songs():
    f = np.array([20, 100, 1000, 4000, 10000, 22050.0])
    return {
        "bright": chain.apply_curve(synth.mix(), SR, f, np.array([-1, -1, 0, 2, 3.5, 3.5])) * 0.9,
        "dark": chain.apply_curve(synth.mix(seed=2), SR, f, np.array([2, 2, 0, -2, -3.5, -3.5])) * 0.4,
        "boomy": chain.apply_curve(synth.mix(seed=4), SR, f, np.array([4, 3, 0, 0, 0, 0])) * 0.6,
    }


def test_album_matches_tone_and_loudness():
    songs = _album_songs()
    prof = albums.profile([(k, a, SR) for k, a in songs.items()])
    alone, together, levels = [], [], []
    for k, a in songs.items():
        y0, _ = master_audio(a, SR, Settings(glue=0), log=lambda m: None)
        y1, info = master_audio(a, SR, Settings(glue=0), log=lambda m: None, album=prof, key=k)
        g, t0 = albums._normalized_spectrum(y0, SR)
        _, t1 = albums._normalized_spectrum(y1, SR)
        alone.append(t0)
        together.append(t1)
        levels.append(lufs(y1, SR))
        assert info["album"]["tone_db"] <= albums.MAX_TONE_DB
    sel = (g > 60) & (g < 14000)
    spread = lambda t: np.mean(np.std(np.array(t)[:, sel], axis=0))  # noqa: E731
    assert spread(together) < spread(alone) * 0.6  # tone differences between songs shrink
    assert albums.spread_db(levels) < 1.0  # and they're equally loud


def test_album_ignores_silent_files_and_respects_references():
    prof = albums.profile([("a", synth.mix(), SR), ("silent", np.zeros((2, SR * 2), np.float32), SR)])
    assert set(prof["loudness"]) == {"a"}
    _, info = master_audio(
        synth.mix(), SR, Settings(), log=lambda m: None, album=prof, key="a", reference=(synth.mix(seed=3), SR)
    )
    assert info["album"] is None  # a reference song decides the tone instead


# ---- the true-peak limiter
@pytest.mark.parametrize("target", [-14.0, -11.0])
def test_limiter_lands_on_target_with_true_peaks_under_the_ceiling(target):
    x = synth.mix(sibilance=0.05) * 0.5  # bright hats and 's' sounds: easy to overshoot between samples
    y = chain.loudness_and_limit(x, SR, target, -1.0)
    assert lufs(y, SR) == pytest.approx(target, abs=0.15)
    assert true_peak_db(y) <= -1.0


def test_limiter_never_clips_even_when_pushed():
    y = chain.loudness_and_limit(synth.mix(), SR, -9.0, -1.0)
    assert true_peak_db(y) <= -1.0
    assert np.max(np.abs(y)) < 10 ** (-1.0 / 20)


def test_quiet_audio_passes_the_limiter_untouched():
    x = synth.song() * 0.1
    lim = chain.TruePeakLimiter(x, SR)
    assert np.allclose(lim.run(0.0, -1.0), x, atol=1e-7)


# ---- waveform
def test_envelope():
    x = synth.song(pad=(1, 0))
    env = envelope(x, 400)
    assert env.shape == (400,) and env.max() <= 1
    assert env[:20].max() == 0  # the silent start
    assert env[100:].max() > 0.1
