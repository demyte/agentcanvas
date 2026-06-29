from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from canvas_core import CanvasError, CanvasRegistry  # noqa: E402


STARTUP_PROBE = Path(tempfile.gettempdir()) / "canvas-mcp-startup.jsonl"
TRAFFIC_PROBE = Path(tempfile.gettempdir()) / "canvas-mcp-traffic.jsonl"


def write_probe(path: Path, entry: dict[str, Any]) -> None:
    payload = {
        "timestamp": dt.datetime.now(dt.UTC).isoformat(),
        **entry,
    }
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
    except OSError:
        pass


def schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


TOOLS: dict[str, dict[str, Any]] = {
    "canvas_init": {
        "description": "Create a semi-persistent canvas workspace.",
        "inputSchema": schema(
            {
                "id": {"type": "string"},
                "scope": {"type": "string", "enum": ["repo", "project", "thread", "user"]},
                "anchor": {"type": "string", "default": ""},
                "title": {"type": "string", "default": ""},
                "purpose": {"type": "string", "default": ""},
                "root": {"type": "string", "default": ""},
            },
            ["id", "scope"],
        ),
    },
    "canvas_list": {
        "description": "List active and archived canvases.",
        "inputSchema": schema(
            {
                "lifecycle": {"type": "string", "enum": ["active", "archived"]},
                "root": {"type": "string", "default": ""},
            }
        ),
    },
    "canvas_get": {
        "description": "Read canvas metadata.",
        "inputSchema": schema(
            {
                "id": {"type": "string"},
                "lifecycle": {"type": "string", "enum": ["active", "archived"]},
                "root": {"type": "string", "default": ""},
            },
            ["id"],
        ),
    },
    "canvas_update_state": {
        "description": "Shallow-merge fields into a canvas state.json file.",
        "inputSchema": schema(
            {
                "id": {"type": "string"},
                "updates": {"type": "object"},
                "root": {"type": "string", "default": ""},
            },
            ["id", "updates"],
        ),
    },
    "canvas_validate": {
        "description": "Validate a canvas metadata/state layout.",
        "inputSchema": schema(
            {
                "id": {"type": "string"},
                "lifecycle": {"type": "string", "enum": ["active", "archived"]},
                "root": {"type": "string", "default": ""},
            },
            ["id"],
        ),
    },
    "canvas_archive": {
        "description": "Move an active canvas to archived.",
        "inputSchema": schema(
            {
                "id": {"type": "string"},
                "root": {"type": "string", "default": ""},
            },
            ["id"],
        ),
    },
    "canvas_promote": {
        "description": "Record an explicit promotion target/reference for a canvas.",
        "inputSchema": schema(
            {
                "id": {"type": "string"},
                "target": {"type": "string"},
                "reference": {"type": "string"},
                "note": {"type": "string", "default": ""},
                "root": {"type": "string", "default": ""},
            },
            ["id", "target", "reference"],
        ),
    },
}


def registry_from_args(args: dict[str, Any]) -> CanvasRegistry:
    root = args.get("root")
    return CanvasRegistry(Path(root) if root else None)


def as_tool_result(data: Any, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(data, indent=2, sort_keys=False),
            }
        ],
        "isError": is_error,
    }


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    registry = registry_from_args(args)
    if name == "canvas_init":
        return as_tool_result(
            registry.init_canvas(
                args["id"],
                scope=args["scope"],
                anchor=args.get("anchor", ""),
                title=args.get("title", ""),
                purpose=args.get("purpose", ""),
            )
        )
    if name == "canvas_list":
        return as_tool_result(registry.list_canvases(args.get("lifecycle")))
    if name == "canvas_get":
        return as_tool_result(registry.get_canvas(args["id"], args.get("lifecycle")))
    if name == "canvas_update_state":
        return as_tool_result(registry.update_state(args["id"], args.get("updates", {})))
    if name == "canvas_validate":
        return as_tool_result(registry.validate_canvas(args["id"], args.get("lifecycle")))
    if name == "canvas_archive":
        return as_tool_result(registry.archive_canvas(args["id"]))
    if name == "canvas_promote":
        return as_tool_result(
            registry.promote_canvas(
                args["id"],
                target=args["target"],
                reference=args["reference"],
                note=args.get("note", ""),
            )
        )
    return as_tool_result({"error": {"type": "UnknownTool", "message": f"Unknown tool: {name}"}}, True)


def list_resources() -> dict[str, Any]:
    return {
        "resources": [
            {
                "uri": "resource://canvas/active",
                "name": "Active canvases",
                "description": "Active canvas metadata records.",
                "mimeType": "application/json",
            },
            {
                "uri": "resource://canvas/archived",
                "name": "Archived canvases",
                "description": "Archived canvas metadata records.",
                "mimeType": "application/json",
            },
        ]
    }


def read_resource(uri: str) -> dict[str, Any]:
    registry = CanvasRegistry()
    if uri == "resource://canvas/active":
        data = registry.list_canvases("active")
    elif uri == "resource://canvas/archived":
        data = registry.list_canvases("archived")
    elif uri.startswith("resource://canvas/"):
        data = registry.get_canvas(uri.rsplit("/", 1)[-1])
    else:
        raise CanvasError(f"Unknown resource URI: {uri}")
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(data, indent=2, sort_keys=False),
            }
        ]
    }


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    if method is None:
        write_probe(TRAFFIC_PROBE, {"event": "ignored_non_request", "message": message})
        return None

    try:
        if method == "initialize":
            result = {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"listChanged": False},
                },
                "serverInfo": {"name": "canvas", "version": "0.1.0"},
            }
        elif method == "notifications/initialized":
            return None
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {
                "tools": [{"name": name, **definition} for name, definition in TOOLS.items()],
                "nextCursor": None,
            }
        elif method == "tools/call":
            result = call_tool(params.get("name", ""), params.get("arguments") or {})
        elif method == "resources/list":
            result = list_resources()
        elif method == "resources/read":
            result = read_resource(params.get("uri", ""))
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except CanvasError as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": as_tool_result(
                {"error": {"type": exc.__class__.__name__, "message": str(exc), "recoverable": True}},
                True,
            ),
        }
    except Exception as exc:  # noqa: BLE001 - convert unknown failures into JSON-RPC errors.
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32603, "message": str(exc)},
        }


def read_message(stream: BinaryIO) -> dict[str, Any] | None:
    first = stream.readline()
    if not first:
        return None
    if first.lower().startswith(b"content-length:"):
        length = int(first.split(b":", 1)[1].strip())
        while True:
            line = stream.readline()
            if line in {b"\r\n", b"\n", b""}:
                break
        body = stream.read(length)
        if not body:
            return None
        message = json.loads(body.decode("utf-8"))
        write_probe(TRAFFIC_PROBE, {"event": "request", "message": message})
        return message
    stripped = first.strip()
    if not stripped:
        return read_message(stream)
    message = json.loads(stripped.decode("utf-8"))
    write_probe(TRAFFIC_PROBE, {"event": "request", "message": message})
    return message


def write_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    write_probe(TRAFFIC_PROBE, {"event": "response", "message": message})
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    stream.write(body)
    stream.write(b"\n")
    stream.flush()


def write_startup_probe() -> None:
    write_probe(STARTUP_PROBE, {
        "event": "canvas_mcp_start",
        "script": str(Path(__file__).resolve()),
        "cwd": str(Path.cwd()),
        "executable": sys.executable,
        "argv": sys.argv,
    })


def main() -> int:
    write_startup_probe()
    input_stream = sys.stdin.buffer
    output_stream = sys.stdout.buffer
    while True:
        message = read_message(input_stream)
        if message is None:
            return 0
        response = handle_request(message)
        if response is not None:
            write_message(output_stream, response)


if __name__ == "__main__":
    raise SystemExit(main())
