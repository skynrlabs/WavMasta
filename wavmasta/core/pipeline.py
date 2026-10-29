"""Mastering one song from start to finish. No GUI code here, so it works from scripts too.

Order: trim silence, hum/whine notches and rumble filter, hiss reduction, harsh-top taming,
de-essing, album tone match, tone EQ (or matching a reference), centring the bass, stereo width,
glue compression (Smooth, Punchy or Three-band),
the fade-out, then loudness and the true-peak limiter, with an optional soft clipper in front of it
(the limiter only touches peaks, so the
fade keeps its shape, and the loudness target counts the fade in).
"""

import os
from dataclasses import asdict, dataclass

import numpy as np

from ..config import DEFAULT_CEILING, LOUDNESS, TONES, log_default
from . import album as albums
from . import audio as aio
from . import chain, cleanup, edges, lowend
from . import reference as refmatch
from .analysis import analyze, find_tones, lufs
from .deess import deess


@dataclass
class Settings:
    tone: str = "Neutral"  # a name from config.TONES
    target_lufs: float = -14.0
    ceiling: float = DEFAULT_CEILING  # dBTP
    denoise: int = 0  # 0-100 %
    fix_tones: bool = True  # notch out steady hum and whine
    tame_top: float = 0.0  # dB cut above 11 kHz
    glue: int = 30  # 0-100 % bus compression
    glue_style: str = chain.GLUE_STYLE_DEFAULT  # a name from chain.GLUE_STYLES
    width: int = 100  # stereo width %
    reference: str | None = None  # a finished song to match tone, density, width and loudness to
    match: int = 80  # 0-100 %: how closely to match the reference (80 stops a little short, which sounds natural)
    trim: bool = True  # cut dead silence from the start and end
    fade_out: float = 0.0  # seconds of fade at the end (0 = none)
    deess: int = 0  # 0-100 % de-essing
    mono_bass: bool = False  # fold everything below lowend.MONO_BELOW Hz to mono
    soft_clip: str = "Auto"  # round off the sharpest peaks before the limiter: Auto, Always or Off

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
        if not 0 <= self.fade_out <= edges.MAX_FADE:
            return f"Fade-out goes from 0 to {edges.MAX_FADE:g} seconds"
        if not 0 <= self.deess <= 100:
            return "De-ess goes from 0 to 100"
        if self.glue_style not in chain.GLUE_STYLES:
            return f"Unknown glue style '{self.glue_style}'. Pick one of: {', '.join(chain.GLUE_STYLES)}"
        if self.soft_clip not in chain.SOFT_CLIP_MODES:
            return f"Soft clip should be one of: {', '.join(chain.SOFT_CLIP_MODES)}"
        if not 0 <= self.match <= 100:
            return "Match strength goes from 0 to 100"
        if self.reference and not os.path.isfile(self.reference):
            return f"Can't find the reference song: {self.reference}"
        return None

    def describe(self):
        """A short line for the log, e.g. 'Country · -14 LUFS · noise 40% · hum fix · glue 30%'."""
        matched = f"matched to {os.path.basename(self.reference)} ({self.match}%)" if self.reference else None
        parts = [matched or self.tone]
        parts.append("reference loudness" if self.reference else f"{self.target_lufs:g} LUFS")
        if self.denoise:
            parts.append(f"noise {self.denoise}%")
        if self.fix_tones:
            parts.append("hum fix")
        if self.tame_top:
            parts.append(f"highs -{self.tame_top:g} dB")
        if self.deess:
            parts.append(f"de-ess {self.deess}%")
        style = "" if self.glue_style == chain.GLUE_STYLE_DEFAULT else f" {self.glue_style.lower()}"
        if self.reference:
            parts.append(f"glue and width from the reference{style}")
        else:
            parts.append(f"glue {self.glue}%{style}" if self.glue else "no glue")
            if self.width != 100:
                parts.append(f"width {self.width}%")
        if self.trim:
            parts.append("trim")
        if self.fade_out:
            parts.append(f"fade {self.fade_out:g} s")
        if self.mono_bass:
            parts.append("bass centred")
        return " · ".join(parts)

    def as_dict(self):
        return asdict(self)


def loudness_target(label_or_value):
    """'Streaming (-14 LUFS)' or -14 -> -14.0"""
    if isinstance(label_or_value, str):
        return LOUDNESS[label_or_value]
    return float(label_or_value)


def master_audio(audio, sr, s, log=log_default, progress=None, reference=None, tones=None, album=None, key=None):
    """Master audio already in memory. reference: (audio, sr) of a finished song, or None.
    tones: hum/whine already found by analyze() (saves looking again), or None to look now.
    album: an album.profile() when mastering a set as one record, with key naming this song in it.

    Returns (mastered audio, info) where info says what was done.
    """

    def step(frac, msg):
        log(msg)
        if progress:
            progress(frac)

    info = {"tones": [], "target": s.target_lufs, "trim": (0.0, 0.0), "fade": 0.0, "album": None, "mono_bass": False}
    if s.trim:
        audio, cut_start, cut_end = edges.trim(audio, sr)
        info["trim"] = (cut_start, cut_end)
        if cut_start or cut_end:
            log(f"  trimmed silence: {cut_start:.1f} s at the start, {cut_end:.1f} s at the end")
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
    if s.deess:
        step(0.55, f"  de-essing ({s.deess}%)")
        x = deess(x, sr, s.deess / 100.0)
    if album is not None and reference is None:
        step(0.58, "  matching the album's tone")
        x, moved = albums.match(x, sr, album)
        info["album"] = {"tone_db": moved}
    glue, width = s.glue, s.width
    if reference is not None:
        ref, ref_sr = reference
        step(0.6, f"  matching the reference song ({s.match}%): tone, density, width and loudness")
        p = refmatch.plan(x, sr, ref, ref_sr, s.match / 100.0, s.ceiling, s.glue_style)
        x = chain.apply_curve(x, sr, *p["curve"])
        glue, width = p["glue"], p["width"]
        info["target"] = p["target"]
        info["reference"] = {
            "name": os.path.basename(s.reference) if s.reference else "the reference",
            "strength": s.match,
            "eq": p["eq"],
            "glue": glue,
            "width": width,
            "target": p["target"],
            "movement": p["movement"],
        }
        for f, g in p["eq"]:
            log(f"    EQ {g:+.1f} dB around {f:,} Hz")
        log(f"    glue {glue}% and width {width}% to match its density and width")
    else:
        step(0.6, f"  tone: {s.tone}")
        x = cleanup.apply(x, sr, chain.tone_filters(s.tone))
    if s.mono_bass and x.shape[0] == 2:
        step(0.65, f"  centring the bass (below {lowend.MONO_BELOW:g} Hz)")
        x = lowend.mono_bass(x, sr)
        info["mono_bass"] = True
    x = chain.stereo_width(x, sr, width)
    if glue:
        step(0.7, f"  glue compression ({glue}%, {s.glue_style.lower()})")
        x = chain.glue(x, sr, glue, s.glue_style)
    if s.fade_out:
        step(0.75, f"  fading out over {s.fade_out:g} s")
        x = edges.fade_out(x, sr, s.fade_out)
        info["fade"] = s.fade_out
    clip = chain.soft_clip_on(s.soft_clip, info["target"])
    if clip:
        info["soft_clip"] = True
    how = ", soft-clipping the sharpest peaks" if clip else ""
    step(0.8, f"  loudness to {info['target']:g} LUFS, peaks under {s.ceiling:g} dBTP{how}")
    x = chain.loudness_and_limit(x, sr, info["target"], s.ceiling, clip=clip)
    step(1.0, "  done")
    return x, info


def master_file(path, s, out_dir=None, fmt="WAV 24-bit", log=log_default, progress=None, album=None):
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
    out, info = master_audio(audio, sr, s, log, progress, reference, tones=before.tones, album=album, key=path)
    after = analyze(out, sr)
    dest = aio.save(aio.output_path(path, out_dir, fmt), out, sr, fmt)
    log(f"  saved {dest}  ({after.summary()})")
    return {"path": path, "saved": dest, "before": before, "after": after, "info": info, "settings": s}
