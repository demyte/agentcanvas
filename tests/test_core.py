from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "canvas.ps1"
CLI = ROOT / "skills" / "canvas" / "bin" / "canvas.exe"
TEMPLATE = ROOT / "templates" / "canvas-viewer.html"


class CanvasCoreBlackBoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(WRAPPER),
                    "-root",
                    tmp,
                    "list",
                ],
                cwd=ROOT,
                check=False,
                text=True,
                capture_output=True,
            )
        if result.returncode != 0:
            raise AssertionError(result.stdout + result.stderr)

    def run_cli(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        return subprocess.run(
            [str(CLI), *args],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
            env=run_env,
        )

    def run_json(self, *args: str, env: dict[str, str] | None = None) -> dict[str, object] | list[dict[str, object]]:
        result = self.run_cli(*args, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_canvas_viewer_template_is_creation_stub(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8").lower()
        self.assertIn("@tailwindcss/browser@4", template)
        self.assertIn("./canvas-data.js", template)
        self.assertNotIn("<body", template)

    def test_default_canvas_root_respects_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            created = self.run_json(
                "init",
                "-id",
                "Env Root",
                "-scope",
                "user",
                env={"CANVAS_ROOT": tmp},
            )
            self.assertEqual(Path(created["storage_path"]).parent.parent, Path(tmp))

    def test_invalid_id_and_duplicate_canvas_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = self.run_cli("-root", tmp, "init", "-id", "!!!", "-scope", "user")
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("CanvasValidationError", bad.stdout)

            self.run_json("-root", tmp, "init", "-id", "Duplicate", "-scope", "user")
            duplicate = self.run_cli("-root", tmp, "init", "-id", "Duplicate", "-scope", "user")
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("Canvas already exists", duplicate.stdout)

    def test_thread_filter_ignores_malformed_associated_threads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.run_json(
                "-root",
                tmp,
                "init",
                "-id",
                "Malformed Threads",
                "-scope",
                "thread",
                "-associated-thread",
                "thread-a",
            )
            metadata_file = Path(tmp) / "active" / "malformed-threads" / "canvas.json"
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            metadata["associatedThreads"] = "thread-a"
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

            listed = self.run_json("-root", tmp, "list", "-thread-id", "thread-a")
            self.assertEqual(listed, [])

    def test_validation_rejects_bad_metadata_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.run_json("-root", tmp, "init", "-id", "Bad Metadata", "-scope", "project")
            metadata_file = Path(tmp) / "active" / "bad-metadata" / "canvas.json"
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            metadata["associatedThreads"] = ["ok", ""]
            metadata["storage_path"] = str(Path(tmp) / "elsewhere")
            metadata["promotion_targets"] = "final-report"
            metadata["promotions"] = [{"target": "final-report", "reference": "out.md"}]
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

            result = self.run_cli("-root", tmp, "validate", "-id", "bad-metadata")
            self.assertEqual(result.returncode, 2, result.stdout)
            payload = json.loads(result.stdout)
            errors = "\n".join(payload["errors"])
            self.assertIn("associatedThreads must be an array of non-empty strings", errors)
            self.assertIn("storage_path must match the canvas directory", errors)
            self.assertIn("promotion_targets must be an array of non-empty strings", errors)
            self.assertIn("promotions[0].promoted_at must be a non-empty string", errors)

    def test_promote_rejects_invalid_target_without_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.run_json(
                "-root",
                tmp,
                "init",
                "-id",
                "Promotion Payload",
                "-scope",
                "project",
                "-promotion-target",
                "final-report",
            )
            metadata_file = Path(tmp) / "active" / "promotion-payload" / "canvas.json"
            before = json.loads(metadata_file.read_text(encoding="utf-8"))

            bad = self.run_cli(
                "-root",
                tmp,
                "promote",
                "-id",
                "promotion-payload",
                "-target",
                "not-allowed",
                "-reference",
                "outputs/report.md",
            )
            self.assertNotEqual(bad.returncode, 0)
            after = json.loads(metadata_file.read_text(encoding="utf-8"))
            self.assertEqual(after, before)

    def test_export_handles_invalid_canvas_and_writes_data_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.run_json("-root", tmp, "init", "-id", "Missing Field", "-scope", "project")
            metadata_file = Path(tmp) / "active" / "missing-field" / "canvas.json"
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            metadata.pop("id")
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

            exported = self.run_json("-root", tmp, "export-html", "-id", "missing-field")
            self.assertFalse(exported["valid"])
            html_path = Path(exported["html_path"])
            data_path = Path(exported["data_path"])
            self.assertEqual(html_path.read_text(encoding="utf-8"), TEMPLATE.read_text(encoding="utf-8"))
            self.assertIn("Missing metadata field: id", data_path.read_text(encoding="utf-8"))

    def test_archive_rejects_corrupt_metadata_before_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.run_json("-root", tmp, "init", "-id", "Corrupt Archive", "-scope", "project")
            canvas_dir = Path(tmp) / "active" / "corrupt-archive"
            archived_dir = Path(tmp) / "archived" / "corrupt-archive"
            (canvas_dir / "canvas.json").write_text("{", encoding="utf-8")

            result = self.run_cli("-root", tmp, "archive", "-id", "corrupt-archive")
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(canvas_dir.exists())
            self.assertFalse(archived_dir.exists())


if __name__ == "__main__":
    unittest.main()
