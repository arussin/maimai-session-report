"""Original geometric DEMO tiles; not game artwork or real song jackets.

Small PNGs are generated with the standard library so the demo stays fully
offline and dependency-free. Only render_demo uses these fictional images.
"""

from __future__ import annotations

import base64
import struct
import zlib
from collections.abc import Mapping

_PALETTES = (
    ((24, 34, 71), (100, 213, 226), (224, 250, 248)),
    ((67, 27, 88), (242, 118, 164), (253, 221, 141)),
    ((17, 60, 77), (88, 217, 192), (209, 245, 232)),
    ((67, 34, 79), (172, 155, 245), (247, 219, 173)),
    ((72, 38, 31), (255, 164, 103), (255, 234, 182)),
    ((23, 43, 73), (111, 175, 250), (251, 193, 213)),
)
_LETTERS = ("110101101101110", "111100110100111", "101111111101101", "111101101101111")


def _tile(index: int) -> bytes:
    size = 96
    dark, accent, light = _PALETTES[index % len(_PALETTES)]
    pixels = bytearray()
    for y in range(size):
        pixels.append(0)  # PNG scanline filter: none
        for x in range(size):
            blend = (x + y) / 240
            color = tuple(round(a + (b - a) * blend) for a, b in zip(dark, accent, strict=True))
            cx, cy = 48 + (index % 3 - 1) * 9, 37
            distance = (x - cx) ** 2 + (y - cy) ** 2
            if 21**2 < distance < 26**2 or (index % 2 and abs(x + y - 78) < 3):
                color = light
            if abs(x - cx) + abs(y - cy) < 16:
                color = accent
            if 76 <= y < 91:
                color = dark
                letter, column = divmod((x - 23) // 3, 4)
                row = (y - 76) // 3
                if 0 <= letter < 4 and column < 3 and _LETTERS[letter][row * 3 + column] == "1":
                    color = light
            pixels.extend(color)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(pixels), level=9))
        + chunk(b"IEND", b"")
    )


def demo_jackets(after_payload: Mapping) -> dict[str, str]:
    """Allow only bundled synthetic song IDs; never inspect or fetch player art."""
    songs = after_payload["body"]["songs"]
    tiles = [
        "data:image/png;base64," + base64.b64encode(_tile(index)).decode() for index in range(12)
    ]
    result = {}
    for index, song in enumerate(songs):
        song_id = song["id"]
        if not song_id.startswith("synthetic-song-"):
            raise ValueError("Demo tiles may only be attached to synthetic fixture songs")
        result[song_id] = tiles[index % len(tiles)]
    return result
