from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = Path.home() / ".codex" / "plugins" / "cache" / "personal" / "canvas"


class SmokeFailure(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_plugin_version() -> str:
    version = load_json(ROOT / ".codex-plugin" / "plugin.json").get("version")
    if not isinstance(version, str) or not version.strip():
        raise SmokeFailure("Source plugin manifest is missing a non-empty version")
    return version


def latest_installed_plugin(expected_version: str | None = None) -> Path:
    if not DEFAULT_CACHE_ROOT.exists():
        raise SmokeFailure(f"Installed canvas plugin cache not found: {DEFAULT_CACHE_ROOT}")
    candidates = [
        item
        for item in DEFAULT_CACHE_ROOT.iterdir()
        if item.is_dir()
        and (item / ".codex-plugin" / "plugin.json").exists()
        and (item / "scripts" / "canvas.py").exists()
    ]
    if not candidates:
        raise SmokeFailure(f"No complete installed canvas plugin versions found under: {DEFAULT_CACHE_ROOT}")
    if expected_version:
        expected = DEFAULT_CACHE_ROOT / expected_version
        if expected not in candidates:
            raise SmokeFailure(f"Installed canvas plugin version {expected_version!r} not found under: {DEFAULT_CACHE_ROOT}")
        return expected
    return max(candidates, key=lambda item: item.name)


def plugin_root(args: argparse.Namespace) -> Path:
    if args.installed:
        expected_version = args.expected_version or source_plugin_version()
        root = Path(args.plugin_root).expanduser() if args.plugin_root else latest_installed_plugin(expected_version)
        actual_version = load_json(root / ".codex-plugin" / "plugin.json").get("version")
        if actual_version != expected_version:
            raise SmokeFailure(f"Installed plugin version {actual_version!r} does not match expected {expected_version!r}")
        return root
    return Path(args.plugin_root).expanduser() if args.plugin_root else ROOT


class CliClient:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.script = self.root / "scripts" / "canvas.py"
        if not self.script.exists():
            raise SmokeFailure(f"Canvas CLI wrapper not found: {self.script}")

    def tool(self, name: str, payload: dict[str, Any]) -> Any:
        result = self.tool_raw(name, payload)
        if result["returncode"] != 0:
            raise SmokeFailure(f"Canvas CLI failed for {name}: {result['data']}")
        return result["data"]

    def tool_raw(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = subprocess.run(
            [sys.executable, str(self.script), "tool", name, json.dumps(payload, separators=(",", ":"))],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SmokeFailure(f"Canvas CLI returned invalid JSON for {name}: {result.stdout}{result.stderr}") from exc
        return {"returncode": result.returncode, "data": data, "stderr": result.stderr}


def smoke(root: Path, canvas_id: str) -> dict[str, Any]:
    client = CliClient(root)
    with tempfile.TemporaryDirectory() as tmp:
        created = client.tool(
            "canvas_init",
            {
                "id": canvas_id,
                "scope": "thread",
                "title": "CLI Smoke",
                "purpose": "automated bundled CLI smoke test",
                "associatedThreads": ["thread-smoke", "thread-shared"],
                "promotion_targets": ["cli-report"],
                "root": tmp,
            },
        )
        listed_by_thread = client.tool("canvas_list", {"threadId": "thread-smoke", "root": tmp})
        associated = client.tool(
            "canvas_associate_thread",
            {"id": canvas_id, "threadId": "thread-associated-smoke", "root": tmp},
        )
        updated = client.tool("canvas_update_state", {"id": canvas_id, "updates": {"status": "ready"}, "root": tmp})
        fetched = client.tool("canvas_get", {"id": canvas_id, "root": tmp})
        active = client.tool("canvas_validate", {"id": canvas_id, "lifecycle": "active", "root": tmp})
        exported = client.tool("canvas_export_html", {"id": canvas_id, "root": tmp})
        promoted = client.tool(
            "canvas_promote",
            {"id": canvas_id, "target": "cli-report", "reference": "outputs/cli-report.md", "root": tmp},
        )
        archived = client.tool("canvas_archive", {"id": canvas_id, "root": tmp})
        archived_validation = client.tool(
            "canvas_validate",
            {"id": canvas_id, "lifecycle": "archived", "root": tmp},
        )

    if [item["id"] for item in listed_by_thread] != [canvas_id]:
        raise SmokeFailure(f"Thread-filtered list was unexpected: {listed_by_thread}")
    if not active["valid"] or not archived_validation["valid"]:
        raise SmokeFailure(f"Validation failed: active={active} archived={archived_validation}")
    return {
        "cli": [sys.executable, str(client.script)],
        "created": created["id"],
        "fetched": fetched["id"],
        "associatedThreads": associated["associatedThreads"],
        "state": updated["state"]["status"],
        "promotion": promoted["promotions"][-1]["target"],
        "exports": {"active": exported["valid"]},
        "archived": archived["lifecycle"],
        "validations": {"active": active["valid"], "archived": archived_validation["valid"]},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the bundled Canvas CLI.")
    parser.add_argument("--installed", action="store_true", help="Smoke-test the installed personal plugin cache matching the source manifest.")
    parser.add_argument("--plugin-root", default="", help="Plugin root to test. Defaults to source root, or in installed mode to the cache matching the expected version.")
    parser.add_argument("--expected-version", default="", help="Expected installed plugin version. Defaults to source manifest.")
    parser.add_argument("--canvas-id", default="cli-smoke", help="Throwaway canvas id for lifecycle calls.")
    args = parser.parse_args()

    root = plugin_root(args).resolve()
    result = smoke(root, args.canvas_id)
    print(json.dumps({"ok": True, "plugin_root": str(root), **result}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
