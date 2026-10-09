"""Shared fixtures: synthetic songs with known problems, written once per test run."""

import pytest

from wavmasta.core.edges import fade_out

from . import synth


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Never touch the real user's settings file."""
    import wavmasta.config as config

    monkeypatch.setattr(config, "SETTINGS_PATH", str(tmp_path / "settings.json"))


@pytest.fixture(scope="session")
def songs(tmp_path_factory):
    """Song files by problem: clean, hiss, whine, hum, fizz, everything, silent."""
    import numpy as np

    d = tmp_path_factory.mktemp("songs")
    made = {
        "clean": fade_out(synth.song(), synth.SR, 3),  # a clean song with a proper ending
        "hiss": synth.song(hiss=0.004),
        "whine": synth.song(whine_hz=3150, whine=0.01),
        "hum": synth.song(hum=0.01),
        "fizz": synth.song(fizz=0.3),
        "messy": synth.song(hiss=0.003, whine_hz=7400, whine=0.006, hum=0.006),
    }
    out = {name: synth.write(d / f"{name.title()} Song.wav", audio) for name, audio in made.items()}
    out["silent"] = synth.write(d / "Silent.wav", np.zeros((2, synth.SR * 3), dtype=np.float32))
    return out


@pytest.fixture(scope="session")
def audio():
    """The same songs as arrays (no file round trip), for engine tests."""
    return {
        "clean": fade_out(synth.song(), synth.SR, 3),  # a clean song with a proper ending
        "hiss": synth.song(hiss=0.004),
        "whine": synth.song(whine_hz=3150, whine=0.01),
        "hum": synth.song(hum=0.01),
        "fizz": synth.song(fizz=0.3),
    }
