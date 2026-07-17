# Repository Instructions

## Purpose

`my-skills` is source repository for portable Agent Skills. Each top-level directory containing `SKILL.md` is one distributable skill.

## Structure

- `skills.json`: repository metadata and public skill registry.
- `<skill-name>/SKILL.md`: required skill definition.
- `<skill-name>/references/`, `scripts/`, `assets/`: optional skill resources.
- `README.md`: public skill list and usage overview.
- `codexradar-model-advisor/`: current OpenAI Codex model-advice skill.

Repository currently has no installer, uninstaller, workflow runtime, or test harness. Do not document or invoke missing commands.

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
- Register every shipped skill in `skills.json`; keep `files` list accurate and remove entries for absent skill directories.
- Update root `README.md` when public skill list or install commands change.
- Preserve source skill behavior during migrations. Do not restore files removed by later source revisions.

## CodexRadar Skill

- Treat CodexRadar as third-party empirical source, not OpenAI-official benchmark.
- Recommend only OpenAI Codex model/effort combinations present in current measured data.
- Fetch current page and community-rating endpoint; never reuse remembered measurements.
- Keep latest rolling rating distinct from 15-day historical context.
- Do not map Anthropic, Google, local, unknown, or uncovered models to Codex IQ values.
- Treat configuration changes as separate action. Preserve unrelated settings and respect target scope.

## Verification

Run checks proportional to change:

```bash
jq empty skills.json
git diff --check
```

For new or changed skills, also run Skill Creator `quick_validate.py` when available. Use Python environment containing `PyYAML`.

For resource scripts, run focused script tests. For source migrations, compare migrated files byte-for-byte when exact preservation is required.

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
