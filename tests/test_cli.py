from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "canvas.py"


class CanvasCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )

    def test_init_validate_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            init = self.run_cli(
                "--root",
                tmp,
                "init",
                "CLI Smoke",
                "--scope",
                "thread",
                "--purpose",
                "cli test",
                "--human-action",
                "approve_cli",
                "--agent-action",
                "summarize_cli",
                "--promotion-target",
                "cli-report",
                "--associated-thread",
                "thread-cli",
                "--associated-thread",
                "thread-shared",
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            created = json.loads(init.stdout)
            self.assertEqual(created["id"], "cli-smoke")
            self.assertEqual(created["human_actions"], ["approve_cli"])
            self.assertEqual(created["agent_actions"], ["summarize_cli"])
            self.assertEqual(created["promotion_targets"], ["cli-report"])
            self.assertEqual(created["associatedThreads"], ["thread-cli", "thread-shared"])

            list_result = self.run_cli("--root", tmp, "list", "--thread-id", "thread-cli")
            self.assertEqual(list_result.returncode, 0, list_result.stdout)
            self.assertEqual([item["id"] for item in json.loads(list_result.stdout)], ["cli-smoke"])

            associate = self.run_cli("--root", tmp, "associate-thread", "cli-smoke", "thread-extra")
            self.assertEqual(associate.returncode, 0, associate.stdout)
            associate_payload = json.loads(associate.stdout)
            self.assertEqual(associate_payload["associatedThreads"], ["thread-cli", "thread-shared", "thread-extra"])
            self.assertEqual(associate_payload["last_updated_from_thread"], "thread-extra")

            validate = self.run_cli("--root", tmp, "validate", "cli-smoke")
            self.assertEqual(validate.returncode, 0, validate.stdout)
            self.assertTrue(json.loads(validate.stdout)["valid"])

            export = self.run_cli("--root", tmp, "export-html", "cli-smoke")
            self.assertEqual(export.returncode, 0, export.stdout)
            export_payload = json.loads(export.stdout)
            html_path = Path(export_payload["html_path"])
            data_path = Path(export_payload["data_path"])
            self.assertTrue(html_path.exists())
            self.assertTrue(data_path.exists())

            promote = self.run_cli(
                "--root",
                tmp,
                "promote",
                "cli-smoke",
                "--target",
                "cli-report",
                "--reference",
                "outputs/cli-report.md",
            )
            self.assertEqual(promote.returncode, 0, promote.stdout)
            self.assertEqual(json.loads(promote.stdout)["promotions"][-1]["target"], "cli-report")

            archive = self.run_cli("--root", tmp, "archive", "cli-smoke")
            self.assertEqual(archive.returncode, 0, archive.stdout)
            self.assertEqual(json.loads(archive.stdout)["lifecycle"], "archived")

    def test_invalid_scope_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli("--root", tmp, "init", "Bad", "--scope", "invalid")
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
