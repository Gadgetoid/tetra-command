#!/usr/bin/env python3
"""Draw the app's mark and pack it into an .icns.

Four squircles for the tetra, in a neon tetra's colours: the blue pair is the
dorsal stripe, split into two tints so the gap reads as one iridescent line, and
the silver and scarlet below are the belly and the tail stripe.

No dependencies. A superellipse has an exact half-width per row, so the shapes
are solved a row at a time rather than sampled, and shot.py already writes a PNG
out of zlib. iconutil packs the result.

    make_icon.py [icon.icns]
"""

import shutil
import subprocess
import sys
import tempfile
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shot import png  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "icon.icns"

# Apple draws a macOS icon's body in 824 of a 1024 canvas, so one that fills the
# canvas sits visibly larger than everything beside it in the Dock.
CANVAS = 1024
BODY = 824

# The exponent of |x/a|^n + |y/b|^n = 1: two is an ellipse, higher is squarer.
# Five is about Apple's corner. The chips take more, since a superellipse's corner
# scales with its own size and four at the plate's exponent read as blobs.
PLATE_N = 5.0
CHIP_N = 7.0
# Sub-rows per pixel row. The row extent is exact, so this is the only sampling.
SUBS = 4

MARGIN = 0.145                    # of the body, around the block of four
GAP = 0.075                       # of the body, between them

# Apple's template drops a soft shadow under the body. Three box passes of
# radius r stand in for a Gaussian of sigma sqrt(r*r + r), near enough r, and
# reach 3r from the edge. That reach plus the drop is what the 100px the body
# leaves inside the canvas has to cover.
SHADOW_BLUR = 14
SHADOW_DROP = 14
SHADOW_ALPHA = 0.32
SHADOW_PASSES = 3

PLATE = (10, 18, 34)
BLUE_LIT = (64, 214, 255)
BLUE_DEEP = (0, 150, 226)
SILVER = (206, 216, 232)
SCARLET = (226, 42, 52)

# Top left, top right, bottom left, bottom right.
CHIPS = (BLUE_LIT, BLUE_DEEP, SILVER, SCARLET)

# What an .icns holds, each also at @2x. Every one divides the canvas.
ICONSET = (16, 32, 128, 256, 512)


def coverage(size, n, subs=SUBS):
    """How much of each pixel a superellipse filling `size` covers, row major."""
    cov = [0.0] * (size * size)
    half = size / 2.0
    share = 1.0 / subs
    for row in range(size):
        base = row * size
        for sub in range(subs):
            y = row + (sub + 0.5) * share - half
            spare = 1.0 - abs(y / half) ** n
            if spare <= 0.0:
                continue
            reach = half * spare ** (1.0 / n)
            left, right = half - reach, half + reach
            first, last = int(left), min(int(right), size - 1)
            if first == last:
                cov[base + first] += (right - left) * share
                continue
            cov[base + first] += (first + 1 - left) * share
            for column in range(first + 1, last):
                cov[base + column] += share
            cov[base + last] += (right - last) * share
    return cov


def rows_blurred(src, size, radius):
    """Box blur each row, edges clamped, with a running sum."""
    out = array("f", bytes(4 * size * size))
    span = radius * 2 + 1
    last = size - 1
    for row in range(size):
        base = row * size
        total = src[base] * radius
        for x in range(radius + 1):
            total += src[base + x if x <= last else base + last]
        for x in range(size):
            out[base + x] = total / span
            total -= src[base + (x - radius if x > radius else 0)]
            ahead = x + radius + 1
            total += src[base + (ahead if ahead <= last else last)]
    return out


def transposed(src, size):
    out = array("f", bytes(4 * size * size))
    for row in range(size):
        base = row * size
        for column in range(size):
            out[column * size + row] = src[base + column]
    return out


def blurred(mask, size, radius, passes=SHADOW_PASSES):
    """Blur a float mask on both axes, all of one axis before transposing."""
    if radius < 1:
        return mask
    for _ in range(passes):
        mask = rows_blurred(mask, size, radius)
    mask = transposed(mask, size)
    for _ in range(passes):
        mask = rows_blurred(mask, size, radius)
    return transposed(mask, size)


def shadow_mask(plate, size, at):
    """The plate's coverage, dropped and blurred, over the whole canvas."""
    mask = array("f", bytes(4 * CANVAS * CANVAS))
    left, top = at
    for row in range(size):
        source = row * size
        target = (top + row) * CANVAS + left
        for column in range(size):
            mask[target + column] = plate[source + column]
    return blurred(mask, CANVAS, SHADOW_BLUR)


def blend(canvas, size, mask, mask_size, colour, at):
    """Composite a coverage mask in one colour over `canvas`, source-over."""
    red, green, blue = colour
    left, top = at
    for row in range(mask_size):
        target = ((top + row) * size + left) * 4
        source = row * mask_size
        for column in range(mask_size):
            alpha = mask[source + column]
            if alpha <= 0.0:
                continue
            if alpha > 1.0:
                alpha = 1.0
            index = target + column * 4
            keep = 1.0 - alpha
            canvas[index] = int(red * alpha + canvas[index] * keep + 0.5)
            canvas[index + 1] = int(green * alpha + canvas[index + 1] * keep + 0.5)
            canvas[index + 2] = int(blue * alpha + canvas[index + 2] * keep + 0.5)
            canvas[index + 3] = int(255 * alpha + canvas[index + 3] * keep + 0.5)


def mark():
    """The mark at CANVAS, as RGBA bytes."""
    canvas = bytearray(CANVAS * CANVAS * 4)
    inset = (CANVAS - BODY) // 2
    plate = coverage(BODY, PLATE_N)

    shadow = shadow_mask(plate, BODY, (inset, inset + SHADOW_DROP))
    for index in range(CANVAS * CANVAS):
        alpha = shadow[index] * SHADOW_ALPHA
        if alpha > 0.0:
            canvas[index * 4 + 3] = int(255 * alpha + 0.5)

    blend(canvas, CANVAS, plate, BODY, PLATE, (inset, inset))

    margin = round(BODY * MARGIN)
    gap = round(BODY * GAP)
    chip = (BODY - 2 * margin - gap) // 2
    mask = coverage(chip, CHIP_N)
    for index, colour in enumerate(CHIPS):
        left = inset + margin + (index % 2) * (chip + gap)
        top = inset + margin + (index // 2) * (chip + gap)
        blend(canvas, CANVAS, mask, chip, colour, (left, top))
    return canvas


def reduce(canvas, size, to):
    """Box filter the canvas down by an integer factor, on premultiplied alpha."""
    step = size // to
    out = bytearray(to * to * 4)
    count = step * step
    for row in range(to):
        for column in range(to):
            red = green = blue = alpha = 0
            for dy in range(step):
                source = ((row * step + dy) * size + column * step) * 4
                for dx in range(step):
                    at = source + dx * 4
                    a = canvas[at + 3]
                    red += canvas[at] * a
                    green += canvas[at + 1] * a
                    blue += canvas[at + 2] * a
                    alpha += a
            index = (row * to + column) * 4
            if alpha:
                out[index] = red // alpha
                out[index + 1] = green // alpha
                out[index + 2] = blue // alpha
            out[index + 3] = alpha // count
    return out


def main():
    if not shutil.which("iconutil"):
        print("iconutil not found; this needs macOS", file=sys.stderr)
        return 1

    canvas = mark()
    with tempfile.TemporaryDirectory() as work:
        iconset = Path(work) / "icon.iconset"
        iconset.mkdir()
        for size in ICONSET:
            for scale in (1, 2):
                px = size * scale
                suffix = "@2x" if scale == 2 else ""
                target = iconset / f"icon_{size}x{size}{suffix}.png"
                png(canvas if px == CANVAS else reduce(canvas, CANVAS, px),
                    px, px, target)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(OUT)],
                       check=True)
    print(f"wrote {OUT.relative_to(ROOT) if OUT.is_relative_to(ROOT) else OUT}, "
          f"{OUT.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
