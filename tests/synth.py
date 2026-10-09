"""Synthetic songs with known problems, so tests can check the engine fixes exactly those.

song() builds about 16 seconds of music: a quiet verse, a loud chorus and short gaps between
phrases (where real noise shows up). Problems are added on top with the keyword arguments.
"""

import numpy as np

from wavmasta.core import save

SR = 44100


def _note(freq, dur, amp, harmonics=((1, 1.0), (2, 0.4), (3, 0.2)), decay=2.0):
    t = np.arange(int(dur * SR)) / SR
    wave = sum(a * np.sin(2 * np.pi * freq * k * t) for k, a in harmonics)
    env = np.minimum(1, t / 0.01) * np.exp(-t * decay) * np.minimum(1, (dur - t) / 0.05)
    return wave * env * amp


def _kick(amp):
    t = np.arange(int(0.3 * SR)) / SR
    return np.sin(2 * np.pi * (50 + 80 * np.exp(-t * 30)) * t) * np.exp(-t * 10) * amp


def music(seconds=16, seed=0):
    """Stereo music: chords panned a little apart, bass and kick in the middle."""
    rng = np.random.default_rng(seed)
    n = seconds * SR
    left, right = np.zeros(n), np.zeros(n)
    chords = [(261.6, 329.6, 392.0), (220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7)]
    bass = [65.4, 55.0, 43.7, 49.0]
    beat = 0.5
    for i in range(int(seconds / 2)):
        start = int(i * 2 * SR)
        loud = 1.0 if (i // 2) % 2 else 0.35  # verse, chorus, verse, chorus...
        for j, f in enumerate(chords[i % 4]):
            tone = _note(f, 1.7, 0.08 * loud, decay=1.2)  # 0.3 s gap before the next chord
            pan = 0.3 * (j - 1)
            end = min(n, start + tone.size)
            left[start:end] += tone[: end - start] * (1 - pan)
            right[start:end] += tone[: end - start] * (1 + pan)
        b = _note(bass[i % 4], 1.7, 0.18 * loud, harmonics=((1, 1.0), (2, 0.5)), decay=0.8)
        end = min(n, start + b.size)
        left[start:end] += b[: end - start]
        right[start:end] += b[: end - start]
        for k in range(4):
            s = start + int(k * beat * SR)
            kick = _kick(0.4 * loud * (1 + 0.05 * rng.standard_normal()))
            e = min(n, s + kick.size)
            left[s:e] += kick[: e - s]
            right[s:e] += kick[: e - s]
    return np.vstack([left, right]).astype(np.float32)


def vocal(seconds=16, sibilance=0.0, seed=0):
    """A sung line (harmonic-rich notes with vibrato) with sharp 's' bursts of the given level:
    5-9 kHz noise, about 100 ms long like a real "s", a couple per phrase. sibilance=0 gives the
    same line without them."""
    from scipy.signal import butter, sosfilt
    from scipy.signal.windows import tukey

    rng = np.random.default_rng(seed + 7)
    n = seconds * SR
    t = np.arange(n) / SR
    v = np.zeros(n)
    notes = [220.0, 246.9, 261.6, 293.7, 329.6, 293.7, 261.6, 246.9]
    for i, f in enumerate(notes * (seconds // 8 + 1)):
        s0, s1 = int(i * SR), int((i + 0.85) * SR)
        if s0 >= n:
            break
        s1 = min(n, s1)
        tt = t[s0:s1] - t[s0]
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * tt)
        tone = sum((0.5**k) * np.sin(2 * np.pi * f * (k + 1) * vib * tt) for k in range(10))
        env = np.minimum(1, tt / 0.05) * np.minimum(1, (tt[-1] - tt) / 0.08)
        v[s0:s1] += 0.12 * tone * env
    if sibilance:
        sos = butter(6, [5000, 9000], btype="bandpass", fs=SR, output="sos")
        for i in range(seconds):
            for at in (0.05, 0.62):  # an 's' at the start and end of each phrase
                s0 = int((i + at + 0.03 * rng.standard_normal()) * SR)
                k = int(0.10 * SR)
                if 0 <= s0 < n - k:
                    burst = sosfilt(sos, rng.normal(0, 1, k)) * tukey(k, 0.6)
                    v[s0 : s0 + k] += sibilance * burst / (np.std(burst) + 1e-9)
    return np.vstack([v, v]).astype(np.float32)


def hats(seconds=16, level=0.03, seed=0):
    """Hi-hats on every eighth note: short 6-14 kHz noise ticks, like the cymbals and air every
    real recording has up top."""
    from scipy.signal import butter, sosfilt

    rng = np.random.default_rng(seed + 11)
    n = seconds * SR
    h = np.zeros(n)
    sos = butter(4, [6000, 14000], btype="bandpass", fs=SR, output="sos")
    k = int(0.06 * SR)
    env = np.exp(-np.arange(k) / SR * 45)
    for i in range(int(seconds * 4)):
        s0 = int(i * 0.25 * SR)
        if s0 + k < n:
            tick = sosfilt(sos, rng.normal(0, 1, k)) * env
            h[s0 : s0 + k] += level * tick / (np.std(tick) + 1e-9) * (0.7 + 0.3 * (i % 2 == 0))
    return np.vstack([h, h]).astype(np.float32)


def song(
    seconds=16, hiss=0.0, whine_hz=None, whine=0.0, hum=0.0, fizz=0.0, seed=0, sibilance=None, pad=(0, 0),
    hihats=False,
):  # fmt: skip
    """Music plus problems: hiss (noise level), a steady whine, 60 Hz mains hum, harsh top end,
    a vocal line (sibilance=level of its 's' bursts, 0 for a clean vocal), hi-hats, and silence
    padded at the start and end (pad=(seconds, seconds))."""
    rng = np.random.default_rng(seed + 1)
    x = music(seconds, seed)
    if sibilance is not None:
        x = x + vocal(seconds, sibilance, seed)
    if hihats:
        x = x + hats(seconds, seed=seed)
    n = x.shape[1]
    t = np.arange(n) / SR
    if hiss:
        x += rng.normal(0, hiss, x.shape).astype(np.float32)
    if whine and whine_hz:
        x += (whine * np.sin(2 * np.pi * whine_hz * t)).astype(np.float32)
    if hum:
        h = hum * (np.sin(2 * np.pi * 60 * t) + 0.4 * np.sin(2 * np.pi * 120 * t))
        x += h.astype(np.float32)
    if fizz:
        from scipy.signal import butter, sosfilt

        sos = butter(4, 12000, btype="highpass", fs=SR, output="sos")
        x += (sosfilt(sos, rng.normal(0, 1, x.shape)) * fizz * np.abs(x.mean(axis=0))).astype(np.float32)
    if pad[0] or pad[1]:
        x = np.concatenate([np.zeros((2, int(pad[0] * SR))), x, np.zeros((2, int(pad[1] * SR)))], axis=1)
    return x.astype(np.float32)


def tone_level_db(audio, freq):
    """Level of one frequency in the audio (dB), measured by correlating with a sine."""
    t = np.arange(audio.shape[1]) / SR
    mono = audio.mean(axis=0)
    return 20 * np.log10(2 * abs(np.mean(mono * np.exp(-2j * np.pi * freq * t))) + 1e-12)


def write(path, audio, fmt="WAV 24-bit"):
    save(str(path), audio, SR, fmt)
    return str(path)


def mix(seconds=16, sibilance=0.0, seed=0, hihats=True):
    """A more realistic mix for de-essing: music, a bright sung vocal (harmonics through the 2-4 kHz
    'presence' range, like a real voice), hi-hats, and the quiet bed of reverb and air that fills
    the top of every real recording. sibilance: level of the vocal's 's' bursts (0 = none)."""
    from scipy.signal import butter, sosfilt
    from scipy.signal.windows import tukey

    rng = np.random.default_rng(seed + 21)
    n = seconds * SR
    t = np.arange(n) / SR
    x = music(seconds, seed)
    # vocal with a presence formant (energy up through 4 kHz)
    v = np.zeros(n)
    notes = [220.0, 246.9, 261.6, 293.7, 329.6, 293.7, 261.6, 246.9]
    for i in range(seconds):
        f = notes[i % len(notes)]
        s0, s1 = int(i * SR), min(n, int((i + 0.85) * SR))
        tt = t[s0:s1] - t[s0]
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * tt)
        tone = np.zeros_like(tt)
        for k in range(1, 20):
            fk = f * k
            gain = (0.85**k) * (1.0 + 1.5 * np.exp(-(((fk - 3000) / 900) ** 2)))  # presence peak near 3 kHz
            tone += gain * np.sin(2 * np.pi * fk * vib * tt)
        env = np.minimum(1, tt / 0.05) * np.minimum(1, (tt[-1] - tt) / 0.08)
        v[s0:s1] += 0.05 * tone * env
    if sibilance:
        sos = butter(6, [5000, 9500], btype="bandpass", fs=SR, output="sos")
        for i in range(seconds):
            for at in (0.05, 0.62):
                s0 = int((i + at + 0.03 * rng.standard_normal()) * SR)
                k = int(0.10 * SR)
                if 0 <= s0 < n - k:
                    burst = sosfilt(sos, rng.normal(0, 1, k)) * tukey(k, 0.6)
                    v[s0 : s0 + k] += sibilance * burst / (np.std(burst) + 1e-9)
    x = x + np.vstack([v, v])
    # air and reverb bed: quiet, steady, bright
    sos = butter(2, 3000, btype="highpass", fs=SR, output="sos")
    bed = sosfilt(sos, rng.normal(0, 1, (2, n)), axis=1)
    x = x + 0.004 * bed / np.std(bed)
    if hihats:
        sos = butter(4, [6000, 14000], btype="bandpass", fs=SR, output="sos")
        k = int(0.08 * SR)
        env = np.exp(-np.arange(k) / SR * 70)  # a closed hat: bright tick, gone in ~40 ms
        for i in range(seconds * 4):
            s0 = int(i * 0.25 * SR)
            if s0 + k < n:
                tick = sosfilt(sos, rng.normal(0, 1, k)) * env
                x[:, s0 : s0 + k] += 0.05 * tick / (np.std(tick) + 1e-9) * (0.7 + 0.3 * (i % 2 == 0))
    return x.astype(np.float32)
