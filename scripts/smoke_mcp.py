from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = Path.home() / ".codex" / "plugins" / "cache" / "personal" / "canvas"


class SmokeFailure(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_installed_plugin() -> Path:
    if not DEFAULT_CACHE_ROOT.exists():
        raise SmokeFailure(f"Installed canvas plugin cache not found: {DEFAULT_CACHE_ROOT}")
    candidates = [
        item
        for item in DEFAULT_CACHE_ROOT.iterdir()
        if item.is_dir() and (item / ".codex-plugin" / "plugin.json").exists() and (item / ".mcp.json").exists()
    ]
    if not candidates:
        raise SmokeFailure(f"No complete installed canvas plugin versions found under: {DEFAULT_CACHE_ROOT}")
    return max(candidates, key=lambda item: item.name)


def plugin_root(args: argparse.Namespace) -> Path:
    if args.installed:
        return Path(args.plugin_root).expanduser() if args.plugin_root else latest_installed_plugin()
    return Path(args.plugin_root).expanduser() if args.plugin_root else ROOT


def server_config(root: Path) -> tuple[list[str], Path]:
    manifest = load_json(root / ".codex-plugin" / "plugin.json")
    mcp_ref = manifest.get("mcpServers")
    if mcp_ref != "./.mcp.json":
        raise SmokeFailure(f"Expected plugin manifest mcpServers './.mcp.json', got {mcp_ref!r}")

    config = load_json(root / ".mcp.json")
    server = config["mcpServers"]["canvas"]
    command = [server["command"], *server["args"]]
    cwd = root if server.get("cwd") == "." else root / str(server.get("cwd", "."))
    return command, cwd


class McpClient:
    def __init__(self, command: list[str], cwd: Path, probe: bool = False):
        env = os.environ.copy()
        if probe:
            env["CANVAS_MCP_PROBE"] = "1"
        self.proc = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)

    def request(self, method: str, params: dict[str, Any] | None = None, request_id: int = 1) -> dict[str, Any]:
        if self.proc.stdin is None or self.proc.stdout is None:
            raise SmokeFailure("MCP process streams are not available")
        message = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
        self.proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            stderr = self.proc.stderr.read() if self.proc.stderr else ""
            raise SmokeFailure(f"MCP server closed before responding to {method}. stderr={stderr}")
        if line.lower().startswith("content-length:"):
            raise SmokeFailure("MCP server emitted Content-Length framing; Codex expects newline-delimited JSON")
        response = json.loads(line)
        if "error" in response:
            raise SmokeFailure(f"MCP error for {method}: {response['error']}")
        return response

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        if self.proc.stdin is None:
            raise SmokeFailure("MCP process stdin is not available")
        message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        self.proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()


def assert_tool_names(tools: list[dict[str, Any]]) -> None:
    names = {tool["name"] for tool in tools}
    required = {
        "canvas_init",
        "canvas_list",
        "canvas_get",
        "canvas_update_state",
        "canvas_validate",
        "canvas_archive",
        "canvas_promote",
        "canvas_export_html",
    }
    missing = sorted(required - names)
    if missing:
        raise SmokeFailure(f"Missing MCP tools: {missing}")


def tool_payload(response: dict[str, Any]) -> Any:
    result = response["result"]
    if result.get("isError"):
        raise SmokeFailure(f"MCP tool returned isError=true: {result}")
    return json.loads(result["content"][0]["text"])


def smoke(command: list[str], cwd: Path, canvas_id: str, probe: bool) -> dict[str, Any]:
    client = McpClient(command, cwd, probe=probe)
    try:
        init = client.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "clientInfo": {"name": "canvas-smoke", "version": "0.1.0"},
                "capabilities": {},
            },
            request_id=1,
        )
        capabilities = init["result"]["capabilities"]
        if "tools" not in capabilities:
            raise SmokeFailure(f"Initialize response did not advertise tools: {capabilities}")
        client.notify("notifications/initialized")

        listed = client.request("tools/list", request_id=2)
        assert_tool_names(listed["result"]["tools"])

        with tempfile.TemporaryDirectory() as tmp:
            created = tool_payload(
                client.request(
                    "tools/call",
                    {
                        "name": "canvas_init",
                        "arguments": {
                            "id": canvas_id,
                            "scope": "thread",
                            "title": "MCP Smoke",
                            "purpose": "automated MCP smoke test",
                            "root": tmp,
                        },
                    },
                    request_id=3,
                )
            )
            active = tool_payload(
                client.request(
                    "tools/call",
                    {"name": "canvas_validate", "arguments": {"id": canvas_id, "lifecycle": "active", "root": tmp}},
                    request_id=4,
                )
            )
            exported = tool_payload(
                client.request(
                    "tools/call",
                    {"name": "canvas_export_html", "arguments": {"id": canvas_id, "root": tmp}},
                    request_id=5,
                )
            )
            archived = tool_payload(
                client.request(
                    "tools/call",
                    {"name": "canvas_archive", "arguments": {"id": canvas_id, "root": tmp}},
                    request_id=6,
                )
            )
            archived_validation = tool_payload(
                client.request(
                    "tools/call",
                    {
                        "name": "canvas_validate",
                        "arguments": {"id": canvas_id, "lifecycle": "archived", "root": tmp},
                    },
                    request_id=7,
                )
            )
            archived_export = tool_payload(
                client.request(
                    "tools/call",
                    {
                        "name": "canvas_export_html",
                        "arguments": {"id": canvas_id, "lifecycle": "archived", "root": tmp},
                    },
                    request_id=8,
                )
            )

        if not active["valid"] or not archived_validation["valid"]:
            raise SmokeFailure(f"Validation failed: active={active} archived={archived_validation}")
        return {
            "server": {"command": command, "cwd": str(cwd)},
            "tools": [tool["name"] for tool in listed["result"]["tools"]],
            "created": created["id"],
            "exports": {"active": exported["valid"], "archived": archived_export["valid"]},
            "archived": archived["lifecycle"],
            "validations": {"active": active["valid"], "archived": archived_validation["valid"]},
        }
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the Canvas MCP server using Codex-compatible stdio.")
    parser.add_argument("--installed", action="store_true", help="Smoke-test the latest installed personal plugin cache.")
    parser.add_argument("--plugin-root", default="", help="Plugin root to test. Defaults to source root or latest cache.")
    parser.add_argument("--canvas-id", default="mcp-smoke", help="Throwaway canvas id for lifecycle calls.")
    parser.add_argument("--probe", action="store_true", help="Enable CANVAS_MCP_PROBE for this run.")
    args = parser.parse_args()

    root = plugin_root(args).resolve()
    command, cwd = server_config(root)
    result = smoke(command, cwd, args.canvas_id, args.probe)
    print(json.dumps({"ok": True, "plugin_root": str(root), **result}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
