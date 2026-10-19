"""Keep bass centred and the mono checks: what each promises and what it must leave alone."""

import numpy as np
import pytest
from scipy.signal import butter, sosfiltfilt

from wavmasta.core import Settings, analyze, chain, master_audio
from wavmasta.core.lowend import MONO_LOSS_DB, SIDE_BASS_DB, mono_bass, mono_loss_db, side_bass_db

from . import synth
from .synth import SR


def _band_db(x, lo, hi):
    sos = butter(4, [lo, hi], "bandpass", fs=SR, output="sos")
    return 10 * np.log10(np.mean(sosfiltfilt(sos, x.astype(np.float64)) ** 2) + 1e-30)


def _mid_side(x):
    return (x[0] + x[1]) / 2, (x[0] - x[1]) / 2


def wide_bass_mix(seed=0):
    """A mix whose bass is pushed out to the sides (left and right in opposite phase below 150 Hz)."""
    x = synth.mix(seconds=12, seed=seed) * 0.5
    bass = sosfiltfilt(butter(4, 150, "low", fs=SR, output="sos"), x.mean(axis=0)).astype(np.float32)
    x = x.copy()
    x[0] += bass
    x[1] -= bass
    return x


def highs_out_of_phase(seed=0):
    """A mix where everything above 2 kHz is flipped in one channel, like a broken stereo widener."""
    x = synth.mix(seconds=12, seed=seed) * 0.5
    hp = butter(4, 2000, "high", fs=SR, output="sos")
    x = x.copy()
    x[1] = (x[1] - 2 * sosfiltfilt(hp, x[1])).astype(np.float32)
    return x


def test_centring_removes_side_bass_and_leaves_everything_else():
    x = wide_bass_mix()
    y = mono_bass(x, SR)
    mid_x, side_x = _mid_side(x)
    mid_y, side_y = _mid_side(y)
    assert _band_db(side_y, 40, 90) < _band_db(side_x, 40, 90) - 30  # the bass in the sides is gone
    assert abs(_band_db(side_y, 300, 3000) - _band_db(side_x, 300, 3000)) < 0.05  # the width above is kept
    assert np.max(np.abs(mid_y - mid_x)) < 1e-5  # the centre is never touched


def test_centring_a_mono_song_changes_nothing():
    x = synth.mix(seconds=6)
    m = np.vstack([x.mean(axis=0)] * 2).astype(np.float32)
    assert np.max(np.abs(mono_bass(m, SR) - m)) < 1e-6
    one = x[:1]
    assert mono_bass(one, SR) is one


@pytest.mark.parametrize("seed", [0, 2])
def test_check_suggests_centring_only_for_wide_bass(seed):
    plain, wide = synth.mix(seconds=12, seed=seed) * 0.5, wide_bass_mix(seed)
    assert side_bass_db(plain, SR) < SIDE_BASS_DB - 20
    assert side_bass_db(wide, SR) > SIDE_BASS_DB
    r = analyze(wide, SR)
    assert r.wide_bass and r.suggested()["mono_bass"] is True
    assert "spread wide" in " ".join(r.findings())
    assert "mono_bass" not in analyze(plain, SR).suggested()


def test_mono_check_warns_only_when_parts_cancel():
    plain = synth.mix(seconds=12) * 0.5
    assert mono_loss_db(plain, SR) < 1.0
    assert mono_loss_db(chain.stereo_width(plain, SR, 150), SR) < 1.0  # wide but healthy is fine
    broken = highs_out_of_phase()
    assert mono_loss_db(broken, SR) > MONO_LOSS_DB
    r = analyze(broken, SR)
    assert r.cancels_in_mono and "cancel out in mono" in " ".join(r.findings())
    assert not analyze(plain, SR).cancels_in_mono
    m = np.vstack([plain.mean(axis=0)] * 2)
    assert mono_loss_db(m, SR) == pytest.approx(0.0, abs=1e-6)


def test_master_centres_the_bass_when_asked():
    x = wide_bass_mix()
    y, info = master_audio(x, SR, Settings(mono_bass=True, glue=0), log=lambda m: None)
    assert info["mono_bass"] is True
    assert side_bass_db(y, SR) < SIDE_BASS_DB - 10
    _, info = master_audio(x, SR, Settings(glue=0), log=lambda m: None)
    assert info["mono_bass"] is False  # off unless you (or Check's suggestions) turn it on
    assert "bass centred" in Settings(mono_bass=True).describe()
