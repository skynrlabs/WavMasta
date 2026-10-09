## What this changes

<!-- What does this PR do, and why? Link the issue it fixes, e.g. "Fixes #12". -->

## How it was tested

<!-- What you ran or clicked to check it works. For changes to the sound, say what you listened to. -->

## Checklist

- [ ] The PR targets `dev`, not `main`
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `pytest` passes (on Linux, `xvfb-run -a pytest` runs the window tests too)
- [ ] A bug fix comes with a test that reproduces it (see `tests/synth.py` for test songs)
- [ ] Window changes: I checked the layout still fits and nothing is cut off
- [ ] The README and Help page are updated if what users see changed
