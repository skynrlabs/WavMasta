"""What the window knows about each song: its own sound settings, what Analyze found, and how
mastering it went."""

import os
from dataclasses import dataclass, field

from ..config import DEFAULT_LOUDNESS, LOUDNESS
from ..core import Settings

SOUND_FIELDS = (
    "tone", "loudness", "denoise", "fix_tones", "tame_top", "glue", "width", "reference", "deess", "fade_out", "trim",
)  # fmt: skip


@dataclass
class Track:
    path: str
    tone: str = "Neutral"
    loudness: str = DEFAULT_LOUDNESS  # a label from config.LOUDNESS
    denoise: int = 0
    fix_tones: bool = True
    tame_top: float = 0.0
    glue: int = 30
    width: int = 100
    reference: str | None = None
    deess: int = 0
    fade_out: float = 0.0
    trim: bool = True
    report: object = None  # the latest analysis.Report, once analysed
    status: str = "not mastered yet"
    status_kind: str = "muted"  # muted, busy, ok or warn
    saved: str = None
    saved_sig: tuple = None  # the settings the saved master was made with (see MasterPage.signature)
    saved_status: str = ""  # the "saved · -14.0 LUFS" text, restored if settings change back
    extra: dict = field(default_factory=dict)

    @property
    def name(self):
        return os.path.basename(self.path)

    def sound(self):
        """This song's settings as a tuple, for spotting changes."""
        return tuple(getattr(self, f) for f in SOUND_FIELDS)

    def settings(self, ceiling):
        return Settings(
            tone=self.tone,
            target_lufs=LOUDNESS[self.loudness],
            ceiling=ceiling,
            denoise=self.denoise,
            fix_tones=self.fix_tones,
            tame_top=self.tame_top,
            glue=self.glue,
            width=self.width,
            reference=self.reference,
            deess=self.deess,
            fade_out=self.fade_out,
            trim=self.trim,
        )

    def reset(self):
        defaults = Track(self.path)
        for f in SOUND_FIELDS:
            setattr(self, f, getattr(defaults, f))

    def copy_settings_from(self, other):
        for f in SOUND_FIELDS:
            setattr(self, f, getattr(other, f))

    def use_suggestions(self):
        """Apply what Analyze suggested. Returns the names of the settings that changed."""
        if self.report is None:
            return []
        changed = []
        for key, value in self.report.suggested().items():
            if getattr(self, key) != value:
                setattr(self, key, value)
                changed.append(key)
        return changed
