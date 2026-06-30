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


def source_plugin_version() -> str:
    manifest = load_json(ROOT / ".codex-plugin" / "plugin.json")
    version = manifest.get("version")
    if not isinstance(version, str) or not version.strip():
        raise SmokeFailure("Source plugin manifest is missing a non-empty version")
    return version


def latest_installed_plugin(expected_version: str | None = None) -> Path:
    if not DEFAULT_CACHE_ROOT.exists():
        raise SmokeFailure(f"Installed canvas plugin cache not found: {DEFAULT_CACHE_ROOT}")
    candidates = [
        item
        for item in DEFAULT_CACHE_ROOT.iterdir()
        if item.is_dir() and (item / ".codex-plugin" / "plugin.json").exists() and (item / ".mcp.json").exists()
    ]
    if not candidates:
        raise SmokeFailure(f"No complete installed canvas plugin versions found under: {DEFAULT_CACHE_ROOT}")
    if expected_version:
        expected = DEFAULT_CACHE_ROOT / expected_version
        if expected not in candidates:
            raise SmokeFailure(f"Installed canvas plugin version {expected_version!r} not found under: {DEFAULT_CACHE_ROOT}")
        return expected
    return max(candidates, key=lambda item: item.name)


def plugin_root(args: argparse.Namespace) -> Path:
    if args.installed:
        expected_version = args.expected_version or source_plugin_version()
        root = Path(args.plugin_root).expanduser() if args.plugin_root else latest_installed_plugin(expected_version)
        manifest = load_json(root / ".codex-plugin" / "plugin.json")
        actual_version = manifest.get("version")
        if actual_version != expected_version:
            raise SmokeFailure(f"Installed plugin version {actual_version!r} does not match expected {expected_version!r}")
        return root
    return Path(args.plugin_root).expanduser() if args.plugin_root else ROOT


def server_config(root: Path) -> tuple[list[str], Path]:
    root = root.resolve()
    manifest = load_json(root / ".codex-plugin" / "plugin.json")
    mcp_ref = manifest.get("mcpServers")
    if mcp_ref != "./.mcp.json":
        raise SmokeFailure(f"Expected plugin manifest mcpServers './.mcp.json', got {mcp_ref!r}")

    config = load_json(root / ".mcp.json")
    server = config["mcpServers"]["canvas"]
    command_name = server.get("command")
    if command_name != "python":
        raise SmokeFailure(f"Canvas MCP command must be 'python', got {command_name!r}")
    args = server.get("args")
    if not isinstance(args, list) or not args:
        raise SmokeFailure("Canvas MCP args must be a non-empty array")
    for arg in args:
        path = Path(str(arg))
        if path.is_absolute() or ".." in path.parts:
            raise SmokeFailure(f"Canvas MCP args must be plugin-relative paths, got {arg!r}")
    entrypoint = (root / str(args[0])).resolve()
    try:
        entrypoint.relative_to(root)
    except ValueError as exc:
        raise SmokeFailure(f"Canvas MCP entrypoint must resolve under the plugin root: {args[0]!r}") from exc
    if not entrypoint.exists():
        raise SmokeFailure(f"Canvas MCP entrypoint does not exist: {entrypoint}")
    cwd_config = server.get("cwd")
    if cwd_config != ".":
        raise SmokeFailure(f"Canvas MCP cwd must be '.', got {cwd_config!r}")
    command = [command_name, *args]
    cwd = root
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
        "canvas_associate_thread",
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
                            "associatedThreads": ["thread-smoke", "thread-shared"],
                            "root": tmp,
                        },
                    },
                    request_id=3,
                )
            )
            listed_by_thread = tool_payload(
                client.request(
                    "tools/call",
                    {"name": "canvas_list", "arguments": {"threadId": "thread-smoke", "root": tmp}},
                    request_id=30,
                )
            )
            associated = tool_payload(
                client.request(
                    "tools/call",
                    {
                        "name": "canvas_associate_thread",
                        "arguments": {"id": canvas_id, "threadId": "thread-associated-smoke", "root": tmp},
                    },
                    request_id=31,
                )
            )
            listed_by_associated_thread = tool_payload(
                client.request(
                    "tools/call",
                    {"name": "canvas_list", "arguments": {"threadId": "thread-associated-smoke", "root": tmp}},
                    request_id=32,
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
        if [item["id"] for item in listed_by_thread] != [canvas_id]:
            raise SmokeFailure(f"Thread-filtered list was unexpected: {listed_by_thread}")
        if [item["id"] for item in listed_by_associated_thread] != [canvas_id]:
            raise SmokeFailure(f"Associated thread-filtered list was unexpected: {listed_by_associated_thread}")
        return {
            "server": {"command": command, "cwd": str(cwd)},
            "tools": [tool["name"] for tool in listed["result"]["tools"]],
            "created": created["id"],
            "associatedThreads": associated["associatedThreads"],
            "exports": {"active": exported["valid"], "archived": archived_export["valid"]},
            "archived": archived["lifecycle"],
            "validations": {"active": active["valid"], "archived": archived_validation["valid"]},
        }
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the Canvas MCP server using Codex-compatible stdio.")
    parser.add_argument("--installed", action="store_true", help="Smoke-test the installed personal plugin cache matching the source manifest.")
    parser.add_argument("--plugin-root", default="", help="Plugin root to test. Defaults to source root, or in installed mode to the cache matching the expected version.")
    parser.add_argument("--expected-version", default="", help="Expected installed plugin version. Defaults to source manifest.")
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
