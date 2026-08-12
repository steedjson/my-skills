---
name: ccs-restore-efforts
description: Restore missing reasoning tiers, Fast Speed, and vendor-verified context windows in the Codex CC Switch model catalog and config.toml. Use when model capabilities disappear or context limits regress after a CC Switch sync or config rewrite.
---

# Restore Reasoning Efforts And Speed

CC Switch keeps the model capability information in both
`~/.codex/cc-switch-model-catalog.json` and the inline model list under
`[model_providers.codex_model_router_v2]` in `~/.codex/config.toml`.

Codex only shows a model-picker row when that model's metadata exposes options
for it:

- `supportedReasoningEfforts` controls the `Effort` choices.
- `serviceTiers` controls the `Speed` choices.

The `Fast` option is the `priority` service tier. If `serviceTiers` is empty,
the `Speed` row is hidden even when a previous Codex session showed it.

## What This Skill Does

1. Adds `max` and `ultra` to the three supported-reasoning metadata forms in
   every existing catalog model, with `Max` as the second-to-last option and
   `Ultra` as the final option.
2. Adds the legacy `fast` flag and the `Fast` / `priority` service tier to
   every existing catalog model.
3. Applies the same capability repair to the inline route-provider models in
   `config.toml`, including models where the Speed fields are absent rather
   than merely empty.
4. Restores a missing top-level `model = "..."` setting, preferring a usable
   chat model over review-only catalog defaults such as `codex-auto-review`.
5. Restores context-window fields from a vendor-verified static map.
6. Parses `config.toml` afterward to verify it is valid TOML.

Existing tiers are preserved. The script never deletes models or replaces
provider credentials.

## Context Window Sources

Values were verified against vendor documentation on August 11, 2026:

| Models | Context window | Primary source |
| --- | ---: | --- |
| GPT-5.6, Sol, Terra, Luna | 1,050,000 | OpenAI model documentation |
| GPT-5.5, GPT-5.4 | 1,050,000 | OpenAI model documentation |
| GPT-5.4 mini | 400,000 | OpenAI model documentation |
| DeepSeek V4 Flash, V4 Pro | 1,000,000 | DeepSeek API documentation |
| Grok 4.5 | 500,000 | xAI model documentation |
| GLM-5.2 | 1,000,000 | Z.AI model documentation |

The script updates `context_window`, `contextWindow`, `max_context_window`,
and `maxContextWindow` in both metadata locations.

CCSwitchMulti may add `upstreamModel` or `upstream_model` beside the route
`model`/`id`/`slug`. The script accepts all five explicit identity fields,
while preferring the route identity and using upstream identity only when no
route field exists. This keeps renamed provider routes repairable without
guessing aliases.

For a new or unknown model, search the model vendor's official documentation
before changing the static map. Use primary vendor sources only. Resolve route
aliases to their real upstream model using explicit provider evidence; never
infer context capacity from a similar name. Preserve and report unverified
models instead of overwriting their existing limits.

## Run

```bash
python3 scripts/restore_efforts.py
```

The script is idempotent. Repeat it after a CC Switch catalog synchronization
if that synchronization clears the capability metadata again.

## Validation

Fully quit and reopen Codex, then open the model picker. `Effort` should offer
the restored levels and `Speed` should show `Standard` plus `Fast`.

## Limits

- The UI option declares a `priority` tier; whether an upstream provider
  honors that tier remains provider-specific.
- Local context metadata controls Codex compaction behavior but cannot increase
  an upstream provider or proxy's actual request limit.
- Writing to `~/.codex/` can require elevated permission in a sandboxed
  Codex task.
