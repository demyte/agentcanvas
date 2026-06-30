from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from canvas_core import CanvasError, CanvasRegistry


HELP_TEXT = """\
Canvas CLI

Commands:
  init              Create a canvas.
  list              List active and/or archived canvases.
  get               Read canvas metadata.
  update-state      Merge state updates into state.json.
  validate          Validate a canvas folder.
  export-html       Export canvas.html and canvas-data.js.
  associate-thread  Associate a Codex thread id with a canvas.
  promote           Record an explicit durable promotion reference.
  archive           Move an active canvas to archived lifecycle.

Common options:
  -root, --root PATH      Canvas root. Defaults to CANVAS_ROOT or ~/.agents/canvas.
  -h, --help, -?         Show help.

Examples:
  canvas init -id review-board -scope repo -anchor D:\\Projects\\repo -purpose "Track review work"
  canvas update-state -id review-board -set status=reviewing -set owner=codex
  canvas update-state -id review-board -merge-file .\\state-update.json
  canvas validate -id review-board
  canvas export-html -id review-board
  canvas list -lifecycle active
"""


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=False))


def add_help_alias(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-?", action="help", help="Show this help message and exit.")


def add_root_argument(parser: argparse.ArgumentParser, *, suppress_default: bool = False) -> None:
    kwargs: dict[str, Any] = {
        "type": Path,
        "help": "Canvas root. Defaults to CANVAS_ROOT or ~/.agents/canvas.",
    }
    if suppress_default:
        kwargs["default"] = argparse.SUPPRESS
    parser.add_argument("-root", "--root", **kwargs)


def add_id_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("legacy_id", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("-id", "--id", dest="id", help="Canvas id.")


def required_id(args: argparse.Namespace) -> str:
    canvas_id = args.id or args.legacy_id
    if not canvas_id:
        raise CanvasError("Canvas id is required. Use -id <canvas-id>.")
    return canvas_id


def set_nested(data: dict[str, Any], dotted_key: str, value: str) -> None:
    parts = [part for part in dotted_key.split(".") if part]
    if not parts:
        raise CanvasError("--set keys must not be empty")
    target = data
    for part in parts[:-1]:
        current = target.get(part)
        if current is None:
            current = {}
            target[part] = current
        if not isinstance(current, dict):
            raise CanvasError(f"Cannot set nested value under non-object key: {part}")
        target = current
    target[parts[-1]] = value


def state_updates(args: argparse.Namespace) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for raw_path in args.merge_files or []:
        path = Path(raw_path).expanduser()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CanvasError(f"Unable to read state merge file {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise CanvasError(f"State merge file must contain a JSON object: {path}")
        updates.update(payload)
    for raw_value in args.set_values or []:
        if "=" not in raw_value:
            raise CanvasError("--set values must use KEY=VALUE")
        key, value = raw_value.split("=", 1)
        set_nested(updates, key.strip(), value)
    if not updates:
        raise CanvasError("No state updates supplied. Use -set KEY=VALUE or -merge-file PATH.")
    return updates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="canvas",
        description="Manage local Codex canvases.",
        epilog=HELP_TEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_help_alias(parser)
    add_root_argument(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a canvas.", formatter_class=argparse.RawDescriptionHelpFormatter)
    add_help_alias(init)
    add_root_argument(init, suppress_default=True)
    add_id_argument(init)
    init.add_argument("-scope", "--scope", required=True, choices=["repo", "project", "thread", "user"], help="Logical canvas scope.")
    init.add_argument("-anchor", "--anchor", default="", help="Repo/project path or other logical anchor.")
    init.add_argument("-title", "--title", default="", help="Human-readable title. Defaults to the normalized id.")
    init.add_argument("-purpose", "--purpose", default="", help="Short explanation of what this canvas is for.")
    init.add_argument("-human-action", "--human-action", dest="human_actions", action="append", help="Allowed human action. Repeatable.")
    init.add_argument("-agent-action", "--agent-action", dest="agent_actions", action="append", help="Allowed agent action. Repeatable.")
    init.add_argument("-promotion-target", "--promotion-target", dest="promotion_targets", action="append", help="Allowed promotion target. Repeatable.")
    init.add_argument("-associated-thread", "--associated-thread", dest="associated_threads", action="append", help="Codex thread id to associate. Repeatable.")

    list_cmd = sub.add_parser("list", help="List canvases.")
    add_help_alias(list_cmd)
    add_root_argument(list_cmd, suppress_default=True)
    list_cmd.add_argument("-lifecycle", "--lifecycle", choices=["active", "archived"], help="Filter by lifecycle.")
    list_cmd.add_argument("-thread-id", "--thread-id", dest="thread_id", help="Filter to canvases associated with this thread id.")

    get = sub.add_parser("get", help="Read canvas metadata.")
    add_help_alias(get)
    add_root_argument(get, suppress_default=True)
    add_id_argument(get)
    get.add_argument("-lifecycle", "--lifecycle", choices=["active", "archived"], help="Read only from this lifecycle.")

    validate = sub.add_parser("validate", help="Validate a canvas.")
    add_help_alias(validate)
    add_root_argument(validate, suppress_default=True)
    add_id_argument(validate)
    validate.add_argument("-lifecycle", "--lifecycle", choices=["active", "archived"], help="Validate only from this lifecycle.")

    archive = sub.add_parser("archive", help="Archive a canvas.")
    add_help_alias(archive)
    add_root_argument(archive, suppress_default=True)
    add_id_argument(archive)

    associate_thread = sub.add_parser("associate-thread", help="Associate a thread id with a canvas.")
    add_help_alias(associate_thread)
    add_root_argument(associate_thread, suppress_default=True)
    add_id_argument(associate_thread)
    associate_thread.add_argument("legacy_thread_id", nargs="?", help=argparse.SUPPRESS)
    associate_thread.add_argument("-thread-id", "--thread-id", dest="thread_id", help="Codex thread id to associate.")
    associate_thread.add_argument("-lifecycle", "--lifecycle", choices=["active", "archived"], default="active", help="Canvas lifecycle to update. Defaults to active.")

    promote = sub.add_parser("promote", help="Record an explicit promotion.")
    add_help_alias(promote)
    add_root_argument(promote, suppress_default=True)
    add_id_argument(promote)
    promote.add_argument("-target", "--target", required=True, help="Promotion target declared on the canvas.")
    promote.add_argument("-reference", "--reference", required=True, help="Durable destination reference, such as a doc path or issue URL.")
    promote.add_argument("-note", "--note", default="", help="Optional note to store with the promotion record.")

    export_html = sub.add_parser("export-html", help="Export a canvas to static HTML.")
    add_help_alias(export_html)
    add_root_argument(export_html, suppress_default=True)
    add_id_argument(export_html)
    export_html.add_argument("-lifecycle", "--lifecycle", choices=["active", "archived"], help="Export from this lifecycle.")
    export_html.add_argument("-output", "--output", default="", help="Output HTML path. Relative paths are resolved inside the canvas folder.")

    update_state = sub.add_parser("update-state", help="Merge values into state.json.")
    add_help_alias(update_state)
    add_root_argument(update_state, suppress_default=True)
    add_id_argument(update_state)
    update_state.add_argument("-set", "--set", dest="set_values", action="append", metavar="KEY=VALUE", help="Set a string value. Dot notation creates nested objects. Repeatable.")
    update_state.add_argument("-merge-file", "--merge-file", dest="merge_files", action="append", metavar="PATH", help="Merge a JSON object from a file. Repeatable.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    registry = CanvasRegistry(args.root)
    try:
        if args.command == "init":
            print_json(
                registry.init_canvas(
                    required_id(args),
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
            print_json(registry.get_canvas(required_id(args), args.lifecycle))
        elif args.command == "validate":
            result = registry.validate_canvas(required_id(args), args.lifecycle)
            print_json(result)
            return 0 if result["valid"] else 2
        elif args.command == "archive":
            print_json(registry.archive_canvas(required_id(args)))
        elif args.command == "associate-thread":
            thread_id = args.thread_id or args.legacy_thread_id
            if not thread_id:
                raise CanvasError("Thread id is required. Use -thread-id <thread-id>.")
            print_json(registry.associate_thread(required_id(args), thread_id=thread_id, lifecycle=args.lifecycle))
        elif args.command == "promote":
            print_json(registry.promote_canvas(required_id(args), target=args.target, reference=args.reference, note=args.note))
        elif args.command == "export-html":
            print_json(registry.export_html(required_id(args), lifecycle=args.lifecycle, output=args.output or None))
        elif args.command == "update-state":
            print_json(registry.update_state(required_id(args), state_updates(args)))
        else:
            parser.error(f"Unknown command: {args.command}")
    except CanvasError as exc:
        print_json({"error": {"type": exc.__class__.__name__, "message": str(exc), "recoverable": True}})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
