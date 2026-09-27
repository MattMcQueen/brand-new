"""Cuts the cover fans for design/bluesky-banner.html out of a screenshot of the live home page.

The covers change every week, so running this gives a banner with that week's covers. It needs
Pillow, which the site itself doesn't use, so install it somewhere temporary rather than in .venv:

    python -m pip install --target %TEMP%/pillow pillow
    set PYTHONPATH=%TEMP%/pillow
    python design/bluesky-banner.py

then render the banner with the Edge command at the top of bluesky-banner.html.

The positions below are for the home page's layout in September 2026 (three tiles a row, dark mode,
a 1500px-wide window). If the layout changes, open the screenshot this script leaves in your temp
folder (it prints where) and adjust them.
"""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
HOME = "https://brand-new.matt-rarely-writes.co.uk/"
OUT = Path(__file__).parent / "bluesky-banner"
SCALE = 1.5               # screenshot at 1.5x for sharper covers
TILE = (26, 32, 41)       # the tiles' background, --surface in dark mode

# Where each fan is, in page pixels: (the tile's centre, the top of its covers).
FANS = {
    "crime": (386, 500), "fantasy": (386, 822), "horror": (750, 1118),               # books
    "pop": (750, 1566), "electronic": (750, 1832), "jazz": (386, 2356),              # music
}
WIDTH, HEIGHT = 248, 136  # generous: albums are trimmed to their covers below


def differs(pixel) -> bool:
    return sum(abs(a - b) for a, b in zip(pixel[:3], TILE)) > 30


def trim_label(fan: Image.Image) -> Image.Image:
    """Album fans are shorter than book fans, so the box can reach the genre's name below them.
    Keep only the first block of rows that aren't plain tile background."""
    rows = [y for y in range(fan.height) if any(differs(fan.getpixel((x, y))) for x in range(0, fan.width, 3))]
    end = rows[0]
    for a, b in zip(rows, rows[1:]):
        if b - a > 6:  # a gap of background: the name starts after it
            break
        end = b
    return fan.crop((0, 0, fan.width, end + 8))


def main() -> None:
    OUT.mkdir(exist_ok=True)
    shot = Path(tempfile.gettempdir()) / "brand-new-home.png"
    # Edge follows Windows' light/dark setting; the banner's colours are the dark ones.
    subprocess.run([EDGE, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-dark-mode",
                    f"--force-device-scale-factor={SCALE}", "--window-size=1500,3200",
                    f"--screenshot={shot}", HOME], check=True, capture_output=True)
    print(f"Screenshot: {shot}")
    page = Image.open(shot)
    for name, (centre, top) in FANS.items():
        box = [round(v * SCALE) for v in (centre - WIDTH / 2, top - 4, centre + WIDTH / 2, top + HEIGHT)]
        trim_label(page.crop(box)).save(OUT / f"fan-{name}.png")
        print(f"{name}: {OUT / f'fan-{name}.png'}")


if __name__ == "__main__":
    main()
