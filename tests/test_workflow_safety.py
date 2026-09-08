from __future__ import annotations

import unittest
from pathlib import Path


class WorkflowSafetyTests(unittest.TestCase):
    def test_artifact_workflow_is_manual_private_and_serialized(self) -> None:
        workflow = Path(".github/workflows/sync-report.yml").read_text(encoding="utf-8")
        self.assertIn("on:\n  workflow_dispatch:\n", workflow)
        self.assertNotIn("\n  schedule:", workflow)
        self.assertNotIn("\n  push:", workflow)
        self.assertIn("github.event.repository.private", workflow)
        self.assertLess(
            workflow.index("Require a private repository"), workflow.index("sync-and-render")
        )
        self.assertIn("group: maimai-report-live-sync", workflow)
        self.assertIn("cancel-in-progress: false", workflow)

    def test_publish_workflow_is_separate_manual_and_private_guarded(self) -> None:
        workflow = Path(".github/workflows/publish-cloudflare.yml").read_text(encoding="utf-8")
        self.assertIn("on:\n  workflow_dispatch:\n", workflow)
        self.assertNotIn("\n  schedule:", workflow)
        self.assertNotIn("\n  push:", workflow)
        self.assertIn("github.event.repository.private", workflow)
        self.assertIn("environment: private-report-production", workflow)
        self.assertIn('CONFIRMATION" == "PUBLISH PRIVATE REPORT', workflow)
        self.assertIn(
            "workers_dev",
            Path("deploy/cloudflare/scripts/generate-config.mjs").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
