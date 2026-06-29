from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from canvas_core import CanvasError, CanvasRegistry


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="canvas", description="Manage local Codex canvases.")
    parser.add_argument("--root", type=Path, help="Canvas root. Defaults to CANVAS_ROOT or Documents/Codex/canvases.")
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

    list_cmd = sub.add_parser("list", help="List canvases.")
    list_cmd.add_argument("--lifecycle", choices=["active", "archived"])

    get = sub.add_parser("get", help="Read canvas metadata.")
    get.add_argument("id")
    get.add_argument("--lifecycle", choices=["active", "archived"])

    validate = sub.add_parser("validate", help="Validate a canvas.")
    validate.add_argument("id")
    validate.add_argument("--lifecycle", choices=["active", "archived"])

    archive = sub.add_parser("archive", help="Archive a canvas.")
    archive.add_argument("id")

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
                )
            )
        elif args.command == "list":
            print_json(registry.list_canvases(args.lifecycle))
        elif args.command == "get":
            print_json(registry.get_canvas(args.id, args.lifecycle))
        elif args.command == "validate":
            result = registry.validate_canvas(args.id, args.lifecycle)
            print_json(result)
            return 0 if result["valid"] else 2
        elif args.command == "archive":
            print_json(registry.archive_canvas(args.id))
        elif args.command == "promote":
            print_json(registry.promote_canvas(args.id, target=args.target, reference=args.reference, note=args.note))
        elif args.command == "export-html":
            print_json(registry.export_html(args.id, lifecycle=args.lifecycle, output=args.output or None))
        elif args.command == "update-state":
            print_json(registry.update_state(args.id, json.loads(args.json)))
        else:
            parser.error(f"Unknown command: {args.command}")
    except CanvasError as exc:
        print_json({"error": {"type": exc.__class__.__name__, "message": str(exc), "recoverable": True}})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
