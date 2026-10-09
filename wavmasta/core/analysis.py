"""Measuring a track: loudness, peaks, hiss, harsh top end, and steady hum or whine.

Everything here only reads the audio. analyze() returns a Report with the numbers and
plain-English findings, plus the settings it would suggest for this track.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import stft, welch

from .deess import SIBILANT_DB

SILENCE_DB = -70.0  # frames quieter than this are digital silence (gaps, fades), not noise
FIZZY_DB = -12.0  # top-end ratio above this sounds fizzy; around -20 is typical
NATURAL_TOP_DB = -14.0  # where Tame harsh highs aims to bring a fizzy song
SHELF_EFFECT = 0.9  # each dB of Tame harsh highs lowers the top-end ratio by about this much (measured)
MAX_TAME_DB = 6.0  # the slider's range
SUGGESTED_FADE = 3.0  # seconds of fade-out suggested for a song that stops dead
SILENCE_WORTH_TRIMMING = 1.0  # seconds; less is just the end of a fade or a breath before the downbeat


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


def suggested_deess(sib):
    from .deess import suggested_amount

    return suggested_amount(sib)


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
    # ...and loud enough to hear: within 55 dB of the song's strongest content. A leftover that's
    # been notched to far below the music is no longer a problem, however clean its surroundings.
    audible = p10 > np.max(p50) - 55
    band = (freqs >= fmin) & (freqs <= fmax)
    idx = np.where(band & steady & audible & (excess > threshold_db))[0]
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
            fine = _steady_spectrum(mono, sr)
        tones.append((float(_refine(f, *fine)), float(excess[k])))
    tones = _snap_to_hum_family(tones)
    tones.sort(key=lambda t: -t[1])
    return tones[:max_n]


def _snap_to_hum_family(tones):
    """Mains hum always comes as a family: 60, 120, 180... Hz (or 50, 100, 150... in Europe).
    When one member is found exactly, low tones near the family's other members are snapped onto
    them; a kick drum or bass sitting on the same spot can blur those members on their own."""
    base = None
    # decide the family from members above 90 Hz first: the 50/60 Hz fundamentals are the ones a
    # kick or bass blurs, and a blurred 60 can even land on exactly 50
    for pool in ([t for t in tones if t[0] >= 90], tones):
        for f, _ in sorted(pool, key=lambda t: -t[1]):
            for b in (60.0, 50.0):
                k = round(f / b)
                if 1 <= k <= 6 and abs(f - k * b) < 0.25 and not (b == 50.0 and f % 60 == 0 and f >= 90):
                    base = b
                    break
            if base:
                break
        if base:
            break
    if base is None:
        return tones
    merged = {}
    for f, ex in tones:
        k = round(f / base)
        if f < 400 and 1 <= k <= 6 and abs(f - k * base) <= 10:
            f = k * base
        merged[f] = max(ex, merged.get(f, ex))
    return list(merged.items())


def _steady_spectrum(mono, sr):
    """Fine-resolution (about 1.3 Hz) spectrum of what's always there: the 10th-percentile level of
    each frequency over time. A hum keeps its level; notes, even loud ones, drop out between plays."""
    n = 32768 if mono.size >= 32768 * 6 else 8192
    ff, _, z = stft(mono, sr, nperseg=n, noverlap=n // 2)
    return ff, np.percentile(np.abs(z), 10, axis=1)


def _refine(freq, ff, steady):
    """Pin a tone's frequency down precisely, since a narrow notch that's 1 Hz off misses most of a
    low tone. Hum is a razor-thin line, while a kick drum or bass is broad, so this picks the
    sharpest steady peak near the rough estimate (not the loudest), snapped to exact mains hum."""
    step = ff[1] - ff[0]
    near = np.where(np.abs(ff - freq) <= 8)[0]
    if near.size < 3:
        return float(freq)
    reach = max(4, int(round(8 / step)))  # how far either side counts as "around" the peak

    def sharpness(i):
        lo, hi = max(0, i - reach), min(len(steady), i + reach + 1)
        ring = np.concatenate([steady[lo : max(lo, i - 2)], steady[i + 3 : hi]])
        return steady[i] / (np.median(ring) + 1e-30) if ring.size else 0.0

    i = max(near, key=sharpness)
    f = float(ff[i])
    if 0 < i < len(steady) - 1:  # parabolic interpolation between bins
        a, b, c = np.log(steady[i - 1 : i + 2] + 1e-30)
        den = a - 2 * b + c
        f += float(0.5 * (a - c) / den if den != 0 else 0.0) * step
    for base in (50.0, 60.0):
        k = round(f / base)
        if 1 <= k <= 6 and abs(f - k * base) <= max(1.0, step):
            return k * base
    return f


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
    lead_silence: float = 0.0  # seconds of silence before the music starts
    tail_silence: float = 0.0  # ...and after it ends
    abrupt_end: bool = False  # stops while still loud, with no fade
    sibilance: float = float("-inf")  # how harsh the 's' sounds are (deess.sibilance_db)

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
        return not np.isnan(self.top_end) and self.top_end > FIZZY_DB

    @property
    def tame_amount(self):
        """How much Tame harsh highs (dB) brings this song's top end back to a natural level,
        in the slider's 0.5 dB steps; 0 if it isn't fizzy."""
        if not self.fizzy:
            return 0.0
        cut = (self.top_end - NATURAL_TOP_DB) / SHELF_EFFECT
        return float(min(MAX_TAME_DB, max(1.0, round(cut * 2) / 2)))

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
            n = self.tame_amount
            most = " (its strongest setting)" if n >= MAX_TAME_DB else ""
            out.append(f"Fizzy, harsh top end. Try Tame harsh highs at -{n:g} dB{most}.")
        if self.sibilance >= SIBILANT_DB:
            out.append(f"Sharp 's' sounds in the vocal. Try De-ess at {suggested_deess(self.sibilance)}%.")
        edges_ = ((self.lead_silence, "start"), (self.tail_silence, "end"))
        silence = [f"{s:.1f} s at the {where}" for s, where in edges_ if s > SILENCE_WORTH_TRIMMING]
        if silence:
            out.append(f"Silence: {' and '.join(silence)}. Trim silence takes it off.")
        if self.abrupt_end:
            out.append(f"The song stops suddenly at the end. Try a {SUGGESTED_FADE:g} s fade-out.")
        if not out:
            out.append("No noise problems found. Pick a tone and loudness and master it.")
        return out

    def suggested(self):
        """Settings this report suggests: {setting name: value}."""
        s = {"denoise": 40 if self.hiss else 0}
        if self.tones:  # only ever turn it on: with no steady tone found it does nothing anyway
            s["fix_tones"] = True
        if self.fizzy:  # only ever suggested when it's needed; a setting you chose yourself is left alone
            s["tame_top"] = self.tame_amount
        if self.sibilance >= SIBILANT_DB:
            s["deess"] = suggested_deess(self.sibilance)
        if max(self.lead_silence, self.tail_silence) > SILENCE_WORTH_TRIMMING:
            s["trim"] = True
        if self.abrupt_end:
            s["fade_out"] = SUGGESTED_FADE
        return s

    def summary(self):
        return f"{self.lufs:.1f} LUFS · peak {self.true_peak:.1f} dBTP"


def analyze(audio, sr):
    from . import edges
    from .deess import sibilance_db

    song = lufs(audio, sr)
    lead, tail = edges.silence_at_edges(audio, sr)
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
        lead_silence=lead,
        tail_silence=tail,
        abrupt_end=edges.ends_abruptly(audio, sr),
        sibilance=sibilance_db(audio, sr),
    )
