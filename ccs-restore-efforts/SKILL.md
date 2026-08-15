---
name: ccs-restore-efforts
description: Restore missing reasoning tiers, Fast Speed, and vendor-verified context windows in the Codex CC Switch model catalog and config.toml; optionally force the MultiRouter-mapped Grok provider onto native chat protocol. Use after CC Switch sync/config rewrite, or when Grok is stuck on responses-to-chat conversion.
---

# Restore Reasoning Efforts, Speed, And Optional Grok Chat

CC Switch keeps model capability information in both
`~/.codex/cc-switch-model-catalog.json` and the inline model list under
`[model_providers.codex_model_router_v2]` in `~/.codex/config.toml`.

Codex only shows a model-picker row when that model's metadata exposes options
for it:

- `supportedReasoningEfforts` controls the `Effort` choices.
- `serviceTiers` controls the `Speed` choices.

The `Fast` option is the `priority` service tier. If `serviceTiers` is empty,
the `Speed` row is hidden even when a previous Codex session showed it.

This skill now has two explicit modes.

## Modes

### 1. `restore-ui`

Restore UI capability metadata only:

1. Restores model-dependent reasoning tiers in the three supported-reasoning
   metadata forms. GPT-5.6 / Sol / Luna / Terra expose
   `none, low, medium, high, xhigh, max`; GPT-5.5 / GPT-5.4 / GPT-5.2 expose
   `none, low, medium, high, xhigh` only. Their defaults are respectively
   `medium`, `medium`, `none`, and `none`.
2. Adds the legacy `fast` flag and the `Fast` / `priority` service tier to
   every existing catalog model.
3. Applies the same capability repair to the inline route-provider models in
   `config.toml`, including models where the Speed fields are absent rather
   than merely empty.
4. Restores a missing top-level `model = "..."` setting, preferring a usable
   chat model over review-only catalog defaults such as `codex-auto-review`.
5. Restores context-window fields from a vendor-verified static map.
6. Parses `config.toml` afterward to verify it is valid TOML.

For the four published GPT families, unsupported `max` / `ultra` entries are
removed so repeated runs converge to the documented model-dependent set.
Other models retain existing tiers and receive the generic `max` / `ultra`
repair. This mode never deletes models or replaces provider credentials.

### 2. `force-grok-chat`

Force the MultiRouter-mapped Grok provider onto native Chat Completions:

1. Read the current Codex MultiRouter provider from `~/.cc-switch/cc-switch.db`.
2. Resolve Grok only from static `settings.codexRouting.routes` mapping.
   Runtime logs are not used for target selection.
3. Require exactly one enabled Grok route; refuse if zero or ambiguous.
4. Dry-run by default: print target provider, matched models, current
   `wire_api` / `apiFormat`, and planned changes.
5. On `--apply`:
   - full-db backup under `~/.cc-switch/backups/grok-chat-repair-<timestamp>.db`
   - set only `wire_api = "chat"` and `apiFormat = "openai_chat"`
   - leave `base_url` unchanged
   - send one minimal chat probe through the active local proxy base URL
   - verify router evidence for `/chat/completions` without responses-to-chat
     conversion
   - restore the full DB backup if probe/route verification fails

This mode intentionally does **not** rewrite MultiRouter global
`config.toml` `wire_api`. It only mutates the mapped Grok upstream provider.

## Context Window Sources

Values were verified against vendor documentation on August 12, 2026:

| Models | Context window | Primary source |
| --- | ---: | --- |
| GPT-5.6, Sol, Terra, Luna | 1,050,000 | OpenAI model documentation |
| GPT-5.5, GPT-5.4 | 1,050,000 | OpenAI model documentation |
| GPT-5.4 mini, GPT-5.2 | 400,000 | OpenAI model documentation |
| GPT-5.3 Codex Spark | 128,000 | OpenAI model documentation |
| Codex Auto Review | 272,000 | OpenAI model documentation |
| DeepSeek V4 Flash, V4 Pro | 1,000,000 | DeepSeek API documentation |
| Grok 4.5, Grok 4.6 | 500,000 | xAI model documentation |
| GLM-5.2 | 1,000,000 | Z.AI model documentation |

Grok 4.5 exposes `low, medium, high`; Grok 4.6 additionally exposes `xhigh`.
Both default to `high`. The GPT-5.6 alias is treated as GPT-5.6 Sol for capability repair. The
`reasoning.mode` setting (`standard` / `pro`) is separate from
`reasoning.effort` and is not changed by this skill. Grok entries are not
changed by the GPT capability policy.

DeepSeek V4 Flash and V4 Pro expose `off, non-think, low, high, max`.
Their default is left unchanged unless explicitly present in the source
metadata.

GPT-5.4 mini exposes `low, medium, high, xhigh`, defaults to `none`, and has
a maximum output limit of `128,000` tokens. The script updates both
`max_output_tokens` and `maxOutputTokens` when those fields are present or
missing.

The script updates `context_window`, `contextWindow`, `max_context_window`,
and `maxContextWindow` in both metadata locations.

CCSwitchMulti may publish route names such as `gpt-5.6-luna-csap-oai` while
also storing the real model in `upstreamModel` / `upstream_model` and display
fields. The UI restore path inspects all explicit identity fields and uses the
first verified match:

1. route `model` / `id` / `slug`
2. `upstreamModel` / `upstream_model`
3. `display_name` / `displayName`
4. explicit non-mechanical aliases such as `deepseek-v4-flash-0731`
5. mechanical strip of auto-detected route suffixes such as `-csap-oai`

`restore-ui` auto-detects strip suffixes from the current catalog/config by
looking for route names that are exactly `base + suffix`, where `base` is a
vendor-verified model or another explicit identity on the same model. It keeps
the longest valid base, prints recommended suffixes, and activates them for the
run. You can also pass `--strip-suffix` or disable detection with
`--no-auto-strip`.

For a new or unknown model, search the model vendor's official documentation
before changing the static map. Use primary vendor sources only. Resolve route
aliases to their real upstream model using explicit provider evidence; never
infer context capacity from a similar name. Preserve and report unverified
models instead of overwriting their existing limits.

## Run

No args opens a menu:

```bash
python3 scripts/restore_efforts.py
```

Direct commands:

```bash
# UI capability restore
python3 scripts/restore_efforts.py restore-ui

# Grok chat force (dry-run)
python3 scripts/restore_efforts.py force-grok-chat

# Grok chat force (apply after reviewing dry-run)
python3 scripts/restore_efforts.py force-grok-chat --apply
```

`restore-ui` is idempotent. Repeat it after a CC Switch catalog synchronization
if that synchronization clears capability metadata again.

`force-grok-chat` is dry-run by default. Use `--apply` only after the printed
static route target looks correct.

## Validation

For `restore-ui`: fully quit and reopen Codex, then open the model picker.
`Effort` should offer the restored levels and `Speed` should show `Standard`
plus `Fast`.

For `force-grok-chat --apply`: confirm the command reports native chat
verification, then send one Grok request and check router logs for
`/chat/completions` without `responses_to_chat=true`.

## Limits

- The UI option declares a `priority` tier; whether an upstream provider
  honors that tier remains provider-specific.
- Local context metadata controls Codex compaction behavior but cannot increase
  an upstream provider or proxy's actual request limit.
- `force-grok-chat` depends on MultiRouter static `codexRouting`; if Grok is not
  uniquely mapped there, the mode refuses to mutate.
- Writing to `~/.codex/` or `~/.cc-switch/` can require elevated permission in a
  sandboxed Codex task.
