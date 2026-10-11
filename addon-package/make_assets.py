"""Generate the required icon sizes from one square source image.

pip install -e ".[assets]"
python addon-package/make_assets.py addon-package/images/source.png
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ICON_SIZES = (72, 64, 88, 126, 180, 241)


def main(source: str) -> None:
    out = Path(__file__).parent / "images"
    out.mkdir(exist_ok=True)
    img = Image.open(source).convert("RGBA")
    for size in ICON_SIZES:
        img.resize((size, size), Image.LANCZOS).save(out / f"icon-{size}.png")
    # TODO: 600x900 carousel image and optional 1200x600 banner (need design input).


if __name__ == "__main__":
    main(sys.argv[1])
