"""Write a short synthetic song with hiss and a whine, for the build smoke test.

python make_test_song.py out.wav
"""

import sys

import numpy as np
from pedalboard.io import AudioFile

sr = 44100
t = np.arange(sr * 8) / sr
rng = np.random.default_rng(0)
music = np.zeros_like(t)
for i, chord in enumerate([(261.6, 329.6, 392.0), (220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7)]):
    seg = (t >= i * 2) & (t < i * 2 + 1.8)
    tt = t[seg] - i * 2
    music[seg] += sum(0.08 * np.sin(2 * np.pi * f * tt) for f in chord) * np.exp(-tt * 1.2)
song = music + rng.normal(0, 0.003, t.size) + 0.008 * np.sin(2 * np.pi * 3150 * t)
stereo = np.vstack([song, song]).astype(np.float32)
with AudioFile(sys.argv[1] if len(sys.argv) > 1 else "test-song.wav", "w", sr, 2, bit_depth=24) as f:
    f.write(stereo)
