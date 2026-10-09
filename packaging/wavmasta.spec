# PyInstaller build for the standalone app:  pyinstaller packaging/wavmasta.spec
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
IS_WIN = sys.platform.startswith("win")

datas = [(os.path.join(ROOT, "wavmasta", "assets"), os.path.join("wavmasta", "assets"))]
binaries = []
hidden = collect_submodules("wavmasta")
# pedalboard is a compiled library with its own data files; take all of it
for pkg in ("pedalboard", "tkinterdnd2"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h

a = Analysis(
    [os.path.join(SPECPATH, "launch.py")],
    pathex=[ROOT],
    datas=datas,
    binaries=binaries,
    hiddenimports=hidden,
    excludes=["matplotlib", "IPython", "pytest", "pyloudnorm", "pandas", "setuptools", "pip"],
    noarchive=False,
)


def _not_tests(entry):
    """Drop the test suites that ship inside numpy, scipy and friends."""
    name = entry[0].replace("\\", "/")
    return not (".tests." in name or name.endswith(".tests") or "/tests/" in name)


a.pure = [e for e in a.pure if _not_tests(e)]
a.datas = [e for e in a.datas if _not_tests(e)]
a.binaries = [e for e in a.binaries if _not_tests(e)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WavMasta",
    console=False,
    strip=not IS_WIN,
    icon=os.path.join(ROOT, "wavmasta", "assets", "wavmasta.ico") if IS_WIN else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=not IS_WIN, name="WavMasta")
