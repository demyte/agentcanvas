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
python ./src/canvas_mcp_server.py
```

This repo is ready to be added to a local Codex plugin marketplace. The current build does not modify any global Codex marketplace files automatically.
