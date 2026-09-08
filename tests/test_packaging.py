from __future__ import annotations

import hashlib
import importlib.util
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


def _load_backend():
    path = Path("build_backend", "maimai_build_backend.py").resolve()
    spec = importlib.util.spec_from_file_location("maimai_build_backend_test", path)
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load the local build backend")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackagingTests(unittest.TestCase):
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
