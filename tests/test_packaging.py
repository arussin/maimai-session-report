from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


def _load_backend():
    path = Path("build_backend", "maimai_build_backend.py").resolve()
    spec = importlib.util.spec_from_file_location("maimai_build_backend_test", path)
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load the local build backend")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackagingTests(unittest.TestCase):
    def test_wheel_order_is_independent_of_entry_insertion(self) -> None:
        backend = _load_backend()
        entries = {
            "maimai_report/_party/LICENSE": b"license\n",
            "maimai_report/_party/PROVENANCE.json": b"{}\n",
            "maimai_report/_party/__init__.py": b"",
            "maimai_report/_party/player_data.py": b"data = None\n",
        }
        record_name = f"{backend.DIST_INFO}/RECORD"
        wheels = []
        with tempfile.TemporaryDirectory() as directory:
            for index, names in enumerate((list(entries), list(reversed(entries)))):
                with self.subTest(order=names):
                    supplied = {name: entries[name] for name in names}
                    with mock.patch.object(backend, "_wheel_entries", return_value=supplied):
                        target = Path(directory, str(index))
                        wheel = target / backend.build_wheel(str(target))
                    wheels.append(wheel.read_bytes())
                    with zipfile.ZipFile(wheel) as archive:
                        self.assertEqual(archive.namelist(), sorted([*entries, record_name]))
                        rows = list(csv.reader(io.StringIO(archive.read(record_name).decode())))
                        self.assertEqual([row[0] for row in rows[:-1]], sorted(entries))
                        self.assertEqual(rows[-1], [record_name, "", ""])
        self.assertEqual(wheels[0], wheels[1])

    def test_wheel_party_files_match_canonical_provenance(self) -> None:
        backend = _load_backend()
        with tempfile.TemporaryDirectory() as directory:
            wheel_name = backend.build_wheel(directory)
            with zipfile.ZipFile(Path(directory, wheel_name)) as archive:
                provenance = json.loads(archive.read("maimai_report/_party/PROVENANCE.json"))
                self.assertEqual(provenance["canonical_text"], "UTF-8 with LF line endings")
                self.assertRegex(provenance["upstream_revision"], r"^[a-f0-9]{40}$")
                paths = {
                    "player_data.py": "_party/player_data.py",
                    "public_matching.py": "_party/public_matching.py",
                    "site-brand.html": "assets/party-site-brand.html",
                    "site-brand.css": "assets/party-site-brand.css",
                }
                self.assertEqual(set(provenance["files"]), set(paths))
                for name, relative_path in paths.items():
                    with self.subTest(file=name):
                        raw = archive.read(f"maimai_report/{relative_path}")
                        canonical = raw.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
                        self.assertEqual(
                            hashlib.sha256(canonical).hexdigest(), provenance["files"][name]
                        )

    def test_wheel_contains_assets_entry_point_and_declared_metadata(self) -> None:
        backend = _load_backend()
        with tempfile.TemporaryDirectory() as directory:
            wheel_name = backend.build_wheel(directory)
            with zipfile.ZipFile(Path(directory, wheel_name)) as archive:
                names = set(archive.namelist())
                metadata = archive.read("maimai_session_report-0.1.0.dist-info/METADATA").decode(
                    "utf-8"
                )
                entry_points = archive.read(
                    "maimai_session_report-0.1.0.dist-info/entry_points.txt"
                ).decode("utf-8")

        self.assertIn("maimai_report/assets/template.html", names)
        self.assertIn("maimai_report/assets/rating-notice.txt", names)
        self.assertIn("maimai_report/assets/rating-frames.css", names)
        self.assertIn("maimai_report/assets/rating-fallback.css", names)
        self.assertIn("maimai-report = maimai_report.cli:main", entry_points)
        self.assertIn("Author: arussin", metadata)
        self.assertIn("Project-URL: Repository, https://github.com/", metadata)
        self.assertIn("Classifier: Programming Language :: Python :: 3.13", metadata)
        self.assertIn("\n\n# maimai Session Report", metadata)

    def test_sdist_is_deterministic_complete_and_excludes_local_state(self) -> None:
        backend = _load_backend()
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_path = Path(first, backend.build_sdist(first))
            second_path = Path(second, backend.build_sdist(second))
            first_digest = hashlib.sha256(first_path.read_bytes()).digest()
            second_digest = hashlib.sha256(second_path.read_bytes()).digest()
            with tarfile.open(first_path, "r:gz") as archive:
                names = set(archive.getnames())

        prefix = "maimai-session-report-0.1.0/"
        self.assertEqual(first_digest, second_digest)
        self.assertIn(prefix + "SECURITY.md", names)
        self.assertIn(prefix + "docs/ARCHITECTURE.md", names)
        self.assertIn(prefix + "deploy/cloudflare/src/worker.js", names)
        self.assertIn(prefix + "tests/test_sync.py", names)
        self.assertIn(prefix + "src/maimai_report/assets/rating-notice.txt", names)
        self.assertIn(prefix + "THIRD_PARTY_NOTICES.md", names)
        self.assertIn(prefix + "scripts/harden_tomomai.py", names)
        self.assertFalse(any("__pycache__" in name for name in names))
        self.assertFalse(any("node_modules" in name for name in names))
        self.assertFalse(any("/.wrangler/" in name for name in names))


if __name__ == "__main__":
    unittest.main()
