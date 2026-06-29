---
name: canvas
description: "Use this whenever the user asks for a canvas, workspace, shared board, live planning surface, interactive dashboard, artifact workspace, or Copilot-style canvas equivalent in Codex. This skill turns ambiguous workflow state into a semi-persistent local work surface: more durable than scratch files, less authoritative than project memory, and explicitly promoted only when the user asks."
---

# Canvas

Use this skill to create and maintain canvas-like working surfaces inside Codex.

A canvas is a semi-persistent working artifact for an active line of thought, investigation, review, plan, or temporary dashboard. It is not throwaway scratch, and it is not project source of truth. It can inform durable state later, but it is not durable state until explicitly promoted.

## Core Model

Separate three tiers:

```text
scratch
  Temporary execution files.
  Safe to delete after the task.

canvas
  Semi-persistent working state for a task, thread, issue, review, or investigation.
  Useful across days or follow-up turns, but not authoritative.

memory/project state
  Durable source of truth.
  Repo files, project docs, checked-in decisions, user preferences, automation rules.
```

The default frame is:

> Canvas = a working set for an active line of thought.

## Storage Rule

Do not store durable canvases in transient dated Codex session folders such as:

```text
Documents\Codex\YYYY-MM-DD\<session-slug>\work
```

Use those folders only for scratch or staging.

By default, store canvases in a stable user-level canvas area:

```text
C:\Users\james\Documents\Codex\canvases\
  active\
    <canvas-id>\
  archived\
    <canvas-id>\
```

If a different durable canvas root is configured by the user or workspace instructions, use that instead.

## Identity vs Storage

Keep the logical anchor separate from the physical storage location.

The anchor explains what the canvas is about. The storage location is where its files live.

Examples:

```text
scope: repo
anchor: D:\xpna\main
storage: C:\Users\james\Documents\Codex\canvases\active\xpna-pr2713-review
```

```text
scope: project
anchor: C:\Users\james\OneDrive\Private\Shared-Summerton\ai
storage: C:\Users\james\Documents\Codex\canvases\active\shared-summerton-email-triage
```

Repo root or project folder may be the context anchor, but do not store canvas files there unless the user explicitly wants that, or the repo/project already has a clearly ignored local convention for agent working files.

## Scope Selection

Choose the narrowest useful scope:

- `repo`: Use when the canvas is about a repository, branch, issue, PR, code review, architecture trace, test plan, or implementation workflow.
- `project`: Use when the canvas is about a non-repo project folder, household workspace, business process, or ongoing operational domain.
- `thread`: Use only when the canvas is intentionally tied to this one conversation and can be archived with it.
- `user`: Use for cross-project personal dashboards, reusable templates, or user-level canvas registries.

Prefer `repo` or `project` when a real anchor exists. Prefer `thread` only for short-lived work that does not naturally belong elsewhere.

## Metadata

Every canvas should include a `canvas.json` file with id, lifecycle, authority, scope, anchor, timestamps, state files, capabilities, and promotion targets.

Populate timestamps and thread identifiers when available. If the thread ID is not available through tools or context, leave it blank rather than inventing it.

## Capabilities

A canvas is not only a folder of files. Treat it as a shared action surface with explicit capabilities.

For each canvas, define:

- `human_actions`: what the user can inspect, decide, edit, mark, approve, reject, archive, or ask to promote.
- `agent_actions`: what Codex can reliably update or perform, such as refreshing source data, adding items, moving cards, regenerating a dashboard, validating links, summarizing changes, or promoting selected output.
- `shared_state`: the files that represent the current state both the user and agent are working from.

Prefer named actions over vague "update the canvas" behavior. The named actions do not need a formal API unless the canvas is implemented as an app, but they should be concrete enough that a later Codex turn can continue the workflow without reinterpreting the whole surface.

When building an interactive HTML page or local app, make these capabilities visible through controls where useful: buttons, filters, status chips, checkboxes, tabs, or forms. When using Markdown only, document the available actions in `README.md`.

## Initial Triage

Before creating a canvas, determine:

1. Purpose: planning, research, review, tracking, editing, dashboarding, artifact generation, or decision support.
2. Anchor: repo, project, thread, or user.
3. Lifecycle: active canvas, scratch-only, or durable project state.
4. Interaction level: Markdown, Markdown plus JSON, static HTML, or local web app.
5. Capabilities: what the user can do directly and what Codex can update reliably.
6. Promotion path: where the result may eventually go if the user chooses to promote it.

If the intent is clear, proceed without asking. Ask only when the wrong anchor or storage choice would create meaningful cleanup or confusion.

## Surface Selection

Use the lightest surface that helps:

- Use Markdown for plans, research notes, specs, reviews, decision logs, and status trackers.
- Use Markdown plus JSON when the workflow has structured state that will be updated repeatedly.
- Use static HTML when the user benefits from a visual browser surface but does not need a backend.
- Use a local web app when the user needs filtering, drag/drop, forms, tabs, persisted controls, previews, or multi-step interaction.
- Use existing project files only when the output is intended as source, documentation, test material, or other durable project state.

When the Canvas MCP tools are available, use `canvas_export_html` to turn an active or archived canvas into a static `canvas.html` review surface for browser inspection. Treat this as a view of the working artifact, not as promotion into project memory, docs, dashboards, or source.

## Repo And Project Hygiene

Do not assume repo-local storage is wanted.

When a canvas is anchored to a repo:

1. Treat the repo root as context, not storage.
2. Store canvas files externally by default.
3. Do not create committable files inside the repo unless the user asks.
4. If the user wants repo-local files, check for an existing ignored convention such as `.codex/`, `.ai/`, `.scratch/`, `tmp/`, or documented local-agent storage.
5. If no ignored convention exists, explain the tradeoff before creating repo-local files.

## Promotion Rule

A canvas can inform durable state, but it is not durable state until explicitly promoted.

Promotion examples:

- Update repo documentation.
- Add or revise project memory.
- Publish or link a project dashboard, board, summary, or other visible project surface.
- Add a dashboard or board to a project hub, launcher, static-site catalog, or similar visibility index.
- Write a GitHub issue or PR comment.
- Create a final report in the outputs directory.
- Convert temporary decisions into checked-in source, tests, or docs.

Do not silently promote canvas content into durable project state.

## Dashboard Promotion Targets

Some projects have dashboard/catalog surfaces that are not merely output files. Treat these as explicit promotion targets when the workspace already uses them.

When promoting a canvas into a dashboard-style project surface:

1. Identify the authoritative source first. This might be `project-memory.md`, a YAML catalog, a generated data file, or a workflow-specific source file.
2. Generate or update the visible surface only after the source state is clear.
3. Update the catalog/index files that make the surface discoverable.
4. Keep plain user-facing summaries aligned with technical state.
5. Verify the dashboard or static page directly when possible.

Do not treat a canvas as promoted merely because an HTML file exists. Promotion requires discoverability through the workspace's dashboard/catalog surfaces when those surfaces are part of the workflow.

If a workspace has a generator for hub pages, use it. If it does not, make the smallest consistent manual update and verify with direct file reads or parsing. In non-git workspaces, verify with direct reads, hashes, or page checks rather than `git diff`.

## Update Loop

When updating an existing canvas:

1. Read `canvas.json`, `state.json`, and `notes.md` first if they exist.
2. Preserve user edits.
3. Apply the smallest update that reflects the new instruction.
4. Update `updated_at` and `last_updated_from_thread` when possible.
5. Validate the canvas with `canvas_validate` when the MCP tool is available.
6. Export or refresh the HTML review surface with `canvas_export_html` when browser inspection would help.
7. Report what changed and where.

Avoid rebuilding the canvas from scratch unless the user asks or the current structure no longer fits the workflow.

## Archival

When a canvas is finished or no longer active, move it from:

```text
canvases\active\<canvas-id>
```

to:

```text
canvases\archived\<canvas-id>
```

Update `canvas.json`:

```json
{
  "lifecycle": "archived"
}
```

If a final artifact was promoted elsewhere, record that in `notes.md`.

## Output To User

When presenting a canvas, keep the response concise and include:

- the canvas id,
- the scope and anchor,
- the storage path,
- what files were created or updated,
- whether anything was promoted to durable state,
- how to continue using or updating it.

Be explicit when something is only a working artifact.
