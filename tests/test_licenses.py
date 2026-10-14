"""The open-source licenses file the Windows app ships, and what the About dialog shows."""

import sys

from wavmasta import licenses


def test_lists_every_library_the_app_needs():
    names = {d.metadata["Name"].lower() for d in licenses.libraries()}
    assert {"numpy", "scipy", "pedalboard", "tkinterdnd2"} <= names
    assert "wavmasta" not in names and "pip" not in names
    assert "pytest" not in names and "pyloudnorm" not in names  # test tools aren't shipped


def test_full_file_has_every_license_text(tmp_path):
    out = tmp_path / licenses.FILE_NAME
    licenses.main(["--out", str(out)])
    text = out.read_text(encoding="utf-8")
    assert text.startswith("WavMasta - open-source licenses")
    assert "GNU GENERAL PUBLIC LICENSE" in text and "Version 3, 29 June 2007" in text  # pedalboard's GPL v3
    assert "NumPy Developers" in text and "MIT License" in text
    for name in ("numpy", "scipy", "pedalboard", "tkinterdnd2"):
        assert f"\n  {name} " in text  # in the list at the top


def test_dialog_lists_libraries_when_installed_with_pip():
    text = licenses.dialog_text()
    assert "MIT License" in text and "GPL v3" in text
    assert "pedalboard" in text and "numpy" in text
    assert "Version 3, 29 June 2007" not in text  # no full texts: pip installed those with each library


def test_packaged_app_shows_the_shipped_file(tmp_path, monkeypatch):
    (tmp_path / licenses.FILE_NAME).write_text("the shipped file", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "WavMasta.exe"))
    assert licenses.dialog_text() == "the shipped file"
