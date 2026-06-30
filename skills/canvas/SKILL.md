---
name: canvas
description: "Use this whenever the user asks for a canvas, workspace, shared board, live planning surface, interactive dashboard, artifact workspace, or Copilot-style canvas equivalent in Codex. Use the bundled Canvas CLI for creation, listing, reads, updates, validation, export, archival, thread association, and promotion records."
---

# Canvas

Use this skill to create and maintain semi-persistent Codex work surfaces.

A canvas is a working artifact for an active investigation, plan, review, dashboard, or decision workflow. It is not scratch, and it is not durable project truth until explicitly promoted.

## CLI Contract

Use the bundled Canvas CLI for all canvas operations. Do not use MCP tools for Canvas.

Resolve the CLI wrapper relative to this `SKILL.md`:

```bash
python ../../scripts/canvas.py tool <operation> '<json-object>'
```

If that relative path cannot be resolved from the installed skill location, locate the installed `canvas` plugin root and run its `scripts/canvas.py`. Assume `python` is on the path.

Supported operation names:

- `canvas_init`
- `canvas_list`
- `canvas_get`
- `canvas_update_state`
- `canvas_validate`
- `canvas_archive`
- `canvas_associate_thread`
- `canvas_promote`
- `canvas_export_html`

Use JSON payloads with the same field names:

```bash
python ../../scripts/canvas.py tool canvas_init '{"id":"review-board","scope":"repo","anchor":"D:\\Projects\\repo","purpose":"Track review work"}'
python ../../scripts/canvas.py tool canvas_update_state '{"id":"review-board","updates":{"status":"reviewing"}}'
python ../../scripts/canvas.py tool canvas_validate '{"id":"review-board"}'
python ../../scripts/canvas.py tool canvas_export_html '{"id":"review-board"}'
```

Do not hand-create `canvas.json`, choose storage paths, move lifecycle folders, or invent the layout. The CLI owns default storage, exact paths, collision handling, validation, archive movement, and export sidecars. Use returned `storage_path`, `html_path`, and `data_path` as authoritative.

Direct filesystem reads or edits are only for inspecting returned files, preserving user edits, or updating canvas-owned notes and custom surfaces after the CLI has created/exported the canvas.

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

Canvases belong in user-level external storage, not transient dated Codex session folders and not repo/project folders unless the user explicitly asks. Repo/project folders are usually anchors, not storage targets.

Keep the logical anchor separate from storage:

```text
scope: repo
anchor: D:\Projects\repo
storage_path: returned by canvas_init or canvas_get
```

## Scope

Choose the narrowest useful scope:

- `repo`: repository, branch, issue, PR, code review, architecture trace, test plan, implementation workflow.
- `project`: non-repo project folder, household workspace, business process, operational domain.
- `thread`: work intentionally tied to one conversation.
- `user`: cross-project dashboards, reusable templates, personal or household planning.

Prefer `repo` or `project` when a real anchor exists. Use `user` for personal planning, household planning, reusable trackers, and casual "create me a canvas for..." requests when there is no real repo or project folder anchor. Use `thread` only when the user explicitly asks for a thread-scoped canvas or the work is meaningless outside the conversation.

Do not treat a delegated source thread id or the current Codex thread id as an anchor by itself. Thread identifiers belong in `associatedThreads` only when available and useful.

## Creation

Before creating a canvas, determine:

1. Purpose: planning, research, review, tracking, editing, dashboarding, artifact generation, or decision support.
2. Anchor: repo, project, thread, or user.
3. Surface: Markdown, Markdown plus JSON, static HTML, or local app.
4. Capabilities: what the user can do and what Codex can reliably update.
5. Promotion path: where results may go if explicitly promoted.

If intent is clear, proceed without asking. Ask only when the wrong anchor or storage choice would create meaningful cleanup or confusion.

Create with `canvas_init`. Pass domain-specific `human_actions`, `agent_actions`, and `promotion_targets` for shaped workflows. Use defaults only for generic canvases. For thread-scoped canvases, pass known thread identifiers as `associatedThreads`; use `canvas_associate_thread` to connect an existing canvas to another thread.

## Surfaces

Use the lightest surface that fits:

```text
Markdown
  Plans, notes, specs, reviews, decision logs.

Markdown + JSON
  Repeatedly updated structured state.

Static HTML + JS/CDN libraries
  Simple interaction: filters, charts, diagrams, drag/drop, tables, maps, calendars.

Vite + React + TypeScript + Tailwind + shadcn/ui
  Complex canvas apps that still build to static files.

Next.js + Tailwind + shadcn/ui
  Only when server behavior, routing, API routes, auth, or similar features are genuinely needed.
```

If the `frontend-design` skill is installed and the canvas needs a new or materially revised browser UI, use that skill before designing or editing the UI. A request for a planner, board, dashboard, tracker, map, calendar, or other usable visual workspace is enough to justify a canvas-specific UI.

Allowed CDN libraries for static pages include Chart.js, Mermaid, SortableJS, Marked, DOMPurify, Fuse.js, Tabulator/Grid.js, Leaflet, and FullCalendar.

Static HTML surfaces must be real HTML pages on disk. Start with `canvas_export_html`, which creates or refreshes the canvas-owned `canvas.html` starter page and `canvas-data.js` sidecar. The shared exported template intentionally has no body. Do not add generic UI to `templates/canvas-viewer.html`. After export, build or update the canvas-specific `canvas.html` body when the request implies a usable surface.

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

Use `canvas_promote` to record explicit promotion targets and references. It records the promotion; it does not write arbitrary destination files by itself.

## Update Loop

When updating an existing canvas:

1. Use `canvas_get` to read metadata.
2. Preserve user edits.
3. Use `canvas_update_state` for structured state changes.
4. Edit returned local files only when notes, README, or custom surfaces need direct file work.
5. Use `canvas_validate` after material changes.
6. Refresh with `canvas_export_html` when browser inspection helps.
7. Report changed files, storage path, promotion status, and how to continue.

Avoid rebuilding from scratch unless the user asks or the current structure no longer fits.

## Response

When presenting a canvas, include:

- canvas id
- scope and anchor
- storage path
- files created or updated
- whether anything was promoted
- how to continue

Be explicit when something is only a working artifact.
