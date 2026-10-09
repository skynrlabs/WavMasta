"""De-esser: tames harsh "s", "sh" and "t" sounds in vocals.

Two questions, the way a mastering engineer listens:

1. Is this an "s"? The 5-10 kHz band jumps well above its typical level over the surrounding
   second (which steady air and sustained cymbals set) and stays up for 70 ms or more (an "s"
   lasts 80-200 ms; a hi-hat tick, ringing included, is gone in about 50).
2. How harsh is it? How much brighter (5-10 kHz compared with the 1-4 kHz body of the mix) the
   song is at that instant than it usually is.

Only the "s" moments are turned down, and only as far as needed to bring them to a smooth level
for this song. Only the top of the song (above about 4.5 kHz, split off with a zero-phase
crossover that adds back up to exactly the original) is touched, with smoothed gain changes (fast
attack, gentle release) so it doesn't lisp.
"""

import numpy as np
from scipy.ndimage import binary_opening, maximum_filter1d, median_filter, uniform_filter1d
from scipy.signal import butter, sosfiltfilt

SPLIT_HZ = 4500
SIB_BAND = (5000, 10000)
BODY_BAND = (1000, 4000)
FRAME = 0.005  # seconds per measurement and gain step


def _band_levels(mono, sr, frame):
    """Per-frame dB levels of the sibilant band and the body band, floored so silence can't
    produce absurd ratios. Returns (sib, body, live) where live marks frames with real sound."""

    def level(lo, hi):
        sos = butter(4, [lo, min(hi, sr / 2 - 200)], btype="bandpass", fs=sr, output="sos")
        band = sosfiltfilt(sos, mono)
        n = band.size // frame
        return 10 * np.log10(np.mean(band[: n * frame].reshape(n, frame) ** 2, axis=1) + 1e-20)

    sib, body = level(*SIB_BAND), level(*BODY_BAND)
    top = max(sib.max(), body.max())
    live = np.maximum(sib, body) > top - 45
    floor = top - 70
    return np.maximum(sib, floor), np.maximum(body, floor), live


MIN_SHARE = 0.02  # 's' sounds must make up at least this share of the song to count as a voice's
HOLD = 0.07  # seconds a burst must stay up to count as an 's' (measured: hat ticks die away sooner)
RISE_DB = 4.0  # how far above the band's typical level a burst must rise


def _bursts(sib, body, live, frame_s):
    """Frames that are an 's': the sibilant band rises RISE_DB above its typical level over the
    surrounding second (the median, which steady air and sustained cymbals set), for at least HOLD
    (hat ticks die away sooner), and loud enough to hear (within 30 dB of the body of the mix)."""
    typical = median_filter(sib, size=max(3, int(1.0 / frame_s)), mode="nearest")
    up = live & (sib > typical + RISE_DB) & (sib > body - 30)
    return binary_opening(up, structure=np.ones(max(2, int(round(HOLD / frame_s))), dtype=bool))


def _brightness(sib, body):
    """How loud the sibilant band is compared with the body of the mix (1-4 kHz), in dB."""
    return sib - body


def _usual_brightness(sib, body, live):
    return float(np.median(_brightness(sib, body)[live])) if live.any() else 0.0


def sibilance_db(audio, sr):
    """How harsh the song's 's' sounds are: how much brighter the song gets during them than it
    usually is (the 90th percentile over all the 's' sounds found), in dB. Returns -inf when no
    's' sounds are found. Around 10 is smooth; above about 15 they cut through."""
    if sr < 24000 or audio.shape[1] < sr:
        return float("-inf")
    mono = audio.mean(axis=0).astype(np.float64)
    frame = int(FRAME * sr)
    sib, body, live = _band_levels(mono, sr, frame)
    bursts = _bursts(sib, body, live, FRAME)
    if bursts.sum() < max(10, MIN_SHARE * live.sum()):  # a few stray frames are chance, not a voice
        return float("-inf")
    return float(np.percentile(_brightness(sib, body)[bursts], 90) - _usual_brightness(sib, body, live))


def deess(audio, sr, amount):
    """Turn 's' sounds down toward a smooth level. amount 0-1: 0.3 is light, 0.6 firm. Only the
    'top' (above about 4.5 kHz) is turned down, only during each 's', by up to 14 dB."""
    if amount <= 0 or sr < 24000 or audio.shape[1] < sr // 2:
        return audio
    amount = float(min(1.0, amount))
    frame = max(1, int(FRAME * sr))
    mono = audio.mean(axis=0).astype(np.float64)
    sib, body, live = _band_levels(mono, sr, frame)
    bursts = _bursts(sib, body, live, FRAME)
    # how much brighter than usual an 's' may stay: 11 dB (light) down to 3 dB (strong)
    target = _usual_brightness(sib, body, live) + 11.0 - 8.0 * amount
    reduction_db = np.where(bursts, np.clip(_brightness(sib, body) - target, 0.0, 4.0 + 10.0 * amount), 0.0)
    reduction_db = maximum_filter1d(reduction_db, size=3)  # catch the start of each 's'
    reduction_db = uniform_filter1d(reduction_db, size=5)  # ease in and out
    gain = np.repeat(10 ** (-reduction_db / 20), frame)
    if gain.size < audio.shape[1]:
        gain = np.concatenate([gain, np.ones(audio.shape[1] - gain.size)])
    gain = gain[: audio.shape[1]]
    sos = butter(4, SPLIT_HZ, btype="lowpass", fs=sr, output="sos")
    out = np.empty_like(audio)
    for ch in range(audio.shape[0]):
        x = audio[ch].astype(np.float64)
        low = sosfiltfilt(sos, x)
        out[ch] = (low + (x - low) * gain).astype(np.float32)  # low + high == x when gain is 1
    return out


SIBILANT_DB = 15.5  # sibilance_db above this: the 's' sounds cut through


def suggested_amount(sib_db):
    """De-ess % to suggest for a measured sibilance, or 0 when it's fine: 30% just past the
    threshold, rising 5% per dB, up to 80%."""
    if not np.isfinite(sib_db) or sib_db < SIBILANT_DB:
        return 0
    return int(min(80, 30 + 5 * round(sib_db - SIBILANT_DB)))
