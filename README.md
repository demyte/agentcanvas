# Canvas

Canvas is a local Codex plugin for semi-persistent workspaces.

It gives Codex a stable place to keep working notes, structured state, browser review surfaces, and promotion records without silently writing those artifacts into the repository or project you are working on.

Use a canvas when a task is too substantial for scratch files, but not ready to become durable project memory, documentation, dashboard state, or committed source.

## Why Use It

Canvas is useful for:

- code reviews and architecture investigations
- research briefs that need to survive across turns
- planning boards and decision logs
- local dashboards for project or household operations
- interactive review surfaces built as static HTML
- work that may later be promoted into docs, memory, issues, PR comments, reports, or dashboards

The important distinction is authority:

```text
scratch
  Temporary execution files. Safe to delete.

canvas
  Semi-persistent working state. Useful across turns or days, but not authoritative.

project truth
  Durable state: repo files, project docs, project memory, dashboards, automation rules.
```

A canvas can inform durable state, but it does not become durable state until you explicitly promote it.

## What It Creates

Each canvas is a folder with a small, predictable file set:

```text
canvas.json       # metadata, scope, lifecycle, capabilities, promotion records
state.json        # structured working state
notes.md          # readable working notes
README.md         # orientation for humans and agents
canvas.html       # optional exported browser surface
canvas-data.js    # optional data sidecar for canvas.html
```

The default storage root is:

```text
~/.agents/canvas
```

On Windows this is normally:

```text
C:\Users\<you>\.agents\canvas
```

The plugin owns the concrete path layout. Codex should use the `storage_path`, `html_path`, and `data_path` returned by the MCP tools instead of guessing paths.

## Using It In Codex

After the plugin is installed, ask Codex for a canvas directly:

```text
Create a canvas for this review.
```

```text
Use /canvas to track this investigation.
```

```text
List my active canvases.
```

```text
Export this canvas to HTML so I can inspect it.
```

The bundled `canvas` skill tells Codex to defer creation, updates, validation, archival, promotion records, and HTML export to the Canvas MCP tools.

## MCP Tools

Canvas exposes these MCP tools:

| Tool | Purpose |
| --- | --- |
| `canvas_init` | Create a new canvas. |
| `canvas_list` | List canvases, optionally by lifecycle or associated thread. |
| `canvas_get` | Read canvas metadata. |
| `canvas_update_state` | Shallow-merge structured updates into `state.json`. |
| `canvas_validate` | Validate a canvas folder and metadata. |
| `canvas_archive` | Move an active canvas to archived lifecycle. |
| `canvas_associate_thread` | Attach another Codex thread id to a canvas. |
| `canvas_promote` | Record that canvas output was explicitly promoted somewhere durable. |
| `canvas_export_html` | Export a static `canvas.html` browser surface. |

Thread-aware canvases use `associatedThreads` in `canvas.json`. You can create a thread-scoped canvas with known thread ids, associate more threads later, and filter `canvas_list` by `threadId`.

## CLI Usage

The local CLI is useful for testing, inspection, and direct operations:

```powershell
python scripts\canvas.py --help
```

Create a repo-scoped canvas:

```powershell
python scripts\canvas.py init review-pr-123 `
  --scope repo `
  --anchor D:\Projects\my-repo `
  --title "PR 123 Review" `
  --purpose "Track review findings and follow-up validation."
```

Create a thread-scoped canvas:

```powershell
python scripts\canvas.py init thread-brief `
  --scope thread `
  --associated-thread <thread-id>
```

List canvases associated with a thread:

```powershell
python scripts\canvas.py list --thread-id <thread-id>
```

Update structured state:

```powershell
python scripts\canvas.py update-state review-pr-123 '{"status":"reviewing"}'
```

Export a browser surface:

```powershell
python scripts\canvas.py export-html review-pr-123
```

Archive when finished:

```powershell
python scripts\canvas.py archive review-pr-123
```

## Browser Surfaces

Canvas exports static HTML starter pages on disk. The HTML file is copied from the checked-in blank template at:

```text
templates/canvas-viewer.html
```

Canvas-specific data is written beside it as `canvas-data.js`. The default template intentionally has no body; it only loads the default browser libraries and the local data sidecar. Treat it as a creation stub, not a designed review surface or a promotion into durable project state.

Seeing a blank page after `canvas_export_html` is expected. Build a body only when you explicitly want a canvas-specific browser surface.

For richer local surfaces, prefer the lightest option that works:

```text
Default
  Static HTML template plus local sidecar data files.

Interactive static page
  Static HTML, JavaScript, and CDN libraries such as Chart.js, Mermaid,
  SortableJS, Marked, DOMPurify, Fuse.js, Tabulator/Grid.js, Leaflet,
  or FullCalendar.

Complex static app
  Vite + React + TypeScript + Tailwind + shadcn/ui.

Server or routing needed
  Next.js + Tailwind + shadcn/ui only when server behavior, API routes,
  auth, or multi-route app structure is genuinely needed.
```

## Promotion

Promotion means copying, summarizing, or integrating canvas output into a durable destination by explicit request.

Examples include:

- repo documentation
- project memory
- project dashboard or catalog entry
- issue or PR comment
- source, test, or docs changes
- final report

`canvas_promote` records the promotion target and reference. It does not perform arbitrary writes into the destination on its own.

## Configuration

Canvas uses Python on the path:

```text
python ./src/canvas_mcp_server.py
```

The plugin manifest is:

```text
.codex-plugin/plugin.json
```

The MCP server config is:

```text
.mcp.json
```

You can override the canvas storage root with `CANVAS_ROOT` or the CLI/MCP `root` argument:

```powershell
$env:CANVAS_ROOT = "D:\CanvasTest"
python scripts\canvas.py list
```

## Install Locally

This repository is intended to be installed as a local Codex plugin.

From the repo root:

```powershell
codex plugin add canvas@personal --json
```

Then confirm the installed plugin:

```powershell
codex plugin list --json
```

## Development

Run unit tests:

```powershell
python -m unittest discover -s tests
```

Run full source validation:

```powershell
python scripts\validate.py
```

Run validation with the installed plugin cache:

```powershell
python scripts\validate.py --installed
```

Run the full scenario suite:

```powershell
python scripts\validate.py --scenarios
python scripts\validate.py --installed --scenarios
```

The scenario suite writes a local report to:

```text
.canvas-test-output\report.html
```

The validation stack checks Python compilation, unit tests, MCP transport behavior, source and installed plugin startup, the plugin manifest, and fifteen end-to-end scenarios.

If a Codex thread cannot see the Canvas MCP tools, use the bundled CLI as a compatibility path for the same operations and report that MCP tools were not exposed in that thread. Do not hand-create `canvas.json` or invent storage paths.

## Repository Layout

```text
.codex-plugin/plugin.json  # Codex plugin manifest
.mcp.json                  # MCP server configuration
skills/canvas/SKILL.md     # Codex skill instructions
src/                       # Core registry, CLI, and MCP server
scripts/                   # CLI wrapper and validation helpers
templates/                 # Static browser surface template
tests/                     # Automated tests
```
