from __future__ import annotations

import base64
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from maimai_report import cli
from maimai_report.artwork import (
    CATALOGUE_URL,
    JACKET_BASE,
    ArtworkUnavailable,
    _download,
    _NoRedirect,
    _thumbnail,
    match_catalogue,
    prepare_jackets,
    report_songs,
)
from maimai_report.fixtures import load_scenario

try:
    from PIL import Image
except ImportError:
    Image = None


class CatalogueTests(unittest.TestCase):
    def test_exact_normalized_title_and_artist_with_unique_filename(self) -> None:
        songs = {"a": ("Ａ  Song", "Composer"), "b": ("A Song", "Another Artist")}
        catalogue = [{"title": "a song", "artist": "composer", "image_url": "abc.png"}]
        self.assertEqual(match_catalogue(songs, catalogue), {"a": "abc.png"})
        catalogue.append({**catalogue[0], "image_url": "different.png"})
        self.assertEqual(match_catalogue(songs, catalogue), {})

    def test_source_paths_and_redirects_are_rejected_before_any_request(self) -> None:
        for filename in ("../x.png", "x.png?token=x", "https://example.com/x.png", "x.svg"):
            row = {"title": "Song", "artist": "Artist", "image_url": filename}
            self.assertEqual(match_catalogue({"a": ("Song", "Artist")}, [row]), {})
            with patch("urllib.request.build_opener") as opener:
                with self.assertRaises(ArtworkUnavailable):
                    _download(JACKET_BASE + filename)
                opener.assert_not_called()
        with self.assertRaises(ArtworkUnavailable):
            _NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com")

    def test_song_collection_omits_conflicting_ids_and_missing_identity(self) -> None:
        good = {"songID": "a", "title": "Song", "artist": "Artist"}
        report = {"after": {"old35": [good, None, {"title": "Unknown"}]}}
        self.assertEqual(report_songs(report), {"a": ("Song", "Artist")})
        report["session"] = {"scores": [{**good, "title": "Different"}]}
        self.assertEqual(report_songs(report), {})

    def test_default_local_render_never_prepares_artwork_or_syncs(self) -> None:
        report, payload = load_scenario("complete")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input.json").write_text(json.dumps(report))
            (root / "pbs.json").write_text(json.dumps(payload))
            args = cli.build_parser().parse_args(
                [
                    "render",
                    "--config",
                    str(root / "absent.toml"),
                    "--report-input",
                    str(root / "input.json"),
                    "--after-pbs",
                    str(root / "pbs.json"),
                    "--output",
                    str(root / "report.html"),
                ]
            )
            with (
                patch("maimai_report.cli.prepare_jackets") as prepare,
                patch("maimai_report.cli.synchronize") as sync,
                patch("maimai_report.cli.KamaitachiClient") as client,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(cli.run(args, environ={}), 0)
            prepare.assert_not_called()
            sync.assert_not_called()
            client.assert_not_called()
            self.assertTrue((root / "report.html").is_file())


@unittest.skipIf(Image is None, "Optional artwork extra is not installed")
class ArtworkPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report = {
            "after": {
                "old35": [
                    {"songID": "synthetic-a", "title": "Synthetic Song", "artist": "Test Artist"}
                ]
            }
        }
        self.catalogue = [
            {"title": "Synthetic Song", "artist": "Test Artist", "image_url": "test.png"}
        ]
        output = io.BytesIO()
        Image.new("RGB", (224, 224), "aqua").save(output, format="PNG")
        self.png = output.getvalue()

    def test_preparation_cache_offline_reuse_and_pixel_decode(self) -> None:
        fetch = Mock(
            side_effect=lambda url: (
                json.dumps(self.catalogue).encode() if url == CATALOGUE_URL else self.png
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            first = prepare_jackets(self.report, Path(directory), fetch=fetch)
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(first.requested, 1)
            self.assertEqual(first.matched, 1)
            data = first.jackets["synthetic-a"].split(",", 1)[1]
            with Image.open(io.BytesIO(base64.b64decode(data))) as image:
                self.assertEqual(image.size, (112, 112))
                self.assertEqual(image.format, "WEBP")
            offline_fetch = Mock(side_effect=AssertionError("Offline request"))
            again = prepare_jackets(self.report, Path(directory), offline=True, fetch=offline_fetch)
            self.assertEqual(first.jackets, again.jackets)
            self.assertEqual(first.provenance, again.provenance)
            offline_fetch.assert_not_called()

    def test_unavailable_sources_keep_renderable_placeholder_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            failed = Mock(side_effect=OSError("Unavailable"))
            missing = prepare_jackets(self.report, root, fetch=failed)
            self.assertEqual(missing.jackets, {})
            self.assertTrue(missing.warnings)
            (root / "catalogue.json").write_text(json.dumps(self.catalogue))
            (root / "test.png").write_bytes(self.png)
            cached = prepare_jackets(self.report, root, fetch=failed)
            self.assertIn("synthetic-a", cached.jackets)
            self.assertTrue(cached.warnings)
            (root / "test.png").write_bytes(b"<html>not an image</html>")
            invalid = prepare_jackets(self.report, root, offline=True, fetch=failed)
            self.assertEqual(invalid.jackets, {})

    def test_decode_limits_and_unsupported_format_fail_safely(self) -> None:
        with patch.object(Image, "MAX_IMAGE_PIXELS", 100):
            with self.assertRaises(ArtworkUnavailable):
                _thumbnail(self.png)
        gif = io.BytesIO()
        Image.new("RGB", (1, 1)).save(gif, format="GIF")
        with self.assertRaises(ArtworkUnavailable):
            _thumbnail(gif.getvalue())

    def test_offline_cli_prepares_from_retained_inputs_without_import(self) -> None:
        report, payload = load_scenario("complete")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input.json").write_text(json.dumps(report))
            (root / "pbs.json").write_text(json.dumps(payload))
            args = cli.build_parser().parse_args(
                [
                    "prepare-jackets",
                    "--config",
                    str(root / "absent.toml"),
                    "--report-input",
                    str(root / "input.json"),
                    "--after-pbs",
                    str(root / "pbs.json"),
                    "--output",
                    str(root / "jackets.json"),
                    "--jacket-cache",
                    str(root / "cache"),
                    "--offline-artwork",
                ]
            )
            with (
                patch("maimai_report.cli.synchronize") as sync,
                patch("maimai_report.cli.KamaitachiClient") as client,
                patch("urllib.request.build_opener") as opener,
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(cli.run(args, environ={}), 0)
            sync.assert_not_called()
            client.assert_not_called()
            opener.assert_not_called()
            self.assertEqual(json.loads((root / "jackets.json").read_text()), {})


if __name__ == "__main__":
    unittest.main()
