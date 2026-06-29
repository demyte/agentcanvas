from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "src" / "canvas_mcp_server.py"
sys.path.insert(0, str(ROOT / "src"))

import canvas_mcp_server  # noqa: E402


class McpServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def tearDown(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.wait(timeout=5)
        if self.proc.stdout:
            self.proc.stdout.close()
        if self.proc.stderr:
            self.proc.stderr.close()

    def send(self, message: dict) -> dict:
        assert self.proc.stdin is not None
        assert self.proc.stdout is not None
        body = json.dumps(message, separators=(",", ":")).encode("utf-8")
        self.proc.stdin.write(b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body)
        self.proc.stdin.flush()
        header = self.proc.stdout.readline()
        self.assertTrue(header.lower().startswith(b"content-length:"), header)
        length = int(header.split(b":", 1)[1].strip())
        blank = self.proc.stdout.readline()
        self.assertIn(blank, {b"\r\n", b"\n"})
        return json.loads(self.proc.stdout.read(length).decode("utf-8"))

    def test_initialize_tools_and_canvas_call(self) -> None:
        init = self.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "canvas")

        tools = self.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = {tool["name"] for tool in tools["result"]["tools"]}
        self.assertIn("canvas_init", names)
        self.assertIn("canvas_validate", names)

        with tempfile.TemporaryDirectory() as tmp:
            created = self.send(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "canvas_init",
                        "arguments": {"id": "MCP Test", "scope": "project", "root": tmp},
                    },
                }
            )
            self.assertFalse(created["result"]["isError"])

            validated = self.send(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "canvas_validate",
                        "arguments": {"id": "mcp-test", "root": tmp},
                    },
                }
            )
            self.assertFalse(validated["result"]["isError"])
            text = validated["result"]["content"][0]["text"]
            self.assertTrue(json.loads(text)["valid"])

    def test_startup_probe_writes_process_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original_probe = canvas_mcp_server.STARTUP_PROBE
            canvas_mcp_server.STARTUP_PROBE = Path(tmp) / "startup.jsonl"
            try:
                canvas_mcp_server.write_startup_probe()
                entry = json.loads(canvas_mcp_server.STARTUP_PROBE.read_text(encoding="utf-8"))
            finally:
                canvas_mcp_server.STARTUP_PROBE = original_probe

        self.assertEqual(entry["event"], "canvas_mcp_start")
        self.assertTrue(Path(entry["script"]).name.endswith("canvas_mcp_server.py"))
        self.assertTrue(entry["executable"])

    def test_probe_writer_records_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "traffic.jsonl"
            canvas_mcp_server.write_probe(path, {"event": "response", "message": {"id": 1}})
            entry = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(entry["event"], "response")
        self.assertEqual(entry["message"], {"id": 1})
        self.assertIn("timestamp", entry)


if __name__ == "__main__":
    unittest.main()
