from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from canvas_core import CanvasError, CanvasRegistry


TOOL_NAMES = {
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


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=False))


def call_tool(name: str, payload: dict[str, Any], root: Path | None = None) -> Any:
    if name not in TOOL_NAMES:
        raise CanvasError(f"Unknown canvas tool: {name}")
    registry = CanvasRegistry(Path(payload["root"]) if payload.get("root") else root)
    if name == "canvas_init":
        return registry.init_canvas(
            payload["id"],
            scope=payload["scope"],
            anchor=payload.get("anchor", ""),
            title=payload.get("title", ""),
            purpose=payload.get("purpose", ""),
            human_actions=payload.get("human_actions") or None,
            agent_actions=payload.get("agent_actions") or None,
            promotion_targets=payload.get("promotion_targets") or None,
            associated_threads=payload.get("associatedThreads") or None,
        )
    if name == "canvas_list":
        return registry.list_canvases(payload.get("lifecycle"), payload.get("threadId"))
    if name == "canvas_get":
        return registry.get_canvas(payload["id"], payload.get("lifecycle"))
    if name == "canvas_update_state":
        return registry.update_state(payload["id"], payload.get("updates", {}))
    if name == "canvas_validate":
        return registry.validate_canvas(payload["id"], payload.get("lifecycle"))
    if name == "canvas_archive":
        return registry.archive_canvas(payload["id"])
    if name == "canvas_associate_thread":
        return registry.associate_thread(
            payload["id"],
            thread_id=payload["threadId"],
            lifecycle=payload.get("lifecycle") or "active",
        )
    if name == "canvas_promote":
        return registry.promote_canvas(
            payload["id"],
            target=payload["target"],
            reference=payload["reference"],
            note=payload.get("note", ""),
        )
    if name == "canvas_export_html":
        return registry.export_html(
            payload["id"],
            lifecycle=payload.get("lifecycle"),
            output=payload.get("output") or None,
        )
    raise CanvasError(f"Unknown canvas tool: {name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="canvas", description="Manage local Codex canvases.")
    parser.add_argument("--root", type=Path, help="Canvas root. Defaults to CANVAS_ROOT or ~/.agents/canvas.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a canvas.")
    init.add_argument("id")
    init.add_argument("--scope", required=True, choices=["repo", "project", "thread", "user"])
    init.add_argument("--anchor", default="")
    init.add_argument("--title", default="")
    init.add_argument("--purpose", default="")
    init.add_argument("--human-action", dest="human_actions", action="append")
    init.add_argument("--agent-action", dest="agent_actions", action="append")
    init.add_argument("--promotion-target", dest="promotion_targets", action="append")
    init.add_argument("--associated-thread", dest="associated_threads", action="append")

    list_cmd = sub.add_parser("list", help="List canvases.")
    list_cmd.add_argument("--lifecycle", choices=["active", "archived"])
    list_cmd.add_argument("--thread-id", dest="thread_id")

    get = sub.add_parser("get", help="Read canvas metadata.")
    get.add_argument("id")
    get.add_argument("--lifecycle", choices=["active", "archived"])

    validate = sub.add_parser("validate", help="Validate a canvas.")
    validate.add_argument("id")
    validate.add_argument("--lifecycle", choices=["active", "archived"])

    archive = sub.add_parser("archive", help="Archive a canvas.")
    archive.add_argument("id")

    associate_thread = sub.add_parser("associate-thread", help="Associate a thread id with a canvas.")
    associate_thread.add_argument("id")
    associate_thread.add_argument("thread_id")
    associate_thread.add_argument("--lifecycle", choices=["active", "archived"], default="active")

    promote = sub.add_parser("promote", help="Record an explicit promotion.")
    promote.add_argument("id")
    promote.add_argument("--target", required=True)
    promote.add_argument("--reference", required=True)
    promote.add_argument("--note", default="")

    export_html = sub.add_parser("export-html", help="Export a canvas to static HTML.")
    export_html.add_argument("id")
    export_html.add_argument("--lifecycle", choices=["active", "archived"])
    export_html.add_argument("--output", default="")

    update_state = sub.add_parser("update-state", help="Shallow-merge JSON into state.json.")
    update_state.add_argument("id")
    update_state.add_argument("json")

    tool = sub.add_parser("tool", help="Run a JSON canvas operation by tool-compatible name.")
    tool.add_argument("name", choices=sorted(TOOL_NAMES))
    tool.add_argument("json", help="JSON object containing the operation arguments.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    registry = CanvasRegistry(args.root)
    try:
        if args.command == "init":
            print_json(
                registry.init_canvas(
                    args.id,
                    scope=args.scope,
                    anchor=args.anchor,
                    title=args.title,
                    purpose=args.purpose,
                    human_actions=args.human_actions,
                    agent_actions=args.agent_actions,
                    promotion_targets=args.promotion_targets,
                    associated_threads=args.associated_threads,
                )
            )
        elif args.command == "list":
            print_json(registry.list_canvases(args.lifecycle, args.thread_id))
        elif args.command == "get":
            print_json(registry.get_canvas(args.id, args.lifecycle))
        elif args.command == "validate":
            result = registry.validate_canvas(args.id, args.lifecycle)
            print_json(result)
            return 0 if result["valid"] else 2
        elif args.command == "archive":
            print_json(registry.archive_canvas(args.id))
        elif args.command == "associate-thread":
            print_json(registry.associate_thread(args.id, thread_id=args.thread_id, lifecycle=args.lifecycle))
        elif args.command == "promote":
            print_json(registry.promote_canvas(args.id, target=args.target, reference=args.reference, note=args.note))
        elif args.command == "export-html":
            print_json(registry.export_html(args.id, lifecycle=args.lifecycle, output=args.output or None))
        elif args.command == "update-state":
            print_json(registry.update_state(args.id, json.loads(args.json)))
        elif args.command == "tool":
            payload = json.loads(args.json)
            if not isinstance(payload, dict):
                raise CanvasError("tool payload must be a JSON object")
            print_json(call_tool(args.name, payload, args.root))
        else:
            parser.error(f"Unknown command: {args.command}")
    except CanvasError as exc:
        print_json({"error": {"type": exc.__class__.__name__, "message": str(exc), "recoverable": True}})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
