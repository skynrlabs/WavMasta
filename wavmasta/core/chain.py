"""The mastering chain: tone EQ (or matching a reference song), stereo width, glue
compression, and loudness with a true-peak limiter."""

import numpy as np
from pedalboard import Compressor, Gain, HighShelfFilter, Limiter, LowShelfFilter, PeakFilter, Pedalboard
from scipy.ndimage import uniform_filter1d
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


def loudness_and_limit(audio, sr, target_lufs, ceiling_db=-1.0):
    """Bring the song to target loudness with a brick-wall limiter, peaks kept under ceiling (dBTP).

    pedalboard's Limiter always outputs up to 0 dBFS, so the limited signal is turned down to the
    ceiling afterwards, and the input gain is searched (always from the unprocessed audio, so gains
    never stack up) until the result lands on the target.
    """
    level = lufs(audio, sr)
    if not np.isfinite(level):
        return audio  # silence

    def run(g):
        out = Pedalboard(
            [Gain(gain_db=g), Limiter(threshold_db=0.0, release_ms=120.0), Gain(gain_db=ceiling_db - 0.4)]
        )(audio, sr)
        return out.astype(np.float32), lufs(out, sr)

    # Secant search: the limiter flattens the response (+3 dB in gives less than +3 dB out),
    # so learn the slope from the last two tries instead of assuming 1:1.
    g0 = target_lufs - level
    out, got0 = run(g0)
    if abs(got0 - target_lufs) >= 0.1:
        g1 = g0 + (target_lufs - got0)
        out, got1 = run(g1)
        for _ in range(5):
            if abs(got1 - target_lufs) < 0.1 or got1 == got0:
                break
            slope = max(0.2, (got1 - got0) / (g1 - g0))
            g0, got0 = g1, got1
            g1 = g1 + (target_lufs - got1) / slope
            out, got1 = run(g1)
    # Catch overs between samples. 4x metering (the streaming standard) can read up to ~0.2 dB
    # under the real peak, so aim that much lower.
    safe = ceiling_db - 0.2
    tp = true_peak_db(out)
    if tp > safe:
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
