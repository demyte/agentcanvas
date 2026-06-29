from __future__ import annotations

import json
import os
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
        line = self.proc.stdout.readline()
        self.assertFalse(line.lower().startswith(b"content-length:"), line)
        return json.loads(line.decode("utf-8"))

    def send_line(self, message: dict) -> dict:
        assert self.proc.stdin is not None
        assert self.proc.stdout is not None
        self.proc.stdin.write(json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        self.assertFalse(line.lower().startswith(b"content-length:"), line)
        return json.loads(line.decode("utf-8"))

    def test_initialize_tools_and_canvas_call(self) -> None:
        init = self.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "canvas")
        self.assertEqual(init["result"]["capabilities"]["tools"], {"listChanged": False})

        tools = self.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = {tool["name"] for tool in tools["result"]["tools"]}
        self.assertIn("canvas_init", names)
        self.assertIn("canvas_validate", names)
        self.assertIsNone(tools["result"]["nextCursor"])

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

    def test_handle_request_ignores_json_rpc_error_messages(self) -> None:
        response = canvas_mcp_server.handle_request(
            {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}
        )
        self.assertIsNone(response)

    def test_ping_returns_empty_result(self) -> None:
        response = canvas_mcp_server.handle_request({"jsonrpc": "2.0", "id": 99, "method": "ping"})
        self.assertEqual(response, {"jsonrpc": "2.0", "id": 99, "result": {}})

    def test_newline_json_transport_matches_codex_stdio(self) -> None:
        response = self.send_line({"jsonrpc": "2.0", "id": 10, "method": "tools/list", "params": {}})
        self.assertIn("tools", response["result"])
        self.assertIn("canvas_init", {tool["name"] for tool in response["result"]["tools"]})

    def test_startup_probe_writes_process_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original_probe = canvas_mcp_server.STARTUP_PROBE
            original_env = os.environ.get("CANVAS_MCP_PROBE")
            canvas_mcp_server.STARTUP_PROBE = Path(tmp) / "startup.jsonl"
            try:
                os.environ["CANVAS_MCP_PROBE"] = "1"
                canvas_mcp_server.write_startup_probe()
                entry = json.loads(canvas_mcp_server.STARTUP_PROBE.read_text(encoding="utf-8"))
            finally:
                canvas_mcp_server.STARTUP_PROBE = original_probe
                if original_env is None:
                    os.environ.pop("CANVAS_MCP_PROBE", None)
                else:
                    os.environ["CANVAS_MCP_PROBE"] = original_env

        self.assertEqual(entry["event"], "canvas_mcp_start")
        self.assertTrue(Path(entry["script"]).name.endswith("canvas_mcp_server.py"))
        self.assertTrue(entry["executable"])

    def test_probe_writer_records_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original_env = os.environ.get("CANVAS_MCP_PROBE")
            path = Path(tmp) / "traffic.jsonl"
            try:
                os.environ["CANVAS_MCP_PROBE"] = "1"
                canvas_mcp_server.write_probe(path, {"event": "response", "message": {"id": 1}})
                entry = json.loads(path.read_text(encoding="utf-8"))
            finally:
                if original_env is None:
                    os.environ.pop("CANVAS_MCP_PROBE", None)
                else:
                    os.environ["CANVAS_MCP_PROBE"] = original_env

        self.assertEqual(entry["event"], "response")
        self.assertEqual(entry["message"], {"id": 1})
        self.assertIn("timestamp", entry)

    def test_probe_writer_is_disabled_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original_env = os.environ.pop("CANVAS_MCP_PROBE", None)
            path = Path(tmp) / "traffic.jsonl"
            try:
                canvas_mcp_server.write_probe(path, {"event": "response"})
            finally:
                if original_env is not None:
                    os.environ["CANVAS_MCP_PROBE"] = original_env

        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
