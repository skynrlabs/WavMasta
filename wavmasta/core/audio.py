"""Reading and writing audio files. Audio is always float32, shaped (channels, samples)."""

import os

import numpy as np
from pedalboard.io import AudioFile

from ..config import FORMATS, OUTPUT_SUFFIX


def load(path):
    """Read any supported file. Mono files come back as two identical channels."""
    with AudioFile(os.fspath(path)) as f:
        audio = f.read(f.frames)
        sr = int(f.samplerate)
    if audio.ndim == 1:
        audio = audio[np.newaxis, :]
    if audio.shape[0] == 1:
        audio = np.vstack([audio, audio])
    elif audio.shape[0] > 2:
        audio = audio[:2]  # mastering is stereo; extra channels are dropped
    return np.ascontiguousarray(audio, dtype=np.float32), sr


def tpdf_dither(audio, bits, seed=0):
    """Add triangular dither before reducing to a lower bit depth (avoids grainy fade-outs)."""
    rng = np.random.default_rng(seed)
    lsb = 1.0 / (2 ** (bits - 1))
    noise = (rng.random(audio.shape, dtype=np.float32) - rng.random(audio.shape, dtype=np.float32)) * lsb
    return audio + noise


def save(path, audio, sr, fmt="WAV 24-bit"):
    """Write a file in one of the FORMATS. Returns the path written."""
    ext, bits, quality = FORMATS[fmt]
    audio = np.clip(audio, -1.0, 1.0).astype(np.float32)
    if bits == 16:
        audio = np.clip(tpdf_dither(audio, 16), -1.0, 1.0)
    kwargs = {}
    if bits:
        kwargs["bit_depth"] = bits
    if quality:
        kwargs["quality"] = quality
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    with AudioFile(os.fspath(path), "w", sr, audio.shape[0], **kwargs) as f:
        f.write(audio)
    return path


def output_path(src, out_dir=None, fmt="WAV 24-bit"):
    """'Song.wav' -> 'Song - master.wav' next to the source (or in out_dir). Never the source itself."""
    ext = FORMATS[fmt][0]
    base = os.path.splitext(os.path.basename(src))[0]
    folder = out_dir or os.path.dirname(os.path.abspath(src))
    path = os.path.join(folder, base + OUTPUT_SUFFIX + ext)
    if os.path.abspath(path) == os.path.abspath(src):
        path = os.path.join(folder, base + OUTPUT_SUFFIX + " (2)" + ext)
    return path
