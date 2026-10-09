"""Mastering one song from start to finish. No GUI code here, so it works from scripts too.

Order: rumble filter, hiss reduction, hum/whine notches, harsh-top taming, tone EQ (or matching
a reference), stereo width, glue compression, then loudness and the true-peak limiter.
"""

import os
from dataclasses import asdict, dataclass

import numpy as np

from ..config import DEFAULT_CEILING, LOUDNESS, TONES, log_default
from . import audio as aio
from . import chain, cleanup
from .analysis import analyze, find_tones, lufs


@dataclass
class Settings:
    tone: str = "Neutral"  # a name from config.TONES
    target_lufs: float = -14.0
    ceiling: float = DEFAULT_CEILING  # dBTP
    denoise: int = 0  # 0-100 %
    fix_tones: bool = True  # notch out steady hum and whine
    tame_top: float = 0.0  # dB cut above 11 kHz
    glue: int = 30  # 0-100 % bus compression
    width: int = 100  # stereo width %
    reference: str | None = None  # a finished song to match tone and loudness to

    def check(self):
        """Returns None if the settings make sense, otherwise what's wrong."""
        if self.tone not in TONES:
            return f"Unknown tone '{self.tone}'. Pick one of: {', '.join(TONES)}"
        if not -24 <= self.target_lufs <= -6:
            return "Loudness should be between -24 and -6 LUFS"
        if not -3 <= self.ceiling <= -0.1:
            return "Peak ceiling should be between -3 and -0.1 dBTP"
        if not 0 <= self.denoise <= 100 or not 0 <= self.glue <= 100:
            return "Noise reduction and glue go from 0 to 100"
        if not 0 <= self.width <= 150:
            return "Stereo width goes from 0 to 150"
        if not 0 <= self.tame_top <= 6:
            return "Tame harsh highs goes from 0 to 6 dB"
        if self.reference and not os.path.isfile(self.reference):
            return f"Can't find the reference song: {self.reference}"
        return None

    def describe(self):
        """A short line for the log, e.g. 'Country · -14 LUFS · noise 40% · hum fix · glue 30%'."""
        parts = ["matched to " + os.path.basename(self.reference) if self.reference else self.tone]
        parts.append("reference loudness" if self.reference else f"{self.target_lufs:g} LUFS")
        if self.denoise:
            parts.append(f"noise {self.denoise}%")
        if self.fix_tones:
            parts.append("hum fix")
        if self.tame_top:
            parts.append(f"highs -{self.tame_top:g} dB")
        parts.append(f"glue {self.glue}%" if self.glue else "no glue")
        if self.width != 100:
            parts.append(f"width {self.width}%")
        return " · ".join(parts)

    def as_dict(self):
        return asdict(self)


def loudness_target(label_or_value):
    """'Streaming (-14 LUFS)' or -14 -> -14.0"""
    if isinstance(label_or_value, str):
        return LOUDNESS[label_or_value]
    return float(label_or_value)


def master_audio(audio, sr, s, log=log_default, progress=None, reference=None, tones=None):
    """Master audio already in memory. reference: (audio, sr) of a finished song, or None.
    tones: hum/whine already found by analyze() (saves looking again), or None to look now.

    Returns (mastered audio, info) where info says what was done.
    """

    def step(frac, msg):
        log(msg)
        if progress:
            progress(frac)

    info = {"tones": [], "target": s.target_lufs}
    # Hum and whine first, on the untouched audio: noise reduction would smear them and hide them
    if s.fix_tones:
        if tones is None:
            step(0.05, "  looking for steady hum and whine")
            tones = find_tones(audio, sr)
        info["tones"] = tones
        for f, ex in tones:
            log(f"    notching {f:,.0f} Hz ({ex:.0f} dB above its surroundings)")
    else:
        tones = []
    step(0.2, "  rumble filter" + (" and notches" if tones else ""))
    x = cleanup.apply(audio, sr, cleanup.cleanup_filters(tones))
    if s.denoise:
        step(0.3, f"  reducing hiss ({s.denoise}%)")
        x = cleanup.denoise(x, sr, s.denoise / 100.0)
    if s.tame_top:
        step(0.5, f"  taming harsh highs (-{s.tame_top:g} dB)")
        x = cleanup.apply(x, sr, cleanup.cleanup_filters(tame_top=s.tame_top, highpass=0))
    if reference is not None:
        ref, ref_sr = reference
        step(0.6, "  matching the reference song's tone")
        f, curve = chain.reference_curve(x, sr, ref, ref_sr)
        x = chain.apply_curve(x, sr, f, curve)
        ref_level = lufs(ref, ref_sr)
        if np.isfinite(ref_level):
            info["target"] = float(np.clip(ref_level, -20.0, -7.0))
    else:
        step(0.6, f"  tone: {s.tone}")
        x = cleanup.apply(x, sr, chain.tone_filters(s.tone))
    x = chain.stereo_width(x, sr, s.width)
    if s.glue:
        step(0.7, f"  glue compression ({s.glue}%)")
        x = chain.glue(x, sr, s.glue)
    step(0.8, f"  loudness to {info['target']:g} LUFS, peaks under {s.ceiling:g} dBTP")
    x = chain.loudness_and_limit(x, sr, info["target"], s.ceiling)
    step(1.0, "  done")
    return x, info


def master_file(path, s, out_dir=None, fmt="WAV 24-bit", log=log_default, progress=None):
    """Master a song file and save it. Returns a result dict (see below), or None if it's silent."""
    err = s.check()
    if err:
        raise ValueError(err)
    log(f"Mastering {os.path.basename(path)}")
    audio, sr = aio.load(path)
    if not np.isfinite(lufs(audio, sr)):
        log("  silent, skipped")
        return None
    before = analyze(audio, sr)
    reference = aio.load(s.reference) if s.reference else None
    out, info = master_audio(audio, sr, s, log, progress, reference, tones=before.tones)
    after = analyze(out, sr)
    dest = aio.save(aio.output_path(path, out_dir, fmt), out, sr, fmt)
    log(f"  saved {dest}  ({after.summary()})")
    return {"path": path, "saved": dest, "before": before, "after": after, "info": info, "settings": s}
