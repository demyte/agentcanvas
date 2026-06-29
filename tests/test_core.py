from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from canvas_core import CanvasRegistry, CanvasValidationError, default_canvas_root, normalize_canvas_id

TEMPLATE = ROOT / "templates" / "canvas-viewer.html"


class CanvasCoreTests(unittest.TestCase):
    def test_default_canvas_root_uses_agents_canvas(self) -> None:
        original = os.environ.pop("CANVAS_ROOT", None)
        try:
            self.assertEqual(default_canvas_root(), Path.home() / ".agents" / "canvas")
        finally:
            if original is not None:
                os.environ["CANVAS_ROOT"] = original

    def test_default_canvas_root_respects_env_override(self) -> None:
        original = os.environ.get("CANVAS_ROOT")
        try:
            os.environ["CANVAS_ROOT"] = "~/custom-canvas-root"
            self.assertEqual(default_canvas_root(), Path("~/custom-canvas-root").expanduser())
        finally:
            if original is None:
                os.environ.pop("CANVAS_ROOT", None)
            else:
                os.environ["CANVAS_ROOT"] = original

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

            exported = registry.export_html("lifecycle-check")
            html_path = Path(exported["html_path"])
            data_path = Path(exported["data_path"])
            self.assertTrue(html_path.exists())
            self.assertTrue(data_path.exists())
            self.assertEqual(html_path.read_text(encoding="utf-8"), TEMPLATE.read_text(encoding="utf-8"))
            data_text = data_path.read_text(encoding="utf-8")
            self.assertIn("Lifecycle Check", data_text)
            self.assertIn("final-report", data_text)
            self.assertTrue(exported["valid"])

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
