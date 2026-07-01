---
name: canvas
description: "Canvas: use when the user asks for a canvas, shared board, workspace, live planning surface, interactive dashboard, artifact workspace, or Copilot-style canvas in Codex. Use the bundled Canvas CLI for creation, listing, reading, updates, validation, export, archival, thread association, server management, and promotion records."
---

# Canvas

Create and maintain semi-persistent Codex work surfaces: durable enough for active work, not durable project truth until the user explicitly promotes them.

## Contract

The Canvas CLI owns storage, lifecycle, paths, validation, export sidecars, server state, archive movement, and promotion records. Do not hand-create `canvas.json`, choose storage paths, move lifecycle folders, or invent the layout.

Run from the skill folder:

```powershell
.\scripts\canvas.exe <command> <arguments>
```

If the executable is missing or stale, publish and run it through the wrapper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\canvas.ps1 <command> <arguments>
```

The wrapper publishes `.\scripts\canvas.cs` to `.\scripts\canvas.exe`. Assume `dotnet` is on the path. Use CLI verbs and arguments, not JSON payloads; for richer state, write a temporary JSON object and pass `-merge-file <path>`.

Treat returned `storage_path`, `html_path`, `data_path`, and HTTP URLs as authoritative.

## Operating Loop

1. Classify the canvas: purpose, scope, anchor, surface, expected actions, and promotion target. Completion: the choices are specific enough to create or update without guessing.
2. Create or read it through the CLI. For new work, run `init`; for existing work, use `list`, `list -thread-id <thread-id>`, or `get`. Pass `-human-action`, `-agent-action`, `-promotion-target`, and `-associated-thread` when they shape the workflow. Completion: the CLI has returned the metadata and paths you will use.
3. Update only canvas-owned artifacts. Use `update-state` for structured state. Edit returned files directly only for notes, README files, or a custom `canvas.html`; preserve user edits. Completion: the intended state, notes, and surface changes are present in the canvas folder, including a usable HTML surface when the request implies a visual workspace.
4. Validate and inspect. Run `validate` after material changes. Use `open -id <canvas-id>` for Browser inspection because it serves `http://127.0.0.1` URLs and starts the server if needed. Completion: validation passes, or any remaining issue is reported explicitly.
5. Promote only on request. Use `promote` to record explicit durable promotion references; it records the promotion and does not write arbitrary destination files. Completion: the user can tell what stayed canvas work and what became durable state.

## Scope

Choose the narrowest useful scope:

- `repo`: repository, branch, issue, PR, code review, architecture trace, test plan, implementation workflow.
- `project`: non-repo project folder, household workspace, business process, operational domain.
- `thread`: work intentionally tied to one conversation.
- `user`: cross-project dashboards, reusable templates, personal or household planning.

Prefer `repo` or `project` when a real anchor exists. Use `user` for casual "create me a canvas for..." requests when no repo or project anchor is real. Use `thread` only when the user asks for thread-scoped work or the work is meaningless outside the conversation.

Thread identifiers are associations, not anchors. Store them with `-associated-thread` during `init` or `associate-thread` afterward.

## Surface

Use the lightest surface that fits, but do not reduce an implied visual workspace to notes-only.

- Markdown: plans, notes, specs, reviews, decision logs.
- Markdown plus JSON: repeatedly updated structured state.
- Static HTML plus JavaScript/CDN libraries: filters, charts, diagrams, drag/drop, tables, maps, calendars, and simple interaction.
- Vite plus React, TypeScript, Tailwind, and shadcn/ui: complex static canvas apps.
- Next.js plus Tailwind and shadcn/ui: only when server behavior, routing, API routes, auth, or similar features are genuinely needed.

If the user asks for a planner, board, dashboard, tracker, calendar, map, or other usable workspace, create or update both the structured state and a real `canvas.html` UI unless the user explicitly asks for notes-only or markdown-only output.

If `frontend-design` is installed and the canvas needs a new or materially revised browser UI, use that skill before designing or editing the UI.

Allowed CDN libraries for static pages include Chart.js, Mermaid, SortableJS, Marked, DOMPurify, Fuse.js, Tabulator/Grid.js, Leaflet, and FullCalendar.

Static HTML surfaces must be real HTML pages on disk. Do not generate scripts whose main job is to write the HTML later.

## Export Guard

`export-html` creates or intentionally regenerates the starter `canvas.html` shell and `canvas-data.js` sidecar. The starter template intentionally has no `<body>` content; do not add generic UI to `templates/canvas-viewer.html`.

Before running `export-html` on an existing canvas, inspect `canvas.html`. If it has a non-empty `<body>`, canvas-specific CSS/JS, or a custom marker, preserve it first and run `export-html` only when intentionally replacing the starter shell or immediately restoring the custom surface.

For existing custom HTML canvases, the default update flow is: edit `state.json`, `notes.md`, and/or `canvas.html`; run `validate`; reload the HTTP URL in the Browser. Do not run `export-html`.

## Server

Use the local server for Browser work:

```powershell
.\scripts\canvas.exe serve
.\scripts\canvas.exe server-status
.\scripts\canvas.exe server-stop
.\scripts\canvas.exe open -id review-board
```

`serve` binds to `127.0.0.1:12345` unless `-port` is passed. The root URL shows a searchable and sortable Canvas index backed by `.server.json`. CLI mutations update `.server.json` when it exists; after direct file edits, run `validate`, `server-status`, or another relevant CLI command before relying on the index.

## Response

When presenting a canvas, include: canvas id, scope and anchor, storage path, files created or updated, promotion status, and how to continue. Be explicit when something is only a working artifact.
