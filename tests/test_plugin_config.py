from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginConfigTests(unittest.TestCase):
    def test_mcp_server_uses_plugin_relative_startup(self) -> None:
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["canvas"]

        self.assert_server_uses_plugin_relative_startup(server)

    def test_plugin_manifest_points_to_mcp_companion_file(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")

    def assert_server_uses_plugin_relative_startup(self, server: dict[str, object]) -> None:
        command = str(server["command"])
        self.assertEqual(command, "python")
        self.assertEqual(server["args"], ["./src/canvas_mcp_server.py"])
        self.assertEqual(server["cwd"], ".")
        args = server["args"]
        self.assertIsInstance(args, list)
        self.assertFalse(Path(str(args[0])).is_absolute())


if __name__ == "__main__":
    unittest.main()
