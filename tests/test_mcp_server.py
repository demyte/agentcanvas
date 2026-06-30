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

    def test_request_id_must_be_string_or_integer(self) -> None:
        for bad_id in [None, 1.5, True]:
            response = canvas_mcp_server.handle_request({"jsonrpc": "2.0", "id": bad_id, "method": "ping"})
            assert response is not None
            self.assertEqual(response["error"]["code"], -32600)
            self.assertIsNone(response["id"])

        string_id = canvas_mcp_server.handle_request({"jsonrpc": "2.0", "id": "request-a", "method": "ping"})
        int_id = canvas_mcp_server.handle_request({"jsonrpc": "2.0", "id": 123, "method": "ping"})
        self.assertEqual(string_id, {"jsonrpc": "2.0", "id": "request-a", "result": {}})
        self.assertEqual(int_id, {"jsonrpc": "2.0", "id": 123, "result": {}})

    def test_params_must_be_an_object_when_present(self) -> None:
        response = canvas_mcp_server.handle_request(
            {"jsonrpc": "2.0", "id": 100, "method": "tools/call", "params": "bad"}
        )

        assert response is not None
        self.assertEqual(response["error"]["code"], -32602)
        self.assertIn("params must be an object", response["error"]["message"])

    def test_notifications_do_not_emit_responses(self) -> None:
        ping = canvas_mcp_server.handle_request({"jsonrpc": "2.0", "method": "ping"})
        cancelled = canvas_mcp_server.handle_request(
            {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 123}}
        )

        self.assertIsNone(ping)
        self.assertIsNone(cancelled)

    def test_id_bearing_initialized_notification_is_a_request_error(self) -> None:
        response = canvas_mcp_server.handle_request(
            {"jsonrpc": "2.0", "id": 101, "method": "notifications/initialized", "params": {}}
        )

        assert response is not None
        self.assertEqual(response["error"]["code"], -32601)
        self.assertNotIn("result", response)

    def test_tool_argument_validation_rejects_bad_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_threads = canvas_mcp_server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "tools/call",
                    "params": {
                        "name": "canvas_init",
                        "arguments": {
                            "id": "Bad Threads",
                            "scope": "thread",
                            "associatedThreads": "thread-alpha",
                            "root": tmp,
                        },
                    },
                }
            )
            missing_id = canvas_mcp_server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 12,
                    "method": "tools/call",
                    "params": {"name": "canvas_get", "arguments": {"root": tmp}},
                }
            )
            bad_updates = canvas_mcp_server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 13,
                    "method": "tools/call",
                    "params": {
                        "name": "canvas_update_state",
                        "arguments": {"id": "anything", "updates": "not-object", "root": tmp},
                    },
                }
            )

        assert bad_threads is not None
        assert missing_id is not None
        assert bad_updates is not None
        for response in [bad_threads, missing_id, bad_updates]:
            self.assertNotIn("result", response)
            self.assertEqual(response["error"]["code"], -32602)
        self.assertIn("associatedThreads", bad_threads["error"]["message"])
        self.assertIn("Missing required argument", missing_id["error"]["message"])
        self.assertIn("updates must be an object", bad_updates["error"]["message"])

    def test_unknown_tool_and_bad_arguments_are_protocol_errors(self) -> None:
        cases = [
            {
                "name": "not_a_tool",
                "arguments": {},
                "message": "Unknown tool",
            },
            {
                "name": "canvas_list",
                "arguments": [],
                "message": "Tool arguments must be an object",
            },
            {
                "name": "canvas_list",
                "arguments": None,
                "message": "Tool arguments must be an object",
            },
            {
                "name": "canvas_list",
                "arguments": "",
                "message": "Tool arguments must be an object",
            },
            {
                "name": "canvas_list",
                "arguments": {"lifecycle": "pending"},
                "message": "lifecycle must be one of",
            },
            {
                "name": "canvas_list",
                "arguments": {"unexpected": "value"},
                "message": "Unknown argument",
            },
        ]
        for index, case in enumerate(cases, start=1):
            response = canvas_mcp_server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 200 + index,
                    "method": "tools/call",
                    "params": {"name": case["name"], "arguments": case["arguments"]},
                }
            )

            assert response is not None
            self.assertNotIn("result", response)
            self.assertEqual(response["error"]["code"], -32602)
            self.assertIn(case["message"], response["error"]["message"])

    def test_resource_errors_are_json_rpc_errors(self) -> None:
        response = canvas_mcp_server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 14,
                "method": "resources/read",
                "params": {"uri": "resource://not-canvas/missing"},
            }
        )

        assert response is not None
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32000)
        self.assertNotIn("result", response)

    def test_resource_read_uri_must_be_non_empty_string(self) -> None:
        for index, params in enumerate([{}, {"uri": None}, {"uri": 5}, {"uri": ""}], start=1):
            response = canvas_mcp_server.handle_request(
                {"jsonrpc": "2.0", "id": 300 + index, "method": "resources/read", "params": params}
            )

            assert response is not None
            self.assertEqual(response["error"]["code"], -32602)
            self.assertIn("uri must be a non-empty string", response["error"]["message"])
            self.assertNotIn("result", response)

    def test_valid_tool_execution_failures_are_tool_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            response = canvas_mcp_server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 400,
                    "method": "tools/call",
                    "params": {"name": "canvas_get", "arguments": {"id": "missing", "root": tmp}},
                }
            )

        assert response is not None
        self.assertNotIn("error", response)
        self.assertTrue(response["result"]["isError"])
        self.assertIn("Canvas not found", response["result"]["content"][0]["text"])

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
