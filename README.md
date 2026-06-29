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

Run only the MCP transport/lifecycle smoke:

```powershell
python scripts\smoke_mcp.py
python scripts\smoke_mcp.py --installed
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
- `scripts\validate.py` runs compile checks, unit tests, source MCP smoke, and plugin manifest validation.
- `scripts\validate.py --installed` additionally verifies the latest installed `canvas@personal` plugin cache.

Fresh Codex thread smoke tests are still useful after reinstalling a cachebusted plugin, but the source and installed MCP smoke scripts catch the transport and lifecycle failures locally before that step.
