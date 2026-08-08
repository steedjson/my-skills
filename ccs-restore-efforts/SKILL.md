---
name: ccs-restore-efforts
description: Restore missing reasoning effort tiers and the Fast Speed selector in the Codex CC Switch model catalog and config.toml. Keeps Max immediately before Ultra. Use when ultra, max, or Speed/Fast disappear after a CC Switch sync or config rewrite.
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
4. Restores a missing top-level `model = "..."` setting.
5. Parses `config.toml` afterward to verify it is valid TOML.

Existing tiers are preserved. The script never deletes models or replaces
provider credentials.

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
- Writing to `~/.codex/` can require elevated permission in a sandboxed
  Codex task.
