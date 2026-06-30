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
        self.assertIn("canvas_export_html", names)
        self.assertIn("canvas_associate_thread", names)
        canvas_list = next(tool for tool in tools["result"]["tools"] if tool["name"] == "canvas_list")
        self.assertIn("threadId", canvas_list["inputSchema"]["properties"])
        canvas_init = next(tool for tool in tools["result"]["tools"] if tool["name"] == "canvas_init")
        self.assertIn("associatedThreads", canvas_init["inputSchema"]["properties"])
        associate_thread = next(tool for tool in tools["result"]["tools"] if tool["name"] == "canvas_associate_thread")
        self.assertIn("threadId", associate_thread["inputSchema"]["properties"])
        self.assertIsNone(tools["result"]["nextCursor"])

        with tempfile.TemporaryDirectory() as tmp:
            created = self.send(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "canvas_init",
                        "arguments": {
                            "id": "MCP Test",
                            "scope": "project",
                            "root": tmp,
                            "human_actions": ["approve_custom_target"],
                            "agent_actions": ["prepare_custom_summary"],
                            "promotion_targets": ["custom-report"],
                            "associatedThreads": ["thread-alpha", "thread-shared"],
                        },
                    },
                }
            )
            self.assertFalse(created["result"]["isError"])
            created_payload = json.loads(created["result"]["content"][0]["text"])
            self.assertEqual(created_payload["human_actions"], ["approve_custom_target"])
            self.assertEqual(created_payload["agent_actions"], ["prepare_custom_summary"])
            self.assertEqual(created_payload["promotion_targets"], ["custom-report"])
            self.assertEqual(created_payload["associatedThreads"], ["thread-alpha", "thread-shared"])

            other = self.send(
                {
                    "jsonrpc": "2.0",
                    "id": 31,
                    "method": "tools/call",
                    "params": {
                        "name": "canvas_init",
                        "arguments": {
                            "id": "Other MCP Test",
                            "scope": "thread",
                            "root": tmp,
                            "associatedThreads": ["thread-beta"],
                        },
                    },
                }
            )
            self.assertFalse(other["result"]["isError"])

            thread_list = self.send(
                {
                    "jsonrpc": "2.0",
                    "id": 32,
                    "method": "tools/call",
                    "params": {
                        "name": "canvas_list",
                        "arguments": {"threadId": "thread-alpha", "root": tmp},
                    },
                }
            )
            self.assertFalse(thread_list["result"]["isError"])
            thread_list_payload = json.loads(thread_list["result"]["content"][0]["text"])
            self.assertEqual([item["id"] for item in thread_list_payload], ["mcp-test"])

            associated = self.send(
                {
                    "jsonrpc": "2.0",
                    "id": 33,
                    "method": "tools/call",
                    "params": {
                        "name": "canvas_associate_thread",
                        "arguments": {"id": "mcp-test", "threadId": "thread-gamma", "root": tmp},
                    },
                }
            )
            self.assertFalse(associated["result"]["isError"])
            associated_payload = json.loads(associated["result"]["content"][0]["text"])
            self.assertEqual(associated_payload["associatedThreads"], ["thread-alpha", "thread-shared", "thread-gamma"])
            self.assertEqual(associated_payload["last_updated_from_thread"], "thread-gamma")

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

            exported = self.send(
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "canvas_export_html",
                        "arguments": {"id": "mcp-test", "root": tmp},
                    },
                }
            )
            self.assertFalse(exported["result"]["isError"])
            exported_payload = json.loads(exported["result"]["content"][0]["text"])
            html_path = Path(exported_payload["html_path"])
            data_path = Path(exported_payload["data_path"])
            self.assertTrue(html_path.exists())
            self.assertTrue(data_path.exists())

            promoted = self.send(
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {
                        "name": "canvas_promote",
                        "arguments": {
                            "id": "mcp-test",
                            "target": "custom-report",
                            "reference": "outputs/custom.md",
                            "root": tmp,
                        },
                    },
                }
            )
            self.assertFalse(promoted["result"]["isError"])
            promoted_payload = json.loads(promoted["result"]["content"][0]["text"])
            self.assertEqual(promoted_payload["promotions"][-1]["target"], "custom-report")

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
