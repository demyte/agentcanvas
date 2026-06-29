from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

from smoke_mcp import McpClient, SmokeFailure, latest_installed_plugin, server_config, tool_payload


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".canvas-test-output"


def call_tool(client: McpClient, name: str, arguments: dict[str, Any], request_id: int) -> Any:
    return tool_payload(
        client.request(
            "tools/call",
            {"name": name, "arguments": arguments},
            request_id=request_id,
        )
    )


def call_tool_error(client: McpClient, name: str, arguments: dict[str, Any], request_id: int) -> dict[str, Any]:
    response = client.request(
        "tools/call",
        {"name": name, "arguments": arguments},
        request_id=request_id,
    )
    result = response["result"]
    if not result.get("isError"):
        raise SmokeFailure(f"Expected {name} to fail, got success: {result}")
    return json.loads(result["content"][0]["text"])


def ensure_contains(path: Path, expected: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [item for item in expected if item not in text]
    if missing:
        raise SmokeFailure(f"{path} missing expected text: {missing}")


def scenario_repo_review(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-repo-architecture-review"
    init = call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "repo",
            "anchor": str(ROOT),
            "title": "Canvas Repo Architecture Review",
            "purpose": "Track plugin architecture risks without writing working files into the repo.",
            "root": str(root),
        },
        request_id,
    )
    request_id += 1
    state = call_tool(
        client,
        "canvas_update_state",
        {
            "id": canvas_id,
            "root": str(root),
            "updates": {
                "items": [
                    {"id": "api", "status": "reviewing", "label": "MCP tools cover lifecycle"},
                    {"id": "storage", "status": "accepted", "label": "Repo is anchor, not storage"},
                ],
                "decisions": ["Keep canvas artifacts external to the repository by default."],
                "open_questions": ["Should future app surfaces use a local web app or static HTML first?"],
            },
        },
        request_id,
    )
    request_id += 1
    fetched = call_tool(client, "canvas_get", {"id": canvas_id, "root": str(root)}, request_id)
    request_id += 1
    validation = call_tool(client, "canvas_validate", {"id": canvas_id, "root": str(root)}, request_id)
    request_id += 1
    export = call_tool(client, "canvas_export_html", {"id": canvas_id, "root": str(root)}, request_id)
    request_id += 1
    html_path = Path(export["html_path"])
    ensure_contains(html_path, ["Canvas Repo Architecture Review", "Repo is anchor, not storage", "valid: true"])
    if str(ROOT) == init["storage_path"]:
        raise SmokeFailure("Repo scenario stored the canvas directly in the repo anchor.")
    return request_id, {
        "name": "Repo architecture review",
        "id": canvas_id,
        "passed": validation["valid"] and fetched["scope"] == "repo" and state["metadata"]["scope"] == "repo",
        "html_path": str(html_path),
        "checks": ["init", "update_state", "get", "validate", "export_html", "external storage"],
    }


def scenario_project_dashboard(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-summerton-dashboard-promotion"
    call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "project",
            "anchor": r"C:\Users\james\OneDrive\Private\Shared-Summerton\ai",
            "title": "Summerton Dashboard Promotion Candidate",
            "purpose": "Model a canvas that can later be promoted into a project hub/dashboard.",
            "root": str(root),
        },
        request_id,
    )
    request_id += 1
    call_tool(
        client,
        "canvas_update_state",
        {
            "id": canvas_id,
            "root": str(root),
            "updates": {
                "dashboard_tiles": [
                    {"title": "Source filing", "state": "ready-for-review"},
                    {"title": "Flagged email triage", "state": "needs-refresh"},
                ],
                "decisions": ["Promotion requires discoverability through the project hub, not just an HTML file."],
            },
        },
        request_id,
    )
    request_id += 1
    promoted = call_tool(
        client,
        "canvas_promote",
        {
            "id": canvas_id,
            "target": "project-dashboard",
            "reference": "project-hub.html#canvas-summerton-dashboard",
            "note": "scenario-only promotion record",
            "root": str(root),
        },
        request_id,
    )
    request_id += 1
    validation = call_tool(client, "canvas_validate", {"id": canvas_id, "root": str(root)}, request_id)
    request_id += 1
    export = call_tool(client, "canvas_export_html", {"id": canvas_id, "root": str(root)}, request_id)
    request_id += 1
    html_path = Path(export["html_path"])
    ensure_contains(html_path, ["Summerton Dashboard Promotion Candidate", "project-dashboard", "scenario-only"])
    return request_id, {
        "name": "Project dashboard promotion",
        "id": canvas_id,
        "passed": validation["valid"] and promoted["promotions"][-1]["target"] == "project-dashboard",
        "html_path": str(html_path),
        "checks": ["project scope", "dashboard state", "promote", "validate", "export_html"],
    }


def scenario_thread_research(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-thread-research-brief"
    call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "thread",
            "anchor": "Codex thread: canvas scenario validation",
            "title": "Thread Research Brief",
            "purpose": "Track a short-lived research thread and promote a final report reference.",
            "root": str(root),
        },
        request_id,
    )
    request_id += 1
    call_tool(
        client,
        "canvas_update_state",
        {
            "id": canvas_id,
            "root": str(root),
            "updates": {
                "sources": [
                    {"label": "skill", "status": "read"},
                    {"label": "mcp smoke", "status": "passed"},
                ],
                "open_questions": [],
            },
        },
        request_id,
    )
    request_id += 1
    promoted = call_tool(
        client,
        "canvas_promote",
        {
            "id": canvas_id,
            "target": "final-report",
            "reference": "outputs/thread-research-brief.md",
            "note": "scenario-only final artifact",
            "root": str(root),
        },
        request_id,
    )
    request_id += 1
    validation = call_tool(client, "canvas_validate", {"id": canvas_id, "root": str(root)}, request_id)
    request_id += 1
    export = call_tool(client, "canvas_export_html", {"id": canvas_id, "root": str(root)}, request_id)
    request_id += 1
    html_path = Path(export["html_path"])
    ensure_contains(html_path, ["Thread Research Brief", "final-report", "mcp smoke"])
    return request_id, {
        "name": "Thread research brief",
        "id": canvas_id,
        "passed": validation["valid"] and promoted["scope"] == "thread",
        "html_path": str(html_path),
        "checks": ["thread scope", "update_state", "final-report promotion", "validate", "export_html"],
    }


def scenario_user_registry_archive(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-user-registry-cleanup"
    call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "user",
            "anchor": "James local Codex canvas registry",
            "title": "User Registry Cleanup",
            "purpose": "Represent a cross-project canvas that is archived after inspection.",
            "root": str(root),
        },
        request_id,
    )
    request_id += 1
    call_tool(
        client,
        "canvas_update_state",
        {
            "id": canvas_id,
            "root": str(root),
            "updates": {
                "items": [{"id": "stale-canvas-review", "status": "done"}],
                "decisions": ["Archive this canvas after export."],
            },
        },
        request_id,
    )
    request_id += 1
    active_list = call_tool(client, "canvas_list", {"lifecycle": "active", "root": str(root)}, request_id)
    request_id += 1
    archived = call_tool(client, "canvas_archive", {"id": canvas_id, "root": str(root)}, request_id)
    request_id += 1
    archived_validation = call_tool(
        client,
        "canvas_validate",
        {"id": canvas_id, "lifecycle": "archived", "root": str(root)},
        request_id,
    )
    request_id += 1
    archived_list = call_tool(client, "canvas_list", {"lifecycle": "archived", "root": str(root)}, request_id)
    request_id += 1
    export = call_tool(
        client,
        "canvas_export_html",
        {"id": canvas_id, "lifecycle": "archived", "root": str(root)},
        request_id,
    )
    request_id += 1
    html_path = Path(export["html_path"])
    ensure_contains(html_path, ["User Registry Cleanup", "lifecycle: archived", "stale-canvas-review"])
    return request_id, {
        "name": "User registry archive",
        "id": canvas_id,
        "passed": (
            archived["lifecycle"] == "archived"
            and archived_validation["valid"]
            and any(item["id"] == canvas_id for item in active_list)
            and any(item["id"] == canvas_id for item in archived_list)
        ),
        "html_path": str(html_path),
        "checks": ["user scope", "list active", "archive", "validate archived", "list archived", "export_html archived"],
    }


def scenario_error_recovery(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-error-recovery"
    call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "project",
            "anchor": r"D:\Projects",
            "title": "Error Recovery",
            "purpose": "Confirm expected MCP errors are structured and recoverable.",
            "root": str(root),
        },
        request_id,
    )
    request_id += 1
    duplicate = call_tool_error(
        client,
        "canvas_init",
        {"id": canvas_id, "scope": "project", "root": str(root)},
        request_id,
    )
    request_id += 1
    bad_promotion = call_tool_error(
        client,
        "canvas_promote",
        {
            "id": canvas_id,
            "target": "unsupported-target",
            "reference": "nowhere",
            "root": str(root),
        },
        request_id,
    )
    request_id += 1
    validation = call_tool(client, "canvas_validate", {"id": canvas_id, "root": str(root)}, request_id)
    request_id += 1
    export = call_tool(client, "canvas_export_html", {"id": canvas_id, "root": str(root)}, request_id)
    request_id += 1
    html_path = Path(export["html_path"])
    ensure_contains(html_path, ["Error Recovery", "valid: true"])
    return request_id, {
        "name": "Error recovery",
        "id": canvas_id,
        "passed": (
            validation["valid"]
            and duplicate["error"]["recoverable"]
            and bad_promotion["error"]["recoverable"]
        ),
        "html_path": str(html_path),
        "checks": ["duplicate error", "bad promotion error", "recoverable errors", "validate after errors", "export_html"],
    }


def render_report(output: Path, plugin_root: Path, scenarios: list[dict[str, Any]], resource_counts: dict[str, int]) -> Path:
    def report_link(path: str) -> str:
        relative = Path(path).resolve().relative_to(output.resolve()).as_posix()
        return quote(relative, safe="/")

    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(item['name'])}</td>"
        f"<td><code>{html.escape(item['id'])}</code></td>"
        f"<td>{'pass' if item['passed'] else 'fail'}</td>"
        f"<td>{html.escape(', '.join(item['checks']))}</td>"
        f"<td><a href=\"{report_link(item['html_path'])}\">canvas.html</a></td>"
        "</tr>"
        for item in scenarios
    )
    failed = [item for item in scenarios if not item["passed"]]
    report = output / "report.html"
    report.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Canvas Scenario Validation</title>
  <style>
    body {{ font-family: Inter, Segoe UI, system-ui, sans-serif; margin: 32px; color: #1c2633; background: #f7f8fa; }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    h1 {{ font-size: 30px; margin: 0 0 8px; letter-spacing: 0; }}
    p {{ color: #4b5563; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #d8dee8; }}
    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #e3e7ef; vertical-align: top; }}
    th {{ background: #eef2f7; font-size: 13px; }}
    code {{ background: #eef2f7; padding: 2px 4px; border-radius: 4px; }}
    .summary {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 18px 0; }}
    .chip {{ border: 1px solid #cfd6e2; background: white; border-radius: 6px; padding: 8px 10px; overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <main>
    <h1>Canvas Scenario Validation</h1>
    <p>Automated MCP scenarios using the Canvas plugin contract and exported browser surfaces.</p>
    <div class="summary">
      <div class="chip">plugin: <code>{html.escape(str(plugin_root))}</code></div>
      <div class="chip">scenarios: {len(scenarios)}</div>
      <div class="chip">failures: {len(failed)}</div>
      <div class="chip">active resources: {resource_counts['active']}</div>
      <div class="chip">archived resources: {resource_counts['archived']}</div>
    </div>
    <table>
      <thead>
        <tr><th>Scenario</th><th>Canvas</th><th>Status</th><th>Checks</th><th>Browser Surface</th></tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )
    return report


def run(plugin_root: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    canvas_root = output / "canvases"
    if canvas_root.exists():
        shutil.rmtree(canvas_root)
    for artifact in [output / "report.html", output / "summary.json"]:
        if artifact.exists():
            artifact.unlink()
    command, cwd = server_config(plugin_root)
    original_canvas_root = os.environ.get("CANVAS_ROOT")
    os.environ["CANVAS_ROOT"] = str(canvas_root)
    client = McpClient(command, cwd)
    try:
        init = client.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "clientInfo": {"name": "canvas-scenarios", "version": "0.1.0"},
                "capabilities": {},
            },
            request_id=1,
        )
        tools = client.request("tools/list", request_id=2)["result"]["tools"]
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
        names = {tool["name"] for tool in tools}
        missing = sorted(required - names)
        if missing:
            raise SmokeFailure(f"Missing scenario tools: {missing}")

        request_id = 3
        scenarios: list[dict[str, Any]] = []
        for scenario in [
            scenario_repo_review,
            scenario_project_dashboard,
            scenario_thread_research,
            scenario_user_registry_archive,
            scenario_error_recovery,
        ]:
            request_id, result = scenario(client, canvas_root, request_id)
            scenarios.append(result)

        resources = client.request("resources/list", request_id=request_id)["result"]["resources"]
        request_id += 1
        if {"resource://canvas/active", "resource://canvas/archived"} - {item["uri"] for item in resources}:
            raise SmokeFailure(f"Missing resources: {resources}")
        active_resource = client.request(
            "resources/read",
            {"uri": "resource://canvas/active"},
            request_id=request_id,
        )["result"]["contents"][0]["text"]
        request_id += 1
        archived_resource = client.request(
            "resources/read",
            {"uri": "resource://canvas/archived"},
            request_id=request_id,
        )["result"]["contents"][0]["text"]
        active_count = len(json.loads(active_resource))
        archived_count = len(json.loads(archived_resource))
    finally:
        client.close()
        if original_canvas_root is None:
            os.environ.pop("CANVAS_ROOT", None)
        else:
            os.environ["CANVAS_ROOT"] = original_canvas_root

    report = render_report(output, plugin_root, scenarios, {"active": active_count, "archived": archived_count})
    summary = {
        "ok": all(item["passed"] for item in scenarios),
        "plugin_root": str(plugin_root),
        "server": {"command": command, "cwd": str(cwd)},
        "initialize": init["result"]["serverInfo"],
        "tools": sorted(names),
        "canvas_root": str(canvas_root),
        "report": str(report),
        "report_uri": report.as_uri(),
        "scenarios": scenarios,
        "resources": {"active": active_count, "archived": archived_count},
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Canvas MCP scenario validation and render a browser report.")
    parser.add_argument("--installed", action="store_true", help="Use the latest installed personal plugin cache.")
    parser.add_argument("--plugin-root", default="", help="Plugin root to test.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Scenario output directory.")
    args = parser.parse_args()

    if args.plugin_root:
        plugin_root = Path(args.plugin_root).expanduser().resolve()
    elif args.installed:
        plugin_root = latest_installed_plugin().resolve()
    else:
        plugin_root = ROOT

    summary = run(plugin_root, args.output.resolve())
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
