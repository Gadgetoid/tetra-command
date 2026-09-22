#!/usr/bin/env python3
"""Turn a raw framebuffer dump into a PNG, so a page can be looked at.

picovector has no encoder and the panel cannot be screenshotted from here, so
the app writes host.framebuffer() straight out and this wraps it. zlib is in the
standard library; nothing else is needed.

    shot.py dump.raw 1280 800 page.png
"""

import struct
import sys
import zlib
from pathlib import Path


def png(raw, width, height, out):
    stride = width * 4
    rows = bytearray()
    for y in range(height):
        rows.append(0)                      # filter: none
        rows += raw[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    out.write_bytes(b"\x89PNG\r\n\x1a\n"
                    + chunk(b"IHDR", header)
                    + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
                    + chunk(b"IEND", b""))


if __name__ == "__main__":
    source, width, height, target = sys.argv[1:5]
    raw = Path(source).read_bytes()
    width, height = int(width), int(height)
    want = width * height * 4
    if len(raw) < want:
        raise SystemExit(f"{source}: {len(raw)} bytes, want {want}")
    png(raw, width, height, Path(target))
    print(f"{target} ({width}x{height})")
