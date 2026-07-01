---
name: canvas
description: "Canvas: use when the user asks for a canvas, shared board, workspace, live planning surface, interactive dashboard, artifact workspace, or Copilot-style canvas in Codex. Use the bundled Canvas CLI for creation, listing, reading, updates, validation, export, archival, thread association, server management, and promotion records."
---

# Canvas

Create and maintain semi-persistent Codex work surfaces.

A canvas is a working artifact for an active investigation, plan, review, dashboard, or decision workflow. It is more durable than scratch, but it is not durable project truth until the user explicitly promotes it.

## Core Contract

The Canvas CLI owns storage, lifecycle, paths, collision handling, validation, export sidecars, server state, and archive movement. Do not hand-create `canvas.json`, choose storage paths, move lifecycle folders, or invent the layout.

The published executable lives under this skill:

```powershell
.\scripts\canvas.exe <command> <arguments>
```

If `scripts\canvas.exe` is missing or older than the bundled source, publish it just in time through the wrapper relative to this `SKILL.md`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\canvas.ps1 <command> <arguments>
```

The wrapper publishes the .NET file-based app from `.\scripts\canvas.cs` into `.\scripts\canvas.exe`, then runs it. Assume `dotnet` is on the path.

Use CLI verbs and arguments, not JSON payloads. For structured state changes, write a temporary JSON object file and pass it with `-merge-file <path>`.

```bash
.\scripts\canvas.exe init -id review-board -scope repo -anchor "D:\Projects\repo" -purpose "Track review work"
.\scripts\canvas.exe update-state -id review-board -set status=reviewing
.\scripts\canvas.exe update-state -id review-board -merge-file .\state-update.json
.\scripts\canvas.exe validate -id review-board
.\scripts\canvas.exe open -id review-board
```

Use `--help`, `-h`, or `-?` for the command reference:

```bash
.\scripts\canvas.exe -?
.\scripts\canvas.exe init -?
```

Treat returned `storage_path`, `html_path`, `data_path`, and HTTP URLs as authoritative.

## Operating Loop

1. Classify the canvas.
   Decide purpose, scope, anchor, surface, capabilities, and possible promotion target. Completion criterion: the choices are specific enough to create or update without guessing where the work belongs.

2. Create or read through the CLI.
   For a new canvas, run `init`. For an existing canvas, use `list`, `list -thread-id <thread-id>`, or `get`. Pass domain-specific `-human-action`, `-agent-action`, `-promotion-target`, and `-associated-thread` values when they shape the workflow. Completion criterion: the CLI has returned the canvas metadata and paths you will use.

3. Update the canvas-owned artifacts.
   Use `update-state` for structured state. Edit returned local files directly only for canvas-owned notes, README files, or a custom `canvas.html` surface. Preserve user edits. Completion criterion: the intended state, notes, and surface changes are present in the canvas folder.

4. Validate and inspect.
   Run `validate` after material changes. When browser inspection or interaction helps, run `open -id <canvas-id>` and use the returned `http://127.0.0.1` URL in the Browser. Completion criterion: validation passes, or any remaining validation issue is reported explicitly.

5. Promote only on request.
   Use `promote` to record explicit durable promotion references. It records the promotion; it does not write arbitrary destination files. Completion criterion: the user can tell what stayed as canvas work and what, if anything, became durable project state.

## Scope Reference

Choose the narrowest useful scope:

- `repo`: repository, branch, issue, PR, code review, architecture trace, test plan, implementation workflow.
- `project`: non-repo project folder, household workspace, business process, operational domain.
- `thread`: work intentionally tied to one conversation.
- `user`: cross-project dashboards, reusable templates, personal or household planning.

Prefer `repo` or `project` when a real anchor exists. Use `user` for personal planning, household planning, reusable trackers, and casual "create me a canvas for..." requests when no repo or project anchor is real. Use `thread` only when the user explicitly asks for a thread-scoped canvas or the work is meaningless outside the conversation.

Thread identifiers are associations, not anchors. Store them with `-associated-thread` during `init` or `associate-thread` afterward.

## Surface Reference

Use the lightest surface that fits:

- Markdown: plans, notes, specs, reviews, decision logs.
- Markdown plus JSON: repeatedly updated structured state.
- Static HTML plus JavaScript/CDN libraries: filters, charts, diagrams, drag/drop, tables, maps, calendars, and other simple interaction.
- Vite plus React, TypeScript, Tailwind, and shadcn/ui: complex static canvas apps.
- Next.js plus Tailwind and shadcn/ui: only when server behavior, routing, API routes, auth, or similar features are genuinely needed.

If `frontend-design` is installed and the canvas needs a new or materially revised browser UI, use that skill before designing or editing the UI. A request for a planner, board, dashboard, tracker, map, calendar, or other usable visual workspace is enough to justify a canvas-specific UI.

Allowed CDN libraries for static pages include Chart.js, Mermaid, SortableJS, Marked, DOMPurify, Fuse.js, Tabulator/Grid.js, Leaflet, and FullCalendar.

Static HTML surfaces must be real HTML pages on disk. Do not generate scripts whose main job is to write the HTML later.

## Export Guard

Use `export-html` to create or intentionally regenerate the starter HTML shell and `canvas-data.js` sidecar. The shared starter template intentionally has no `<body>` content; do not add generic UI to this skill's `templates/canvas-viewer.html`.

`export-html` is not a safe refresh command for an existing customized `canvas.html`: it can overwrite the custom UI with the blank starter shell. Before running it, inspect `canvas.html` if it exists. If it has a non-empty `<body>`, canvas-specific CSS/JS, or a custom surface marker, preserve it first and run `export-html` only when intentionally regenerating the starter shell or immediately restoring/reapplying the custom surface.

For existing custom HTML canvases, the default update flow is: edit `state.json`, `notes.md`, and/or `canvas.html`; run `validate`; reload the HTTP URL in the Browser. Do not run `export-html`.

## Local Server

Prefer the Canvas HTTP server over `file://` paths for Browser inspection. Pages served from `http://127.0.0.1` are easier for Codex Browser tooling to inspect and control.

```bash
.\scripts\canvas.exe serve
.\scripts\canvas.exe server-status
.\scripts\canvas.exe server-stop
.\scripts\canvas.exe open -id review-board
```

`serve` binds to `127.0.0.1:12345` unless `-port` is passed. `open -id <canvas-id>` starts the server if needed and returns the canvas URL. The root URL shows a searchable and sortable Canvas index backed by `.server.json`.

CLI mutations update `.server.json` when it exists. If direct file edits make the index stale, run `server-status` or a relevant CLI update/validate flow before relying on the index.

## Response

When presenting a canvas, include:

- canvas id
- scope and anchor
- storage path
- files created or updated
- whether anything was promoted
- how to continue

Be explicit when something is only a working artifact.
