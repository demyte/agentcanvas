from __future__ import annotations

import json
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
            self.assertEqual(metadata["associatedThreads"], [])
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
            self.assertFalse((Path(tmp) / "active" / "lifecycle-check").exists())
            self.assertTrue((Path(tmp) / "archived" / "lifecycle-check").exists())
            self.assertTrue(registry.validate_canvas("lifecycle-check", "archived")["valid"])

    def test_canvas_list_filters_by_associated_thread(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            first = registry.init_canvas(
                "Thread One",
                scope="thread",
                associated_threads=["thread-a", "thread-shared"],
            )
            registry.init_canvas(
                "Thread Two",
                scope="thread",
                associated_threads=["thread-b", "thread-shared"],
            )
            registry.init_canvas("No Thread", scope="project")

            self.assertEqual(first["associatedThreads"], ["thread-a", "thread-shared"])
            thread_a = registry.list_canvases(thread_id="thread-a")
            thread_shared = registry.list_canvases(thread_id="thread-shared")
            missing = registry.list_canvases(thread_id="missing-thread")

            self.assertEqual([item["id"] for item in thread_a], ["thread-one"])
            self.assertEqual({item["id"] for item in thread_shared}, {"thread-one", "thread-two"})
            self.assertEqual(missing, [])

    def test_canvas_list_thread_filter_ignores_malformed_associated_threads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Malformed Threads", scope="thread", associated_threads=["thread-a"])
            metadata_file = Path(tmp) / "active" / "malformed-threads" / "canvas.json"
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            metadata["associatedThreads"] = "thread-a"
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

            self.assertEqual(registry.list_canvases(thread_id="thread-a"), [])

    def test_associated_threads_must_be_non_empty_strings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Bad Threads", scope="thread")
            metadata_file = Path(tmp) / "active" / "bad-threads" / "canvas.json"
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            metadata["associatedThreads"] = ["ok", ""]
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

            validation = registry.validate_canvas("bad-threads")
            self.assertFalse(validation["valid"])
            self.assertIn("associatedThreads must be an array of non-empty strings", validation["errors"])

    def test_init_rejects_string_associated_threads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))

            with self.assertRaises(CanvasValidationError):
                registry.init_canvas("Bad Thread Init", scope="thread", associated_threads="thread-alpha")
            self.assertFalse((Path(tmp) / "active" / "bad-thread-init").exists())

            created = registry.init_canvas("Bad Thread Init", scope="thread", associated_threads=["thread-alpha"])
            self.assertEqual(created["associatedThreads"], ["thread-alpha"])

    def test_init_rolls_back_directory_after_write_failure(self) -> None:
        class FailingRegistry(CanvasRegistry):
            def _write_json(self, path: Path, data: dict) -> None:
                super()._write_json(path, data)
                if path.name == "canvas.json":
                    raise OSError("simulated write failure")

        with tempfile.TemporaryDirectory() as tmp:
            registry = FailingRegistry(Path(tmp))
            canvas_dir = Path(tmp) / "active" / "write-failure"

            with self.assertRaises(OSError):
                registry.init_canvas("Write Failure", scope="project")

            self.assertFalse(canvas_dir.exists())
            created = CanvasRegistry(Path(tmp)).init_canvas("Write Failure", scope="project")
            self.assertEqual(created["id"], "write-failure")

    def test_validation_rejects_stale_storage_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Stale Storage", scope="project")
            metadata_file = Path(tmp) / "active" / "stale-storage" / "canvas.json"
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            metadata["storage_path"] = str(Path(tmp) / "somewhere-else")
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

            validation = registry.validate_canvas("stale-storage")
            self.assertFalse(validation["valid"])
            self.assertIn("storage_path must match the canvas directory", validation["errors"])

    def test_validation_rejects_bad_promotion_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Bad Promotions", scope="project")
            metadata_file = Path(tmp) / "active" / "bad-promotions" / "canvas.json"
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            metadata["promotion_targets"] = "final-report"
            metadata["promotions"] = [{"target": "final-report", "reference": "out.md"}]
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

            validation = registry.validate_canvas("bad-promotions")
            self.assertFalse(validation["valid"])
            self.assertIn("promotion_targets must be an array of non-empty strings", validation["errors"])
            self.assertIn("promotions[0].promoted_at must be a non-empty string", validation["errors"])
            with self.assertRaises(CanvasValidationError):
                registry.promote_canvas("bad-promotions", target="final-report", reference="outputs/report.md")

    def test_promote_rejects_invalid_payload_without_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Promotion Payload", scope="project")
            metadata_file = Path(tmp) / "active" / "promotion-payload" / "canvas.json"
            before = json.loads(metadata_file.read_text(encoding="utf-8"))

            with self.assertRaises(CanvasValidationError):
                registry.promote_canvas("promotion-payload", target="final-report", reference="")
            with self.assertRaises(CanvasValidationError):
                registry.promote_canvas("promotion-payload", target="final-report", reference="outputs/report.md", note=None)

            after = json.loads(metadata_file.read_text(encoding="utf-8"))
            self.assertEqual(after, before)
            self.assertTrue(registry.validate_canvas("promotion-payload")["valid"])

    def test_validation_rejects_stale_metadata_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Folder Name", scope="project")
            metadata_file = Path(tmp) / "active" / "folder-name" / "canvas.json"
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            metadata["id"] = "different-id"
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

            validation = registry.validate_canvas("folder-name")
            self.assertFalse(validation["valid"])
            self.assertIn("id must match the canvas directory", validation["errors"])

    def test_export_validates_requested_canvas_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Folder Name", scope="project")
            registry.init_canvas("Different Id", scope="project")
            metadata_file = Path(tmp) / "active" / "folder-name" / "canvas.json"
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            metadata["id"] = "different-id"
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

            exported = registry.export_html("folder-name")
            self.assertFalse(exported["valid"])
            data_path = Path(exported["data_path"])
            self.assertIn("id must match the canvas directory", data_path.read_text(encoding="utf-8"))

    def test_associate_thread_updates_existing_canvas_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Existing Thread Target", scope="thread", associated_threads=["thread-a"])

            updated = registry.associate_thread("existing-thread-target", thread_id="thread-b")
            updated_again = registry.associate_thread("existing-thread-target", thread_id="thread-b")

            self.assertEqual(updated["associatedThreads"], ["thread-a", "thread-b"])
            self.assertEqual(updated["last_updated_from_thread"], "thread-b")
            self.assertEqual(updated_again["associatedThreads"], ["thread-a", "thread-b"])
            self.assertEqual(
                [item["id"] for item in registry.list_canvases(thread_id="thread-b")],
                ["existing-thread-target"],
            )

    def test_associate_thread_rejects_empty_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Empty Thread", scope="thread")

            with self.assertRaises(CanvasValidationError):
                registry.associate_thread("empty-thread", thread_id=" ")

    def test_associate_thread_does_not_mutate_invalid_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Invalid Associate", scope="thread", associated_threads=["thread-a"])
            canvas_dir = Path(tmp) / "active" / "invalid-associate"
            metadata_file = canvas_dir / "canvas.json"
            before = json.loads(metadata_file.read_text(encoding="utf-8"))
            (canvas_dir / "notes.md").unlink()

            with self.assertRaises(CanvasValidationError):
                registry.associate_thread("invalid-associate", thread_id="thread-b")

            after = json.loads(metadata_file.read_text(encoding="utf-8"))
            self.assertEqual(after, before)

    def test_archive_rejects_invalid_metadata_before_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Corrupt Archive", scope="project")
            canvas_dir = Path(tmp) / "active" / "corrupt-archive"
            archived_dir = Path(tmp) / "archived" / "corrupt-archive"
            (canvas_dir / "canvas.json").write_text("{", encoding="utf-8")

            with self.assertRaises(CanvasValidationError):
                registry.archive_canvas("corrupt-archive")

            self.assertTrue(canvas_dir.exists())
            self.assertFalse(archived_dir.exists())

    def test_reject_duplicate_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = CanvasRegistry(Path(tmp))
            registry.init_canvas("Duplicate", scope="user")
            with self.assertRaises(CanvasValidationError):
                registry.init_canvas("Duplicate", scope="user")


if __name__ == "__main__":
    unittest.main()
