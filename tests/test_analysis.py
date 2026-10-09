"""Measuring songs: loudness, true peak, and finding hiss, hum, whine and harsh highs."""

import numpy as np
import pytest

from wavmasta.core import analyze
from wavmasta.core.analysis import find_tones, lufs, tone_kind, true_peak_db

from .synth import SR


def sine(freq, amp, seconds=5, sr=SR, channels=2):
    t = np.arange(int(seconds * sr)) / sr
    return np.vstack([amp * np.sin(2 * np.pi * freq * t)] * channels).astype(np.float32)


# ---- meters
@pytest.mark.parametrize("sr", [44100, 48000, 96000])
def test_lufs_of_reference_sine(sr):
    """BS.1770: a 1 kHz sine at -20 dBFS in both channels reads -20.0 LUFS (within 0.1)."""
    assert lufs(sine(1000, 0.1, sr=sr), sr) == pytest.approx(-20.0, abs=0.1)


def test_lufs_matches_pyloudnorm_on_music(audio):
    pyln = pytest.importorskip("pyloudnorm")
    x = audio["clean"]
    ref = pyln.Meter(SR).integrated_loudness(x.T.astype(np.float64))
    assert lufs(x, SR) == pytest.approx(ref, abs=0.1)


def test_lufs_of_silence_is_minus_infinity():
    assert lufs(np.zeros((2, SR * 2), dtype=np.float32), SR) == float("-inf")


def test_true_peak_finds_peaks_between_samples():
    # a quarter-sample-rate sine sampled 45 degrees off its peaks: samples read 3 dB low
    n = np.arange(SR)
    x = np.vstack([0.5 * np.sin(np.pi / 2 * n + np.pi / 4)] * 2).astype(np.float32)
    sample_peak = 20 * np.log10(np.max(np.abs(x)))
    assert true_peak_db(x) > sample_peak + 2.5


# ---- finding problems
def test_clean_song_has_no_findings(audio):
    r = analyze(audio["clean"], SR)
    assert not r.hiss and not r.fizzy and r.tones == []
    assert r.findings() == ["No noise problems found. Pick a tone and loudness and master it."]


def test_musical_notes_are_not_mistaken_for_hum(audio):
    """The chords and bass repeat for the whole song but come and go; they must never be notched."""
    assert find_tones(audio["clean"], SR) == []


def test_finds_a_whine_to_the_hertz(audio):
    tones = find_tones(audio["whine"], SR)
    assert len(tones) == 1
    assert tones[0][0] == pytest.approx(3150, abs=0.5)
    assert tone_kind(tones[0][0]) == "whine"


def test_finds_mains_hum_and_its_harmonic(audio):
    freqs = sorted(round(f) for f, _ in find_tones(audio["hum"], SR))
    assert freqs == [60, 120]
    assert tone_kind(60.0) == "hum" and tone_kind(100.0) == "hum" and tone_kind(3150.0) == "whine"


def test_finds_hiss(audio):
    r = analyze(audio["hiss"], SR)
    assert r.hiss
    assert any("Hiss" in line for line in r.findings())
    assert r.suggested()["denoise"] == 40


def test_finds_fizzy_highs(audio):
    r = analyze(audio["fizz"], SR)
    assert r.fizzy and not r.hiss
    assert r.suggested()["tame_top"] > 0


def test_hiss_is_still_found_under_a_whine():
    from . import synth

    r = analyze(synth.song(hiss=0.003, whine_hz=3150, whine=0.008), SR)
    assert r.hiss and r.tones


def test_reports_clipping():
    x = np.clip(sine(200, 1.5), -1, 1)
    r = analyze(x, SR)
    assert r.clipped > 100
    assert r.findings()[0].startswith("Clipping")


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
@pytest.mark.parametrize("amp", [0.006, 0.01])
def test_hum_is_found_on_the_exact_frequency_under_kick_and_bass(amp, seed):
    """The test songs have a kick and a bass note within a few Hz of 60 Hz; the hum notch must still
    land exactly on 60 and 120 (a narrow notch a few Hz off misses the hum)."""
    from . import synth

    tones = sorted(f for f, _ in find_tones(synth.song(hum=amp, seed=seed), SR))
    assert tones == [60.0, 120.0]


def test_50hz_hum_family():
    from . import synth

    x = synth.song()
    t = np.arange(x.shape[1]) / SR
    x = x + (0.006 * (np.sin(2 * np.pi * 50 * t) + 0.5 * np.sin(2 * np.pi * 100 * t))).astype(np.float32)
    assert all(f % 50 == 0 for f, _ in find_tones(x, SR))
