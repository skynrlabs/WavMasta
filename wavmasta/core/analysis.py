"""Measuring a track: loudness, peaks, hiss, harsh top end, and steady hum or whine.

Everything here only reads the audio. analyze() returns a Report with the numbers and
plain-English findings, plus the settings it would suggest for this track.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import stft, welch

SILENCE_DB = -70.0  # frames quieter than this are digital silence (gaps, fades), not noise


def _k_filter(sr):
    """ITU-R BS.1770 K-weighting (high shelf + high pass) for any sample rate, as second-order sections."""
    # the standard's coefficients, recalculated for this sample rate (same method as libebur128)
    f0, g, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = np.tan(np.pi * f0 / sr)
    vh = 10 ** (g / 20)
    vb = vh**0.4996667741545416
    a0 = 1 + k / q + k * k
    shelf_b = np.array([(vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0])
    shelf_a = np.array([1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0])
    f0, q = 38.13547087602444, 0.5003270373238773
    k = np.tan(np.pi * f0 / sr)
    hp_b = np.array([1.0, -2.0, 1.0])
    hp_a = np.array([1.0, 2 * (k * k - 1) / (1 + k / q + k * k), (1 - k / q + k * k) / (1 + k / q + k * k)])
    return np.vstack([np.concatenate([shelf_b, shelf_a]), np.concatenate([hp_b, hp_a])])


def lufs(audio, sr):
    """Integrated loudness (ITU-R BS.1770-4, as used by streaming services), or -inf for silence.

    Matches libebur128 and pyloudnorm to within 0.1 LU, and is vectorised so it's quick to re-run.
    """
    from scipy.signal import sosfilt

    n = audio.shape[1]
    block, step = int(0.4 * sr), int(0.1 * sr)
    if n < block:
        return float("-inf")
    y = sosfilt(_k_filter(sr), audio.astype(np.float64), axis=1)
    c = np.concatenate([np.zeros((y.shape[0], 1)), np.cumsum(y * y, axis=1)], axis=1)
    starts = np.arange(0, n - block + 1, step)
    z = (c[:, starts + block] - c[:, starts]) / block  # mean square per 400 ms block, per channel
    power = z.sum(axis=0)  # stereo channels weigh 1.0 each
    with np.errstate(divide="ignore"):
        loud = -0.691 + 10 * np.log10(power)
    gated = power[loud > -70]
    if gated.size == 0:
        return float("-inf")
    rel = -0.691 + 10 * np.log10(gated.mean()) - 10
    with np.errstate(divide="ignore"):
        final = power[(loud > -70) & (loud > rel)]
    return float(-0.691 + 10 * np.log10(final.mean()))


def _oversampling_phases():
    """A 48-tap 4x interpolation filter split into its 4 phases (12 taps each), as in BS.1770 Annex 2."""
    from scipy.signal import firwin

    h = firwin(48, 0.24, window=("kaiser", 7.0)) * 4  # cutoff just below the original Nyquist
    return [h[p::4] for p in range(4)]


_PHASES = None


def true_peak_db(audio):
    """Highest peak including the ones between samples (4x oversampling), in dBTP."""
    global _PHASES
    if _PHASES is None:
        _PHASES = _oversampling_phases()
    best = float(np.max(np.abs(audio)))
    if best == 0:
        return -240.0
    for ch in audio:
        x = ch.astype(np.float32)
        for taps in _PHASES:
            best = max(best, float(np.max(np.abs(np.convolve(x, taps.astype(np.float32), mode="same")))))
    return 20 * np.log10(best)


def sample_peak_db(audio):
    return 20 * np.log10(float(np.max(np.abs(audio))) + 1e-12)


def _frames_rms(mono, frame):
    n = len(mono) // frame
    if n == 0:
        return np.zeros(0)
    return np.sqrt(np.mean(mono[: n * frame].reshape(n, frame).astype(np.float64) ** 2, axis=1))


def quiet_passages(audio, sr, frame=4096):
    """How loud the 2-16 kHz band is in the quietest (but not silent) 10% of the track, and how
    noise-like it is there. Hiss is flat like white noise (flatness well above 0.2); quiet music is
    tonal (well below 0.1). Returns (band level dBFS, flatness 0-1), or (None, None) if the track
    has no quiet passages to read.
    """
    mono = audio.mean(axis=0)
    rms = _frames_rms(mono, frame)
    db = 20 * np.log10(rms + 1e-12)
    live = np.where(db > SILENCE_DB)[0]
    if live.size < 20:
        return None, None
    cut = np.percentile(db[live], 10)
    quiet = live[db[live] <= cut]
    spec = np.zeros(frame // 2 + 1)
    window = np.hanning(frame)
    for i in quiet:
        spec += np.abs(np.fft.rfft(mono[i * frame : (i + 1) * frame] * window)) ** 2
    spec /= len(quiet) * frame * np.sum(window**2) / 2  # mean power per bin (bins add up to the total power)
    freqs = np.fft.rfftfreq(frame, 1 / sr)
    band = spec[(freqs >= 2000) & (freqs <= min(16000, sr / 2 - 1))] + 1e-20
    # ignore the loudest 2% of bins, so a whine on top of hiss doesn't make the hiss look tonal
    flat_band = np.sort(band)[: max(1, int(band.size * 0.98))]
    flatness = float(np.exp(np.mean(np.log(flat_band))) / np.mean(flat_band))
    band_db = float(10 * np.log10(np.sum(band)))  # how loud the 2-16 kHz noise is in those passages
    return band_db, flatness


def top_end_ratio_db(audio, sr):
    """Energy above 12 kHz compared with 1-4 kHz. Around -20 is typical; above -12 sounds fizzy."""
    freqs, psd = welch(audio.mean(axis=0), sr, nperseg=8192)
    hi = psd[(freqs > 12000) & (freqs < min(18000, sr / 2))]
    mid = psd[(freqs > 1000) & (freqs < 4000)]
    if hi.size == 0 or mid.size == 0:
        return float("nan")
    return float(10 * np.log10((hi.mean() + 1e-20) / (mid.mean() + 1e-20)))


def find_tones(audio, sr, threshold_db=10.0, fmin=40, fmax=16000, max_n=6):
    """Steady narrow tones that never go away: mains hum, whine, ringing.

    Uses the 10th-percentile level of each frequency over time. Notes come and go with the
    music, so they sit low at the 10th percentile; a hum or whine is there the whole time.
    Returns [(frequency Hz, dB above its surroundings), ...], strongest first.
    """
    mono = audio.mean(axis=0).astype(np.float32)
    if mono.size < 2 * sr:
        return []
    freqs, _, z = stft(mono, sr, nperseg=8192, noverlap=4096)
    level = 20 * np.log10(np.abs(z) + 1e-9)
    loud = level.max(axis=0) > level.max() - 80  # leave out digital silence
    if loud.sum() < 8:
        return []
    level = level[:, loud]
    p10, p50 = np.percentile(level, [10, 50], axis=1)
    excess = p10 - median_filter(p10, size=41)
    # A hum or whine holds the same level the whole song; notes swell and fade. So the typical level
    # must sit close to the quietest level, or it's music and must not be notched.
    steady = (p50 - p10) < 6.0
    band = (freqs >= fmin) & (freqs <= fmax)
    idx = np.where(band & steady & (excess > threshold_db))[0]
    groups, cur = [], []
    for i in idx:
        if cur and i != cur[-1] + 1:
            groups.append(cur)
            cur = []
        cur.append(i)
    if cur:
        groups.append(cur)
    tones = []
    fine = None
    for g in groups:
        k = g[int(np.argmax(excess[g]))]
        f = float(freqs[k])
        if fine is None:
            fine = welch(mono, sr, nperseg=min(mono.size, 1 << 16))  # ~0.7 Hz steps for exact frequencies
        tones.append((_refine(f, *fine), float(excess[k])))
    tones.sort(key=lambda t: -t[1])
    return tones[:max_n]


def _refine(freq, ff, psd):
    """Pin a tone's frequency down precisely: hum snaps to its 50/60 Hz harmonic, anything else to
    the exact spectral peak (a narrow notch that's 1 Hz off misses most of a low tone)."""
    for base in (50.0, 60.0):
        k = round(freq / base)
        if 1 <= k <= 6 and abs(freq - k * base) < 4:
            return k * base
    near = np.where(np.abs(ff - freq) <= 8)[0]
    if near.size < 3:
        return freq
    i = near[int(np.argmax(psd[near]))]
    if 0 < i < len(psd) - 1:  # parabolic interpolation between bins
        a, b, c = np.log(psd[i - 1 : i + 2] + 1e-30)
        d = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
        return float(ff[i] + d * (ff[1] - ff[0]))
    return float(ff[i])


def tone_kind(freq):
    """'hum' for mains hum and its harmonics (50/60 Hz family), otherwise 'whine'."""
    for base in (50.0, 60.0):
        k = round(freq / base)
        if 1 <= k <= 6 and abs(freq - k * base) < 4:
            return "hum"
    return "whine"


@dataclass
class Report:
    duration: float
    sample_rate: int
    lufs: float
    true_peak: float
    clipped: int  # samples at or above full scale
    quiet_level: float | None  # 2-16 kHz level in the quiet parts, dB relative to the song's loudness
    quiet_flatness: float | None
    top_end: float
    tones: list = field(default_factory=list)

    @property
    def hiss(self):
        """Steady hiss: the quiet passages are noise-like and not far below the music."""
        return (
            self.quiet_flatness is not None
            and self.quiet_level is not None
            and self.quiet_flatness > 0.2
            and self.quiet_level > -60
        )

    @property
    def fizzy(self):
        return not np.isnan(self.top_end) and self.top_end > -12

    def findings(self):
        """Plain-English lines about what was found, most important first."""
        out = []
        if self.clipped > 100:
            out.append(
                f"Clipping: {self.clipped:,} samples hit full scale. Mastering can't undo it; "
                "export the mix a few dB quieter if you can."
            )
        if self.hiss:
            out.append("Hiss in the quiet parts. Try Noise reduction around 40%.")
        for f, ex in self.tones:
            what = "Mains hum" if tone_kind(f) == "hum" else "Steady whine"
            out.append(
                f"{what} at {f:,.0f} Hz ({ex:.0f} dB above its surroundings). Remove hum and whine will notch it out."
            )
        if self.fizzy:
            out.append("Fizzy, harsh top end. Try Tame harsh highs.")
        if not out:
            out.append("No noise problems found. Pick a tone and loudness and master it.")
        return out

    def suggested(self):
        """Settings this report suggests: {setting name: value}."""
        s = {"denoise": 40 if self.hiss else 0}
        if self.tones:  # only ever turn it on: with no steady tone found it does nothing anyway
            s["fix_tones"] = True
        if self.fizzy:
            s["tame_top"] = 3.0 if self.top_end > -8 else 1.5
        else:
            s["tame_top"] = 0.0
        return s

    def summary(self):
        return f"{self.lufs:.1f} LUFS · peak {self.true_peak:.1f} dBTP"


def analyze(audio, sr):
    song = lufs(audio, sr)
    level, flatness = quiet_passages(audio, sr)
    rel = None if level is None or not np.isfinite(song) else level - song
    return Report(
        duration=audio.shape[1] / sr,
        sample_rate=sr,
        lufs=song,
        true_peak=true_peak_db(audio),
        clipped=int(np.sum(np.abs(audio) >= 0.999)),
        quiet_level=rel,
        quiet_flatness=flatness,
        top_end=top_end_ratio_db(audio, sr),
        tones=find_tones(audio, sr),
    )
