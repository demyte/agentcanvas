from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginConfigTests(unittest.TestCase):
    def test_mcp_server_uses_plugin_relative_startup(self) -> None:
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["canvas"]

        self.assertEqual(server["command"], "python")
        self.assertEqual(server["args"], ["./src/canvas_mcp_server.py"])
        self.assertEqual(server["cwd"], ".")
        self.assertFalse(Path(server["args"][0]).is_absolute())


if __name__ == "__main__":
    unittest.main()

