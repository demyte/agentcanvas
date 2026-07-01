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

The plugin owns the concrete path layout. Codex should use the `storage_path`, `html_path`, and `data_path` returned by the bundled CLI instead of guessing paths.

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

The bundled `canvas` skill tells Codex to defer creation, updates, validation, archival, promotion records, and HTML export to the Canvas CLI.

## CLI Operations

Canvas bundles a .NET file-based CLI with command verbs:

| Command | Purpose |
| --- | --- |
| `init` | Create a new canvas. |
| `list` | List canvases, optionally by lifecycle or associated thread. |
| `get` | Read canvas metadata. |
| `update-state` | Merge structured updates into `state.json`. |
| `validate` | Validate a canvas folder and metadata. |
| `archive` | Move an active canvas to archived lifecycle. |
| `associate-thread` | Attach another Codex thread id to a canvas. |
| `promote` | Record that canvas output was explicitly promoted somewhere durable. |
| `export-html` | Export a static `canvas.html` browser surface. |
| `serve` | Start the local Canvas HTTP server. |
| `open` | Start the server if needed and return a canvas HTTP URL. |
| `server-status` | Show local Canvas HTTP server status. |
| `server-stop` | Stop the local Canvas HTTP server. |

Thread-aware canvases use `associatedThreads` in `canvas.json`. You can create a thread-scoped canvas with known thread ids, associate more threads later, and filter with `list -thread-id <thread-id>`.

Run operations through:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\canvas.ps1 init -id "review-board" -scope repo -anchor "D:\Projects\repo"
skills\canvas\cli\canvas.exe list -lifecycle active
skills\canvas\cli\canvas.exe validate -id "review-board"
```

The PowerShell wrapper publishes `scripts\canvas.cs` just in time to `skills\canvas\cli\canvas.exe` when the executable is missing or stale. The `cli` folder is ignored by git.

## CLI Usage

The local CLI is useful for testing, inspection, and direct operations:

```powershell
skills\canvas\cli\canvas.exe --help
skills\canvas\cli\canvas.exe -?
skills\canvas\cli\canvas.exe init -?
```

Create a repo-scoped canvas:

```powershell
skills\canvas\cli\canvas.exe init -id review-pr-123 `
  -scope repo `
  -anchor D:\Projects\my-repo `
  -title "PR 123 Review" `
  -purpose "Track review findings and follow-up validation."
```

Create a thread-scoped canvas:

```powershell
skills\canvas\cli\canvas.exe init -id thread-brief `
  -scope thread `
  -associated-thread <thread-id>
```

List canvases associated with a thread:

```powershell
skills\canvas\cli\canvas.exe list -thread-id <thread-id>
```

Update structured state:

```powershell
skills\canvas\cli\canvas.exe update-state -id review-pr-123 -set status=reviewing
```

Merge richer state from a file:

```powershell
skills\canvas\cli\canvas.exe update-state -id review-pr-123 -merge-file .\state-update.json
```

Export a browser surface:

```powershell
skills\canvas\cli\canvas.exe export-html -id review-pr-123
```

`export-html` writes the starter `canvas.html` shell. For an existing canvas with a customized HTML surface, inspect or back up `canvas.html` first; running this command can replace that custom page with the blank starter template.

Archive when finished:

```powershell
skills\canvas\cli\canvas.exe archive -id review-pr-123
```

Start the local web server and open a canvas URL:

```powershell
skills\canvas\cli\canvas.exe serve
skills\canvas\cli\canvas.exe open -id review-pr-123
```

Without `-port`, `serve` binds to `127.0.0.1:12345`. Use `server-status` to inspect it and `server-stop` to stop it.

## Browser Surfaces

Canvas exports static HTML starter pages on disk. The HTML file is copied from the checked-in blank template at:

```text
skills/canvas/templates/canvas-viewer.html
```

Canvas-specific data is written beside it as `canvas-data.js`. The default template intentionally has no body; it only loads the default browser libraries and the local data sidecar. Treat it as a creation stub, not the final surface.

For existing customized HTML canvases, the normal update flow is to edit `state.json`, `notes.md`, and/or the custom `canvas.html`, run `validate`, then reload the open browser tab if possible. Do not run `export-html` as a routine refresh unless you mean to regenerate the starter shell or you will immediately restore/reapply the custom surface.

For Codex Browser inspection and control, prefer the local Canvas server instead of opening `file://` pages. `open -id <canvas-id>` starts the server if needed and returns a URL like:

```text
http://127.0.0.1:12345/canvas/review-pr-123/
```

The server root at `http://127.0.0.1:12345/` serves a searchable Canvas index from `.server.json`. It shows one card per canvas and supports local sorting by name or last modified time.

For planners, boards, dashboards, trackers, maps, calendars, or artifact workspaces, build the actual canvas-specific body in that canvas folder after export. Keep the shared template blank.

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

`promote` records the promotion target and reference. It does not perform arbitrary writes into the destination on its own.

## Configuration

Canvas uses the .NET SDK on the path to publish the file-based app:

```text
dotnet publish scripts\canvas.cs
```

The runtime executable is:

```text
skills\canvas\cli\canvas.exe
```

The plugin manifest is:

```text
.codex-plugin/plugin.json
```

You can override the canvas storage root with `CANVAS_ROOT` or the CLI `root` argument:

```powershell
$env:CANVAS_ROOT = "D:\CanvasTest"
skills\canvas\cli\canvas.exe list
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

The validation stack checks test helper compilation, unit tests, source and installed CLI startup, the plugin manifest, and fifteen end-to-end scenarios.

## Repository Layout

```text
.codex-plugin/plugin.json  # Codex plugin manifest
skills/canvas/SKILL.md     # Codex skill instructions
skills/canvas/templates/   # Static browser surface and server index templates
skills/canvas/cli/         # JIT-published canvas.exe, ignored by git
scripts/canvas.cs          # .NET file-based app entrypoint
scripts/canvas/            # Included C# CLI, registry, and server sources
scripts/                   # CLI wrapper and validation helpers
tests/                     # Automated tests
```
