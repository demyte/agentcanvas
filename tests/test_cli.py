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
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            self.assertEqual(json.loads(init.stdout)["id"], "cli-smoke")

            validate = self.run_cli("--root", tmp, "validate", "cli-smoke")
            self.assertEqual(validate.returncode, 0, validate.stdout)
            self.assertTrue(json.loads(validate.stdout)["valid"])

            export = self.run_cli("--root", tmp, "export-html", "cli-smoke")
            self.assertEqual(export.returncode, 0, export.stdout)
            html_path = Path(json.loads(export.stdout)["html_path"])
            self.assertTrue(html_path.exists())

            archive = self.run_cli("--root", tmp, "archive", "cli-smoke")
            self.assertEqual(archive.returncode, 0, archive.stdout)
            self.assertEqual(json.loads(archive.stdout)["lifecycle"], "archived")

    def test_invalid_scope_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli("--root", tmp, "init", "Bad", "--scope", "invalid")
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
