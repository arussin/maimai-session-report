from __future__ import annotations

import base64
import hashlib
import re
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from maimai_report.badges import (
    MAX_IMAGE_BYTES,
    MAX_MANIFEST_BYTES,
    TIERS,
    _frame_path,
    _image_url,
    _jpeg_size,
    _webp_size,
    badge_css,
    export_badge_pack,
    validate_badge_pack,
)
from maimai_report.errors import ConfigError, OutputError


def png(width: int = 4, height: int = 2) -> bytes:
    """Construct tiny, synthetic RGBA image bytes without image dependencies."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload))
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress((b"\x00" + b"\x60\xd4\xf0\xff" * width) * height))
        + chunk(b"IEND", b"")
    )


class BundledBadgeTests(unittest.TestCase):
    def test_original_all_twelve_distinct_frames_are_embedded(self) -> None:
        css = badge_css()
        frames = re.findall(r"\.tier-([a-z-]+).*?base64,([A-Za-z0-9+/=]+)", css)
        self.assertEqual(tuple(tier for tier, _ in frames), TIERS)
        self.assertEqual(len({image for _, image in frames}), 12)
        for tier, image in frames:
            data = base64.b64decode(image, validate=True)
            self.assertEqual(_webp_size(data), (296, 86), tier)
        self.assertEqual(
            hashlib.sha256(base64.b64decode(frames[-1][1])).hexdigest(),
            "48491ddf896f057b5e25516734828690087816f79f9228d049caf36169c149f7",
        )

    def test_original_and_plain_are_deterministic_local_only(self) -> None:
        with patch("socket.socket", side_effect=AssertionError("unexpected network")):
            for pack in (None, "builtin", "plain"):
                validate_badge_pack(pack)
                self.assertEqual(badge_css(pack), badge_css(pack))
                self.assertNotRegex(badge_css(pack), r"(?i)https?://")
                self.assertNotIn("</style", badge_css(pack))
        self.assertEqual(badge_css(), badge_css("builtin"))
        self.assertIn("data:image/webp;base64,", badge_css())
        self.assertNotIn("data:image", badge_css("plain"))

    def test_invalid_pack_values_fail_clearly(self) -> None:
        for value in ("", " ", True, [], "https://example.invalid/pack.toml", "//host/share"):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                validate_badge_pack(value)


class CustomBadgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.manifest = self.root / "badges.toml"
        self.picture = self.root / "frame.png"
        self.picture.write_bytes(png())

    def pack(
        self, settings: str = 'fallback = "plain"', frames: str = 'gold = "frame.png"'
    ) -> Path:
        self.manifest.write_text(f"version = 1\n{settings}\n[frames]\n{frames}\n", encoding="utf-8")
        return self.manifest

    def test_complete_custom_pack_needs_no_fallback(self) -> None:
        self.pack(settings="", frames="\n".join(f'{tier} = "frame.png"' for tier in TIERS))
        with patch("socket.socket", side_effect=AssertionError("unexpected network")):
            css = badge_css(self.manifest)
            validate_badge_pack(self.manifest)
        self.assertEqual(css.count("data:image/png;base64,"), 12)
        self.assertNotIn("data:image/webp", css)
        self.assertEqual(css, badge_css(self.manifest))

    def test_partial_pack_requires_explicit_fallback(self) -> None:
        with self.assertRaisesRegex(ConfigError, "incomplete.*white.*rainbow-ex"):
            badge_css(self.pack(settings=""))
        plain = badge_css(self.pack())
        self.assertTrue(plain.startswith(badge_css("plain")))
        self.assertIn(".tier-gold .rating-plaque::before", plain)
        builtin = badge_css(self.pack(settings='fallback = "builtin"'))
        self.assertTrue(builtin.startswith(badge_css()))
        self.assertEqual(builtin.count("data:image/png;base64,"), 1)

    def test_manifest_has_strict_version_tiers_and_settings(self) -> None:
        for document in (
            "version = 2\n[frames]\ngold = 'frame.png'",
            "version = true\n[frames]\ngold = 'frame.png'",
            "version = 1\nfallback = 'remote'\n[frames]\ngold = 'frame.png'",
            "version = 1\nfallback = 'plain'\ncss = '</style>'\n[frames]\ngold = 'frame.png'",
            "version = 1\nfallback = 'plain'\n[frames]\nunknown = 'frame.png'",
            "version = 1\nfallback = 'plain'\n[frames]",
            "version = 1\nfallback = 'plain'\nframes = []",
            "version = 1\nfallback = 'plain'\n[frames]\ngold = 10",
            "[unclosed",
        ):
            with self.subTest(document=document):
                self.manifest.write_text(document, encoding="utf-8")
                with self.assertRaises(ConfigError):
                    validate_badge_pack(self.manifest)

    def test_manifest_limits_and_missing_file(self) -> None:
        with self.assertRaisesRegex(ConfigError, "not found"):
            validate_badge_pack(self.manifest)
        self.manifest.write_bytes(b"#" * (MAX_MANIFEST_BYTES + 1))
        with self.assertRaisesRegex(ConfigError, "size limit"):
            validate_badge_pack(self.manifest)
        self.manifest.write_bytes(b"\xff")
        with self.assertRaisesRegex(ConfigError, "UTF-8 TOML"):
            validate_badge_pack(self.manifest)

    def test_remote_absolute_parent_and_windows_paths_rejected(self) -> None:
        for name in (
            "https://example.invalid/a.png",
            "data:image/png;base64,AA==",
            "/absolute/frame.png",
            "../frame.png",
            "sub/../../frame.png",
            "C:/frame.png",
            "C:\\frame.png",
            "\\\\server\\frame.png",
            "~/.config/frame.png",
        ):
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(ConfigError, "relative local path"),
            ):
                self.pack(frames=f"gold = '{name}'")
                validate_badge_pack(self.manifest)

    def test_nested_image_and_unusual_filename_cannot_inject_css(self) -> None:
        folder = self.root / "nested"
        folder.mkdir()
        (folder / "quoted'; Japanese_日本.png").write_bytes(png())
        self.pack(frames='gold = "nested/quoted\'; Japanese_日本.png"')
        css = badge_css(self.manifest)
        self.assertNotIn("Japanese", css)
        self.assertNotIn("quoted", css)
        self.assertNotIn("</style", css)
        self.assertIn("data:image/png;base64,", css)

    def test_symlink_cannot_escape_pack_directory(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "outside.png"
            target.write_bytes(png())
            try:
                (self.root / "escape.png").symlink_to(target)
            except OSError:
                self.skipTest("Creating symlinks requires unavailable platform privileges")
            with self.assertRaisesRegex(ConfigError, "inside the artwork pack"):
                badge_css(self.pack(frames='gold = "escape.png"'))

    def test_resolved_target_containment_is_enforced_on_every_platform(self) -> None:
        # Also exercises the security decision on Windows without symlink privileges.
        outside = self.root.parent / "outside.png"
        with patch.object(Path, "resolve", return_value=outside):
            with self.assertRaisesRegex(ConfigError, "inside the artwork pack"):
                _frame_path(self.root, "frame.png", "gold")

    def test_unsupported_or_invalid_images_are_rejected(self) -> None:
        for name, data in (
            ("frame.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
            ("fake.png", b"<script>alert(1)</script>"),
            ("fake.jpg", png()),
            ("fake.webp", b"RIFF" + bytes(50)),
            ("truncated.png", png()[:-1]),
            ("appended.png", png() + b"</style>"),
        ):
            with self.subTest(name=name):
                (self.root / name).write_bytes(data)
                with self.assertRaises(ConfigError):
                    badge_css(self.pack(frames=f'gold = "{name}"'))
        self.picture.write_bytes(b"x" * (MAX_IMAGE_BYTES + 1))
        with self.assertRaisesRegex(ConfigError, "size limit"):
            badge_css(self.pack())

    def test_oversize_and_zero_dimensions_are_rejected(self) -> None:
        for width, height in ((4097, 1), (1, 4097), (0, 1)):
            self.picture.write_bytes(png(width, height))
            with self.assertRaisesRegex(ConfigError, "dimensions"):
                badge_css(self.pack())

    def test_missing_image_directory_and_corrupt_png_crc(self) -> None:
        with self.assertRaisesRegex(ConfigError, "missing"):
            badge_css(self.pack(frames='gold = "missing.png"'))
        damaged = bytearray(png())
        damaged[20] ^= 1
        self.picture.write_bytes(damaged)
        with self.assertRaisesRegex(ConfigError, "valid supported"):
            badge_css(self.pack())
        folder = self.root / "folder.png"
        folder.mkdir()
        with self.assertRaisesRegex(ConfigError, "regular file"):
            badge_css(self.pack(frames='gold = "folder.png"'))

    def test_jpeg_header_dimensions_are_read_without_dependencies(self) -> None:
        # Synthetic 2x1 solid-aqua JPEG; tests do not depend on an image library.
        data = base64.b64decode(
            "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwg"
            "JC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIy"
            "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAIDASIAAhEBAxEB/8QA"
            "FQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAA"
            "AAAABQb/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwC1APIp/9k="
        )
        self.assertEqual(_jpeg_size(data), (2, 1))
        (self.root / "frame.jpg").write_bytes(data)
        self.assertTrue(_image_url(self.root / "frame.jpg", "gold").startswith("data:image/jpeg;"))
        for bad in (
            b"",
            b"\xff\xd8\xff\xda\x00\x08" + bytes(8) + b"\xff\xd9",
            data[:-2],
            b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x56\x01\x28\x01\x01\x11\x00\xff\xd9",
        ):
            with self.assertRaises(ValueError):
                _jpeg_size(bad)

    def test_webp_truncation_animation_and_oversized_chunks_are_rejected(self) -> None:
        original = base64.b64decode(re.search(r"base64,([A-Za-z0-9+/=]+)", badge_css())[1])
        for invalid in (original[:-1], original + b"x", b"RIFF" + bytes(26)):
            with self.assertRaises(ValueError):
                _webp_size(invalid)
        payload = b"VP8X" + struct.pack("<I", 10) + b"\x02" + bytes(9)
        data = b"RIFF" + struct.pack("<I", len(payload) + 4) + b"WEBP" + payload
        with self.assertRaises(ValueError):
            _webp_size(data)


class BadgeExportTests(unittest.TestCase):
    def test_export_complete_pack_roundtrips_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            with patch("socket.socket", side_effect=AssertionError("unexpected network")):
                manifest = export_badge_pack(root / "one")
                validate_badge_pack(manifest)
                second = export_badge_pack(root / "two")
            self.assertEqual(len(list(manifest.parent.glob("*.webp"))), 12)
            self.assertEqual(manifest.read_bytes(), second.read_bytes())
            self.assertEqual(badge_css(manifest), badge_css(second))
            self.assertIn("SEGA", (manifest.parent / "ARTWORK_NOTICE.txt").read_text())
            original = re.findall(r"data:image/webp;base64,([A-Za-z0-9+/=]+)", badge_css())
            exported = re.findall(r"data:image/webp;base64,([A-Za-z0-9+/=]+)", badge_css(manifest))
            self.assertEqual(exported, original)

    def test_export_refuses_any_existing_directory_or_file(self) -> None:
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            for name, contents in (("empty", None), ("existing", b"keep")):
                destination = root / name
                if contents is None:
                    destination.mkdir()
                else:
                    destination.write_bytes(contents)
                with self.assertRaisesRegex(OutputError, "already exists"):
                    export_badge_pack(destination)
                if contents is not None:
                    self.assertEqual(destination.read_bytes(), contents)
            result = export_badge_pack(root / "pack")
            before = result.read_bytes()
            with self.assertRaisesRegex(OutputError, "already exists"):
                export_badge_pack(result.parent)
            self.assertEqual(result.read_bytes(), before)

    def test_failed_export_does_not_leave_partial_destination(self) -> None:
        with tempfile.TemporaryDirectory() as work:
            destination = Path(work) / "pack"
            with patch("pathlib.Path.write_bytes", side_effect=OSError("simulated full disk")):
                with self.assertRaisesRegex(OutputError, "output permissions"):
                    export_badge_pack(destination)
            self.assertFalse(destination.exists())
            self.assertEqual(list(Path(work).iterdir()), [])
