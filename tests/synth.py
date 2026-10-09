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


def song(seconds=16, hiss=0.0, whine_hz=None, whine=0.0, hum=0.0, fizz=0.0, seed=0):
    """Music plus problems: hiss (noise level), a steady whine, 60 Hz mains hum, harsh top end."""
    rng = np.random.default_rng(seed + 1)
    x = music(seconds, seed)
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
    return x


def tone_level_db(audio, freq):
    """Level of one frequency in the audio (dB), measured by correlating with a sine."""
    t = np.arange(audio.shape[1]) / SR
    mono = audio.mean(axis=0)
    return 20 * np.log10(2 * abs(np.mean(mono * np.exp(-2j * np.pi * freq * t))) + 1e-12)


def write(path, audio, fmt="WAV 24-bit"):
    save(str(path), audio, SR, fmt)
    return str(path)
