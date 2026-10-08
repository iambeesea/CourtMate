"""Draw the CourtMate app icons as PNG files using only the standard library.

    python3 scripts/make-icons.py

Writes public/icons/*.png. The mark is a white court outline with a net line and
a Rally Lime ball on Court Navy. Edges are anti-aliased from signed distances.
"""

import struct
import zlib
from pathlib import Path

NAVY = (0x1F, 0x3B, 0x73)
WHITE = (0xFF, 0xFF, 0xFF)
LIME = (0xE0, 0xFE, 0x2C)
OUT = Path(__file__).resolve().parent.parent / "public" / "icons"


def rounded_box(x: float, y: float, cx: float, cy: float, half_w: float, half_h: float, radius: float) -> float:
    """Signed distance from (x, y) to a rounded rectangle; negative inside."""
    dx = abs(x - cx) - (half_w - radius)
    dy = abs(y - cy) - (half_h - radius)
    outside = (max(dx, 0.0) ** 2 + max(dy, 0.0) ** 2) ** 0.5
    return outside + min(max(dx, dy), 0.0) - radius


def coverage(distance: float) -> float:
    return min(1.0, max(0.0, 0.5 - distance))


def blend(base: tuple, top: tuple, amount: float) -> tuple:
    return tuple(base[i] + (top[i] - base[i]) * amount for i in range(len(top))) + tuple(base[len(top) :])


def draw(size: int, *, rounded: bool, inset: float) -> bytes:
    """`inset` scales the mark toward the centre (maskable icons need a safe zone)."""
    unit = size / 512
    scale = unit * inset
    offset = size * (1 - inset) / 2

    def at(value: float) -> float:
        return offset + value * scale

    rows = bytearray()
    for py in range(size):
        rows.append(0)
        for px in range(size):
            x, y = px + 0.5, py + 0.5
            alpha = coverage(rounded_box(x, y, size / 2, size / 2, size / 2, size / 2, 112 * unit)) if rounded else 1.0
            colour = NAVY
            # Court outline: the band between two rounded rectangles.
            outer = rounded_box(x, y, at(256), at(261), 157 * scale, 152 * scale, 73 * scale)
            inner = rounded_box(x, y, at(256), at(261), 123 * scale, 118 * scale, 39 * scale)
            colour = blend(colour, WHITE, coverage(max(outer, -inner)))
            # Net line across the court.
            net = max(abs(y - at(231)) - 17 * scale, abs(x - at(256)) - 140 * scale)
            colour = blend(colour, WHITE, coverage(net))
            # Ball in the upper-right of the court.
            ball = ((x - at(338)) ** 2 + (y - at(178)) ** 2) ** 0.5 - 27 * scale
            colour = blend(colour, LIME, coverage(ball))
            rows.extend((round(colour[0]), round(colour[1]), round(colour[2]), round(alpha * 255)))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b"")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    targets = {
        "icon-192.png": (192, True, 1.0),
        "icon-512.png": (512, True, 1.0),
        # Maskable and Apple icons are full-bleed squares; the platform applies its own shape.
        "maskable-512.png": (512, False, 0.78),
        "apple-touch-icon.png": (180, False, 0.9),
    }
    for name, (size, rounded, inset) in targets.items():
        (OUT / name).write_bytes(draw(size, rounded=rounded, inset=inset))
        print(f"wrote {name} ({size}px)")


if __name__ == "__main__":
    main()
