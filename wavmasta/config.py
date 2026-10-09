"""Shared constants: tone presets, loudness targets, output formats and saved settings."""

import json
import os
import sys

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(PACKAGE_DIR, "assets")
REPO_URL = "https://github.com/skynrlabs/WavMasta"
SUPPORT_URL = "https://skynrlabs.itch.io/wavmasta"  # "Support WavMasta" links in the app (pay what you want)

AUDIO_EXTENSIONS = (".wav", ".mp3", ".flac", ".aif", ".aiff", ".ogg", ".m4a")

# Tone presets: gentle EQ moves, each band is (kind, frequency Hz, gain dB, Q).
# kind is "peak", "lowshelf" or "highshelf". Mastering EQ should be subtle; these stay within 2 dB.
TONES = {
    "Neutral": [],
    "Country": [  # clear vocal, sparkle on acoustic and steel, tidy low-mids
        ("peak", 250, -1.5, 1.0),
        ("peak", 3000, 1.0, 0.8),
        ("highshelf", 10000, 1.5, 0.7),
    ],
    "Roots rock": [  # weight in the low end, presence for guitars, less boxiness
        ("lowshelf", 90, 1.5, 0.7),
        ("peak", 400, -1.5, 1.0),
        ("peak", 2500, 1.0, 0.9),
        ("highshelf", 9000, 1.0, 0.7),
    ],
    "Pop": [  # tight low end, forward vocal, open top
        ("lowshelf", 60, 1.0, 0.7),
        ("peak", 300, -1.0, 1.0),
        ("peak", 4000, 1.0, 0.8),
        ("highshelf", 12000, 2.0, 0.7),
    ],
    "Warm": [  # softer top, fuller low-mids
        ("lowshelf", 150, 1.0, 0.7),
        ("highshelf", 7000, -1.5, 0.7),
    ],
    "Bright": [  # more air and clarity
        ("peak", 200, -1.0, 1.0),
        ("highshelf", 8000, 2.0, 0.7),
    ],
}
TONE_HINTS = {
    "Neutral": "no tone change, just cleanup and loudness",
    "Country": "clear vocal, sparkle on acoustic and steel",
    "Roots rock": "weight in the lows, presence for guitars",
    "Pop": "tight lows, forward vocal, open top",
    "Warm": "softer top, fuller low-mids",
    "Bright": "more air and clarity",
}

# Loudness targets in LUFS (integrated). Streaming services turn louder songs down to about -14,
# so going louder than that mostly costs punch.
LOUDNESS = {
    "Streaming (-14 LUFS)": -14.0,
    "Apple Music (-16 LUFS)": -16.0,
    "Loud (-11 LUFS)": -11.0,
    "Very loud (-9 LUFS)": -9.0,
}
DEFAULT_LOUDNESS = "Streaming (-14 LUFS)"
DEFAULT_CEILING = -1.0  # dBTP: leaves room for MP3/AAC conversion by streaming services

# (label, file extension, pedalboard bit depth or None, quality)
FORMATS = {
    "WAV 24-bit": (".wav", 24, None),
    "WAV 16-bit (CD)": (".wav", 16, None),
    "FLAC 24-bit": (".flac", 24, None),
    "MP3 320 kbps": (".mp3", None, "320"),
}
DEFAULT_FORMAT = "WAV 24-bit"
OUTPUT_SUFFIX = " - master"


def _settings_dir():
    """Your own app-data folder, so settings survive updates and work in an installed copy."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "WavMasta")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/WavMasta")
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "wavmasta")


SETTINGS_PATH = os.path.join(_settings_dir(), "settings.json")


def load_settings():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_settings(data):
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass


def log_default(msg):
    print(msg, flush=True)
