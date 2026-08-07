# my-skills repository layout refactor

Date: 2026-08-07

## Decision

Move `custom-image-gen` out of `openai/` and make it a root-level standalone Skill.

Keep standalone Skills flat at repository root. Use metadata and README sections for classification; do not nest distributable Skills under category directories until an installer or registry resolver explicitly supports paths.

Move Codex plugin packaging to the official repo-marketplace shape:

```text
my-skills/
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── plugins/
│   └── openwolf-codegraph-bridge/
│       ├── .codex-plugin/plugin.json
│       ├── hooks/
│       └── README.md
├── codexradar-model-advisor/
├── model-delegate/
├── cc-switch-reasoning-tier-repair/
├── chatgpt-codex-history-repair/
├── custom-image-gen/
├── django-api-change/
├── plans/
├── skills.json
├── AGENTS.md
└── README.md
```

## Why

- Repository contract says each root directory containing `SKILL.md` is one distributable Skill (`AGENTS.md:3-12`). `openai/custom-image-gen/` violates that invariant.
- `custom-image-gen` adapts custom provider credentials and endpoints, then delegates image work to the system `imagegen` Skill. It is not OpenAI-owned package content.
- Current `openai/` mixes two package types: standalone Skill and Codex marketplace/plugin runtime.
- `skills.json` identifies Skill packages by `name` and lists files relative to each package. It has no path resolver. Root folder matching Skill name is least surprising contract.
- Current Codex plugin documentation recommends repository marketplace metadata at `.agents/plugins/marketplace.json` and plugin packages under `plugins/`. Marketplace `source.path` resolves relative to repository marketplace root.

## Phase 0 — documented contracts

### Allowed structures

- Standalone Skill: `<skill-name>/SKILL.md`, optionally with `agents/`, `scripts/`, `references/`, and `assets/`.
- Plugin: `<plugin-name>/.codex-plugin/plugin.json`, optionally with `skills/`, `hooks/`, assets, `.mcp.json`, and `.app.json` at plugin root.
- Repo marketplace: `.agents/plugins/marketplace.json` with local plugin path such as `./plugins/openwolf-codegraph-bridge`.
- Skill folder names: kebab case, at most 64 characters.
- Skill frontmatter: `name` and `description`; preserve intentional legacy metadata unless separately migrated.

### Sources

- Local repository rules: `AGENTS.md:3-15`, `AGENTS.md:27-38`, `AGENTS.md:49-64`.
- Current registry: `skills.json:1-59`.
- Current public paths and install commands: `README.md:5-39`, `README.md:43-94`, `README.md:98-125`.
- Official Codex manual sections fetched on 2026-08-07:
  - `Build skills`
  - `Package your plugin`
  - `Plugin structure`
  - `Install a local plugin manually`
  - `Marketplace metadata`

### Guards

- Do not invent an installer, uninstaller, or runtime that this repository does not contain.
- Do not use category nesting for Skills while registry path resolution is implicit.
- Do not mix marketplace metadata into a Skill directory.
- Do not change Skill behavior while moving source files.
- Do not overwrite installed copies under user configuration directories as part of repository-only refactor.

## Phase 1 — normalize standalone Skills

### Implement

1. Move `openai/custom-image-gen/` to `custom-image-gen/` using a history-preserving filesystem move.
2. Preserve `SKILL.md` and `agents/openai.yaml` byte-for-byte, including current endpoint and API-key precedence changes.
3. Update all source links and copy commands from `openai/custom-image-gen/` to `custom-image-gen/`.
4. Confirm `skills.json` file list remains accurate; no path field is required because folder and Skill name now match.

### Verify

- Compare moved files against pre-move hashes.
- Run Skill Creator `quick_validate.py custom-image-gen`.
- Confirm `rg 'openai/custom-image-gen'` returns no active references.
- Confirm installed Skill copies are unchanged.

### Guards

- Do not regenerate `agents/openai.yaml` during move.
- Do not alter image model defaults, endpoint selection, credential precedence, retry rules, or system `imagegen` delegation.

## Phase 2 — add classification without path coupling

### Implement

Add a `category` field to each `skills.json` entry and group README display by the same taxonomy:

| Category | Skills |
| --- | --- |
| `models-and-routing` | `codexradar-model-advisor`, `model-delegate`, `cc-switch-reasoning-tier-repair` |
| `codex-maintenance` | `chatgpt-codex-history-repair` |
| `media-generation` | `custom-image-gen` |
| `framework-workflows` | `django-api-change` |

Keep directories flat. Category changes discovery and documentation only.

### Verify

- `jq empty skills.json`.
- Every registered Skill has exactly one category.
- Every registered Skill resolves to `<name>/SKILL.md`.
- Every `files` entry exists relative to its Skill directory.
- README categories and registry categories match.

### Guards

- Do not add `skills/<category>/<name>` directories.
- Do not add a `path` field unless future tooling consumes and validates it.
- Do not rename Skills merely to make category names visible.

## Phase 2.5 — clarify package identities

- Rename `ccswitchmulti-reasoning-tier-repair` to `cc-switch-reasoning-tier-repair` for readable product namespacing while keeping the UI display name `CCSwitchMulti Reasoning 档位修复`.
- Rename plugin `openwolf-codegraph` to `openwolf-codegraph-bridge` because it bridges lifecycle events and navigation guidance; it is not the OpenWolf or CodeGraph runtime itself.
- Rename marketplace `my-skills-local` to `vlong-skills-local` to avoid a generic globally visible identifier.
- Preserve established, clear Skill IDs such as `custom-image-gen`, `model-delegate`, and `django-api-change`; avoid churn without a concrete discovery or ambiguity benefit.
- Treat installed old names as external state. Do not remove or rewrite them during repository refactoring.

## Phase 3 — normalize plugin marketplace layout

### Implement

1. Move `openai/openwolf-codegraph/` to `plugins/openwolf-codegraph-bridge/`, preserving runtime behavior while clarifying that the plugin is an integration bridge.
2. Move `openai/.agents/plugins/marketplace.json` to root `.agents/plugins/marketplace.json`.
3. Change marketplace local source path from `./openwolf-codegraph` to `./plugins/openwolf-codegraph-bridge`.
4. Update README commands and plugin-local README paths.
5. Remove empty `openai/` directory after confirming no active files remain.

### Compatibility note

Existing marketplace registration that points directly to the old `openai/` directory may continue to reference stale source or cache. Repository refactor must document a separate user-approved re-registration step. Do not mutate global Codex configuration automatically.

### Verify

- Validate `.agents/plugins/marketplace.json` as JSON.
- Validate `plugins/openwolf-codegraph-bridge/.codex-plugin/plugin.json` with Plugin Creator validator.
- Run `node --check plugins/openwolf-codegraph-bridge/hooks/openwolf.mjs`.
- Confirm marketplace `source.path` resolves inside repository to plugin manifest.
- Search for old `openai/openwolf-codegraph` and marketplace-add commands targeting `/openai`.
- In a new Codex task, verify plugin listing and hook trust lifecycle after user-approved marketplace refresh.

### Guards

- Do not treat plugin as a standalone Skill or add it to `skills.json`.
- Do not place hooks inside `.codex-plugin/`; only `plugin.json` belongs there.
- Do not claim source validation proves installed-cache activation.

## Phase 4 — codify repository invariants

### Implement

Update `AGENTS.md` and README to state:

- Root-level directories with `SKILL.md` are standalone Skill packages.
- `plugins/<plugin-name>/` contains installable Codex plugins.
- `.agents/plugins/marketplace.json` catalogs repository plugins.
- `skills.json.category` classifies Skills without controlling paths.
- Plugin install/cache verification requires a new task and hook trust review where applicable.

Update `.wolf/anatomy.md` through normal OpenWolf maintenance so source map reflects moved files.

### Verify

- Documented tree matches filesystem.
- No documentation invokes missing repository tooling.
- All links and shell paths resolve.

## Phase 5 — final verification

Run:

```bash
jq empty skills.json
jq empty .agents/plugins/marketplace.json
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py custom-image-gen
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/openwolf-codegraph-bridge
node --check plugins/openwolf-codegraph-bridge/hooks/openwolf.mjs
git diff --check
```

Then perform deterministic path checks:

- Every `skills.json` Skill name has a root directory and `SKILL.md`.
- Every registered file exists.
- No standalone Skill exists under `plugins/`.
- Every marketplace plugin path contains `.codex-plugin/plugin.json`.
- No active path references remain under `openai/`.
- Pre-move and post-move content hashes match for moved package files, except explicitly edited path metadata and documentation.

## Execution order and rollback

Execute Phase 1 first. It resolves current inconsistency with smallest blast radius and does not affect plugin installation.

Execute Phases 2 and 3 separately so category metadata changes do not obscure plugin path migration. Commit or checkpoint each phase independently if version-control actions are later requested.

Rollback uses inverse moves plus previous marketplace source path. Do not delete old marketplace registration or installed plugin cache during repository rollback; those are external state and require separate approval.
