# Canvas

Canvas is a local Codex plugin for semi-persistent workspaces.

A canvas is more durable than scratch files and less authoritative than project memory. It gives Codex a stable place to track state, notes, actions, and promotion targets across turns without silently committing files into a repo or project.

## Layout

```text
.codex-plugin/plugin.json  # Codex plugin manifest
.mcp.json                  # MCP server configuration
skills/canvas/SKILL.md     # Codex skill instructions
scripts/                   # CLI and support scripts
src/canvas/                # Core implementation
tests/                     # Automated tests
```

## Development

Run tests:

```powershell
python -m unittest discover -s tests
```

Run full validation:

```powershell
python scripts\validate.py
```

Run full validation plus the installed personal plugin cache smoke:

```powershell
python scripts\validate.py --installed
```

Run the full validation plus the fifteen-scenario MCP/browser-surface suite:

```powershell
python scripts\validate.py --scenarios
python scripts\validate.py --installed --scenarios
```

Run only the MCP transport/lifecycle smoke:

```powershell
python scripts\smoke_mcp.py
python scripts\smoke_mcp.py --installed
```

Run the scenario suite directly:

```powershell
python scripts\run_scenarios.py
python scripts\run_scenarios.py --installed
```

The scenario suite writes a local browser report to:

```text
.canvas-test-output\report.html
```

Run CLI locally:

```powershell
python scripts\canvas.py --help
```

## Codex Connection

The plugin manifest is at:

```text
.codex-plugin/plugin.json
```

The MCP server config is at:

```text
.mcp.json
```

The MCP server entry point is:

```text
src/canvas_mcp_server.py
```

The plugin MCP config starts the server relative to the installed plugin root:

```text
C:\Users\james\AppData\Local\Python\pythoncore-3.14-64\python.exe ./src/canvas_mcp_server.py
```

This repo is ready to be added to a local Codex plugin marketplace. The current build does not modify any global Codex marketplace files automatically.

## Testing Strategy

The automated checks are layered:

- Unit tests cover the registry, CLI, plugin config, MCP methods, error handling, and probes.
- `scripts\smoke_mcp.py` starts the MCP server through the plugin `.mcp.json` command and uses Codex-compatible newline JSON-RPC over stdio.
- `scripts\run_scenarios.py` drives fifteen end-to-end MCP scenarios and renders HTML surfaces for browser validation.
- `scripts\validate.py` runs compile checks, unit tests, source MCP smoke, optional scenario validation, and plugin manifest validation.
- `scripts\validate.py --installed` additionally verifies the latest installed `canvas@personal` plugin cache.

Fresh Codex thread smoke tests are still useful after reinstalling a cachebusted plugin, but the source and installed MCP smoke scripts catch the transport and lifecycle failures locally before that step.

## Browser Surfaces

Canvas can export any active or archived canvas to a deterministic static HTML file:

```powershell
python scripts\canvas.py export-html <canvas-id>
```

The MCP equivalent is `canvas_export_html`. The HTML export is a review surface for the current working artifact; it does not promote canvas content into durable project state by itself.

The exported `canvas.html` is copied from the checked-in disk template at `templates\canvas-viewer.html`. Export does not build HTML with Python string templates. Canvas-specific state is written beside it as `canvas-data.js`, and the page reads that local sidecar file in the browser.

## Custom Capabilities

Canvas metadata can carry domain-specific actions and promotion targets. With the CLI, pass repeated values while creating a canvas:

```powershell
python scripts\canvas.py init incident-board --scope project --human-action declare_severity --agent-action summarize_timeline --promotion-target post-incident-report
```

The MCP `canvas_init` tool accepts matching `human_actions`, `agent_actions`, and `promotion_targets` arrays.
