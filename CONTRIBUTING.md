# Contributing to WavMasta

Thank you for your interest in contributing. Please read this document before opening issues or pull requests.

---

## Code of Conduct

Be respectful. Harassment, discrimination, or abusive language toward any contributor will not be tolerated and may result in removal from the project. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## License

WavMasta is open-source under the **MIT** license. By submitting a contribution you agree to license your work under the same terms.

---

## Branch Model

| Branch | Purpose |
|---|---|
| `main` | Stable, release-ready. Never commit directly here. |
| `dev` | Integration target. All PRs merge here first. |
| `feature/*` | New features (`feature/de-esser`) |
| `fix/*` | Bug fixes (`fix/denoise-artifacts`) |
| `release/*` | Release stabilization (`release/v1.1`) |

**Flow:** `feature/* / fix/*` → PR to `dev` → PR to `main` → tag release

---

## Opening Issues

Before opening an issue:

- Search existing issues to avoid duplicates.
- For bugs, include: OS, Python version, the song's format (WAV, MP3...), the settings you used, and what you expected vs. what happened.
- For sound problems (artifacts, a missed hum, wrong loudness), a short clip helps a lot, if you have the rights to share it.
- For feature requests, describe the problem you are trying to solve, not just the solution.
- For security issues, **do not open a public issue** — see [SECURITY.md](SECURITY.md).

---

## Submitting a Pull Request

1. Fork the repo and create your branch from `dev`, not `main`.
2. Name your branch `feature/short-description` or `fix/short-description`.
3. Keep PRs focused — one feature or fix per PR.
4. Run the checks locally (see **Tests and lint** below). On GitHub, **Lint and test** must pass. If you change anything in `packaging/`, run `.\packaging\build.ps1` on Windows and say so in the PR.
5. Write a clear PR description — what changed and why. Before/after measurements (LUFS, peak, noise levels) on a test song are great for sound changes.
6. Link any related issue in the PR body (`Closes #123`).

---

## Coding Standards

- **Language:** Python 3.10+
- **Style:** Follow existing patterns in the file. Do not reformat unrelated code.
- **Naming:** `snake_case` for functions and variables, `UPPER_CASE` for constants.
- **Keep the layers apart:** audio code goes in `wavmasta/core/` and must not import Tkinter; window code goes in `wavmasta/gui/`.
- **GUI threads:** Never touch Tkinter widgets from a worker thread. Use `app.post()` from `gui/app.py`.
- **New page?** Add a module in `gui/pages/` and an entry in `PAGES`. **New workflow?** Add a journey class in `gui/journeys.py`.
- **Dependencies:** Do not add required dependencies without discussion. Optional ones must fail gracefully.
- **No dead code:** Do not leave commented-out code in PRs.

---

## Running Locally

```
git clone https://github.com/skynrlabs/WavMasta.git
cd WavMasta
pip install -e ".[dev]"
python -m wavmasta
```

---

## Tests and lint

```
ruff check .            # lint
ruff format .           # format (CI runs `ruff format --check`)
pytest                  # all tests, about 35 seconds
```

- The tests build **synthetic songs with known problems** (`tests/synth.py`): hiss, a 3,150 Hz whine, 60 Hz hum, fizzy highs. They check each fix removes its problem by a measured amount and leaves the music alone, not just that nothing crashes.
- **Window tests** (`tests/test_gui.py`) open the real app. They need a display: on Linux run `xvfb-run -a pytest`; without one they're skipped.
- Add a test with every bug fix: reproduce it with a synthetic song first.

---

## Releasing

The Windows installer is built on a Windows PC, not on GitHub (the Actions tab is public, and downloads go through itch.io). You need Python 3.11 and [Inno Setup 6](https://jrsoftware.org/isdl.php).

1. Bump `__version__` in `wavmasta/__init__.py`, and get the change into `main` through `dev`.
2. On `main`, run `.\packaging\build.ps1` in PowerShell. It builds the app, checks that it masters a test song, and writes `dist\installer\WavMasta-Setup-x.y.z.exe`.
3. Install it and give it a quick try.
4. On GitHub, go to **Releases → Draft a new release**, create the tag `v` + the version (for example `v1.0.0`), list what changed, and click **Publish release**. Don't attach the installer.
5. Upload the installer to the [itch.io page](https://skynrlabs.itch.io/wavmasta).

---

## Questions

Open a GitHub Discussion if you have a question that is not a bug or feature request.
