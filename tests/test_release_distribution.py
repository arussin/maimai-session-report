"""Keep a fresh release usable without access to another product repository."""

import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

from build_backend.maimai_build_backend import _metadata


class ReleaseDistributionTests(unittest.TestCase):
    def test_package_metadata_identifies_this_standalone_release(self):
        metadata = _metadata()
        self.assertIn("Name: maimai-session-report\n", metadata)
        self.assertIn("https://github.com/arussin/maimai-session-report\n", metadata)

    def test_every_packaged_caller_action_uses_this_release_repository(self):
        directory = Path("templates/private-caller/.github/workflows")
        for workflow in directory.glob("*.yml"):
            with self.subTest(workflow=workflow):
                actions = re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", workflow.read_text(), re.M)
                core = [action for action in actions if not action.startswith("actions/")]
                self.assertTrue(core)
                self.assertEqual(
                    set(core), {"arussin/maimai-session-report/installation@__CORE_SHA__"}
                )

    def test_documentation_local_links_have_targets(self):
        documents = [*Path(".").glob("*.md"), *Path("docs").glob("*.md")]
        for document in documents:
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", text):
                parsed = urlsplit(target)
                if parsed.scheme or not parsed.path:
                    continue
                with self.subTest(document=document, target=target):
                    self.assertTrue((document.parent / unquote(parsed.path)).exists())


if __name__ == "__main__":
    unittest.main()
