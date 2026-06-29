from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from canvas_core import CanvasRegistry, CanvasValidationError, normalize_canvas_id


class CanvasCoreTests(unittest.TestCase):
    def test_normalize_canvas_id(self) -> None:
        self.assertEqual(normalize_canvas_id("PR 2713 Review Board"), "pr-2713-review-board")
        with self.assertRaises(CanvasValidationError):
            normalize_canvas_id("!!!")

    def test_canvas_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            metadata = registry.init_canvas(
                "Lifecycle Check",
                scope="project",
                anchor="D:\\Projects",
                title="Lifecycle Check",
                purpose="test",
            )

            self.assertEqual(metadata["id"], "lifecycle-check")
            self.assertEqual(metadata["lifecycle"], "active")
            self.assertTrue((Path(tmp) / "active" / "lifecycle-check" / "canvas.json").exists())
            self.assertTrue(registry.validate_canvas("lifecycle-check")["valid"])

            updated = registry.update_state("lifecycle-check", {"items": [{"id": "one"}]})
            self.assertEqual(updated["state"]["items"][0]["id"], "one")

            promoted = registry.promote_canvas(
                "lifecycle-check",
                target="final-report",
                reference="outputs/report.md",
                note="test",
            )
            self.assertEqual(promoted["promotions"][0]["target"], "final-report")

            archived = registry.archive_canvas("lifecycle-check")
            self.assertEqual(archived["lifecycle"], "archived")
            self.assertTrue(registry.validate_canvas("lifecycle-check", "archived")["valid"])

    def test_reject_duplicate_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Duplicate", scope="user")
            with self.assertRaises(CanvasValidationError):
                registry.init_canvas("Duplicate", scope="user")


if __name__ == "__main__":
    unittest.main()
