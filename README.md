# Canvas

Canvas is a local Codex plugin that gives agents a semi-persistent workspace for active work.

It is for work that should survive beyond a scratch file, but is not yet durable project truth. A canvas can hold notes, structured state, browser-facing HTML, thread associations, and promotion records without writing those working artifacts into the repository you are operating on.

## What It Does

Canvas lets an agent:

- create named workspaces under the user profile
- keep structured state in `state.json`
- keep readable notes in `notes.md`
- track metadata, lifecycle, scope, thread associations, and promotions in `canvas.json`
- serve canvases over `http://127.0.0.1:12345/` for Codex Browser inspection
- create interactive static HTML surfaces when the task calls for a board, planner, dashboard, tracker, map, or review surface
- archive canvases when the active work is finished
- dry-run cleanup of stale thread associations from a supplied `threads.json`

Default storage:

```text
~/.agents/canvas
```

On Windows this is normally:

```text
C:\Users\<you>\.agents\canvas
```

Canvas stores work outside the repo by default. Nothing becomes durable project documentation, project memory, issue content, or source code unless the user explicitly asks for promotion.

## Prerequisites

- Codex with local plugin support.
- `codex` CLI available on the path.
- .NET SDK on the path as `dotnet`.
- PowerShell for the bundled wrapper examples.

The CLI is a .NET file-based app. If `skills/canvas/scripts/canvas.exe` is missing or stale, the wrapper publishes it from `skills/canvas/scripts/canvas.cs`.

## Install

Clone the repository, then install it from the repo root:

```powershell
git clone https://github.com/demyte/agentcanvas.git
cd agentcanvas
codex plugin add canvas@personal --json
```

Confirm it is installed:

```powershell
codex plugin list --json
```

The plugin installs the `canvas` skill and bundles the Canvas CLI.

## Use It From An Agent

After installation, ask Codex naturally:

```text
Create a canvas for this review.
```

```text
List my active canvases.
```

```text
Open the canvas for this investigation.
```

```text
Create a meal planner canvas named meals01.
```

The skill tells the agent to start the Canvas server if needed, use the bundled CLI for storage and lifecycle operations, and return the HTTP URL for the canvas.

## Use The CLI Directly

From the repo root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File skills\canvas\scripts\canvas.ps1 --help
```

After the executable exists:

```powershell
skills\canvas\scripts\canvas.exe --help
```

Common commands:

| Command | Purpose |
| --- | --- |
| `init` | Create a canvas. |
| `list` | List canvases. |
| `get` | Read canvas metadata. |
| `update-state` | Merge values into `state.json`. |
| `validate` | Validate canvas metadata and files. |
| `serve` | Start the local HTTP server. |
| `open` | Return the HTTP URL for one canvas. |
| `archive` | Move an active canvas to archived lifecycle. |
| `associate-thread` | Add a Codex thread id to `associatedThreads`. |
| `clean-threads` | Dry-run or apply cleanup from a supplied `threads.json`. |
| `promote` | Record an explicit promotion reference. |
| `export-html` | Regenerate the starter HTML shell and data sidecar. |

Create a repo-scoped canvas:

```powershell
skills\canvas\scripts\canvas.exe init `
  -id review-board `
  -scope repo `
  -anchor D:\Projects\repo `
  -purpose "Track review work"
```

Start the server and open a canvas:

```powershell
skills\canvas\scripts\canvas.exe serve
skills\canvas\scripts\canvas.exe open -id review-board
```

The default server URL is:

```text
http://127.0.0.1:12345/
```

## Thread Cleanup

Thread-aware canvases store associations in `canvas.json`:

```json
{
  "associatedThreads": [
    "019eecad-8e7f-7df0-85ef-385e2b0d8ace"
  ]
}
```

The CLI does not discover Codex thread status by itself. The agent should build a `threads.json` snapshot from Codex thread tooling, then pass it to the CLI.

Example `threads.json`:

```json
{
  "generated_at": "2026-07-02T04:10:00Z",
  "threads": [
    {
      "id": "019eecad-8e7f-7df0-85ef-385e2b0d8ace",
      "exists": false,
      "status": "missing",
      "archived": false
    }
  ]
}
```

Dry-run cleanup:

```powershell
skills\canvas\scripts\canvas.exe clean-threads -thread-state-file .\threads.json
```

Apply after review:

```powershell
skills\canvas\scripts\canvas.exe clean-threads -thread-state-file .\threads.json -apply
```

## Browser Surfaces

Canvas serves canvases through the local server so Codex Browser can inspect them as normal web pages.

Static canvas pages can use JavaScript and CDN libraries. The shared template at `skills/canvas/templates/canvas-viewer.html` is only a blank creation stub. Existing custom `canvas.html` files should be edited directly and validated; do not run `export-html` as a routine refresh because it can overwrite a custom page with the starter shell.

## Repository Layout

```text
.codex-plugin/plugin.json       Codex plugin manifest
skills/canvas/SKILL.md          Agent instructions
skills/canvas/scripts/          CLI source, wrapper, and generated exe
skills/canvas/templates/        HTML and server templates
```

Generated executables and test output are ignored by git.
