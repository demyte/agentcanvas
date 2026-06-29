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
    sidecar = path.parent / "canvas-data.js"
    if sidecar.exists():
        text += "\n" + sidecar.read_text(encoding="utf-8")
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
    ensure_contains(html_path, ["Canvas Repo Architecture Review", "Repo is anchor, not storage", '"valid": true'])
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
    ensure_contains(html_path, ["User Registry Cleanup", '"lifecycle": "archived"', "stale-canvas-review"])
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
    ensure_contains(html_path, ["Error Recovery", '"valid": true'])
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


def scenario_incident_command_center(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-incident-command-center"
    created = call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "project",
            "anchor": "ops://payments-api/incident/2026-06-29",
            "title": "Payments Incident Command Center",
            "purpose": "Coordinate a live service incident without confusing working notes with the post-incident record.",
            "human_actions": ["declare_severity", "assign_incident_commander", "approve_customer_update"],
            "agent_actions": ["refresh_status", "summarize_timeline", "draft_customer_update"],
            "promotion_targets": ["issue-comment", "post-incident-report"],
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
                "severity": "SEV2",
                "incident_roles": {
                    "commander": "unassigned",
                    "communications": "support-lead",
                    "scribe": "codex",
                },
                "timeline": [
                    {"time": "10:04", "event": "Checkout latency breached threshold"},
                    {"time": "10:12", "event": "Suspected upstream gateway degradation"},
                    {"time": "10:19", "event": "Mitigation candidate identified"},
                ],
                "customer_update_status": "draft-needed",
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
            "target": "issue-comment",
            "reference": "incident-tracker://PAY-481#comment",
            "note": "scenario-only incident status handoff",
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
    ensure_contains(html_path, ["Payments Incident Command Center", "SEV2", "declare_severity", "issue-comment"])
    return request_id, {
        "name": "Incident command center",
        "id": canvas_id,
        "passed": (
            validation["valid"]
            and created["human_actions"][0] == "declare_severity"
            and promoted["promotions"][-1]["target"] == "issue-comment"
        ),
        "html_path": str(html_path),
        "checks": ["custom actions", "incident timeline", "issue-comment promotion", "validate", "export_html"],
    }


def scenario_contract_negotiation(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-contract-negotiation-room"
    created = call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "project",
            "anchor": "contracts://vendor-platform-renewal",
            "title": "Vendor Contract Negotiation Room",
            "purpose": "Track clause-level negotiation state before anything becomes an approved legal position.",
            "human_actions": ["approve_clause_position", "request_legal_review", "mark_walkaway_term"],
            "agent_actions": ["summarize_clause_risk", "compare_terms", "draft_counterposition"],
            "promotion_targets": ["legal-brief", "final-report"],
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
                "clauses": [
                    {"name": "Data processing", "risk": "medium", "position": "needs DPA attachment"},
                    {"name": "Liability cap", "risk": "high", "position": "reject 1x fees cap"},
                    {"name": "Renewal notice", "risk": "low", "position": "accept 60 days"},
                ],
                "walkaway_terms": ["Unlimited data reuse", "One-way indemnity"],
                "open_questions": ["Does procurement require price hold language?"],
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
            "target": "legal-brief",
            "reference": "legal-review://vendor-platform-renewal/brief",
            "note": "scenario-only brief reference",
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
    ensure_contains(html_path, ["Vendor Contract Negotiation Room", "Liability cap", "legal-brief", "walkaway"])
    return request_id, {
        "name": "Contract negotiation room",
        "id": canvas_id,
        "passed": (
            validation["valid"]
            and "legal-brief" in created["promotion_targets"]
            and promoted["promotions"][-1]["target"] == "legal-brief"
        ),
        "html_path": str(html_path),
        "checks": ["custom promotion target", "clause risk state", "legal-brief promotion", "validate", "export_html"],
    }


def scenario_data_migration_cutover(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-data-migration-cutover"
    created = call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "repo",
            "anchor": r"D:\Projects\data-platform",
            "title": "Data Migration Cutover Board",
            "purpose": "Coordinate a reversible data migration without storing cutover state in the repo.",
            "human_actions": ["approve_cutover", "pause_migration", "trigger_rollback"],
            "agent_actions": ["check_row_counts", "compare_watermarks", "summarize_cutover_readiness"],
            "promotion_targets": ["repo-doc", "pull-request-comment", "rollback-runbook"],
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
                "phases": [
                    {"name": "snapshot", "status": "complete"},
                    {"name": "dual-write", "status": "monitoring"},
                    {"name": "read-switch", "status": "blocked"},
                ],
                "gates": {"row_count_delta": "0.02%", "watermark_lag": "3m", "rollback_ready": True},
                "rollback_plan": ["disable read switch", "replay queue", "restore old watermark"],
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
            "target": "rollback-runbook",
            "reference": "runbooks/data-migration-rollback.md",
            "note": "scenario-only rollback handoff",
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
    ensure_contains(html_path, ["Data Migration Cutover Board", "dual-write", "rollback-runbook", "watermark_lag"])
    return request_id, {
        "name": "Data migration cutover",
        "id": canvas_id,
        "passed": (
            validation["valid"]
            and created["scope"] == "repo"
            and promoted["promotions"][-1]["target"] == "rollback-runbook"
        ),
        "html_path": str(html_path),
        "checks": ["repo anchor", "cutover gates", "custom rollback target", "validate", "export_html"],
    }


def scenario_hiring_review_panel(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-hiring-review-panel"
    created = call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "user",
            "anchor": "hiring://principal-engineer-panel",
            "title": "Hiring Review Panel",
            "purpose": "Compare fictional candidate feedback before a hiring packet is written.",
            "human_actions": ["mark_conflict", "approve_shortlist", "request_followup_interview"],
            "agent_actions": ["normalize_feedback", "summarize_signal", "draft_hiring_packet"],
            "promotion_targets": ["hiring-packet", "final-report"],
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
                "candidates": [
                    {"alias": "Candidate A", "system_design": 4, "execution": 5, "risk": "scope calibration"},
                    {"alias": "Candidate B", "system_design": 5, "execution": 3, "risk": "delivery depth"},
                    {"alias": "Candidate C", "system_design": 3, "execution": 4, "risk": "needs followup"},
                ],
                "panel_decision": "shortlist Candidate A and Candidate B",
                "bias_checks": ["Use aliases only", "Separate evidence from recommendation"],
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
            "target": "hiring-packet",
            "reference": "hiring://principal-engineer-panel/packet-draft",
            "note": "scenario-only packet draft",
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
    ensure_contains(html_path, ["Hiring Review Panel", "Candidate A", "hiring-packet", "bias_checks"])
    return request_id, {
        "name": "Hiring review panel",
        "id": canvas_id,
        "passed": (
            validation["valid"]
            and created["scope"] == "user"
            and promoted["promotions"][-1]["target"] == "hiring-packet"
        ),
        "html_path": str(html_path),
        "checks": ["user scope", "candidate comparison state", "custom hiring target", "validate", "export_html"],
    }


def scenario_editorial_calendar(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-editorial-calendar"
    created = call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "project",
            "anchor": "content://developer-blog/q3",
            "title": "Developer Blog Editorial Calendar",
            "purpose": "Plan a content release train before publishing anything to the site catalog.",
            "human_actions": ["approve_headline", "move_publish_date", "mark_asset_ready"],
            "agent_actions": ["refresh_asset_status", "draft_social_copy", "validate_publish_checklist"],
            "promotion_targets": ["static-site-catalog", "content-calendar"],
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
                "posts": [
                    {"slug": "mcp-debugging", "stage": "outline", "owner": "engineering"},
                    {"slug": "canvas-workflows", "stage": "draft", "owner": "product"},
                    {"slug": "local-first-agents", "stage": "asset-review", "owner": "design"},
                ],
                "publish_window": "Q3",
                "asset_checklist": ["hero image", "code snippets", "social cards"],
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
            "target": "static-site-catalog",
            "reference": "site-catalog://developer-blog/q3",
            "note": "scenario-only catalog staging",
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
    ensure_contains(html_path, ["Developer Blog Editorial Calendar", "canvas-workflows", "static-site-catalog"])
    return request_id, {
        "name": "Editorial calendar",
        "id": canvas_id,
        "passed": (
            validation["valid"]
            and "content-calendar" in created["promotion_targets"]
            and promoted["promotions"][-1]["target"] == "static-site-catalog"
        ),
        "html_path": str(html_path),
        "checks": ["project scope", "content calendar state", "catalog promotion", "validate", "export_html"],
    }


def scenario_food_service_prep(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-food-service-prep"
    created = call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "project",
            "anchor": "venue://market-stall/saturday-service",
            "title": "Saturday Service Prep Board",
            "purpose": "Coordinate menu, prep quantities, and service risks before writing a final run sheet.",
            "human_actions": ["approve_menu", "adjust_batch_size", "mark_supplier_confirmed"],
            "agent_actions": ["scale_recipe_quantities", "summarize_prep_risks", "draft_service_run_sheet"],
            "promotion_targets": ["service-run-sheet", "supplier-order"],
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
                "menu": [
                    {"item": "miso mushroom bowls", "target_serves": 90, "prep_status": "batching"},
                    {"item": "ginger lime spritz", "target_serves": 120, "prep_status": "supplier pending"},
                ],
                "cold_chain": {"ice_packs": 18, "esky_labels": ["sauce", "greens", "drinks"]},
                "service_risks": ["rain frontage", "limited handwash access", "card reader battery"],
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
            "target": "service-run-sheet",
            "reference": "ops://market-stall/saturday-run-sheet",
            "note": "scenario-only run sheet",
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
    ensure_contains(html_path, ["Saturday Service Prep Board", "miso mushroom bowls", "service-run-sheet"])
    return request_id, {
        "name": "Food service prep",
        "id": canvas_id,
        "passed": validation["valid"] and created["scope"] == "project" and promoted["promotions"][-1]["target"] == "service-run-sheet",
        "html_path": str(html_path),
        "checks": ["menu state", "cold-chain state", "custom service target", "validate", "export_html"],
    }


def scenario_film_shoot_day(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-film-shoot-day"
    created = call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "project",
            "anchor": "production://short-film/day-03",
            "title": "Short Film Shoot Day Board",
            "purpose": "Track shot readiness, locations, and continuity before a call sheet is locked.",
            "human_actions": ["approve_shot_order", "flag_continuity_issue", "confirm_location_release"],
            "agent_actions": ["summarize_shot_risk", "regenerate_call_sheet", "check_prop_dependencies"],
            "promotion_targets": ["call-sheet", "shot-list"],
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
                "shots": [
                    {"scene": "3A", "lens": "35mm", "location": "alley", "status": "ready"},
                    {"scene": "4C", "lens": "85mm", "location": "rooftop", "status": "weather hold"},
                    {"scene": "7B", "lens": "24mm", "location": "van interior", "status": "prop missing"},
                ],
                "continuity": ["coffee cup hand switches in scene 3A", "jacket zipper position"],
                "crew_calls": {"camera": "05:30", "sound": "05:45", "talent": "06:15"},
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
            "target": "call-sheet",
            "reference": "production://short-film/day-03/call-sheet",
            "note": "scenario-only call sheet",
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
    ensure_contains(html_path, ["Short Film Shoot Day Board", "weather hold", "call-sheet"])
    return request_id, {
        "name": "Film shoot day",
        "id": canvas_id,
        "passed": validation["valid"] and created["promotion_targets"][0] == "call-sheet" and promoted["promotions"][-1]["target"] == "call-sheet",
        "html_path": str(html_path),
        "checks": ["shot list state", "continuity state", "call-sheet promotion", "validate", "export_html"],
    }


def scenario_lab_specimen_chain(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-lab-specimen-chain"
    created = call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "project",
            "anchor": "lab://field-samples/batch-17",
            "title": "Field Specimen Chain Board",
            "purpose": "Track sample custody and assay readiness before updating the lab register.",
            "human_actions": ["verify_custody", "quarantine_sample", "approve_assay_batch"],
            "agent_actions": ["check_missing_temperatures", "summarize_chain_breaks", "draft_lab_register_update"],
            "promotion_targets": ["lab-register", "assay-plan"],
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
                "samples": [
                    {"id": "FS-17-001", "temp_c": 4.1, "custody": "checked-in", "assay": "pcr"},
                    {"id": "FS-17-002", "temp_c": 7.8, "custody": "quarantine", "assay": "hold"},
                    {"id": "FS-17-003", "temp_c": 3.9, "custody": "checked-in", "assay": "culture"},
                ],
                "chain_breaks": ["FS-17-002 exceeded cold range for 18 minutes"],
                "register_status": "not-promoted",
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
            "target": "lab-register",
            "reference": "lab-register://batch-17/staged",
            "note": "scenario-only register staging",
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
    ensure_contains(html_path, ["Field Specimen Chain Board", "FS-17-002", "lab-register"])
    return request_id, {
        "name": "Lab specimen chain",
        "id": canvas_id,
        "passed": validation["valid"] and created["scope"] == "project" and promoted["promotions"][-1]["target"] == "lab-register",
        "html_path": str(html_path),
        "checks": ["sample custody state", "quarantine state", "lab-register promotion", "validate", "export_html"],
    }


def scenario_emergency_supply_cache(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-emergency-supply-cache"
    created = call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "user",
            "anchor": "home://storm-season/supply-cache",
            "title": "Storm Season Supply Cache",
            "purpose": "Plan household emergency supplies before promoting anything into durable household records.",
            "human_actions": ["mark_bin_checked", "approve_purchase", "assign_pack_owner"],
            "agent_actions": ["calculate_day_coverage", "summarize_gaps", "draft_purchase_list"],
            "promotion_targets": ["household-checklist", "purchase-list"],
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
                "bins": [
                    {"name": "water", "days": 3, "status": "short"},
                    {"name": "lighting", "days": 7, "status": "ready"},
                    {"name": "first aid", "days": 14, "status": "check expiry"},
                ],
                "purchase_gaps": ["water containers", "radio batteries", "pet food"],
                "owners": {"water": "James", "first aid": "family review"},
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
            "target": "purchase-list",
            "reference": "household://storm-season/purchase-list",
            "note": "scenario-only shopping list",
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
    ensure_contains(html_path, ["Storm Season Supply Cache", "water containers", "purchase-list"])
    return request_id, {
        "name": "Emergency supply cache",
        "id": canvas_id,
        "passed": validation["valid"] and created["scope"] == "user" and promoted["promotions"][-1]["target"] == "purchase-list",
        "html_path": str(html_path),
        "checks": ["household supply state", "coverage gaps", "purchase-list promotion", "validate", "export_html"],
    }


def scenario_game_balance_lab(client: McpClient, root: Path, request_id: int) -> tuple[int, dict[str, Any]]:
    canvas_id = "scenario-game-balance-lab"
    created = call_tool(
        client,
        "canvas_init",
        {
            "id": canvas_id,
            "scope": "project",
            "anchor": "game://deckbuilder/prototype-2",
            "title": "Deckbuilder Balance Lab",
            "purpose": "Track playtest signals and tuning hypotheses before changing game source assets.",
            "human_actions": ["approve_card_tweak", "reject_playtest_outlier", "schedule_rematch"],
            "agent_actions": ["summarize_playtest_delta", "rank_balance_risks", "draft_patch_notes"],
            "promotion_targets": ["design-changelog", "playtest-report"],
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
                "cards": [
                    {"name": "Spark Engine", "win_rate": 0.64, "proposal": "-1 charge"},
                    {"name": "Ash Sentinel", "win_rate": 0.42, "proposal": "+1 armor"},
                    {"name": "Market Trick", "win_rate": 0.51, "proposal": "no change"},
                ],
                "playtests": {"matches": 48, "median_turns": 8, "stall_reports": 6},
                "hypotheses": ["Spark Engine snowballs too early", "Ash Sentinel underperforms into control"],
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
            "target": "playtest-report",
            "reference": "playtests://deckbuilder/prototype-2/report",
            "note": "scenario-only balance report",
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
    ensure_contains(html_path, ["Deckbuilder Balance Lab", "Spark Engine", "playtest-report"])
    return request_id, {
        "name": "Game balance lab",
        "id": canvas_id,
        "passed": validation["valid"] and created["promotion_targets"][1] == "playtest-report" and promoted["promotions"][-1]["target"] == "playtest-report",
        "html_path": str(html_path),
        "checks": ["playtest state", "balance hypotheses", "playtest-report promotion", "validate", "export_html"],
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
            scenario_incident_command_center,
            scenario_contract_negotiation,
            scenario_data_migration_cutover,
            scenario_hiring_review_panel,
            scenario_editorial_calendar,
            scenario_food_service_prep,
            scenario_film_shoot_day,
            scenario_lab_specimen_chain,
            scenario_emergency_supply_cache,
            scenario_game_balance_lab,
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
