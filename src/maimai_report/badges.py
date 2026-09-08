"""Sealed, local-only rating frames with optional user-owned artwork packs.

No CSS or markup is accepted from a pack. Image bytes are checked and embedded
as data URLs, while the application retains its established badge geometry.
"""

from __future__ import annotations

import base64
import re
import struct
import tempfile
import tomllib
import zlib
from importlib import resources
from pathlib import Path

from .errors import ConfigError, OutputError

TIERS = (
    "white",
    "blue",
    "green",
    "yellow",
    "red",
    "purple",
    "bronze",
    "silver",
    "gold",
    "platinum",
    "rainbow",
    "rainbow-ex",
)
MAX_IMAGE_BYTES = 512 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_IMAGE_DIMENSION = 4096
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _asset(name: str) -> str:
    return resources.files("maimai_report.assets").joinpath(name).read_text(encoding="utf-8")


def _bounded_read(path: Path, limit: int, label: str) -> bytes:
    try:
        if not path.is_file():
            raise ConfigError(f"{label} must be a readable regular file.")
        with path.open("rb") as stream:
            result = stream.read(limit + 1)
    except OSError as exc:
        raise ConfigError(f"{label} could not be read; check its path and permissions.") from exc
    if len(result) > limit:
        raise ConfigError(f"{label} exceeds the {limit // 1024} KiB size limit.")
    return result


def _png_size(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError
    offset = 8
    size = None
    pixels = False
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        kind = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError
        payload = data[offset + 8 : end - 4]
        checksum = int.from_bytes(data[end - 4 : end], "big")
        if zlib.crc32(kind + payload) != checksum:
            raise ValueError
        if kind == b"acTL":  # Animated PNG is not a static rating frame.
            raise ValueError
        if offset == 8:
            if kind != b"IHDR" or length != 13:
                raise ValueError
            size = struct.unpack(">II", payload[:8])
        elif kind == b"IHDR":
            raise ValueError
        if kind == b"IDAT":
            pixels = True
        if kind == b"IEND":
            if length or end != len(data) or not pixels or size is None:
                raise ValueError
            return size
        offset = end
    raise ValueError


def _jpeg_size(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
        raise ValueError
    offset = 2
    size = None
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            raise ValueError
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            raise ValueError
        marker = data[offset]
        offset += 1
        if marker in (0xD8, 0xD9, 0x00) or 0xD0 <= marker <= 0xD7:
            raise ValueError
        length = int.from_bytes(data[offset : offset + 2], "big")
        if length < 2 or offset + length > len(data):
            raise ValueError
        if marker == 0xDA:  # A frame header alone is not an image.
            if size is None or length < 6 or offset + length >= len(data) - 2:
                raise ValueError
            components = data[offset + 2]
            if not 1 <= components <= 4 or length != 6 + 2 * components:
                raise ValueError
            return size
        if marker in (0xC0, 0xC1, 0xC2):  # Baseline, extended sequential, progressive.
            if length < 8 or size is not None:
                raise ValueError
            height, width = struct.unpack(">HH", data[offset + 3 : offset + 7])
            components = data[offset + 7]
            if not 1 <= components <= 4 or length != 8 + 3 * components:
                raise ValueError
            size = width, height
        offset += length
    raise ValueError


def _webp_size(data: bytes) -> tuple[int, int]:
    if len(data) < 26 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError
    if int.from_bytes(data[4:8], "little") + 8 != len(data):
        raise ValueError
    offset = 12
    extended_size = None
    image_size = None
    while offset + 8 <= len(data):
        kind = data[offset : offset + 4]
        length = int.from_bytes(data[offset + 4 : offset + 8], "little")
        end = offset + 8 + length + length % 2
        if end > len(data):
            raise ValueError
        payload = data[offset + 8 : offset + 8 + length]
        if kind in (b"ANIM", b"ANMF"):
            raise ValueError
        if kind == b"VP8X":
            if offset != 12 or length != 10 or payload[0] & 0x02:
                raise ValueError
            extended_size = (
                1 + int.from_bytes(payload[4:7], "little"),
                1 + int.from_bytes(payload[7:10], "little"),
            )
        if kind in (b"VP8 ", b"VP8L"):
            if image_size is not None:
                raise ValueError
            if kind == b"VP8 " and length >= 10 and payload[3:6] == b"\x9d\x01\x2a":
                width, height = struct.unpack("<HH", payload[6:10])
                image_size = width & 0x3FFF, height & 0x3FFF
            elif kind == b"VP8L" and length >= 5 and payload[0] == 0x2F:
                packed = int.from_bytes(payload[1:5], "little")
                image_size = (packed & 0x3FFF) + 1, ((packed >> 14) & 0x3FFF) + 1
            else:
                raise ValueError
        offset = end
    if offset != len(data) or image_size is None:
        raise ValueError
    if extended_size is not None and image_size != extended_size:
        raise ValueError
    return image_size


def _image_url(path: Path, tier: str) -> str:
    mime = _MIME.get(path.suffix.lower())
    if mime is None:
        raise ConfigError(f"Badge frame '{tier}' must be a PNG, JPEG, or WebP file (not SVG).")
    data = _bounded_read(path, MAX_IMAGE_BYTES, f"Badge frame '{tier}'")
    reader = {"image/png": _png_size, "image/jpeg": _jpeg_size, "image/webp": _webp_size}[mime]
    try:
        width, height = reader(data)
    except (ValueError, IndexError, struct.error) as exc:
        raise ConfigError(f"Badge frame '{tier}' is not a valid supported static image.") from exc
    if not (0 < width <= MAX_IMAGE_DIMENSION and 0 < height <= MAX_IMAGE_DIMENSION):
        raise ConfigError(f"Badge frame '{tier}' dimensions must be between 1 and 4096 pixels.")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _frame_path(root: Path, value: object, tier: str) -> Path:
    # Only portable relative paths: no drive letters, URLs, UNC or home expansion.
    if (
        not isinstance(value, str)
        or not value
        or any(char in value for char in ("\\", ":", "\x00", "\n", "\r"))
        or value.startswith(("/", "~"))
        or ".." in value.split("/")
    ):
        raise ConfigError(
            f"Badge frame '{tier}' must use a relative local path with forward slashes."
        )
    try:
        target = (root / value).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ConfigError(
            f"Badge frame '{tier}' is missing or its path cannot be resolved."
        ) from exc
    if not target.is_relative_to(root):
        raise ConfigError(f"Badge frame '{tier}' must stay inside the artwork pack directory.")
    return target


def _custom_css(path: Path) -> str:
    try:
        manifest = path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ConfigError("Badge pack manifest was not found; provide a local TOML file.") from exc
    data = _bounded_read(manifest, MAX_MANIFEST_BYTES, "Badge pack manifest")
    try:
        pack = tomllib.loads(data.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError("Badge pack manifest must contain valid UTF-8 TOML.") from exc
    if set(pack) - {"version", "fallback", "frames"}:
        raise ConfigError("Badge pack allows only version, fallback, and [frames] settings.")
    if type(pack.get("version")) is not int or pack["version"] != 1:
        raise ConfigError("Badge pack must declare version = 1.")
    fallback = pack.get("fallback")
    if fallback is not None and fallback not in ("builtin", "plain"):
        raise ConfigError("Badge pack fallback must be 'builtin' or 'plain'.")
    frames = pack.get("frames")
    if not isinstance(frames, dict) or not frames:
        raise ConfigError("Badge pack must define at least one relative image path in [frames].")
    if set(frames) - set(TIERS):
        raise ConfigError("Badge pack [frames] contains an unknown rating tier; see the tier list.")
    missing = [tier for tier in TIERS if tier not in frames]
    if missing and fallback is None:
        raise ConfigError(
            "Badge pack is incomplete: add frames for "
            + ", ".join(missing)
            + "; or explicitly set fallback = 'builtin' or 'plain'."
        )
    css = badge_css(fallback) if fallback else ""
    for tier in TIERS:
        if tier not in frames:
            continue
        image = _image_url(_frame_path(manifest.parent, frames[tier], tier), tier)
        # Reset CSS fallback decorations only for tiers supplied by the pack.
        # All dimensions and digit positions continue to come from styles.css.
        css += (
            f'\n.tier-{tier} .rating-plaque {{ background: url("{image}") '
            "center / 100% 100% no-repeat; border: 0; border-radius: 0; "
            "box-shadow: none; overflow: visible; }\n"
            f".tier-{tier} .rating-plaque::before, .tier-{tier} .rating-plaque::after "
            "{ content: none; }\n"
            f".tier-{tier} .rating-value > span + span {{ border-left: 0; }}\n"
        )
    return css


def badge_css(pack: Path | str | None = None) -> str:
    """Return sealed CSS for built-in artwork, plain CSS, or a local TOML pack."""

    if pack is None or pack == "builtin":
        return _asset("rating-frames.css")
    if pack == "plain":
        return _asset("rating-fallback.css")
    if not isinstance(pack, (str, Path)) or not str(pack).strip():
        raise ConfigError("badge_pack must be 'builtin', 'plain', or a local TOML manifest path.")
    if str(pack).startswith(("\\\\", "//")) or re.match(r"[A-Za-z][\w+.-]*://", str(pack)):
        raise ConfigError("Badge pack must be a local TOML file, not a URL or network share.")
    return _custom_css(Path(pack))


def validate_badge_pack(pack: Path | str | None = None) -> None:
    """Validate every configured frame before any sync; never access the network."""

    badge_css(pack)


def export_badge_pack(output_dir: Path) -> Path:
    """Export all twelve built-in frames to a new directory, never overwriting it."""

    directory = Path(output_dir)
    if directory.exists() or directory.is_symlink():
        raise OutputError("Badge export directory already exists; choose a new directory.")
    images = re.findall(
        r'\.tier-([a-z-]+) \.rating-plaque \{ background-image: url\("'
        r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)"\); \}',
        badge_css(),
    )
    if tuple(tier for tier, _, _ in images) != TIERS:
        raise OutputError("Bundled badge artwork is incomplete; reinstall the application.")
    try:
        directory.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".maimai-badges-", dir=directory.parent) as work:
            staging = Path(work) / "pack"
            staging.mkdir()
            manifest = [
                "# Custom local badge artwork. Images retain their original rights notices.",
                "# Keep the 296:86 layout; rating digits are supplied by the report.",
                "version = 1",
                "",
                "[frames]",
            ]
            for tier, extension, encoded in images:
                filename = f"{tier}.{extension}"
                (staging / filename).write_bytes(base64.b64decode(encoded, validate=True))
                manifest.append(f'{tier} = "{filename}"')
            (staging / "badges.toml").write_text("\n".join(manifest) + "\n", encoding="utf-8")
            (staging / "ARTWORK_NOTICE.txt").write_text(
                _asset("rating-notice.txt"), encoding="utf-8"
            )
            validate_badge_pack(staging / "badges.toml")
            # The directory is complete before it becomes visible at the output path.
            # Never replace any existing directory, even an empty one.
            if directory.exists() or directory.is_symlink():
                raise OutputError("Badge export directory already exists; choose a new directory.")
            staging.rename(directory)
    except OSError as exc:
        raise OutputError(
            "Could not export badge artwork; check output permissions and free space."
        ) from exc
    return directory / "badges.toml"
