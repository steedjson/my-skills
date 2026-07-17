# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

`my-skills` is source repo for portable Agent Skills. Each top-level directory containing `SKILL.md` is one distributable skill. Repo name stays `my-skills`; installed Claude Code package name/path stay `vlong` / `~/.claude/skills/vlong/`.

No installer, uninstaller, workflow runtime, or test harness exists in this repo. Do not document or invoke missing commands.

## Structure

- `skills.json` — skill registry (metadata + `files` list per skill).
- `<skill-name>/SKILL.md` — required skill definition.
- `<skill-name>/references/`, `scripts/`, `assets/` — optional skill resources.

## Commands

```bash
jq empty skills.json     # validate registry JSON
git diff --check         # whitespace/conflict check
```

For new/changed skills, also run Skill Creator `quick_validate.py` when available (needs Python with `PyYAML`). For resource scripts, run focused script tests. For source migrations, compare migrated files byte-for-byte when exact preservation is required.

## Code Navigation

If repo root contains `.codegraph/`, use CodeGraph before `rg`/`find`/broad reads:

```bash
codegraph explore "<symbol or question>"
```

Skip entirely if `.codegraph/` absent — indexing is user's call.

## Skill Changes

Follow portable Agent Skills layout.

- Skill folder name: lowercase letters/digits/hyphens, max 64 chars.
- `SKILL.md` frontmatter: prefer only `name` + `description` for portable skills. Preserve intentional legacy fields on existing skills unless the task requires migration.
- `description`: state capability and trigger conditions; put operational workflow in the body.
- `README.md` per skill is optional — don't create one just to satisfy the installer.
- Add reusable scripts only when deterministic execution or real reuse warrants them; test every script added.
- Register every shipped skill in `skills.json`; keep `files` list accurate and remove entries for absent skill directories.
- Update root `README.md` when the public skill list changes.
- Preserve source skill behavior during migrations — don't restore files a later source revision removed.

## CodexRadar Skill

- Treat CodexRadar as third-party empirical source, not OpenAI-official benchmark.
- Recommend only OpenAI Codex model/effort combinations present in current measured data.
- Fetch current page and community-rating endpoint; never reuse remembered measurements.
- Keep latest rolling rating distinct from 15-day historical context.
- Do not map Anthropic, Google, local, or uncovered models to Codex IQ values.
- Treat configuration changes as separate action. Preserve unrelated settings and respect target scope.

## Worktree Safety

Repo may contain unrelated uncommitted work. Preserve it — inspect overlapping diffs before editing, never reset/delete user changes.

## Response Style

Respond terse, like a smart caveman. Keep all technical substance; cut fluff only.

- Drop articles, filler (just/really/basically), pleasantries, hedging.
- Fragments OK. Short synonyms. Technical terms exact. Code stays unchanged.
- Pattern: `[thing] [action] [reason]. [next step].`
- Switch level: `/caveman lite|full|ultra|wenyan`. Stop: "stop caveman" or "normal mode".
- Drop caveman automatically for security warnings, irreversible actions, or user confusion; resume after.
- Code, commits, and PR text are always written normal (not caveman-style).
