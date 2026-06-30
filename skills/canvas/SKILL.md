---
name: canvas
description: "Use this whenever the user asks for a canvas, workspace, shared board, live planning surface, interactive dashboard, artifact workspace, or Copilot-style canvas equivalent in Codex. This skill creates semi-persistent local work surfaces: more durable than scratch files, less authoritative than project memory, and promoted only when explicitly requested."
---

# Canvas

Use this skill to create and maintain semi-persistent Codex work surfaces.

A canvas is a working artifact for an active investigation, plan, review, dashboard, or decision workflow. It is not scratch, and it is not durable project truth until explicitly promoted.

Assume the Canvas MCP tools are available. Defer canvas creation, reads, updates, validation, archival, promotion records, and HTML export to those tools.

If the MCP tools are not exposed in the current thread, do not hand-create canvas metadata or invent the storage layout. Use the installed Canvas CLI only as a compatibility path for the same operations, and say clearly that MCP tools were not exposed. Direct filesystem reads or edits are only for inspecting returned files, preserving user edits, or narrowly repairing a failed operation.

## Model

```text
scratch
  Temporary execution files. Safe to delete.

canvas
  Semi-persistent task state. Useful across turns or days, but not authoritative.

memory/project state
  Durable truth. Repo files, project docs, project memory, automation rules, published dashboards.
```

Default frame: `Canvas = a working set for an active line of thought.`

## Storage

Do not choose or construct canvas storage paths in the skill. The MCP owns concrete path knowledge: default root, exact on-disk layout, lifecycle placement, collision handling, migrations, and where `canvas.json` lives.

Policy only: canvases belong in user-level external storage, not transient dated Codex session folders and not repo/project folders unless the user explicitly asks. Use the `storage_path` returned by `canvas_init` or `canvas_get` as authoritative.

Keep the logical anchor separate from storage:

```text
scope: repo
anchor: D:\xpna\main
storage_path: returned by the MCP
```

Repo/project folders are usually anchors, not storage targets. Do not create committable repo-local canvas files unless the user asks or the repo has a clearly ignored local-agent convention.

## Scope

Choose the narrowest useful scope:

- `repo`: repository, branch, issue, PR, code review, architecture trace, test plan, implementation workflow.
- `project`: non-repo project folder, household workspace, business process, operational domain.
- `thread`: short-lived work intentionally tied to this one conversation.
- `user`: cross-project dashboards, reusable templates, user-level registries.

Prefer `repo` or `project` when a real anchor exists. Use `user` for personal planning, household planning, reusable trackers, and casual "create me a canvas for..." requests when there is no real repo or project folder anchor. Use `thread` only when the user explicitly asks for a thread-scoped canvas or the work is meaningless outside this one conversation.

Do not treat a delegated source thread id or the current Codex thread id as an anchor by itself. Thread identifiers belong in `associatedThreads` only when available and useful; they are not a substitute for a real repo/project anchor.

## Metadata

The MCP maintains the core files:

- `canvas.json`: id, lifecycle, authority, scope, anchor, associatedThreads, timestamps, state files, capabilities, promotion targets.
- `state.json`: structured shared state.
- `notes.md`: readable working notes.
- `README.md`: quick human/agent orientation.

For thread-scoped canvases, pass one or more known thread identifiers as `associatedThreads` to `canvas_init`. Use `canvas_associate_thread` to tie an existing canvas to another thread, and `canvas_list` with `threadId` to find canvases tied to a thread. Populate thread identifiers only when available; leave them empty rather than inventing them.

## Capabilities

Treat a canvas as a shared action surface, not just a folder.

Define concrete:

- `human_actions`: inspect, decide, edit, approve, reject, archive, request promotion.
- `agent_actions`: refresh state, add/update items, summarize, regenerate surfaces, validate, archive.
- `shared_state`: files both human and agent can inspect/update.
- `promotion_targets`: allowed durable destinations.

Pass domain-specific `human_actions`, `agent_actions`, and `promotion_targets` to `canvas_init` for shaped workflows. Use defaults only for generic canvases.

## Creation Triage

Before creating a canvas, determine:

1. Purpose: planning, research, review, tracking, editing, dashboarding, artifact generation, or decision support.
2. Anchor: repo, project, thread, or user.
3. Lifecycle: active canvas, scratch-only, or durable project state.
4. Surface: Markdown, Markdown plus JSON, static HTML, or local app.
5. Capabilities: what the user can do and what Codex can reliably update.
6. Promotion path: where results may go if explicitly promoted.

If intent is clear, proceed without asking. Ask only when the wrong anchor or storage choice would create meaningful cleanup or confusion.

Create the canvas with `canvas_init`. Do not hand-create the folder or `canvas.json`.

## Surfaces

Use the lightest surface that fits:

```text
Markdown
  Plans, notes, specs, reviews, decision logs.

Markdown + JSON
  Repeatedly updated structured state.

Static HTML
  Browser review surface without a backend.

Static HTML + JS/CDN libraries
  Simple interaction: filters, charts, diagrams, drag/drop, tables, maps, calendars.

Vite + React + TypeScript + Tailwind + shadcn/ui
  Complex canvas apps that still build to static files.

Next.js + Tailwind + shadcn/ui
  Only when server behavior, routing, API routes, auth, or similar features are genuinely needed.
```

If the `frontend-design` skill is installed and the user explicitly asks to build or materially revise a browser UI, use that skill before designing or editing the UI. Do not treat normal `canvas_export_html` output as a design task by itself.

Do not choose Next.js by default for local canvas artifacts.

Allowed CDN libraries for static pages include Chart.js, Mermaid, SortableJS, Marked, DOMPurify, Fuse.js, Tabulator/Grid.js, Leaflet, and FullCalendar.

Static HTML surfaces must be real HTML pages on disk. Start from the checked-in blank template and place local state beside it, such as `canvas-data.js`, `state.json`, `canvas.json`, and `notes.md`. Do not generate whole HTML pages from script strings.

Use `canvas_export_html` to create or refresh the `canvas.html` starter page and `canvas-data.js` sidecar. The exported HTML template intentionally has no body and will render as a blank browser page until a user explicitly asks for a custom surface. Do not "fix" a blank starter export by adding a body, dashboard, or generated UI. Populate the body only when the user explicitly asks to build a canvas-specific surface. The export is a working artifact, not a durable promotion.

## Promotion

A canvas can inform durable state, but is not durable state until explicitly promoted.

Promotion examples:

- repo documentation
- project memory
- project dashboard or hub/catalog entry
- static-site catalog
- issue or PR comment
- final report
- source/tests/docs changes

When promoting into dashboard/catalog surfaces:

1. Identify the authoritative source first.
2. Update or generate visible pages only after source state is clear.
3. Update index/catalog files that make the surface discoverable.
4. Verify the surface directly when possible.

In non-git workspaces, verify with direct reads, hashes, or page checks instead of `git diff`.

## Update Loop

When updating an existing canvas:

1. Use `canvas_get` to read the canvas metadata.
2. Preserve user edits.
3. Use `canvas_update_state` for structured state changes.
4. Inspect or edit returned local files only when notes, README, or custom surfaces need direct file work.
5. Use `canvas_validate` after material changes.
6. Refresh with `canvas_export_html` when browser inspection helps.
7. Report changed files, storage path, promotion status, and how to continue.

Avoid rebuilding from scratch unless the user asks or the current structure no longer fits.

## Drift Guards

- A blank `canvas.html` from `canvas_export_html` is expected for the default starter template.
- Do not create a user-facing dashboard, app, or custom HTML body unless the user asks for that surface explicitly.
- Do not copy bespoke output files from a Codex thread into canvas storage unless the user asks to replace or customize the canvas surface.
- If the user reacts to a blank starter page ambiguously, clarify that the blank page is expected before changing it.
- Keep promotion records separate from presentation changes; a rendered local surface is still not promotion.

## Archival

When finished, call `canvas_archive`. Do not move folders or edit lifecycle fields manually unless recovering from an MCP failure.

## Response

When presenting a canvas, include:

- canvas id
- scope and anchor
- storage path
- files created or updated
- whether anything was promoted
- how to continue

Be explicit when something is only a working artifact.
