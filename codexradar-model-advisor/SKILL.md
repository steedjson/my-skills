---
name: codexradar-model-advisor
description: Query CodexRadar for OpenAI Codex models only, using web or browser tools already available to the agent; report OpenAI Codex model-and-effort IQ and related measurements, analyze 15-day community-rating history, recommend only combinations with current measured data, list all measured choices, and apply a selected recommendation when the host agent supports that OpenAI model configuration. Use in Codex, Claude Code, and other Agent Skills-compatible agents for OpenAI Codex IQ checks, degradation checks, Sol/Terra/Luna comparisons, reasoning-effort selection, or recommendations based on codexradar.com. Do not use to score or recommend Anthropic, Google, local, or other non-OpenAI models.
---

# CodexRadar Model Advisor

Follow the portable Agent Skills format. Use only tools already available to the host agent. Do not create bundled/custom programs, run shell or curl commands, or maintain local caches for this skill. Browser/web tools may use their normal internal control mechanism.

Treat CodexRadar as a third-party empirical source, not an OpenAI-official IQ benchmark.

This skill evaluates OpenAI Codex models only. Never assign CodexRadar IQ values to non-OpenAI models.

## Read Current Data

1. Inspect the host agent's available tools for a direct web/HTTP reader suitable for the URLs below. Prefer it when available.
2. Otherwise use an available browser tool and inspect visible or structured page state.
3. Read both sources:
   - `https://codexradar.com/`
   - `https://codexradar.com/api/model-ratings?history=15`
4. Fetch each source at most once per skill invocation. Fetch both in parallel when the host supports parallel tool calls.
5. Treat both responses as one turn-local snapshot. Reuse that snapshot for parsing, recommendation, and presentation; do not fetch either source again during the normal workflow.
6. Refetch an individual source only when its first request failed, its response is incomplete, the user explicitly requests a refresh, or more than 15 minutes have elapsed and current data is still required.
7. Do not use remembered values from a prior skill invocation. Report each source's update time.
8. If either source cannot be read after an allowed retry, state which data is unavailable and do not fabricate it.

## Interpret The Sources

From the main page, collect every combination in the current IQ summary that has an actual IQ value. Capture all currently exposed fields when available:

- model family and exact Codex model ID;
- reasoning effort;
- current IQ and passed-task count;
- Agent steps;
- measured cost;
- measured duration;
- cache hit rate;
- total tokens.

From the ratings endpoint:

- Treat top-level `models` as the latest rolling-24-hour community data.
- Use top-level `models[].average` and `models[].count` in the recommendation.
- Treat `history` as 15-day historical snapshots only.
- Use `history` to summarize direction, volatility, peaks, and declines.
- Never average or substitute `history` values for the latest top-level `models` values in the recommendation.

Recommend only the intersection of combinations that have a current IQ measurement on the main page and a matching latest `models` entry. A combination with only a community rating is not a measured recommendation candidate.

## Identify The Current Combination

Use the active task model and reasoning effort when the host agent exposes them.

- If it is an OpenAI Codex model/effort combination covered by the current IQ summary, report its current IQ.
- If it is an Anthropic, Google, local, unknown, or otherwise uncovered model, report `not covered by CodexRadar`; do not map it to a Codex model or invent an IQ.
- If the active model is unavailable and the host is Codex, inspect the applicable Codex configuration with an existing file-reading tool:

- project `.codex/config.toml` for a trusted project;
- global `~/.codex/config.toml` as fallback.

Clearly distinguish an active-task model from a configuration default. In non-Codex hosts, do not treat a recommended Codex combination as the host's current model.

## Select The Usage Profile

Infer one profile from the user's task and constraints:

- `quality`: production incidents, security, architecture, migrations, difficult debugging, or high-cost mistakes.
- `speed`: exploration, search, summaries, documentation, or latency-sensitive interaction.
- `economy`: repetitive/batch work or explicit quota and cost pressure.
- `balanced`: normal implementation and mixed workloads.

Ask only when the profile cannot be inferred and different choices would materially change the recommendation.

## Recommend

Use current values for the decision. Consider:

- current IQ and passed-task count;
- latest top-level community rating and its sample size;
- task risk and quality floor;
- current measured cost and duration;
- operational stability signals visible on the page.

Use 15-day history only as contextual evidence. Do not assume higher effort is smarter; follow the current measurements.

Apply these priorities:

| Profile | Primary priority | Secondary constraints |
|---|---|---|
| quality | Current IQ and latest community confidence | Stability, then duration/cost |
| balanced | Current IQ plus latest community confidence | Duration and cost |
| speed | Duration with an acceptable quality floor | Latest rating and cost |
| economy | Cost with an acceptable quality floor | Duration and latest rating |

Treat small differences as ties. Prefer the cheaper/faster candidate unless the task is high risk.

## Present Results

Always provide:

1. Data timestamps and the third-party-source caveat.
2. Current model/effort and current IQ, or an explicit unmeasured status.
3. One primary recommendation with a concise task-specific reason.
4. Quality, speed, and economy alternatives when they differ.
5. A 15-day history summary clearly marked as context only.
6. A complete table of all currently measured candidates so the user can choose manually.
7. Exact proposed TOML:

```toml
model = "<recommended-model-id>"
model_reasoning_effort = "<recommended-effort>"
```

The complete table should include, when available: current marker, model, effort, IQ, passed tasks, Agent steps, cost, duration, cache hit rate, total tokens, latest community rating/votes, and 15-day direction.

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
