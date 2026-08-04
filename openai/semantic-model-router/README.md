# Semantic Model Router

Local Codex plugin control plane for semantic task routing.

Current implementation covers Phases 0-6:

- trusted `UserPromptSubmit` hook;
- mode-0600, ten-minute prompt spool;
- opaque prompt references consumed once through MCP;
- `@current`, `@auto-off`, and `@auto-on` bypass controls;
- status and compact workflow receipts;
- a JSONL Codex App Server client with exact model/effort preflight;
- a per-turn supervisor that discovers the live App Server catalog through
  `model/list`, scores candidates by role, applies exact model/effort settings,
  downgrades only unsupported `max`/`ultra` requests to the highest supported
  effort, and keeps cancellation, timeouts, and child-process cleanup.
- bounded L/S workflow orchestration with structured classifier, planner packet,
  executor, reviewer, repair limits, and hard-risk approval pause.
- durable private approval tasks with single-use tokens, reject/resume controls,
  weak-versus-strong route feedback, repository-scoped metadata deletion, and
  explicit local data deletion confirmations.
- data-only policy candidates evaluated against frozen safety cases, explicit
  review/activation gates, rollback, and retention cleanup. Policy data never
  edits plugin source, hooks, permissions, or model targets.

Phase 6 is active through `create_policy_candidate`,
`review_policy_candidate`, `activate_policy_candidate`, `rollback_policy`, and
`run_route_retention`. `run_route_maintenance` provides a weekly-idempotent
local entry point; it never activates a candidate automatically.

## Automatic model selection

Normal workflow targets use `model: "auto"`. Each classifier, planner, executor,
and reviewer turn discovers the current App Server catalog and selects a
role-fit model deterministically. Route receipts report the actual model and
resolved effort used for each role.

`@luna` and `@sol` remain explicit model-family overrides. When requested effort
is unavailable, the router may lower it to the highest supported effort that
still satisfies the role minimum; the receipt shows requested and resolved
values. If the current model is available, it is used only as a degraded
fallback when classifier or L-route execution cannot start. Sol-path
unavailability remains fail-closed.

Policy learning can generate data-only candidates from confirmed feedback and
frozen replay cases. Candidates require explicit review and activation; no model
may edit router source, hooks, permissions, or model targets.

## Development

```bash
npm install
npm test
npm run lint
npm run verify:runtime
```

Build before installing plugin. Codex must explicitly trust bundled hook. Test changed hook or MCP code only after reinstall and in new task.

Optional macOS maintenance schedule:

```bash
npm run maintenance:launchd
npm run maintenance:launchd:remove
```

Install registers Sunday 03:00 Asia/Shanghai local maintenance. It retains
weak feedback, creates eligible candidates, and never activates a policy
without explicit confirmation.

## Privacy

Raw prompts exist only in private spool files and are deleted after MCP consumption or ten-minute expiry. Pending approval records retain only redacted, bounded task text and hashed repository/session metadata. Logs, MCP responses, and status data never contain raw prompts, full code, credentials, endpoint URLs, request IDs, or absolute paths.
