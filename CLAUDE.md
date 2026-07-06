# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

Personal collection of Claude Code skills authored by the user ("自己日常总结的skills"). Not a git repository. Each skill lives in its own top-level directory. Currently contains one skill: `route-effort`.

## Skill package layout

Every skill directory follows the same convention (see `route-effort/` as the reference example):

- `SKILL.md` — the skill definition consumed by Claude Code's Skill tool. Frontmatter (`name`, `description`) controls discovery/triggering; the body documents the decision rules.
- `<name>.js` — an optional Workflow script implementing the skill's logic (used when the skill needs to orchestrate `agent()` calls rather than just provide guidance text).
- `install.sh` — installer that copies (local) or `curl`s (remote) the skill's files into `~/.claude/skills/<name>/` and `~/.claude/workflows/`. Detects local-vs-remote execution by checking whether `BASH_SOURCE` resolves to a real path.
- `README.md` — human-facing usage docs and copy-paste install instructions.

When adding a new skill, mirror this four-file structure rather than inventing a new layout.

## route-effort skill

Routes a task description to an agent `effort` level (`low`/`medium`/`high`/`xhigh`/`max`) based on risk and required reasoning depth, so simple tasks don't burn tokens and critical tasks don't get under-reasoned.

Critical constraint to know before touching this skill or writing similar ones: **the `effort` option only takes effect inside a Workflow script's `agent()` calls.** The standalone `Agent` tool has no `effort` parameter — passing one there is silently ignored. Any effort-routing logic must be applied through `Workflow({scriptPath, args})`, not through a direct `Agent` call.

`effort-routed-task.js` demonstrates the pattern: it first calls `agent()` at `effort: 'medium'` to classify the task (deliberately not `low` — that under-rates complex tasks) and parses `effort=<level>` from the response, then re-dispatches the actual task via `agent()` at the routed effort level.

Routing is sensitive to phrasing in the task description — vague framing like "分析影响范围" gets under-routed to `medium`; a description that explicitly names cross-module scope ("跨模块变更：修改X，影响A/B/C模块") reliably routes to `xhigh`. See the table and examples in `route-effort/SKILL.md` for the full rule set before changing routing behavior.

## Known gaps

`install.sh` and `README.md` still contain the placeholder `YOUR_USERNAME` in the GitHub raw-content URL — the remote `curl | bash` install path won't work until that's replaced with the actual repo owner/path.

## Commands

No build, lint, or test tooling exists in this repo — it's skill/doc/shell content only.

- Install the `route-effort` skill locally: `./route-effort/install.sh` (copies `SKILL.md` into `~/.claude/skills/route-effort/` and `effort-routed-task.js` into `~/.claude/workflows/`)
- Exercise the workflow after installing: `Workflow({scriptPath: '~/.claude/workflows/effort-routed-task.js', args: {task: "<task description>"}})`
