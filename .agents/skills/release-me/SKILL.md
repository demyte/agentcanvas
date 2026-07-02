---
name: release-me
description: User-invoked release checklist for Codex plugins and similar repos.
disable-model-invocation: true
---

# Release Me

Run a tight release: make version intent explicit, validate the artifact, tag only verified official releases, and prove what reached the remote.

## Gate

1. Inspect release state. Read the version source (`.codex-plugin/plugin.json`, `package.json`, `.csproj`, etc.), branch, remote, local tags, matching remote tags, remote branch head, and worktree status. Completion: current version, branch, remote target, local/remote tag state, remote branch head, and uncommitted changes are known.
2. Classify intent. Use `official` for clean SemVer releases and `local-dev` for cache-bust installs. If release kind, version/bump, or publish intent is missing, ask before editing. Completion: intent is explicit, e.g. `official 0.2.1, commit/tag/push` or `local-dev cache bust, install only`.
3. Set the version. For `official`, write clean SemVer only. For `local-dev`, write SemVer plus build metadata. Completion: the version source matches the chosen rule and the diff contains only intended release files.
4. Validate. Run the repo's real validation path: documented checks, plugin validation, tests, and help/version smoke tests that apply. Completion: every relevant check passes, or the release stops with exact failing commands.
5. Commit. Commit only intended release files when files changed. Completion: `HEAD` contains the release diff and the worktree is clean.
6. Tag official releases. Create the `vX.Y.Z` tag only after validation and commit, and only if it does not already exist locally or remotely. Completion: the tag points at the validated release commit.
7. Push only requested refs. Push the branch and/or tag according to the user's publish intent. Completion: `git ls-remote` shows every pushed branch/tag points at the expected commit.

## Version Rules

Official manifest versions:

```text
0.2.1
0.3.0
1.0.0
```

Official tags:

```text
v0.2.1
v0.3.0
v1.0.0
```

Local development cache-bust versions:

```text
0.2.1+codex.20260702123000
0.2.1+local.james.5
```

Do not tag local-dev versions. Do not leave cache-bust metadata in an official release manifest.

## Questions

If version intent is missing, ask:

```text
What release bump/version should I use: patch, minor, major, explicit X.Y.Z, or local-dev cache bust?
```

If publish intent is missing after validation, ask:

```text
Should I push the branch, create/push the tag, or leave the release commit local?
```

## Codex Plugin Notes

For Codex plugin repos:

- `.codex-plugin/plugin.json` is the usual version source.
- `codex plugin add <plugin>@<marketplace> --json` installs from configured marketplace selectors, not raw GitHub URLs.
- Official releases should validate that tag `vX.Y.Z` matches manifest version `X.Y.Z`; do not rely on a workflow to rewrite the manifest during release.
- Local-dev cache busts usually change only `.codex-plugin/plugin.json`.
- If available, run `plugin-creator` validation against the repo root.

Useful checks:

```powershell
git status --short --untracked-files=all
git branch --show-current
git remote -v
git tag --list --sort=-creatordate
git ls-remote --tags origin vX.Y.Z
git ls-remote --heads origin <branch>
python C:\Users\james\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py .
```
