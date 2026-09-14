# -*- coding: utf-8 -*-
"""
One-time asset pass: trim the uniform border around each partner logo.

Source logos are screenshots with wildly different internal padding, so they
render at inconsistent sizes in a fixed-size chip. Trimming the surrounding
flat colour and re-saving on a transparent-safe white canvas makes them
optically consistent. Re-run after adding a new partner logo.

    .venv/bin/python tools/trim_logos.py
"""
import os
import sys

from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO_DIR = os.path.join(os.path.dirname(HERE), "public", "assets", "partners")
PAD = 10          # breathing room left around the trimmed mark
TOLERANCE = 18    # how far from the corner colour still counts as background


def trim(path):
    image = Image.open(path).convert("RGB")
    before = image.size

    # Background colour taken from the corners (logos are centred on a flat field).
    corners = [image.getpixel((0, 0)), image.getpixel((image.width - 1, 0)),
               image.getpixel((0, image.height - 1)),
               image.getpixel((image.width - 1, image.height - 1))]
    background = max(set(corners), key=corners.count)

    canvas = Image.new("RGB", image.size, background)
    diff = ImageChops.difference(image, canvas).convert("L")
    mask = diff.point(lambda p: 255 if p > TOLERANCE else 0)
    box = mask.getbbox()
    if not box:
        return before, before, background

    left = max(0, box[0] - PAD)
    top = max(0, box[1] - PAD)
    right = min(image.width, box[2] + PAD)
    bottom = min(image.height, box[3] + PAD)
    cropped = image.crop((left, top, right, bottom))

    # Cap the long edge so the files stay small; quality 88 is plenty for a logo chip.
    if max(cropped.size) > 900:
        ratio = 900.0 / max(cropped.size)
        cropped = cropped.resize((int(cropped.width * ratio), int(cropped.height * ratio)),
                                 Image.LANCZOS)
    cropped.save(path, "JPEG", quality=88, optimize=True)
    return before, cropped.size, background


def main():
    if not os.path.isdir(LOGO_DIR):
        print("no logo directory at %s" % LOGO_DIR)
        return 1
    for name in sorted(os.listdir(LOGO_DIR)):
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        path = os.path.join(LOGO_DIR, name)
        before, after, background = trim(path)
        print("  %-20s %sx%s -> %sx%s   bg=%s  %d KB" % (
            name, before[0], before[1], after[0], after[1], background,
            os.path.getsize(path) // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
