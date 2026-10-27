"""Glue styles and the soft clipper: what each promises, and what they must leave alone."""

import numpy as np
import pytest
from pedalboard import Compressor, Gain, Pedalboard

from wavmasta.core import Settings, chain, master_audio
from wavmasta.core.analysis import lufs, true_peak_db

from . import synth
from .synth import SR


def _frames_db(x, n=2205):
    m = np.asarray(x, dtype=np.float64).mean(axis=0)
    k = len(m) // n
    return 10 * np.log10(np.mean(m[: k * n].reshape(k, n) ** 2, axis=1) + 1e-12)


def _tone(freq, seconds, amp):
    t = np.arange(int(seconds * SR)) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def kick_and_vocal(seconds=8):
    """A steady 1 kHz 'vocal' with a loud 60 Hz 'kick' every half second."""
    vocal = _tone(1000, seconds, 0.12)
    kick = np.zeros_like(vocal)
    t = np.arange(int(0.25 * SR)) / SR
    hit = (0.7 * np.sin(2 * np.pi * 60 * t) * np.exp(-t * 12)).astype(np.float32)
    for s in range(0, len(kick) - hit.size, SR // 2):
        kick[s : s + hit.size] += hit
    x = vocal + kick
    return np.vstack([x, x])


def _vocal_dips(x, y):
    """How far the 1 kHz part moves (dB, max - min over time) after processing."""
    mid_in, mid_out = chain.split_bands(x, SR)[1], chain.split_bands(y, SR)[1]
    d = _frames_db(mid_out) - _frames_db(mid_in)
    d = d[5:-5]
    return float(d.max() - d.min())


# ---- the three bands
def test_bands_add_back_up_to_the_song():
    x = synth.mix(seconds=6) * 0.5
    lo, mid, hi = chain.split_bands(x, SR)
    assert np.max(np.abs(lo + mid + hi - x)) < 1e-5
    # and each band really holds its own range
    spectrum = lambda b: np.abs(np.fft.rfft(b[0]))  # noqa: E731
    f = np.fft.rfftfreq(x.shape[1], 1 / SR)
    for band, (a, b) in ((lo, (0, 100)), (hi, (5000, 15000))):
        inside = spectrum(band)[(f > a) & (f < b)].sum()
        assert inside > 0.6 * spectrum(x)[(f > a) & (f < b)].sum()


# ---- glue styles
def test_smooth_is_the_original_glue():
    x = synth.mix(seconds=6) * 0.5
    a = 0.4
    pre = -18.0 - lufs(x, SR)
    old = Pedalboard(
        [
            Gain(gain_db=pre),
            Compressor(threshold_db=-14.0 - 10.0 * a, ratio=1.5 + 2.5 * a, attack_ms=30.0, release_ms=180.0),
            Gain(gain_db=-pre),
        ]
    )(x, SR)
    assert np.max(np.abs(chain.glue(x, SR, 40) - old)) < 1e-6
    assert np.array_equal(chain.glue(x, SR, 40, "Smooth"), chain.glue(x, SR, 40))


def test_glue_off_leaves_the_song_alone_in_every_style():
    x = synth.mix(seconds=4) * 0.5
    for style in chain.GLUE_STYLES:
        assert chain.glue(x, SR, 0, style) is x


def test_punchy_lets_the_hits_through():
    x = kick_and_vocal()

    def first_hit_peak(y):
        return np.abs(y[0, : int(0.02 * SR)]).max()  # the first 20 ms of the first kick

    smooth, punchy = chain.glue(x, SR, 70, "Smooth"), chain.glue(x, SR, 70, "Punchy")
    hit_smooth, hit_punchy = first_hit_peak(smooth), first_hit_peak(punchy)
    assert hit_punchy > hit_smooth * 1.05


def test_three_band_keeps_a_loud_kick_from_ducking_the_vocal():
    x = kick_and_vocal()
    smooth = _vocal_dips(x, chain.glue(x, SR, 70, "Smooth"))
    three = _vocal_dips(x, chain.glue(x, SR, 70, "Three-band"))
    assert smooth > 1.5  # one compressor: the vocal dips with every kick
    assert three < smooth / 3


# ---- soft clip
def test_soft_clip_leaves_quiet_audio_alone():
    x = synth.mix(seconds=4) * 0.1
    y = chain.soft_clip(x, -1.0)
    assert np.max(np.abs(y - x)) < 1e-3


def test_soft_clip_rounds_peaks_under_its_limit():
    x = synth.mix(seconds=4)
    x = x * (2.0 / np.abs(x).max())  # peaks at +6 dBFS
    y = chain.soft_clip(x, -1.0)
    # a few dB shaved; the filtering after can overshoot a little, which the limiter after it catches
    assert true_peak_db(y) < true_peak_db(x) - 3
    assert true_peak_db(y) < -1.0 + 2.5
    # most of the song is untouched: only the peaks change
    quiet = np.abs(x) < 10 ** (-6 / 20)
    assert np.mean(np.abs(y - x)[quiet]) < 0.01


@pytest.mark.parametrize(
    "mode, target, on",
    [("Auto", -14.0, False), ("Auto", -16.0, False), ("Auto", -11.0, True), ("Auto", -9.0, True),
     ("Always", -14.0, True), ("Off", -9.0, False)],
)  # fmt: skip
def test_soft_clip_modes(mode, target, on):
    assert chain.soft_clip_on(mode, target) is on


def test_loud_masters_pump_less_with_soft_clip():
    x = synth.mix(seconds=12) * 0.4

    def pumping(y):
        ref = x * 10 ** ((-9.0 - lufs(x, SR)) / 20)
        a, b = _frames_db(ref, 8820), _frames_db(y, 8820)
        keep = a > a.max() - 25
        return float(np.std(b[keep] - a[keep]))

    off = chain.loudness_and_limit(x, SR, -9.0, -1.0, clip=False)
    on = chain.loudness_and_limit(x, SR, -9.0, -1.0, clip=True)
    for y in (off, on):
        assert true_peak_db(y) <= -1.0
    # this mix is so peaky the limiter alone stops short of -9 rather than distort; with soft clip it gets there
    assert abs(lufs(on, SR) - -9.0) < 0.2
    assert abs(lufs(on, SR) - -9.0) < abs(lufs(off, SR) - -9.0)
    assert pumping(on) < pumping(off)


# ---- settings and the pipeline
def test_settings_check_the_new_choices():
    assert Settings(glue_style="Wobbly").check().startswith("Unknown glue style")
    assert "Soft clip" in Settings(soft_clip="Sometimes").check()
    assert Settings(glue_style="Three-band", soft_clip="Always").check() is None
    assert "glue 30% punchy" in Settings(glue_style="Punchy").describe()
    assert "glue 30% ·" in Settings().describe()  # the default style isn't spelled out


def test_pipeline_soft_clips_only_when_asked():
    x = synth.mix(seconds=8) * 0.4
    _, loud = master_audio(x, SR, Settings(target_lufs=-9.0), log=lambda m: None)
    _, streaming = master_audio(x, SR, Settings(), log=lambda m: None)
    _, always = master_audio(x, SR, Settings(soft_clip="Always"), log=lambda m: None)
    _, off = master_audio(x, SR, Settings(target_lufs=-9.0, soft_clip="Off"), log=lambda m: None)
    assert loud.get("soft_clip") and always.get("soft_clip")
    assert not streaming.get("soft_clip") and not off.get("soft_clip")
