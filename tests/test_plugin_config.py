from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys
import argparse
import contextlib
import io
import subprocess


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import smoke_mcp  # noqa: E402
import run_scenarios  # noqa: E402


class PluginConfigTests(unittest.TestCase):
    def test_mcp_server_uses_plugin_relative_startup(self) -> None:
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["canvas"]

        self.assert_server_uses_plugin_relative_startup(server)

    def test_plugin_manifest_points_to_mcp_companion_file(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")

    def test_smoke_selects_exact_installed_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            self.write_plugin_root(cache_root / "0.1.0+old", "0.1.0+old")
            expected = self.write_plugin_root(cache_root / "0.1.0+new", "0.1.0+new")
            original = smoke_mcp.DEFAULT_CACHE_ROOT
            try:
                smoke_mcp.DEFAULT_CACHE_ROOT = cache_root
                self.assertEqual(smoke_mcp.latest_installed_plugin("0.1.0+new"), expected)
                with self.assertRaises(smoke_mcp.SmokeFailure):
                    smoke_mcp.latest_installed_plugin("0.1.0+missing")
            finally:
                smoke_mcp.DEFAULT_CACHE_ROOT = original

    def test_scenarios_select_exact_installed_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            self.write_plugin_root(cache_root / "0.1.0+z-stale", "0.1.0+z-stale")
            expected = self.write_plugin_root(cache_root / "0.1.0+current", "0.1.0+current")
            original = smoke_mcp.DEFAULT_CACHE_ROOT
            original_run = run_scenarios.run
            original_argv = sys.argv
            captured: dict[str, Path] = {}

            def fake_run(plugin_root: Path, output: Path) -> dict[str, object]:
                captured["plugin_root"] = plugin_root
                return {"ok": True, "plugin_root": str(plugin_root), "output": str(output)}

            try:
                smoke_mcp.DEFAULT_CACHE_ROOT = cache_root
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
                smoke_mcp.DEFAULT_CACHE_ROOT = original
                run_scenarios.run = original_run
                sys.argv = original_argv

    def test_smoke_rejects_absolute_mcp_arg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.write_plugin_root(Path(tmp), "0.1.0+test")
            config = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
            config["mcpServers"]["canvas"]["args"] = [str((root / "src" / "canvas_mcp_server.py").resolve())]
            (root / ".mcp.json").write_text(json.dumps(config), encoding="utf-8")

            with self.assertRaises(smoke_mcp.SmokeFailure):
                smoke_mcp.server_config(root)

    def test_smoke_rejects_non_python_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.write_plugin_root(Path(tmp), "0.1.0+test")
            config = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
            config["mcpServers"]["canvas"]["command"] = sys.executable
            (root / ".mcp.json").write_text(json.dumps(config), encoding="utf-8")

            with self.assertRaises(smoke_mcp.SmokeFailure):
                smoke_mcp.server_config(root)

    def test_smoke_help_matches_exact_installed_selection(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "smoke_mcp.py"), "--help"],
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

    def assert_server_uses_plugin_relative_startup(self, server: dict[str, object]) -> None:
        command = str(server["command"])
        self.assertEqual(command, "python")
        self.assertEqual(server["args"], ["./src/canvas_mcp_server.py"])
        self.assertEqual(server["cwd"], ".")
        args = server["args"]
        self.assertIsInstance(args, list)
        self.assertFalse(Path(str(args[0])).is_absolute())

    def write_plugin_root(self, root: Path, version: str) -> Path:
        (root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
        (root / "src").mkdir(parents=True, exist_ok=True)
        (root / "src" / "canvas_mcp_server.py").write_text("print('ok')\n", encoding="utf-8")
        (root / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"version": version, "mcpServers": "./.mcp.json"}),
            encoding="utf-8",
        )
        (root / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"canvas": {"command": "python", "args": ["./src/canvas_mcp_server.py"], "cwd": "."}}}),
            encoding="utf-8",
        )
        return root


if __name__ == "__main__":
    unittest.main()
