"""Start WavMasta: `python -m wavmasta` opens the window; add file names to use the command line."""

import importlib.util
import os
import sys


def _check_libraries():
    for name in ("numpy", "scipy", "pedalboard"):
        if importlib.util.find_spec(name) is None:
            print(f"Missing library: {name}. Run:  pip install -e .  (from the WavMasta folder)")
            sys.exit(1)


def _prepare_environment():
    """Make a packaged (double-clicked) copy behave like a normal one."""
    if sys.stdout is None:  # windowed app: no console to print to
        sys.stdout = open(os.devnull, "w")  # noqa: SIM115 - stays open for the life of the app
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")  # noqa: SIM115


def main():
    _prepare_environment()
    _check_libraries()
    if len(sys.argv) > 1:
        from .cli import main as cli_main

        sys.exit(cli_main())
    else:
        from .gui import run_gui

        run_gui()


if __name__ == "__main__":
    main()
