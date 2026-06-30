from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from canvas_core import CanvasError, CanvasRegistry, CanvasValidationError  # noqa: E402


STARTUP_PROBE = Path(tempfile.gettempdir()) / "canvas-mcp-startup.jsonl"
TRAFFIC_PROBE = Path(tempfile.gettempdir()) / "canvas-mcp-traffic.jsonl"


def write_probe(path: Path, entry: dict[str, Any]) -> None:
    if os.environ.get("CANVAS_MCP_PROBE") != "1":
        return
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
                "human_actions": {"type": "array", "items": {"type": "string"}, "default": []},
                "agent_actions": {"type": "array", "items": {"type": "string"}, "default": []},
                "promotion_targets": {"type": "array", "items": {"type": "string"}, "default": []},
                "associatedThreads": {"type": "array", "items": {"type": "string"}, "default": []},
                "root": {"type": "string", "default": ""},
            },
            ["id", "scope"],
        ),
    },
    "canvas_list": {
        "description": "List canvases, optionally filtered by lifecycle or associated thread.",
        "inputSchema": schema(
            {
                "lifecycle": {"type": "string", "enum": ["active", "archived"]},
                "threadId": {"type": "string", "default": ""},
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
    "canvas_associate_thread": {
        "description": "Associate a thread id with an existing canvas.",
        "inputSchema": schema(
            {
                "id": {"type": "string"},
                "threadId": {"type": "string"},
                "lifecycle": {"type": "string", "enum": ["active", "archived"]},
                "root": {"type": "string", "default": ""},
            },
            ["id", "threadId"],
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
    "canvas_export_html": {
        "description": "Export a canvas to a static HTML surface for browser inspection.",
        "inputSchema": schema(
            {
                "id": {"type": "string"},
                "lifecycle": {"type": "string", "enum": ["active", "archived"]},
                "output": {"type": "string", "default": ""},
                "root": {"type": "string", "default": ""},
            },
            ["id"],
        ),
    },
}


def registry_from_args(args: dict[str, Any]) -> CanvasRegistry:
    root = args.get("root")
    return CanvasRegistry(Path(root) if root else None)


def validate_tool_args(name: str, args: Any) -> dict[str, Any]:
    if name not in TOOLS:
        raise CanvasValidationError(f"Unknown tool: {name}")
    if not isinstance(args, dict):
        raise CanvasValidationError("Tool arguments must be an object.")

    input_schema = TOOLS[name]["inputSchema"]
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])
    unknown = sorted(set(args) - set(properties))
    missing = [field for field in required if field not in args]
    if unknown:
        raise CanvasValidationError(f"Unknown argument(s) for {name}: {', '.join(unknown)}")
    if missing:
        raise CanvasValidationError(f"Missing required argument(s) for {name}: {', '.join(missing)}")

    for field, value in args.items():
        spec = properties[field]
        expected_type = spec.get("type")
        if expected_type == "string":
            if not isinstance(value, str):
                raise CanvasValidationError(f"{field} must be a string.")
            enum = spec.get("enum")
            if enum and value not in enum:
                raise CanvasValidationError(f"{field} must be one of {enum}.")
        elif expected_type == "object":
            if not isinstance(value, dict):
                raise CanvasValidationError(f"{field} must be an object.")
        elif expected_type == "array":
            if not isinstance(value, list):
                raise CanvasValidationError(f"{field} must be an array.")
            item_type = spec.get("items", {}).get("type")
            if item_type == "string" and not all(isinstance(item, str) for item in value):
                raise CanvasValidationError(f"{field} must be an array of strings.")
    return args


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
    if name not in TOOLS:
        return as_tool_result({"error": {"type": "UnknownTool", "message": f"Unknown tool: {name}"}}, True)
    args = validate_tool_args(name, args)
    registry = registry_from_args(args)
    if name == "canvas_init":
        return as_tool_result(
            registry.init_canvas(
                args["id"],
                scope=args["scope"],
                anchor=args.get("anchor", ""),
                title=args.get("title", ""),
                purpose=args.get("purpose", ""),
                human_actions=args.get("human_actions") or None,
                agent_actions=args.get("agent_actions") or None,
                promotion_targets=args.get("promotion_targets") or None,
                associated_threads=args.get("associatedThreads") or None,
            )
        )
    if name == "canvas_list":
        return as_tool_result(registry.list_canvases(args.get("lifecycle"), args.get("threadId")))
    if name == "canvas_get":
        return as_tool_result(registry.get_canvas(args["id"], args.get("lifecycle")))
    if name == "canvas_update_state":
        return as_tool_result(registry.update_state(args["id"], args.get("updates", {})))
    if name == "canvas_validate":
        return as_tool_result(registry.validate_canvas(args["id"], args.get("lifecycle")))
    if name == "canvas_archive":
        return as_tool_result(registry.archive_canvas(args["id"]))
    if name == "canvas_associate_thread":
        return as_tool_result(
            registry.associate_thread(args["id"], thread_id=args["threadId"], lifecycle=args.get("lifecycle") or "active")
        )
    if name == "canvas_promote":
        return as_tool_result(
            registry.promote_canvas(
                args["id"],
                target=args["target"],
                reference=args["reference"],
                note=args.get("note", ""),
            )
        )
    if name == "canvas_export_html":
        return as_tool_result(
            registry.export_html(
                args["id"],
                lifecycle=args.get("lifecycle"),
                output=args.get("output") or None,
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
    is_notification = "id" not in message

    if method is None:
        write_probe(TRAFFIC_PROBE, {"event": "ignored_non_request", "message": message})
        return None
    if is_notification:
        write_probe(TRAFFIC_PROBE, {"event": "ignored_notification", "method": method})
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
            try:
                result = call_tool(params.get("name", ""), params.get("arguments") or {})
            except CanvasError as exc:
                result = as_tool_result(
                    {"error": {"type": exc.__class__.__name__, "message": str(exc), "recoverable": True}},
                    True,
                )
        elif method == "resources/list":
            result = list_resources()
        elif method == "resources/read":
            try:
                result = read_resource(params.get("uri", ""))
            except CanvasError as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": str(exc)},
                }
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
            "error": {"code": -32000, "message": str(exc)},
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
