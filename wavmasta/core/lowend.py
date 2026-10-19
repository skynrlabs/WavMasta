"""The low end and mono compatibility.

Keep bass centred folds everything below MONO_BELOW to mono. Bass that's spread across the
stereo field (common in AI-generated songs) sounds thin on phones and small speakers and wastes
loudness; centring it is a standard mastering step. Above the crossover nothing changes.

Two measurements for Check:
- side_bass_db: how much of the bass is in the sides rather than the centre. Real mixes range from
  about -40 dB (centred) to about -4 dB (orchestral or wide synth bass, on purpose), so Check only
  suggests centring when it's clearly spread, and leaves the choice to you.
- mono_loss_db: how much quieter each part of the song gets when left and right are added together,
  as on a phone speaker, Bluetooth speaker or club system. Out-of-phase parts cancel. Normal mixes
  lose under about 3 dB in every band; a fully out-of-phase part loses far more.
"""

import numpy as np
from scipy.signal import butter, sosfiltfilt

MONO_BELOW = 120.0  # Hz
SIDE_BASS_DB = -6.0  # bass in the sides within 6 dB of the centre counts as spread wide
MONO_LOSS_DB = 4.5  # a band losing more than this in mono has parts cancelling out
MONO_BANDS = ((150, 1000), (1000, 4000), (4000, 12000))


def _mid_side(audio):
    left, right = audio[0].astype(np.float64), audio[1].astype(np.float64)
    return (left + right) / 2, (left - right) / 2


def mono_bass(audio, sr, below=MONO_BELOW):
    """Fold everything below `below` Hz to mono. The split is zero-phase, so the sides above the
    crossover come out exactly as they went in, and the centre is never touched."""
    if audio.ndim != 2 or audio.shape[0] != 2:
        return audio
    mid, side = _mid_side(audio)
    low = sosfiltfilt(butter(4, below, "low", fs=sr, output="sos"), side)
    side = side - low
    return np.vstack([mid + side, mid - side]).astype(np.float32)


def side_bass_db(audio, sr, below=MONO_BELOW):
    """The bass in the sides relative to the bass in the centre, dB (-inf for mono songs)."""
    if audio.ndim != 2 or audio.shape[0] != 2:
        return float("-inf")
    mid, side = _mid_side(audio)
    lp = butter(4, below, "low", fs=sr, output="sos")
    m, s = np.mean(sosfiltfilt(lp, mid) ** 2), np.mean(sosfiltfilt(lp, side) ** 2)
    if m <= 1e-14:
        return float("-inf")
    return float(10 * np.log10(s / m + 1e-30))


def mono_loss_db(audio, sr):
    """The most any band (low mids, mids, highs) gets quieter when the song is played in mono, dB.
    0 for a mono song; a fully out-of-phase part gives tens of dB."""
    if audio.ndim != 2 or audio.shape[0] != 2:
        return 0.0
    left, right = audio[0].astype(np.float64), audio[1].astype(np.float64)
    bands = []
    for lo, hi in MONO_BANDS:
        hi = min(hi, sr / 2 * 0.95)
        sos = butter(4, [lo, hi], "bandpass", fs=sr, output="sos")
        lb, rb = sosfiltfilt(sos, left), sosfiltfilt(sos, right)
        stereo = (np.mean(lb**2) + np.mean(rb**2)) / 2
        bands.append((stereo, np.mean(((lb + rb) / 2) ** 2)))
    loudest = max(s for s, _ in bands)
    if loudest <= 1e-12:
        return 0.0
    worst = 0.0
    for stereo, mono in bands:
        if stereo < loudest * 1e-3:
            continue  # more than 30 dB below the rest: too faint to matter if it cancels
        worst = max(worst, float(10 * np.log10(stereo / (mono + 1e-30))))
    return min(worst, 60.0)
