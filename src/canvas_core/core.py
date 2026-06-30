from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCOPES = {"repo", "project", "thread", "user"}
LIFECYCLES = {"active", "archived"}
CANVAS_VIEWER_TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "canvas-viewer.html"

DEFAULT_HUMAN_ACTIONS = [
    "inspect",
    "edit_notes",
    "mark_done",
    "request_refresh",
    "request_promotion",
]

DEFAULT_AGENT_ACTIONS = [
    "refresh_state",
    "add_item",
    "update_item",
    "summarize_changes",
    "regenerate_surface",
    "validate_surface",
    "archive_canvas",
]

DEFAULT_PROMOTION_TARGETS = [
    "repo-doc",
    "project-memory",
    "project-dashboard",
    "static-site-catalog",
    "issue-comment",
    "pull-request-comment",
    "final-report",
]


class CanvasError(Exception):
    """Base exception for canvas operations."""


class CanvasValidationError(CanvasError):
    """Raised when a canvas fails validation."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_canvas_root() -> Path:
    configured = os.environ.get("CANVAS_ROOT")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".agents" / "canvas"


def normalize_canvas_id(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    normalized = re.sub(r"-+", "-", normalized)
    if not normalized:
        raise CanvasValidationError("Canvas id cannot be empty after normalization.")
    if len(normalized) > 96:
        raise CanvasValidationError("Canvas id must be 96 characters or fewer.")
    return normalized


def ensure_relative_file(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise CanvasValidationError(f"State file must be relative to the canvas: {value}")
    return path.as_posix()


def coerce_list(values: list[str] | None, fallback: list[str], field_name: str = "value") -> list[str]:
    if values is None:
        return list(fallback)
    if not isinstance(values, list):
        raise CanvasValidationError(f"{field_name} must be an array of strings.")
    clean: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise CanvasValidationError(f"{field_name} must be an array of strings.")
        item = value.strip()
        if item and item not in clean:
            clean.append(item)
    return clean


def coerce_thread_ids(values: list[str] | None) -> list[str]:
    return coerce_list(values, [], "associatedThreads")


def validate_non_empty_string_list(value: Any, field_name: str, *, allow_missing: bool = False) -> list[str] | None:
    if value is None and allow_missing:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise CanvasValidationError(f"{field_name} must be an array of non-empty strings")
    return value


def validate_promotions(value: Any) -> None:
    if not isinstance(value, list):
        raise CanvasValidationError("promotions must be an array of promotion records")
    for index, promotion in enumerate(value):
        if not isinstance(promotion, dict):
            raise CanvasValidationError(f"promotions[{index}] must be an object")
        for field in ["target", "reference", "promoted_at"]:
            if not isinstance(promotion.get(field), str) or not promotion[field].strip():
                raise CanvasValidationError(f"promotions[{index}].{field} must be a non-empty string")
        if "note" in promotion and not isinstance(promotion["note"], str):
            raise CanvasValidationError(f"promotions[{index}].note must be a string")


def anchor_fingerprint(anchor: str | None) -> str:
    if not anchor:
        return ""
    expanded = Path(anchor).expanduser()
    try:
        resolved = expanded.resolve()
        return f"path:{resolved}"
    except OSError:
        return f"text:{anchor.strip()}"


@dataclass(frozen=True)
class CanvasPaths:
    root: Path
    active: Path
    archived: Path


class CanvasRegistry:
    def __init__(self, root: Path | None = None):
        self.paths = CanvasPaths(
            root=(root or default_canvas_root()).expanduser(),
            active=(root or default_canvas_root()).expanduser() / "active",
            archived=(root or default_canvas_root()).expanduser() / "archived",
        )

    def ensure_root(self) -> None:
        self.paths.active.mkdir(parents=True, exist_ok=True)
        self.paths.archived.mkdir(parents=True, exist_ok=True)

    def init_canvas(
        self,
        canvas_id: str,
        *,
        scope: str,
        anchor: str = "",
        title: str = "",
        purpose: str = "",
        human_actions: list[str] | None = None,
        agent_actions: list[str] | None = None,
        promotion_targets: list[str] | None = None,
        associated_threads: list[str] | None = None,
    ) -> dict[str, Any]:
        self.ensure_root()
        normalized_id = normalize_canvas_id(canvas_id)
        if scope not in SCOPES:
            raise CanvasValidationError(f"Scope must be one of {sorted(SCOPES)}.")

        canvas_dir = self.paths.active / normalized_id
        archived_dir = self.paths.archived / normalized_id
        if canvas_dir.exists() or archived_dir.exists():
            raise CanvasValidationError(f"Canvas already exists: {normalized_id}")

        canvas_dir.mkdir(parents=True)
        now = utc_now()
        state_files = ["state.json", "notes.md"]
        associated_thread_ids = coerce_thread_ids(associated_threads)
        metadata = {
            "id": normalized_id,
            "kind": "canvas",
            "lifecycle": "active",
            "authority": "working-artifact",
            "scope": scope,
            "anchor": anchor,
            "anchor_fingerprint": anchor_fingerprint(anchor),
            "storage_policy": "external-user-codex",
            "storage_path": str(canvas_dir),
            "title": title or normalized_id,
            "purpose": purpose,
            "created_from_thread": "",
            "last_updated_from_thread": "",
            "associatedThreads": associated_thread_ids,
            "created_at": now,
            "updated_at": now,
            "state_files": state_files,
            "human_actions": coerce_list(human_actions, DEFAULT_HUMAN_ACTIONS, "human_actions"),
            "agent_actions": coerce_list(agent_actions, DEFAULT_AGENT_ACTIONS, "agent_actions"),
            "shared_state": state_files,
            "promotion_targets": coerce_list(promotion_targets, DEFAULT_PROMOTION_TARGETS, "promotion_targets"),
            "promotions": [],
        }

        self._write_json(canvas_dir / "canvas.json", metadata)
        self._write_json(
            canvas_dir / "state.json",
            {
                "items": [],
                "decisions": [],
                "open_questions": [],
                "updated_at": now,
            },
        )
        (canvas_dir / "notes.md").write_text(
            f"# {metadata['title']}\n\nPurpose: {purpose or 'Working canvas.'}\n",
            encoding="utf-8",
        )
        (canvas_dir / "README.md").write_text(self._readme_text(metadata), encoding="utf-8")
        return metadata

    def list_canvases(self, lifecycle: str | None = None, thread_id: str | None = None) -> list[dict[str, Any]]:
        self.ensure_root()
        lifecycles = [lifecycle] if lifecycle else ["active", "archived"]
        thread_id = thread_id.strip() if thread_id else None
        records: list[dict[str, Any]] = []
        for item in lifecycles:
            if item not in LIFECYCLES:
                raise CanvasValidationError(f"Lifecycle must be one of {sorted(LIFECYCLES)}.")
            base = getattr(self.paths, item)
            for metadata_file in sorted(base.glob("*/canvas.json")):
                try:
                    metadata = self._read_json(metadata_file)
                    associated_threads = metadata.get("associatedThreads", [])
                    if thread_id and (
                        not isinstance(associated_threads, list) or thread_id not in associated_threads
                    ):
                        continue
                    records.append(metadata)
                except (OSError, json.JSONDecodeError):
                    if thread_id:
                        continue
                    records.append({"id": metadata_file.parent.name, "lifecycle": item, "invalid": True})
        return records

    def get_canvas(self, canvas_id: str, lifecycle: str | None = None) -> dict[str, Any]:
        metadata_file = self._metadata_path(canvas_id, lifecycle)
        return self._read_json(metadata_file)

    def update_state(
        self,
        canvas_id: str,
        updates: dict[str, Any],
        *,
        lifecycle: str | None = "active",
    ) -> dict[str, Any]:
        metadata_file = self._metadata_path(canvas_id, lifecycle)
        canvas_dir = metadata_file.parent
        state_file = canvas_dir / "state.json"
        state = self._read_json(state_file) if state_file.exists() else {}
        state.update(updates)
        state["updated_at"] = utc_now()
        self._write_json(state_file, state)

        metadata = self._read_json(metadata_file)
        metadata["updated_at"] = state["updated_at"]
        self._write_json(metadata_file, metadata)
        return {"metadata": metadata, "state": state}

    def archive_canvas(self, canvas_id: str) -> dict[str, Any]:
        self.ensure_root()
        normalized_id = normalize_canvas_id(canvas_id)
        source = self.paths.active / normalized_id
        target = self.paths.archived / normalized_id
        if not source.exists():
            raise CanvasValidationError(f"Active canvas not found: {normalized_id}")
        if target.exists():
            raise CanvasValidationError(f"Archived canvas already exists: {normalized_id}")

        validation = self.validate_canvas(normalized_id, "active")
        if not validation["valid"]:
            raise CanvasValidationError("; ".join(validation["errors"]))

        shutil.move(str(source), str(target))
        metadata_file = target / "canvas.json"
        metadata = self._read_json(metadata_file)
        metadata["lifecycle"] = "archived"
        metadata["storage_path"] = str(target)
        metadata["updated_at"] = utc_now()
        self._write_json(metadata_file, metadata)
        return metadata

    def associate_thread(
        self,
        canvas_id: str,
        *,
        thread_id: str,
        lifecycle: str | None = "active",
    ) -> dict[str, Any]:
        thread_id = thread_id.strip()
        if not thread_id:
            raise CanvasValidationError("threadId cannot be empty.")
        metadata_file = self._metadata_path(canvas_id, lifecycle)

        validation = self.validate_canvas(canvas_id, lifecycle)
        if not validation["valid"]:
            raise CanvasValidationError("; ".join(validation["errors"]))

        metadata = self._read_json(metadata_file)
        associated_threads = metadata.get("associatedThreads", [])
        validate_non_empty_string_list(associated_threads, "associatedThreads")
        if thread_id not in associated_threads:
            associated_threads = [*associated_threads, thread_id]
        metadata["associatedThreads"] = associated_threads
        metadata["last_updated_from_thread"] = thread_id
        metadata["updated_at"] = utc_now()
        self._write_json(metadata_file, metadata)
        validation = self.validate_canvas(metadata["id"], metadata["lifecycle"])
        if not validation["valid"]:
            raise CanvasValidationError("; ".join(validation["errors"]))
        return metadata

    def validate_canvas(self, canvas_id: str, lifecycle: str | None = None) -> dict[str, Any]:
        metadata_file = self._metadata_path(canvas_id, lifecycle)
        canvas_dir = metadata_file.parent
        errors: list[str] = []
        warnings: list[str] = []

        try:
            metadata = self._read_json(metadata_file)
        except json.JSONDecodeError as exc:
            return {"id": canvas_dir.name, "valid": False, "errors": [f"Invalid JSON: {exc}"], "warnings": []}

        required = ["id", "kind", "lifecycle", "authority", "scope", "storage_path", "state_files"]
        for field in required:
            if field not in metadata:
                errors.append(f"Missing metadata field: {field}")
        if metadata.get("kind") != "canvas":
            errors.append("kind must be 'canvas'")
        if metadata.get("lifecycle") not in LIFECYCLES:
            errors.append("lifecycle must be active or archived")
        else:
            actual_lifecycle = metadata_file.parent.parent.name
            if actual_lifecycle in LIFECYCLES and metadata.get("lifecycle") != actual_lifecycle:
                errors.append(f"lifecycle must match canvas location: {actual_lifecycle}")
        if metadata.get("scope") not in SCOPES:
            errors.append(f"scope must be one of {sorted(SCOPES)}")
        storage_path = metadata.get("storage_path")
        if not isinstance(storage_path, str) or not storage_path.strip():
            errors.append("storage_path must be a non-empty string")
        else:
            try:
                if Path(storage_path).expanduser().resolve() != canvas_dir.resolve():
                    errors.append("storage_path must match the canvas directory")
            except OSError as exc:
                errors.append(f"storage_path could not be resolved: {exc}")
        if "associatedThreads" in metadata:
            associated_threads = metadata["associatedThreads"]
            try:
                validate_non_empty_string_list(associated_threads, "associatedThreads")
            except CanvasValidationError as exc:
                errors.append(str(exc))
        if "promotion_targets" in metadata:
            try:
                validate_non_empty_string_list(metadata["promotion_targets"], "promotion_targets")
            except CanvasValidationError as exc:
                errors.append(str(exc))
        if "promotions" in metadata:
            try:
                validate_promotions(metadata["promotions"])
            except CanvasValidationError as exc:
                errors.append(str(exc))

        try:
            state_files = validate_non_empty_string_list(metadata.get("state_files", []), "state_files") or []
        except CanvasValidationError as exc:
            errors.append(str(exc))
            state_files = []
        for filename in state_files:
            try:
                relative = ensure_relative_file(str(filename))
            except CanvasValidationError as exc:
                errors.append(str(exc))
                continue
            if not (canvas_dir / relative).exists():
                errors.append(f"Missing state file: {relative}")

        try:
            shared_state = validate_non_empty_string_list(
                metadata.get("shared_state", []), "shared_state"
            ) or []
        except CanvasValidationError as exc:
            errors.append(str(exc))
            shared_state = []
        for filename in shared_state:
            try:
                relative = ensure_relative_file(str(filename))
            except CanvasValidationError as exc:
                errors.append(str(exc))
                continue
            if not (canvas_dir / relative).exists():
                errors.append(f"Missing shared state file: {relative}")

        if not (canvas_dir / "README.md").exists():
            warnings.append("README.md is missing")
        if not metadata.get("agent_actions"):
            warnings.append("agent_actions is empty")
        if not metadata.get("human_actions"):
            warnings.append("human_actions is empty")

        return {
            "id": metadata.get("id", canvas_dir.name),
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "metadata": metadata,
        }

    def promote_canvas(
        self,
        canvas_id: str,
        *,
        target: str,
        reference: str,
        note: str = "",
    ) -> dict[str, Any]:
        metadata_file = self._metadata_path(canvas_id, "active")
        validation = self.validate_canvas(canvas_id, "active")
        if not validation["valid"]:
            raise CanvasValidationError("; ".join(validation["errors"]))
        metadata = self._read_json(metadata_file)
        validate_non_empty_string_list(metadata.get("promotion_targets"), "promotion_targets")
        validate_promotions(metadata.get("promotions", []))
        allowed = set(metadata.get("promotion_targets", []))
        if target not in allowed:
            raise CanvasValidationError(f"Promotion target '{target}' is not allowed for this canvas.")
        promotion = {
            "target": target,
            "reference": reference,
            "note": note,
            "promoted_at": utc_now(),
        }
        metadata.setdefault("promotions", []).append(promotion)
        metadata["updated_at"] = promotion["promoted_at"]
        self._write_json(metadata_file, metadata)
        notes_file = metadata_file.parent / "notes.md"
        with notes_file.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## Promotion\n\n- {promotion['promoted_at']}: {target} -> {reference}")
            if note:
                handle.write(f" ({note})")
            handle.write("\n")
        return metadata

    def export_html(
        self,
        canvas_id: str,
        *,
        lifecycle: str | None = None,
        output: str | Path | None = None,
    ) -> dict[str, Any]:
        metadata_file = self._metadata_path(canvas_id, lifecycle)
        canvas_dir = metadata_file.parent
        metadata = self._read_json(metadata_file)
        state_file = canvas_dir / "state.json"
        notes_file = canvas_dir / "notes.md"
        state = self._read_json(state_file) if state_file.exists() else {}
        notes = notes_file.read_text(encoding="utf-8") if notes_file.exists() else ""
        validation = self.validate_canvas(metadata["id"], metadata["lifecycle"])

        output_path = Path(output).expanduser() if output else canvas_dir / "canvas.html"
        if not output_path.is_absolute():
            output_path = canvas_dir / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CANVAS_VIEWER_TEMPLATE, output_path)
        data_path = output_path.parent / "canvas-data.js"
        data_path.write_text(
            "window.CANVAS_DATA = "
            + json.dumps(
                {
                    "metadata": metadata,
                    "state": state,
                    "notes": notes,
                    "validation": validation,
                },
                indent=2,
                sort_keys=False,
            )
            + ";\n",
            encoding="utf-8",
        )
        return {
            "id": metadata["id"],
            "lifecycle": metadata["lifecycle"],
            "html_path": str(output_path),
            "data_path": str(data_path),
            "valid": validation["valid"],
            "warnings": validation["warnings"],
        }

    def _metadata_path(self, canvas_id: str, lifecycle: str | None = None) -> Path:
        self.ensure_root()
        normalized_id = normalize_canvas_id(canvas_id)
        if lifecycle:
            if lifecycle not in LIFECYCLES:
                raise CanvasValidationError(f"Lifecycle must be one of {sorted(LIFECYCLES)}.")
            path = getattr(self.paths, lifecycle) / normalized_id / "canvas.json"
            if path.exists():
                return path
            raise CanvasValidationError(f"Canvas not found: {normalized_id}")
        for base in [self.paths.active, self.paths.archived]:
            path = base / normalized_id / "canvas.json"
            if path.exists():
                return path
        raise CanvasValidationError(f"Canvas not found: {normalized_id}")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    @staticmethod
    def _readme_text(metadata: dict[str, Any]) -> str:
        return (
            f"# {metadata['title']}\n\n"
            f"Canvas id: `{metadata['id']}`\n\n"
            f"Scope: `{metadata['scope']}`\n\n"
            f"Anchor: `{metadata.get('anchor', '')}`\n\n"
            "## Human Actions\n\n"
            + "\n".join(f"- `{item}`" for item in metadata.get("human_actions", []))
            + "\n\n## Agent Actions\n\n"
            + "\n".join(f"- `{item}`" for item in metadata.get("agent_actions", []))
            + "\n"
        )
