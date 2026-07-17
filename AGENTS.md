# Repository Instructions

## Purpose

`my-skills` is source repository for `vlong`, personal Agent Skills collection. Repository name remains `my-skills`; installed Claude Code package name and path remain `vlong` and `~/.claude/skills/vlong/`.

## Structure

- `skills.json`: authoritative skill registry used by `install.sh`.
- `<skill-name>/SKILL.md`: required skill definition.
- `<skill-name>/references/`, `scripts/`, `assets/`: optional skill resources.
- `install.sh`: package entrypoint; installs one skill or every registered skill.
- `shared/install_skill.sh`: shared local-copy and Claude Code symlink logic.
- `uninstall.sh`: removes installed skill while preserving `skill-opt/` data.
- `test/install-test.sh`: isolated installer regression suite using temporary `HOME` directories.
- `route-effort-workspace/`: generated training/evaluation workspace. Do not treat it as shipped skill source.

## Code Navigation

When repository root contains `.codegraph/`, use CodeGraph before `rg`, `find`, or broad file reads:

```bash
codegraph explore "<symbol or question>"
```

Skip CodeGraph completely when `.codegraph/` is absent. User decides whether to create index.

## Skill Changes

Follow portable Agent Skills layout.

- Skill folder name: lowercase letters, digits, hyphens; maximum 64 characters.
- `SKILL.md` frontmatter: prefer only `name` and `description` for portable skills. Preserve intentional legacy fields in existing skills unless task requires migration.
- `description`: state capability and trigger conditions. Put operational workflow in body.
- `README.md`: optional. Do not create auxiliary docs solely to satisfy installer.
- Add reusable scripts only when deterministic execution or meaningful reuse warrants them. Test every added script.
- Register every shipped skill in `skills.json`; keep `files` list accurate.
- Update root `README.md` when public skill list or install commands change.
- Preserve source skill behavior during migrations. Do not restore files removed by later source revisions.

## Installer Constraints

- Support macOS system Bash 3.2. Avoid Bash 4-only commands such as `mapfile`.
- Preserve `set -euo pipefail`, path traversal guards, temporary-repository cleanup, and isolated installation paths.
- `SKILL.md` is required; other skill files are optional unless skill itself needs them.
- `--all` must install every entry from `skills.json` with and without `jq`.
- Never run installer tests against real user `HOME`.
- Do not rewrite unrelated installed files, configuration, or `skill-opt/` training data.

## Verification

Run checks proportional to change:

```bash
jq empty skills.json
bash -n install.sh shared/install_skill.sh uninstall.sh test/install-test.sh
bash test/install-test.sh
git diff --check
```

For new or changed skills, also run Skill Creator `quick_validate.py` when available. Use Python environment containing `PyYAML`.

Installer regression suite includes remote version-pin cases. Keep all writes under temporary `HOME`; report when network-dependent coverage cannot run.

## Worktree Safety

Repository may contain unrelated uncommitted work. Preserve it. Inspect overlapping diffs before editing; never reset or delete user changes.

## Response Style

Respond terse like smart caveman. All technical substance stay. Only fluff die.

Rules:
- Drop: articles (a/an/the), filler (just/really/basically), pleasantries, hedging
- Fragments OK. Short synonyms. Technical terms exact. Code unchanged.
- Pattern: [thing] [action] [reason]. [next step].
- Not: "Sure! I'd be happy to help you with that."
- Yes: "Bug in auth middleware. Fix:"

Switch level: /caveman lite|full|ultra|wenyan
Stop: "stop caveman" or "normal mode"

Auto-Clarity: drop caveman for security warnings, irreversible actions, user confused. Resume after.

Boundaries: code/commits/PRs written normal.
