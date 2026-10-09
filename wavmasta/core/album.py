"""Album mode: master a set of songs so they sound like one record.

Two things make an album hang together:

* Tone. Each song's tonal balance is nudged part of the way toward the album's average (measured
  from all the songs), so no song sounds brighter, darker or boomier than its neighbours. Each
  song's own tone preset is still applied on top, so you keep the character you picked.
* Loudness. Every song lands on the same perceived loudness, whatever level it was exported at,
  so nothing jumps out or drops away on a playlist. (Mastering engineers sometimes keep a ballad
  a touch quieter on purpose; set that song's Loudness one step lower if you want that.)
"""

import numpy as np

from .analysis import lufs
from .chain import _smoothed_spectrum_db, apply_curve

TONE_STRENGTH = 0.6  # how far toward the album's average each song moves (1 = all the way)
MAX_TONE_DB = 4.0  # never more than this much EQ, either way


def _normalized_spectrum(audio, sr):
    """Tonal balance on a fixed log-frequency grid, with the 200 Hz-5 kHz level set to 0 dB, so songs
    of any loudness can be averaged and compared."""
    f, db = _smoothed_spectrum_db(audio, sr)
    grid = np.geomspace(30, 18000, 240)
    on_grid = np.interp(grid, f, db)
    band = (grid > 200) & (grid < 5000)
    return grid, on_grid - on_grid[band].mean()


def profile(songs):
    """songs: [(key, audio, sr), ...]. Returns the album profile used by master_audio(album=...):
    {"freqs", "tone" (average balance), "loudness" {key: LUFS before mastering}}."""
    tones, levels = [], {}
    grid = None
    for key, audio, sr in songs:
        level = lufs(audio, sr)
        if not np.isfinite(level):
            continue  # a silent file doesn't shape the album
        grid, t = _normalized_spectrum(audio, sr)
        tones.append(t)
        levels[key] = level
    if not tones:
        return None
    return {"freqs": grid, "tone": np.mean(tones, axis=0), "loudness": levels}


def tone_curve(audio, sr, album):
    """EQ that moves this song part of the way toward the album's average balance: (freqs, dB)."""
    grid, mine = _normalized_spectrum(audio, sr)
    diff = np.clip((album["tone"] - mine) * TONE_STRENGTH, -MAX_TONE_DB, MAX_TONE_DB)
    diff[(grid < 35) | (grid > 16000)] = 0.0
    return grid, diff


def match(audio, sr, album):
    """Apply the album tone match. Returns (audio, largest EQ move in dB)."""
    f, curve = tone_curve(audio, sr, album)
    return apply_curve(audio, sr, f, curve), float(np.max(np.abs(curve)))


def spread_db(values):
    """Difference between the loudest and quietest, in dB (LU)."""
    values = [v for v in values if np.isfinite(v)]
    return float(max(values) - min(values)) if len(values) > 1 else 0.0
