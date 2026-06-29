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
python -m pytest
```

Run CLI locally:

```powershell
python -m canvas_cli --help
```

