from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .core import CanvasRegistry, normalize_canvas_id, utc_now


DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 12345
SERVER_STATE_FILE = ".server.json"
SERVER_INDEX_TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "server-index.html"


def server_state_path(registry: CanvasRegistry) -> Path:
    return registry.paths.root / SERVER_STATE_FILE


def canvas_url(port: int, canvas_id: str, host: str = DEFAULT_SERVER_HOST) -> str:
    return f"http://{host}:{port}/canvas/{normalize_canvas_id(canvas_id)}/"


def read_server_state(registry: CanvasRegistry) -> dict[str, Any] | None:
    path = server_state_path(registry)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_server_state(
    registry: CanvasRegistry,
    *,
    host: str = DEFAULT_SERVER_HOST,
    port: int,
    pid: int | None = None,
    running: bool = True,
) -> dict[str, Any]:
    registry.ensure_root()
    state = {
        "kind": "canvas-server",
        "host": host,
        "port": port,
        "pid": pid if pid is not None else os.getpid(),
        "root": str(registry.paths.root),
        "url": f"http://{host}:{port}/",
        "running": running,
        "updated_at": utc_now(),
        "canvases": server_canvas_records(registry, host=host, port=port),
    }
    server_state_path(registry).write_text(json.dumps(state, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return state


def refresh_server_state_if_present(registry: CanvasRegistry) -> None:
    state = read_server_state(registry)
    if not state:
        return
    host = str(state.get("host") or DEFAULT_SERVER_HOST)
    try:
        port = int(state.get("port") or DEFAULT_SERVER_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_SERVER_PORT
    pid = state.get("pid")
    write_server_state(registry, host=host, port=port, pid=pid if isinstance(pid, int) else None, running=bool(state.get("running", True)))


def server_canvas_records(registry: CanvasRegistry, *, host: str, port: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for metadata in registry.list_canvases():
        canvas_id = metadata.get("id")
        if not isinstance(canvas_id, str) or not canvas_id:
            continue
        canvas_dir = Path(str(metadata.get("storage_path") or ""))
        html_path = canvas_dir / "canvas.html"
        try:
            modified_at = max(
                item.stat().st_mtime
                for item in [canvas_dir / "canvas.json", canvas_dir / "state.json", canvas_dir / "notes.md", html_path]
                if item.exists()
            )
        except ValueError:
            modified_at = 0.0
        records.append(
            {
                "id": canvas_id,
                "title": metadata.get("title") or canvas_id,
                "purpose": metadata.get("purpose") or "",
                "scope": metadata.get("scope") or "",
                "lifecycle": metadata.get("lifecycle") or "",
                "anchor": metadata.get("anchor") or "",
                "updated_at": metadata.get("updated_at") or "",
                "modified_at": modified_at,
                "storage_path": str(canvas_dir),
                "has_html": html_path.exists(),
                "url": canvas_url(port, canvas_id, host),
            }
        )
    return sorted(records, key=lambda item: str(item.get("title", "")).lower())


def is_server_live(registry: CanvasRegistry) -> bool:
    state = read_server_state(registry)
    if not state:
        return False
    host = state.get("host") or DEFAULT_SERVER_HOST
    port = state.get("port")
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/canvases", timeout=1.5) as response:
            return response.status == HTTPStatus.OK
    except (OSError, urllib.error.URLError, ValueError):
        return False


def wait_for_server(registry: CanvasRegistry, *, timeout_seconds: float = 8.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_state: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        last_state = read_server_state(registry)
        if is_server_live(registry) and last_state:
            return last_state
        time.sleep(0.15)
    raise RuntimeError(f"Canvas server did not start within {timeout_seconds:.1f}s: {last_state}")


def start_server_process(
    registry: CanvasRegistry,
    *,
    script: Path,
    port: int = DEFAULT_SERVER_PORT,
) -> dict[str, Any]:
    state = read_server_state(registry)
    if state and is_server_live(registry):
        return state

    command = [
        sys.executable,
        str(script),
        "-root",
        str(registry.paths.root),
        "serve",
        "-port",
        str(port),
        "--foreground",
    ]
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(
        command,
        cwd=script.resolve().parents[1],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return wait_for_server(registry)


def stop_server(registry: CanvasRegistry) -> dict[str, Any]:
    state = read_server_state(registry)
    if not state:
        return {"running": False, "stopped": False, "message": "No server state found."}
    host = state.get("host") or DEFAULT_SERVER_HOST
    port = state.get("port")
    try:
        urllib.request.urlopen(f"http://{host}:{port}/__shutdown", timeout=2).read()
    except (OSError, urllib.error.URLError, ValueError):
        pass
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not is_server_live(registry):
            break
        time.sleep(0.15)
    state["running"] = False
    state["stopped_at"] = utc_now()
    server_state_path(registry).write_text(json.dumps(state, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return {"running": is_server_live(registry), "stopped": True, "state": state}


class CanvasHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], registry: CanvasRegistry):
        self.registry = registry
        super().__init__(server_address, CanvasRequestHandler)


class CanvasRequestHandler(BaseHTTPRequestHandler):
    server: CanvasHTTPServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            if path == "/":
                self._serve_index()
            elif path == "/server-state.json":
                self._serve_json(write_server_state(self.server.registry, port=self.server.server_port))
            elif path == "/api/canvases":
                state = write_server_state(self.server.registry, port=self.server.server_port)
                self._serve_json(state["canvases"])
            elif path.startswith("/api/canvas/") and path.endswith("/state"):
                self._serve_canvas_state(path)
            elif path == "/__shutdown":
                self._serve_json({"ok": True, "stopping": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            elif path.startswith("/canvas/"):
                self._serve_canvas_file(path)
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
        except Exception as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def _serve_index(self) -> None:
        self._serve_file(SERVER_INDEX_TEMPLATE, "text/html; charset=utf-8")

    def _serve_canvas_state(self, path: str) -> None:
        canvas_id = path.removeprefix("/api/canvas/").removesuffix("/state").strip("/")
        metadata = self.server.registry.get_canvas(canvas_id)
        state_path = Path(metadata["storage_path"]) / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        self._serve_json({"metadata": metadata, "state": state})

    def _serve_canvas_file(self, path: str) -> None:
        parts = [part for part in path.split("/") if part]
        if len(parts) < 2:
            self.send_error(HTTPStatus.NOT_FOUND, "Canvas id missing")
            return
        canvas_id = parts[1]
        relative_parts = parts[2:] or ["canvas.html"]
        metadata = self.server.registry.get_canvas(canvas_id)
        canvas_dir = Path(metadata["storage_path"]).resolve()
        target = (canvas_dir / Path(*relative_parts)).resolve()
        if canvas_dir != target and canvas_dir not in target.parents:
            self.send_error(HTTPStatus.FORBIDDEN, "Path escapes canvas directory")
            return
        if target.is_dir():
            target = target / "canvas.html"
        if not target.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Canvas file not found")
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.suffix.lower() in {".html", ".js", ".css", ".json", ".md", ".txt"}:
            content_type += "; charset=utf-8"
        self._serve_file(target, content_type)

    def _serve_json(self, payload: Any) -> None:
        body = json.dumps(payload, indent=2, sort_keys=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def run_foreground_server(registry: CanvasRegistry, *, port: int = DEFAULT_SERVER_PORT) -> dict[str, Any]:
    registry.ensure_root()
    with CanvasHTTPServer((DEFAULT_SERVER_HOST, port), registry) as httpd:
        actual_port = int(httpd.server_address[1])
        state = write_server_state(registry, port=actual_port)
        try:
            httpd.serve_forever()
        finally:
            state["running"] = False
            state["stopped_at"] = utc_now()
            server_state_path(registry).write_text(json.dumps(state, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        return state
