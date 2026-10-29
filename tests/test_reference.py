"""Matching a reference song: tone, density, width and loudness, at the strength asked for."""

import numpy as np

from wavmasta.core import Settings, chain, master_audio
from wavmasta.core import reference as R

from . import synth
from .synth import SR


def _side_scaled(x, k):
    mid, side = (x[0] + x[1]) / 2, (x[0] - x[1]) / 2 * k
    return np.vstack([mid + side, mid - side]).astype(np.float32)


def song():
    return synth.mix(seconds=12, seed=1) * 0.4


def test_the_default_match_keeps_the_original_tone_curve():
    x, ref = song(), synth.mix(seconds=12, seed=5) * 0.5
    f0, old = chain.reference_curve(x, SR, ref, SR)
    f1, new = R.eq_curve(x, SR, ref, SR, 0.8)
    assert np.allclose(f0, f1) and np.allclose(old, new)


def test_strength_scales_the_tone_match():
    x = song()
    bright = chain.apply_curve(x, SR, np.array([20, 2000, 6000, 20000.0]), np.array([0, 0, 8.0, 8.0]))
    gains = [np.abs(R.eq_curve(x, SR, bright, SR, s)[1]).max() for s in (0.0, 0.5, 1.0)]
    assert gains[0] == 0 and gains[0] < gains[1] < gains[2]


def test_strength_zero_leaves_tone_density_and_width_alone():
    x = song()
    p = R.plan(x, SR, _side_scaled(song(), 2.5), SR, 0.0)
    assert p["width"] == 100 and p["glue"] == 30 and np.abs(p["curve"][1]).max() == 0


def test_width_follows_the_reference():
    x = song()
    assert R.plan(x, SR, _side_scaled(x, 2.0), SR, 0.8)["width"] > 110
    assert R.plan(x, SR, _side_scaled(x, 0.4), SR, 0.8)["width"] < 90
    mono_ref = np.vstack([x.mean(axis=0)] * 2)
    assert R.plan(x, SR, mono_ref, SR, 0.8)["width"] == 100  # a mono reference doesn't squash the song


def _pumping(depth_db, seconds=12, seed=0):
    """Band-limited noise whose level jumps by depth_db twice a second: a mix that moves around a lot."""
    from scipy.signal import butter, sosfilt

    rng = np.random.default_rng(seed)
    n = seconds * SR
    noise = sosfilt(butter(2, [80, 8000], "bandpass", fs=SR, output="sos"), rng.standard_normal((2, n)))
    t = np.arange(n) / SR
    gain = np.where((t * 2) % 1 < 0.5, 1.0, 10 ** (-depth_db / 20))
    return (0.1 * noise * gain).astype(np.float32)


def test_a_denser_reference_asks_for_more_glue():
    x = _pumping(8)
    dense, dynamic = _pumping(1, seed=1), _pumping(12, seed=2)
    assert R.movement_db(dense, SR) < R.movement_db(x, SR) < R.movement_db(dynamic, SR)
    g_dense = R.plan(x, SR, dense, SR, 1.0)["glue"]
    g_dynamic = R.plan(x, SR, dynamic, SR, 1.0)["glue"]
    assert g_dense > 30 > g_dynamic


def test_the_pipeline_reports_what_it_matched():
    x, ref = song(), _side_scaled(synth.mix(seconds=12, seed=5) * 0.6, 1.8)
    _, info = master_audio(x, SR, Settings(match=90), log=lambda m: None, reference=(ref, SR))
    r = info["reference"]
    assert r["strength"] == 90 and r["width"] > 100 and 0 <= r["glue"] <= 100
    assert info["target"] == r["target"]
    assert set(r["movement"]) == {"reference", "master"}


def test_settings_check_and_describe_the_match():
    assert "Match strength" in Settings(match=120).check()
    s = Settings(reference=__file__, match=65)
    assert s.check() is None
    assert "(65%)" in s.describe() and "glue and width from the reference" in s.describe()
