"""The open-source libraries WavMasta is built on, and their licenses.

The Windows app ships these libraries inside it, so it has to ship their licenses too.
`packaging/build.ps1` writes them all to THIRD_PARTY_LICENSES.txt next to WavMasta.exe:

    python -m wavmasta.licenses --out dist/WavMasta/THIRD_PARTY_LICENSES.txt

The About dialog shows that file. A pip or pipx install has no such file (pip installed each
library with its own license), so the dialog lists what's installed instead.
"""

import argparse
import hashlib
import os
import re
import sys
from importlib import metadata

APP = "wavmasta"
FILE_NAME = "THIRD_PARTY_LICENSES.txt"
# Left out of the Windows build by packaging/wavmasta.spec, so not shipped
NOT_BUNDLED = {"pip", "setuptools", "wheel"}

HEADER = """\
WavMasta - open-source licenses
===============================

WavMasta is Copyright (c) 2026 Skynr Labs and is licensed under the MIT License.
Source code: https://github.com/skynrlabs/WavMasta

The Windows app also includes the open-source libraries listed below, each under its own
license. One of them, pedalboard (Spotify), is licensed under the GNU General Public License
v3, so the Windows app as a whole is distributed under the terms of the GPL v3. You can get the
complete source code for free at the address above, and you're free to share, change and
redistribute the app under those terms. WavMasta's own code stays available under the MIT
License.

Many thanks to everyone who builds and maintains these libraries.
"""

_KNOWN_TEXTS = (
    ("Apache License", "Apache-2.0"),
    ("GNU GENERAL PUBLIC LICENSE", "GPL"),
    ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL"),
    ("MIT License", "MIT"),
    ("Permission is hereby granted, free of charge", "MIT"),
)
_LICENSE_NAME = re.compile(r"^(licen[cs]e|copying|notice|thirdpartynotices|license_notes)", re.IGNORECASE)


def _canon(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _license_of(dist):
    m = dist.metadata
    expr = m.get("License-Expression")
    if expr:
        return expr
    classifiers = [c.split("::")[-1].strip() for c in (m.get_all("Classifier") or []) if c.startswith("License ::")]
    if classifiers:
        return ", ".join(classifiers)
    text = (m.get("License") or "").strip()
    if text and "\n" not in text and len(text) <= 60:
        return text
    for _, path in _license_files(dist):  # no metadata: recognise the license file itself
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                head = fh.read(2000)
        except OSError:
            continue
        for marker, name in _KNOWN_TEXTS:
            if marker in head:
                return name
    return "see license text"


def _homepage(dist):
    m = dist.metadata
    if m.get("Home-page"):
        return m["Home-page"]
    for url in m.get_all("Project-URL") or []:
        label, _, link = url.partition(",")
        if label.strip().lower() in ("homepage", "home", "source", "repository", "source code"):
            return link.strip()
    return ""


def _wanted(requirement):
    """Whether a Requires-Dist line applies here (skips extras like [dev] and other platforms)."""
    try:
        from packaging.requirements import Requirement
    except ImportError:
        return "extra ==" not in requirement
    req = Requirement(requirement)
    return req.marker is None or req.marker.evaluate({"extra": ""})


def _requirement_name(requirement):
    return re.match(r"[A-Za-z0-9._-]+", requirement).group(0)


def libraries(root=APP, exclude=()):
    """Every library `root` needs at run time (not the app itself), sorted by name."""
    skip = {_canon(n) for n in (*NOT_BUNDLED, *exclude)}
    found, todo = {}, [root]
    while todo:
        name = _canon(todo.pop())
        if name in found or name in skip:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        found[name] = dist
        todo += [_requirement_name(r) for r in dist.requires or [] if _wanted(r)]
    found.pop(_canon(root), None)
    return sorted(found.values(), key=lambda d: _canon(d.metadata["Name"]))


def _license_files(dist):
    """The license, copying and notice files a library ships, without vendored or test copies."""
    for f in dist.files or []:
        p = str(f).replace("\\", "/")
        base = p.rsplit("/", 1)[-1]
        if not _LICENSE_NAME.match(base) or base.endswith((".py", ".pyc")):
            continue
        if any(part in p for part in ("/_vendor/", "/tests/", "/test/")):
            continue
        yield p, f.locate()


def _platform_licenses():
    """Python and Tcl/Tk, which PyInstaller bundles too."""
    out = []
    for name in ("LICENSE.txt", "LICENSE"):
        for base in (
            sys.base_prefix,
            os.path.join(sys.base_prefix, "lib", f"python{sys.version_info[0]}.{sys.version_info[1]}"),
        ):
            path = os.path.join(base, name)
            if os.path.isfile(path):
                out.append((f"Python {sys.version.split()[0]}", "PSF-2.0", "https://www.python.org", [(name, path)]))
                break
        if out:
            break
    try:
        import tkinter

        tcl = tkinter.Tcl()
        for lib in ("tcl_library", "tk_library"):
            try:
                path = os.path.join(tcl.eval(f"set {lib}"), "license.terms")
            except tkinter.TclError:
                continue
            if os.path.isfile(path):
                label = "Tcl" if lib == "tcl_library" else "Tk"
                out.append((label, "TCL", "https://www.tcl-lang.org", [("license.terms", path)]))
    except ImportError:
        pass
    return out


def _entries(dists):
    for d in dists:
        m = d.metadata
        yield f"{m['Name']} {m['Version']}", _license_of(d), _homepage(d), list(_license_files(d))


def full_text(exclude=()):
    """The whole THIRD_PARTY_LICENSES.txt: a list of libraries, then every license text in full."""
    sections = [("Included in the app", list(_entries(libraries(exclude=exclude))) + _platform_licenses())]
    lines = [HEADER]
    for title, entries in sections:
        lines += ["", title, "-" * len(title)]
        lines += [f"  {name:<34} {lic}" + (f"\n  {'':<34} {url}" if url else "") for name, lic, url, _ in entries]
    seen = set()
    for _, entries in sections:
        for name, lic, url, files in entries:
            lines += ["", "", "=" * 100, f"{name}  ({lic})", *([url] if url else []), "=" * 100]
            if not files:
                lines.append("(no license file shipped; see the project's home page)")
            for label, path in files:
                try:
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        text = fh.read().strip()
                except OSError:
                    continue
                digest = hashlib.sha1(text.encode()).hexdigest()
                lines += ["", f"--- {label}", ""]
                lines.append(text if digest not in seen else "(same text as shown above)")
                seen.add(digest)
    return "\n".join(lines) + "\n"


def bundled_file():
    """THIRD_PARTY_LICENSES.txt next to the app, if this is the packaged Windows app."""
    if getattr(sys, "frozen", False):
        path = os.path.join(os.path.dirname(sys.executable), FILE_NAME)
        if os.path.isfile(path):
            return path
    return None


def dialog_text():
    """What the Open-source licenses window shows."""
    path = bundled_file()
    if path:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    lines = [
        HEADER,
        "Installed from source or with pip: each library below was installed with its own license file.",
        "",
    ]
    for name, lic, url, _ in _entries(libraries()):
        lines.append(f"  {name:<34} {lic}")
        if url:
            lines.append(f"  {'':<34} {url}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description="Write the licenses of every library the app ships with.")
    p.add_argument("--out", required=True, help="file to write, e.g. dist/WavMasta/THIRD_PARTY_LICENSES.txt")
    p.add_argument("--exclude", action="append", default=[], help="a library left out of the build")
    args = p.parse_args(argv)
    text = full_text(exclude=args.exclude)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"Wrote {args.out} ({len(libraries(exclude=args.exclude))} libraries)")


if __name__ == "__main__":
    main()
