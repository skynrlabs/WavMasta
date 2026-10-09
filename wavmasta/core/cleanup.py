"""Cleanup before mastering: hiss reduction, hum and whine notches, harsh-top taming, rumble.

Noise reduction here is a gentle de-hisser. It learns the noise floor of each frequency (the
level that's always there, even between notes) and turns down only what sits near that floor,
so the music on top is left alone. It works above about 1 kHz, where hiss lives; the bass and
the body of voices and instruments below that are never touched.
"""

import numpy as np
from pedalboard import HighpassFilter, HighShelfFilter, PeakFilter, Pedalboard
from scipy.ndimage import uniform_filter, uniform_filter1d
from scipy.signal import istft, stft

from .analysis import tone_kind

N_FFT = 2048
HOP = 512
STRONG_TONE_DB = 20.0  # a steady tone this far above its surroundings gets a deep, very narrow notch


def _noise_profile(x, sr, chunk, samples=8):
    """Per-frequency noise level, from up to `samples` stretches spread across the song.

    Levels are smoothed over about 0.2 s first: smoothing evens out the flicker of noise (so its
    quietest moments are close to its average), while notes still rise and fall. The quiet end
    of each frequency's smoothed level is then the noise floor.
    """
    profiles = []
    starts = range(0, x.size, chunk)
    if len(starts) > samples:
        starts = np.linspace(0, x.size - chunk, samples).astype(int)
    for start in starts:
        seg = x[start : start + chunk]
        if seg.size < N_FFT * 4:
            continue
        _, _, z = stft(seg, sr, nperseg=N_FFT, noverlap=N_FFT - HOP)
        power = np.abs(z) ** 2
        loud = power.sum(axis=0) > 1e-12  # skip digital silence, which would make the floor zero
        if loud.sum() < 32:
            continue
        smooth = uniform_filter1d(power[:, loud], size=17, axis=1, mode="nearest")
        profiles.append(np.sqrt(np.percentile(smooth, 10, axis=1) * 1.4))  # 1.4: noise sits a bit above p10
    if not profiles:
        return None
    return np.median(np.stack(profiles), axis=0)


def denoise(audio, sr, amount, chunk_seconds=15):
    """Reduce steady hiss. amount 0-1: 0.3 is light, 0.6 is strong; above 0.8 can sound watery."""
    if amount <= 0:
        return audio
    amount = float(min(amount, 1.0))
    floor_gain = 10 ** (-(6 + 18 * amount) / 20)  # how far noise is turned down: 6 dB to 24 dB
    over = 0.8 + 0.6 * amount  # how much of the near-floor content counts as noise (gentle: keeps treble detail)
    chunk = int(chunk_seconds * sr)
    pad = N_FFT * 2
    out = np.empty_like(audio)
    freqs = np.fft.rfftfreq(N_FFT, 1 / sr)
    # 0 below 1 kHz (never touched), rising to full strength from 3 kHz up
    reach = np.clip((np.log2(np.maximum(freqs, 1)) - np.log2(1000)) / np.log2(3), 0, 1)[:, None]
    for ch in range(audio.shape[0]):
        x = audio[ch]
        profile = _noise_profile(x, sr, chunk)
        if profile is None:
            return audio  # nothing but silence
        profile = profile[:, None]
        n = x.size
        for start in range(0, n, chunk):
            lo, hi = max(0, start - pad), min(n, start + chunk + pad)
            seg = x[lo:hi]
            _, _, z = stft(seg, sr, nperseg=N_FFT, noverlap=N_FFT - HOP)
            mag = np.abs(z) + 1e-12
            gain = np.clip(1.0 - over * profile / mag, floor_gain, 1.0)
            gain = uniform_filter(gain, size=(3, 5), mode="nearest")  # smooth: no "musical noise" chirps
            gain = 1.0 - reach * (1.0 - gain)
            _, y = istft(z * gain, sr, nperseg=N_FFT, noverlap=N_FFT - HOP)
            y = y[: seg.size]
            if y.size < seg.size:
                y = np.pad(y, (0, seg.size - y.size))
            take = slice(start - lo, start - lo + min(chunk, n - start))
            out[ch, start : start + min(chunk, n - start)] = y[take]
    return out.astype(np.float32)


def tone_filters(tones):
    """Notch filters for steady tones from analysis.find_tones()."""
    fx = []
    for freq, excess in tones:
        if excess >= STRONG_TONE_DB:
            # very narrow, but never narrower than about 4 Hz, so a low tone that's a hair off still lands
            q = min(30.0, max(8.0, freq / 4.0))
            fx.append(PeakFilter(cutoff_frequency_hz=freq, gain_db=-min(excess, 30.0), q=q))
        else:
            fx.append(PeakFilter(cutoff_frequency_hz=freq, gain_db=-min(excess, 8.0), q=10.0))
        if tone_kind(freq) == "hum" and freq < 70:  # hum comes with harmonics; catch the next two
            for k in (2, 3):
                fx.append(PeakFilter(cutoff_frequency_hz=freq * k, gain_db=-6.0, q=20.0))
    return fx


def cleanup_filters(tones=(), tame_top=0.0, highpass=25.0):
    """The static part of cleanup as a list of pedalboard plugins."""
    fx = [HighpassFilter(cutoff_frequency_hz=highpass)] if highpass else []
    fx += tone_filters(tones)
    if tame_top > 0:
        fx.append(HighShelfFilter(cutoff_frequency_hz=11000, gain_db=-tame_top, q=0.7))
    return fx


def apply(audio, sr, fx):
    if not fx:
        return audio
    return Pedalboard(fx)(audio, sr).astype(np.float32)
