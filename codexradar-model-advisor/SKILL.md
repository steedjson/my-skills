---
name: codexradar-model-advisor
description: Query CodexRadar for OpenAI Codex models only through non-browser access such as hidden fetch/request tools, direct web or HTTP readers, or shell/curl; retain raw responses as temporary evidence; normalize them into a turn-local JSON snapshot without bundled scripts; report current model-and-effort IQ and related measurements; provide one real-time recommendation from today's evaluation and one stable recommendation from 15-day history; list all measured choices; and apply a selected recommendation when the host agent supports that OpenAI model configuration. Use in Codex, Claude Code, and other Agent Skills-compatible agents for OpenAI Codex IQ checks, degradation checks, Sol/Terra/Luna comparisons, reasoning-effort selection, or recommendations based on codexradar.com. Never use browser tools. Do not use to score or recommend Anthropic, Google, local, or other non-OpenAI models.
---

# CodexRadar Model Advisor

Follow the portable Agent Skills format. Use non-browser request mechanisms already available to the host agent: hidden fetch/request tools, direct web or HTTP readers, or shell with curl. Never use browser, browser-control, or UI-automation tools for CodexRadar access. Do not create or require bundled scripts, custom programs, Python, Node.js, or persistent local caches.

Treat CodexRadar as a third-party empirical source, not an OpenAI-official IQ benchmark.

This skill evaluates OpenAI Codex models only. Never assign CodexRadar IQ values to non-OpenAI models.

## Read Current Data

1. Select available non-browser access in this order: hidden fetch/request tool, direct web/HTTP reader, then shell with `curl -fsSL`.
2. Never open CodexRadar in a browser or use browser-control/UI-automation as fallback. If no non-browser request mechanism is available, state that current data cannot be retrieved and do not recommend a combination.
3. Read both sources directly:
   - `https://codexradar.com/`
   - `https://codexradar.com/api/model-ratings?history=15`
4. Fetch each source at most once per skill invocation. Fetch both in parallel when the host supports parallel tool calls.
5. Retain both raw response bodies unchanged as turn-local evidence until the recommendation is complete. Keep them in tool/context state when possible; otherwise use uniquely named temporary text files.
6. Do not fetch either source again during the normal workflow. Refetch an individual source only when its first request failed, its response is incomplete, the user explicitly requests a refresh, or more than 15 minutes have elapsed and current data is still required.
7. Do not use remembered values from a prior skill invocation. Report each source's update time.
8. If either source cannot be read after an allowed retry, state which data is unavailable and do not fabricate it.

## Build The JSON Snapshot

After both raw responses are available, actively normalize them into one turn-local JSON object. Use native model reasoning, host structured-data operations, or disposable shell one-liners. Do not create a reusable script or require a language runtime.

Use this shape:

```json
{
  "schema_version": 1,
  "fetched_at": "",
  "sources": {
    "iq_page": {"url": "", "updated_at": null, "received_at": null, "raw_retained": true},
    "ratings_api": {"url": "", "updated_at": null, "received_at": null, "window_hours": null, "raw_retained": true}
  },
  "measurements": [],
  "latest_ratings": [],
  "rating_history": [],
  "iq_history": [],
  "candidates": [],
  "warnings": []
}
```

Normalize with these rules:

- Keep raw response bodies outside the JSON snapshot; do not duplicate the full HTML or API body inside it.
- Store numeric measurements as numbers in their documented units. Store missing values as `null`; never invent, coerce, or silently omit them.
- Give every measurement and rating an exact model ID, model family, and reasoning effort. Normalize source-specific keys to one canonical `model_id + effort` identity.
- Put today's IQ, passed/total tasks, Agent steps, cost, duration, cache hit rate, and tokens in `measurements`.
- Put rolling-24-hour averages and vote counts in `latest_ratings`; keep all dated API snapshots in `rating_history`.
- Put directly exposed historical IQ points in `iq_history`, including observation label/time and available cost, duration, pass count, and cache data.
- Build `candidates` only from the intersection of current measurements and latest ratings. Include derived history snapshot count, median, volatility, and trend for both rating and IQ history.
- Record source gaps, unmatched IDs, duplicate identities, parse uncertainty, and excluded candidates in `warnings`.

Validate before recommending:

1. Confirm `schema_version`, `fetched_at`, and both source records exist. Capture each source update time when exposed; record a warning when it is absent.
2. Confirm each candidate has unique identity, current IQ, latest rating, and vote count.
3. Confirm every candidate maps back to entries in both `measurements` and `latest_ratings`.
4. Confirm historical statistics use only non-null observations and report actual sample counts.
5. If validation fails for one candidate, exclude it and record why. If all candidates fail, do not recommend.
6. Treat uncertain model identity, current IQ, latest rating, vote count, or source-level parsing as a hard failure for affected candidates. Do not guess from retained raw text; use raw text only to verify an unambiguous extraction.
7. If `candidates` is empty or source-level validation prevents a trustworthy intersection, report that no recommendation is available.

Use the normalized JSON snapshot for all calculations, tables, and recommendations. Consult retained raw text only to resolve validation warnings or verify an extracted value; never refetch for verification.

## Interpret The Sources

From the retained main-page text, populate `measurements` with every combination in today's current IQ summary that has an actual IQ value. Capture all currently exposed fields when available:

- model family and exact Codex model ID;
- reasoning effort;
- current IQ and passed-task count;
- Agent steps;
- measured cost;
- measured duration;
- cache hit rate;
- total tokens.

Also populate `iq_history` with historical IQ measurements directly exposed in the retained text. Do not infer missing history from charts or inaccessible browser state.

From the retained ratings API text:

- Treat top-level `models` as the latest rolling-24-hour community data.
- Use top-level `models[].average` and `models[].count` in the recommendation.
- Treat `history` as 15-day historical snapshots.
- Use `history` to calculate per-combination coverage, median rating, volatility, direction, peaks, and declines.
- Keep latest top-level `models` values separate from `history`; never substitute one for the other.

Use the validated `candidates` array as the only recommendation candidate set. A combination with only community or historical data is not a recommendation candidate.

## Identify The Current Combination

Use the current Codex session model and reasoning effort, not a generic future default.

- Prefer explicit runtime/session metadata when the host exposes it.
- If runtime metadata is unavailable but Codex's current trusted session configuration exposes `model` and `model_reasoning_effort`, treat that pair as the `current usage model` for this session. Report source as `Codex session configuration`; do not label it `configuration default`.
- Read project `.codex/config.toml` first for the trusted current project, then global `~/.codex/config.toml` as fallback. Use `configuration default` wording only when the host explicitly identifies the value as a future default rather than the current session setting.
- If runtime metadata and session configuration disagree, report both, use runtime metadata for current-task status, and explain discrepancy.
- If it is an OpenAI Codex model/effort combination covered by the current IQ summary, report its current IQ.
- If it is an Anthropic, Google, local, unknown, or otherwise uncovered model, report `not covered by CodexRadar`; do not map it to a Codex model or invent an IQ.
- In non-Codex hosts, do not treat a recommended Codex combination as the host's current model.

## Select The Usage Profile

Infer one profile from the user's task and constraints:

- `quality`: production incidents, security, architecture, migrations, difficult debugging, or high-cost mistakes.
- `speed`: exploration, search, summaries, documentation, or latency-sensitive interaction.
- `economy`: repetitive/batch work or explicit quota and cost pressure.
- `balanced`: normal implementation and mixed workloads.

Ask only when the profile cannot be inferred and different choices would materially change the recommendation.

## Recommend

Always produce two profile-aware recommendations from the same validated JSON snapshot. Do not assume higher effort is smarter; follow measured data.

### Real-Time Recommendation

Rank the current candidate set primarily from today's evaluation:

- current IQ and passed-task count;
- latest top-level community rating and its sample size;
- task risk and quality floor;
- current measured cost and duration;
- operational stability signals visible on the page.

Use 15-day history only as secondary context for this recommendation. Label result `Real-time recommendation` and state that it may change after next evaluation.

### Stable Recommendation

Rank only combinations in the current candidate set that also have 15-day history. Prefer:

- stronger historical median over isolated peaks;
- lower historical volatility;
- broader day coverage and larger vote samples;
- flat or improving trend over sustained decline;
- stable historical IQ when the main-page response exposes it;
- acceptable current quality, cost, and duration for selected usage profile.

Require at least three historical snapshots before calling a result stable. If no candidate qualifies, report `Stable recommendation unavailable` instead of falling back to current data. Label result `Stable recommendation` and explain historical evidence.

Apply these priorities:

| Profile | Real-time priority | Stable priority |
|---|---|---|
| quality | Today's IQ and latest community confidence | Historical IQ/rating median, coverage, and low volatility |
| balanced | Today's IQ plus latest community confidence, duration, and cost | Historical median and trend, constrained by current duration and cost |
| speed | Current duration with acceptable current quality | Current duration with acceptable historical median and volatility |
| economy | Current cost with acceptable current quality | Current cost with acceptable historical median and volatility |

Treat small differences as ties. Prefer cheaper/faster candidate unless task is high risk. Recommendations may match; when they differ, explain whether latest performance or historical consistency caused divergence.

## Present Results

Always provide:

1. Data timestamps and the third-party-source caveat.
2. Current model/effort and current IQ, or an explicit unmeasured status.
3. One `Real-time recommendation` from today's evaluation with concise task-specific reason.
4. One `Stable recommendation` from 15-day history with concise stability evidence, or explicit unavailable status.
5. A comparison explaining why both recommendations match or differ.
6. Quality, speed, and economy alternatives when they materially differ.
7. A 15-day history summary.
8. A complete table of all currently measured candidates so the user can choose manually.
9. Exact proposed TOML for each available recommendation in separate blocks.

Real-time recommendation:

```toml
model = "<recommended-model-id>"
model_reasoning_effort = "<recommended-effort>"
```

Stable recommendation:

```toml
model = "<stable-model-id>"
model_reasoning_effort = "<stable-effort>"
```

The complete table should include, when available: current marker, model, effort, today's IQ, passed tasks, Agent steps, cost, duration, cache hit rate, total tokens, latest community rating/votes, historical snapshot count, 15-day median, volatility, and direction.

## Clean Up

After deriving the results and before ending the invocation, delete any temporary raw-text and normalized-JSON files created during this invocation. Keep no cross-invocation cache. Preserve an artifact only when the user explicitly asks to export or save it.

## Apply A Choice

Changing configuration is a separate action:

- If the user explicitly asked to apply or execute the recommendation, first determine whether the host supports selecting the recommended OpenAI Codex model and effort.
- In Codex, state the selected combination and target scope before editing. Prefer project `.codex/config.toml`; edit global `~/.codex/config.toml` only when explicitly requested.
- In Claude Code or another host that does not natively support the recommended Codex model, provide the recommendation but do not rewrite that host's model configuration or imply compatibility.
- When the host exposes a supported provider/model mapping, show the mapping and ask for confirmation before changing provider-specific settings.
- Use existing file-editing tools and preserve unrelated configuration and comments.
- In Codex, change only `model` and `model_reasoning_effort` unless another setting is explicitly requested.
- Validate the final configuration with an available configuration/file tool, not a generated program.
- Explain when the new default takes effect; configuration changes normally do not replace the model already running the current turn.
