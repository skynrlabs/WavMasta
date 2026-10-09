"""The start and end of a song: trimming dead silence and fading out.

Distributors and playlists don't like long silent intros, and many songs (AI-generated ones
especially) stop dead instead of ending. Trimming runs on the original audio, before mastering,
so loudness is measured on the music; the fade runs just before the loudness stage, so the
loudness target counts it in (the limiter only touches peaks, so the fade keeps its shape).
"""

import numpy as np

SILENCE_DBFS = -60.0  # quieter than this counts as silence
KEEP_BEFORE = 0.05  # seconds of silence left before the first sound (so the attack isn't clipped)
KEEP_AFTER = 0.30  # seconds left after the last sound (room for the very end of a reverb tail)
MICRO_FADE = 0.010  # seconds: a tiny fade where a trim cuts, so there's never a click
MAX_FADE = 10.0  # seconds: the longest fade-out


def _loud_mask(audio, sr, threshold_db=SILENCE_DBFS, window=0.01):
    """True for each 10 ms block louder than the silence threshold."""
    mono = np.max(np.abs(audio), axis=0)
    hop = max(1, int(window * sr))
    n = mono.size // hop
    if n == 0:
        return np.zeros(0, dtype=bool), hop
    peaks = mono[: n * hop].reshape(n, hop).max(axis=1)
    return peaks > 10 ** (threshold_db / 20), hop


def silence_at_edges(audio, sr):
    """(seconds of silence at the start, seconds at the end), measured the same way trim() cuts."""
    loud, hop = _loud_mask(audio, sr)
    if not loud.any():
        return 0.0, 0.0
    first = int(np.argmax(loud)) * hop
    last = (len(loud) - int(np.argmax(loud[::-1]))) * hop
    return first / sr, max(0.0, (audio.shape[1] - last) / sr)


def trim(audio, sr):
    """Cut dead silence from the start and end. Returns (audio, seconds cut at start, at end)."""
    lead, tail = silence_at_edges(audio, sr)
    n = audio.shape[1]
    start = max(0, int((lead - KEEP_BEFORE) * sr))
    end = min(n, n - int(max(0.0, tail - KEEP_AFTER) * sr))
    if start == 0 and end == n:
        return audio, 0.0, 0.0
    out = audio[:, start:end].copy()
    k = min(int(MICRO_FADE * sr), out.shape[1] // 2)
    if k:
        ramp = np.linspace(0.0, 1.0, k, dtype=np.float32)
        if start:
            out[:, :k] *= ramp
        if end < n:
            out[:, -k:] *= ramp[::-1]
    return out, start / sr, (n - end) / sr


def fade_out(audio, sr, seconds):
    """Fade the last `seconds` to silence on a smooth (raised-cosine) curve that sounds even."""
    k = min(int(seconds * sr), audio.shape[1])
    if k <= 0:
        return audio
    t = np.linspace(0.0, 1.0, k, dtype=np.float64)
    curve = (0.5 * (1 + np.cos(np.pi * t))) ** 1.5  # starts gently, ends at exactly zero
    out = audio.copy()
    out[:, -k:] *= curve.astype(np.float32)
    return out


def ends_abruptly(audio, sr):
    """True when the song stops while still loud: the last half second is within 20 dB of the
    song's typical level, with no silence after it."""
    _, tail = silence_at_edges(audio, sr)
    if tail > 0.5 or audio.shape[1] < sr * 5:
        return False
    mono = audio.mean(axis=0)
    end = mono[-int(0.5 * sr) :]
    hop = int(0.4 * sr)
    n = mono.size // hop
    blocks = np.sqrt(np.mean(mono[: n * hop].reshape(n, hop) ** 2, axis=1))
    typical = np.median(blocks[blocks > 1e-6]) if np.any(blocks > 1e-6) else 0.0
    level = np.sqrt(np.mean(end**2))
    return typical > 0 and level > typical * 10 ** (-20 / 20)
