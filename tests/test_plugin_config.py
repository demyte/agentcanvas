from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_scenarios  # noqa: E402
import smoke_cli  # noqa: E402


class PluginConfigTests(unittest.TestCase):
    def test_plugin_manifest_uses_bundled_cli_not_mcp(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

        self.assertNotIn("mcpServers", manifest)
        self.assertNotIn("MCP", manifest["interface"]["capabilities"])
        self.assertTrue((ROOT / "scripts" / "canvas.py").exists())
        self.assertTrue((ROOT / "src" / "canvas_cli.py").exists())

    def test_skill_documents_cli_contract_and_blank_stub_contract(self) -> None:
        skill = (ROOT / "skills" / "canvas" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("Use the bundled Canvas CLI", skill)
        self.assertIn("../../scripts/canvas.py", skill)
        self.assertIn("python ../../scripts/canvas.py -?", skill)
        self.assertIn('init -id "review-board" -scope repo', skill)
        self.assertIn("update-state -id", skill)
        self.assertIn("-merge-file", skill)
        self.assertIn("Do not use MCP tools for Canvas", skill)
        self.assertNotIn("tool canvas_init", skill)
        self.assertNotIn("<json-object>", skill)
        self.assertIn("The shared exported template intentionally has no body", skill)
        self.assertIn("build or update the canvas-specific `canvas.html` body", skill)
        self.assertIn("Do not add generic UI to `templates/canvas-viewer.html`", skill)
        self.assertIn("Use `user` for personal planning", skill)
        self.assertIn("Do not treat a delegated source thread id", skill)

    def test_smoke_selects_exact_installed_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            self.write_plugin_root(cache_root / "0.1.0+old", "0.1.0+old")
            expected = self.write_plugin_root(cache_root / "0.1.0+new", "0.1.0+new")
            original = smoke_cli.DEFAULT_CACHE_ROOT
            try:
                smoke_cli.DEFAULT_CACHE_ROOT = cache_root
                self.assertEqual(smoke_cli.latest_installed_plugin("0.1.0+new"), expected)
                with self.assertRaises(smoke_cli.SmokeFailure):
                    smoke_cli.latest_installed_plugin("0.1.0+missing")
            finally:
                smoke_cli.DEFAULT_CACHE_ROOT = original

    def test_scenarios_select_exact_installed_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            self.write_plugin_root(cache_root / "0.1.0+z-stale", "0.1.0+z-stale")
            expected = self.write_plugin_root(cache_root / "0.1.0+current", "0.1.0+current")
            original = smoke_cli.DEFAULT_CACHE_ROOT
            original_run = run_scenarios.run
            original_argv = sys.argv
            captured: dict[str, Path] = {}

            def fake_run(plugin_root: Path, output: Path) -> dict[str, object]:
                captured["plugin_root"] = plugin_root
                return {"ok": True, "plugin_root": str(plugin_root), "output": str(output)}

            try:
                smoke_cli.DEFAULT_CACHE_ROOT = cache_root
                run_scenarios.run = fake_run
                args = argparse.Namespace(
                    installed=True,
                    plugin_root="",
                    expected_version="0.1.0+current",
                )
                self.assertEqual(run_scenarios.resolve_plugin_root(args), expected)
                sys.argv = ["run_scenarios.py", "--installed", "--expected-version", "0.1.0+current"]
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(run_scenarios.main(), 0)
                self.assertEqual(captured["plugin_root"], expected.resolve())
            finally:
                smoke_cli.DEFAULT_CACHE_ROOT = original
                run_scenarios.run = original_run
                sys.argv = original_argv

    def test_smoke_help_matches_exact_installed_selection(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "smoke_cli.py"), "--help"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        normalized_help = " ".join(result.stdout.split())
        self.assertIn(
            "Plugin root to test. Defaults to source root, or in installed mode to the cache matching the expected version.",
            normalized_help,
        )
        self.assertNotIn("latest cache", result.stdout)

    def write_plugin_root(self, root: Path, version: str) -> Path:
        (root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "src").mkdir(parents=True, exist_ok=True)
        (root / "scripts" / "canvas.py").write_text("print('{}')\n", encoding="utf-8")
        (root / "src" / "canvas_cli.py").write_text("", encoding="utf-8")
        (root / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"version": version}),
            encoding="utf-8",
        )
        return root


if __name__ == "__main__":
    unittest.main()
