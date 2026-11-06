# Changelog

All notable changes. Versions follow semantic versioning once 1.0.0 is out.

## Unreleased

- README no longer names a version (it said 0.1.0 after 0.1.1 shipped); the version in `pyproject.toml`,
  `.claude-plugin/plugin.json` and the MCP server's `serverInfo` now says 0.1.1. No code change.

## 0.1.1 (2026-11-06)

- `action.yml`: description shortened to 117 characters so the Action can be listed on the GitHub Marketplace
  (its limit is under 125). No code change.

## 0.1.0 (2026-11-04)

First public version.

- Runner (`prove.py`): plants a bug, runs the tests (red), restores the file byte-identical, runs again
  (green); PASS only when every plant ran, was killed, restored and controlled.
- Safety: refuses uncommitted work or a non-git folder (`--allow-dirty` overrides); journal written and
  fsynced before any change; files restored on any crash, SIGINT, SIGTERM, SIGHUP or SIGQUIT; `recover` after
  `kill -9`; a failed apply (read-only file, disk full) restores and is NOT-APPLIED.
- Honest verdicts: a timeout is NOT-RUN, never a kill; flaky tests are detected (3 baseline runs, a red
  control re-run once) and never counted as kills; non-UTF-8 files and no-op plants are STALE.
- Plants from any AI: one model-neutral prompt, `check-plants` validation, a headless writer for the
  Anthropic API or any OpenAI-compatible endpoint, an MCP server, adapters for Claude Code, Codex
  (`AGENTS.md`), Gemini CLI and Cursor.
- Install: pipx or uv from git, Claude Code plugin and marketplace manifests, GitHub Action.
- Bytecode safe: test runs write no .pyc, rewritten files get an mtime at least 1 s newer (a cached .pyc can
  never stand in for a planted or restored file), and runtime caches never count as uncommitted work.
- Auto plants for JS/TS (`plant.py`): `<` and `>` of TypeScript type arguments, generics, casts and JSX tags
  are never planted as comparisons (a plant that only breaks compilation tests nothing).
- Self-test: 60 runner cases, 18 adapter cases, 91 meta plants.
