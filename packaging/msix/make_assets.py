"""Make the MSIX icons (Start menu, taskbar, tiles, Store logo) from the app's 256 px icon.

    python packaging/msix/make_assets.py wavmasta/assets/icon.png dist/msix/root/Assets

The taskbar and Start list use the Square44x44Logo "targetsize" images; the "altform-unplated"
versions stop Windows drawing a coloured square behind the icon.
"""

import os
import sys

from PIL import Image


def fit(icon, size, box):
    """The icon scaled to `box` pixels, centred on a transparent canvas of `size` (w, h)."""
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    art = icon.resize((box, box), Image.LANCZOS)
    canvas.alpha_composite(art, ((size[0] - box) // 2, (size[1] - box) // 2))
    return canvas


def main(src, out):
    os.makedirs(out, exist_ok=True)
    icon = Image.open(src).convert("RGBA")
    files = {
        "StoreLogo.png": fit(icon, (50, 50), 50),
        "Square44x44Logo.png": fit(icon, (44, 44), 44),
        "Square150x150Logo.png": fit(icon, (150, 150), 100),
        "Wide310x150Logo.png": fit(icon, (310, 150), 100),
    }
    for t in (16, 20, 24, 30, 32, 36, 40, 44, 48, 60, 64, 72, 80, 96, 256):
        img = fit(icon, (t, t), t)
        files[f"Square44x44Logo.targetsize-{t}.png"] = img
        files[f"Square44x44Logo.targetsize-{t}_altform-unplated.png"] = img
        files[f"Square44x44Logo.targetsize-{t}_altform-lightunplated.png"] = img
    for name, img in files.items():
        img.save(os.path.join(out, name))
    print(f"{len(files)} icons in {out}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
