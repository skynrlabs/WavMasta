"""Before/after preview: the loudest stretch of the song, original and mastered, at equal loudness.

Comparing at equal loudness matters: louder always sounds "better" at first, so the original is
turned up (or down) to match the master. What you hear is the difference in tone and noise.
"""

import sys
import wave

import numpy as np

from .analysis import lufs

PREVIEW_SECONDS = 20


def loudest_window(audio, sr, seconds=PREVIEW_SECONDS):
    """(start, end) samples of the loudest stretch, which is usually the chorus."""
    n = audio.shape[1]
    length = int(seconds * sr)
    if n <= length:
        return 0, n
    hop = sr // 2
    mono = audio.mean(axis=0)
    energy = np.convolve(mono[: (n // hop) * hop].reshape(-1, hop).std(axis=1) ** 2, np.ones(2 * seconds), "valid")
    start = int(np.argmax(energy)) * hop
    return start, min(n, start + length)


def _fade(x, sr, ms=30):
    k = min(x.shape[1] // 2, int(sr * ms / 1000))
    if k:
        ramp = np.linspace(0, 1, k, dtype=np.float32)
        x = x.copy()
        x[:, :k] *= ramp
        x[:, -k:] *= ramp[::-1]
    return x


def ab_clips(original, mastered, sr, seconds=PREVIEW_SECONDS):
    """Matching clips of the original (level-matched) and the master."""
    a, b = loudest_window(mastered, sr, seconds)
    before, after = original[:, a:b], mastered[:, a:b]
    lb, la = lufs(before, sr), lufs(after, sr)
    if np.isfinite(lb) and np.isfinite(la):
        gain = la - lb  # bring the original up (or down) to the master's loudness
        peak = float(np.max(np.abs(before))) * 10 ** (gain / 20)
        if peak > 0.98:
            # The original can't come up that far without clipping, so meet in the middle:
            # turn both down by the same amount and they stay equally loud.
            short = 20 * np.log10(peak / 0.98)
            gain -= short
            after = after * 10 ** (-short / 20)
        before = before * 10 ** (gain / 20)
    return _fade(before.astype(np.float32), sr), _fade(after.astype(np.float32), sr), a / sr


def write_wav16(path, audio, sr):
    """Plain 16-bit WAV that every system player (including Windows' built-in one) can play."""
    pcm = (np.clip(audio.T, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(audio.shape[0])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


class Player:
    """Plays a WAV in the background and can stop it. Uses Windows' built-in player when available."""

    def __init__(self):
        self.proc = None

    def play(self, wav):
        self.stop()
        if sys.platform.startswith("win"):
            import winsound

            winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            import shutil
            import subprocess

            for cmd in (
                ["afplay"],
                ["aplay", "-q"],
                ["paplay"],
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
            ):
                if shutil.which(cmd[0]):
                    self.proc = subprocess.Popen(cmd + [wav])
                    return
            raise RuntimeError("no audio player found")

    def stop(self):
        if sys.platform.startswith("win"):
            import winsound

            winsound.PlaySound(None, 0)
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.proc = None
