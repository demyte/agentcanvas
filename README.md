# Canvas

Canvas is a local Codex plugin that gives agents a semi-persistent workspace for active work.

Use it when a task needs a shared working surface that should survive beyond scratch notes, but should not yet be written into the repo or promoted into durable project memory.

Canvas is useful for reviews, investigations, planning boards, trackers, dashboards, research notes, browser-inspectable artifacts, and small interactive workspaces.

## Prerequisites

- Codex with local plugin support.
- `codex` CLI available on the path.
- .NET SDK available as `dotnet`.
- PowerShell.

## Install

Clone the repo and install the plugin from the repo root:

```powershell
git clone https://github.com/demyte/agentcanvas.git
cd agentcanvas
codex plugin add canvas@personal --json
```

Confirm it is installed:

```powershell
codex plugin list --json
```

`codex plugin add` installs from a configured marketplace selector such as `canvas@personal`. It does not currently install directly from a raw GitHub repo URL, so clone the repo first.

## Use It From An Agent

After installation, ask Codex naturally. You can refer to it as Canvas, `/canvas`, `$canvas`, or `@Canvas`.

Create a new canvas:

```text
@Canvas create a canvas for this review.
```

```text
Create a meal planner canvas named meals01.
```

Open or inspect an existing canvas:

```text
@Canvas open the canvas for this investigation.
```

```text
Show me the HTTP link for the xpna-prod-exception-loop canvas.
```

List canvases:

```text
@Canvas list my active canvases.
```

Update canvas state or notes:

```text
Add the current decisions and open questions to this canvas.
```

```text
Refresh the review canvas and validate it.
```

Create a visual surface:

```text
Create a project dashboard canvas for this work.
```

```text
Turn this plan into an interactive tracker canvas.
```

Clean up thread associations:

```text
@Canvas dry-run cleanup for stale thread associations.
```

Archive completed work:

```text
Archive the canvas for this finished review.
```

Canvas starts its local server when needed and returns HTTP links like:

```text
http://127.0.0.1:12345/canvas/<canvas-id>/
```

The server index is:

```text
http://127.0.0.1:12345/
```

## Local Web Server

Canvas uses a small local web server because the Codex in-app Browser works more reliably with normal `http://` pages than with `file://` URLs. Serving canvases over HTTP lets the agent inspect and interact with canvas pages as web pages.

The server binds only to `127.0.0.1`. It is local to the machine running Codex and is not exposed to other machines on the network.
