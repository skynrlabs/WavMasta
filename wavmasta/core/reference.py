"""Matching a finished reference song: its tone, density, width and loudness.

A released master sounds "finished" mostly because of how dense it is (how little its level moves
around), how wide it is and its tonal balance, not just how loud it is. plan() measures all of those on
the reference and on the song, and works out the EQ curve, the glue amount and the stereo width that
move the song toward the reference. `strength` (0-1) says how far: 0.8 (the default) stops a little
short of a full match, which sounds more natural; 1.0 goes all the way.
"""

import numpy as np
from scipy.signal import butter, resample_poly, sosfiltfilt

from . import chain
from .analysis import lufs

WINDOW = 60.0  # seconds: density is measured on the loudest minute (the chorus, usually)
GLUE_STEPS = (0, 20, 40, 60, 80, 100)
WIDTH_RANGE = (60, 150)
EQ_BANDS = (60, 120, 250, 500, 1000, 2000, 4000, 8000, 12000)  # Hz, for describing the EQ in History


def loudest_part(audio, sr, seconds=WINDOW):
    """The loudest `seconds` of the song (all of it if it's shorter)."""
    n = int(seconds * sr)
    if audio.shape[1] <= n:
        return audio
    hop = int(5 * sr)
    power = np.mean(audio.astype(np.float64) ** 2, axis=0)
    csum = np.concatenate([[0.0], np.cumsum(power)])
    starts = np.arange(0, audio.shape[1] - n + 1, hop)
    best = starts[np.argmax(csum[starts + n] - csum[starts])]
    return audio[:, best : best + n]


def movement_db(audio, sr):
    """How much the level moves around (dB): the spread of 400 ms loudness frames near the top.
    A dense, compressed master moves less; a raw, dynamic mix moves more."""
    mono = np.mean(audio, axis=0).astype(np.float64)
    win, hop = int(0.4 * sr), int(0.1 * sr)
    if mono.size < win * 4:
        return 0.0
    csum = np.concatenate([[0.0], np.cumsum(mono**2)])
    starts = np.arange(0, mono.size - win, hop)
    db = 10 * np.log10((csum[starts + win] - csum[starts]) / win + 1e-12)
    keep = db > db.max() - 20
    return float(np.std(db[keep]))


def spread_db(audio, sr):
    """Side energy relative to mid energy above 150 Hz (dB): how wide the song sounds.
    -inf for mono."""
    if audio.shape[0] != 2:
        return float("-inf")
    hp = butter(2, 150, "high", fs=sr, output="sos")
    mid = sosfiltfilt(hp, (audio[0] + audio[1]) / 2)
    side = sosfiltfilt(hp, (audio[0] - audio[1]) / 2)
    pm, ps = np.mean(mid**2), np.mean(side**2)
    if pm <= 0 or ps <= 1e-14:
        return float("-inf")
    return float(10 * np.log10(ps / pm))


def _half_rate(audio, sr):
    """A half-rate copy for the quick tries in the glue search."""
    return resample_poly(audio, 1, 2, axis=-1).astype(np.float32), sr // 2


def _glue_for(x, sr, ref_move, strength, target_lufs, ceiling, style):
    """The glue amount (0-100) that takes the master `strength` of the way from its usual density (30%
    glue) to the reference's (ref_move), and the movement that gives.
    Each try runs the glue and a quick level-to-target with the limiter, on the loudest minute at half
    rate, so it measures the song the way the finished master will sound."""
    part, psr = _half_rate(loudest_part(x, sr), sr)
    moves = []
    for amount in GLUE_STEPS:
        y = chain.glue(part, psr, amount, style)
        level = lufs(y, psr)
        if not np.isfinite(level):
            return 0, 0.0
        y = chain.TruePeakLimiter(y, psr).run(target_lufs - level, ceiling - 0.3)
        moves.append(movement_db(y, psr))
    moves = np.array(moves)
    # start from what WavMasta does without a reference (30% glue) and go `strength` of the way
    base = float(np.interp(30, GLUE_STEPS, moves))
    target_move = base + (ref_move - base) * strength
    steps = np.array(GLUE_STEPS, dtype=float)
    if target_move >= moves[0]:
        return 0, float(moves[0])  # already as dense as the reference (or denser)
    if target_move <= moves[-1]:
        return 100, float(moves[-1])  # as dense as glue can make it
    # movement falls as glue rises: find where it crosses the target
    i = int(np.argmax(moves <= target_move))
    m0, m1 = moves[i - 1], moves[i]
    k = 0.0 if m0 == m1 else (m0 - target_move) / (m0 - m1)
    return int(round(steps[i - 1] + k * (steps[i] - steps[i - 1]))), float(target_move)


def eq_curve(x, sr, ref, ref_sr, strength):
    """The tone-matching EQ at this strength. 80% is WavMasta's original match (capped at 6 dB);
    stronger matches may move a band up to 9 dB."""
    limit = 6.0 if strength <= 0.8 else 6.0 + 15.0 * (strength - 0.8)
    f, diff = chain.reference_curve(x, sr, ref, ref_sr, max_db=limit)
    return f, diff / 0.8 * strength  # reference_curve applies 0.8 itself


def describe_eq(freqs, gains_db, top=3):
    """The biggest moves, e.g. [(80, 3.1), (3000, -2.2)], for the History report."""
    moves = []
    for b in EQ_BANDS:
        g = float(np.interp(b, freqs, gains_db))
        if abs(g) >= 1.0:
            moves.append((b, round(g, 1)))
    return sorted(moves, key=lambda m: -abs(m[1]))[:top]


def plan(x, sr, ref, ref_sr, strength=0.8, ceiling=-1.0, style=chain.GLUE_STYLE_DEFAULT):
    """Everything needed to move the song x toward the reference. Returns a dict:
    curve (freqs, gains dB), width %, glue %, target LUFS, and the measurements behind them."""
    s = float(np.clip(strength, 0.0, 1.0))
    ref_level = lufs(ref, ref_sr)
    target = round(float(np.clip(ref_level, -20.0, -7.0)), 1) if np.isfinite(ref_level) else -14.0
    freqs, gains = eq_curve(x, sr, ref, ref_sr, s)

    # width: scale the sides so the song's spread moves toward the reference's
    mine, theirs = spread_db(x, sr), spread_db(ref, ref_sr)
    if np.isfinite(mine) and np.isfinite(theirs) and theirs > -40:
        full = 100 * 10 ** ((theirs - mine) / 20)
        width = int(round(np.clip(100 + (full - 100) * s, *WIDTH_RANGE)))
    else:
        width = 100  # a mono song or a mono reference: leave the width alone

    # density: how much the reference's level moves, and the glue that gets the song there
    ref_part = loudest_part(ref, ref_sr)
    ref_move = movement_db(ref_part, ref_sr)
    shaped = chain.apply_curve(x, sr, freqs, gains)
    shaped = chain.stereo_width(shaped, sr, width)
    glue, got = _glue_for(shaped, sr, ref_move, s, target, ceiling, style)
    return {
        "curve": (freqs, gains),
        "width": width,
        "glue": glue,
        "target": target,
        "strength": s,
        "eq": describe_eq(freqs, gains),
        "movement": {"reference": round(ref_move, 1), "master": round(got, 1)},
        "spread": {"song": mine, "reference": theirs},
    }
