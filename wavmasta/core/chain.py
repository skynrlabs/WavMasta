"""The mastering chain: tone EQ (or matching a reference song), stereo width, glue
compression, and loudness with a true-peak limiter."""

import numpy as np
from pedalboard import Compressor, Gain, HighShelfFilter, LowShelfFilter, PeakFilter, Pedalboard
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import fftconvolve, firwin2, welch

from ..config import TONES
from .analysis import lufs, true_peak_db


def tone_filters(name):
    fx = []
    for kind, f, g, q in TONES.get(name, []):
        cls = {"peak": PeakFilter, "lowshelf": LowShelfFilter, "highshelf": HighShelfFilter}[kind]
        fx.append(cls(cutoff_frequency_hz=f, gain_db=g, q=q))
    return fx


def stereo_width(audio, sr, percent):
    """Mid/side width: 100 is unchanged, 0 is mono, 130 is wider. Lows stay centred either way."""
    if percent == 100 or audio.shape[0] != 2:
        return audio
    from scipy.signal import butter, sosfiltfilt

    mid = (audio[0] + audio[1]) / 2
    side = (audio[0] - audio[1]) / 2
    k = percent / 100.0
    if k > 1:  # widen only above 150 Hz, so bass and kick stay solid in the middle
        sos = butter(2, 150, btype="highpass", fs=sr, output="sos")
        side = side + (k - 1) * sosfiltfilt(sos, side)
    else:
        side = side * k
    return np.vstack([mid + side, mid - side]).astype(np.float32)


def glue(audio, sr, amount):
    """Gentle bus compression that holds the mix together. amount 0-100 (0 = off)."""
    if amount <= 0:
        return audio
    a = amount / 100.0
    # set the level going in, so the same amount behaves the same on quiet and loud mixes
    level = lufs(audio, sr)
    pre = 0.0 if not np.isfinite(level) else -18.0 - level
    board = Pedalboard(
        [
            Gain(gain_db=pre),
            Compressor(threshold_db=-14.0 - 10.0 * a, ratio=1.5 + 2.5 * a, attack_ms=30.0, release_ms=180.0),
            Gain(gain_db=-pre),
        ]
    )
    return board(audio, sr).astype(np.float32)


class TruePeakLimiter:
    """A look-ahead brick-wall limiter that watches true peaks (between samples too).

    Clipping-style limiters create distortion that peaks well over the ceiling between samples,
    so streaming services turn the song down or it crackles after conversion. This one never
    clips: it estimates each sample's true peak (4x oversampled), looks 2 ms ahead, and lowers the
    gain smoothly *before* each peak, then lets it recover over the release time.

    The peak detection is done once; trying a different input gain is cheap, which suits the
    loudness search below.
    """

    LOOKAHEAD = 0.002  # seconds
    BLOCK = 64  # samples per step of the release curve

    def __init__(self, audio, sr, release_ms=80.0):
        from .analysis import _oversampling_phases

        self.audio, self.sr = audio, sr
        peak = np.max(np.abs(audio), axis=0).astype(np.float32)
        for taps in _oversampling_phases():
            for ch in audio:
                est = np.abs(np.convolve(ch.astype(np.float32), taps.astype(np.float32), mode="same"))
                np.maximum(peak, est, out=peak)
        self.peak = peak  # true-peak estimate per sample, before any gain
        self.release = float(np.exp(-self.BLOCK / (sr * release_ms / 1000.0)))

    def run(self, gain_db, ceiling_db):
        """The audio turned up by gain_db and limited so true peaks stay at or under ceiling_db."""
        g = 10 ** (gain_db / 20)
        limit = 10 ** (ceiling_db / 20)
        need = np.minimum(1.0, limit / np.maximum(self.peak * g, 1e-12))  # gain each sample needs
        la = max(1, int(self.LOOKAHEAD * self.sr))
        # attack: be at the needed gain before the peak arrives (min over the look-ahead), then ease
        # in with a moving average whose window lies inside that min, so it never undershoots
        held = minimum_filter1d(need, size=2 * la + 1, mode="nearest")
        attack = uniform_filter1d(held, size=la, mode="nearest")
        attack = np.minimum(attack, need)
        # release: recover smoothly, one block at a time, never faster than the release time
        n = attack.size
        nb = -(-n // self.BLOCK)
        padded = np.pad(attack, (0, nb * self.BLOCK - n), constant_values=1.0)
        blocks = padded.reshape(nb, self.BLOCK).min(axis=1)
        smooth = np.empty(nb, dtype=np.float64)
        level, r = 1.0, self.release
        for i, b in enumerate(blocks):  # one step per 64 samples: about 165k steps for 4 minutes
            level = b if b < level else b + (level - b) * r
            smooth[i] = level
        curve = np.interp(np.arange(n), np.arange(nb) * self.BLOCK + self.BLOCK / 2, smooth)
        gain = np.minimum(curve, attack).astype(np.float32)
        return (self.audio * (g * gain)).astype(np.float32)


def loudness_and_limit(audio, sr, target_lufs, ceiling_db=-1.0):
    """Bring the song to target loudness with a true-peak limiter, peaks kept under ceiling (dBTP).

    The input gain is searched (always applied to the unprocessed audio, so gains never stack up)
    until the result lands on the target. The limiter aims 0.3 dB under the ceiling, because 4x
    true-peak meters (the streaming standard) can read a little under the real peak.
    """
    level = lufs(audio, sr)
    if not np.isfinite(level):
        return audio  # silence
    limiter = TruePeakLimiter(audio, sr)
    aim = ceiling_db - 0.3

    def run(g):
        out = limiter.run(g, aim)
        return out, lufs(out, sr)

    # Secant search: the limiter flattens the response (+3 dB in gives less than +3 dB out),
    # so learn the slope from the last two tries instead of assuming 1:1.
    g0 = target_lufs - level
    out, got0 = run(g0)
    if abs(got0 - target_lufs) >= 0.1:
        g1 = g0 + (target_lufs - got0)
        out, got1 = run(g1)
        for _ in range(10):
            if abs(got1 - target_lufs) < 0.1 or got1 == got0:
                break
            slope = max(0.08, (got1 - got0) / (g1 - g0))
            g0, got0 = g1, got1
            g1 = g1 + min(12.0, (target_lufs - got1) / slope)  # never jump more than 12 dB at once
            out, got1 = run(g1)
    safe = ceiling_db - 0.2
    tp = true_peak_db(out)
    if tp > safe:  # a last safety net; the limiter keeps this from being needed
        out = (out * 10 ** ((safe - tp) / 20)).astype(np.float32)
    return out


# ---- matching a reference song
def _smoothed_spectrum_db(audio, sr):
    freqs, psd = welch(audio.mean(axis=0), sr, nperseg=8192)
    db = 10 * np.log10(psd + 1e-20)
    # smooth on a log-frequency scale (about 1/3 octave) so only the broad tonal balance remains
    logf = np.log2(np.maximum(freqs, 1.0))
    grid = np.linspace(np.log2(20), np.log2(sr / 2), 400)
    on_grid = np.interp(grid, logf, db)
    on_grid = uniform_filter1d(on_grid, size=int(400 / np.log2(sr / 2 / 20) / 3) or 1, mode="nearest")
    return 2**grid, on_grid


def reference_curve(audio, sr, ref, ref_sr, max_db=6.0):
    """The EQ that moves this song's tonal balance toward the reference: (freqs Hz, gain dB)."""
    f, mine = _smoothed_spectrum_db(audio, sr)
    fr, theirs = _smoothed_spectrum_db(ref, ref_sr)
    theirs = np.interp(f, fr, theirs)
    diff = theirs - mine
    band = (f > 200) & (f < 5000)
    diff -= np.mean(diff[band])  # match the shape, not the level (loudness is handled separately)
    diff = np.clip(diff, -max_db, max_db)
    diff[f < 30] = 0.0
    diff[f > 18000] = 0.0
    return f, diff * 0.8  # stop a little short of a full match: it sounds more natural


def apply_curve(audio, sr, freqs, gains_db, taps=4097):
    """Apply an EQ curve with a linear-phase filter (no smearing, no delay)."""
    nyq = sr / 2
    pts = np.concatenate([[0.0], np.clip(freqs, 1.0, nyq - 1) / nyq, [1.0]])
    gains = 10 ** (np.concatenate([[gains_db[0]], gains_db, [gains_db[-1]]]) / 20)
    order = np.argsort(pts)
    pts, gains = pts[order], gains[order]
    keep = np.concatenate([[True], np.diff(pts) > 0])
    fir = firwin2(taps, pts[keep], gains[keep])
    out = np.vstack([fftconvolve(ch, fir, mode="same") for ch in audio])
    return out.astype(np.float32)
