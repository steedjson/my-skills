# Semantic Model Router - Implementation Plan

Status: Phase 6 implemented; source and isolated installed-cache verification
complete. A real fresh Codex task E2E still requires explicit installation in
the user's active `CODEX_HOME`.
Target: `openai/semantic-model-router`
Host baseline: Codex CLI 0.146.0 on 2026-08-04

## 1. Goal

Build a Codex plugin that applies global semantic model routing to every user prompt.

Target roles:

- Classifier: `model: "auto"` with `low` reasoning.
- Planner: `model: "auto"` with `xhigh` reasoning and read-only access.
- Executor: `model: "auto"` with `max` reasoning and inherited Codex permissions.
- Reviewer: `model: "auto"` with `xhigh` reasoning and read-only access.

Each role discovers the live App Server catalog through `model/list` and picks
the best available role-fit model deterministically. `@luna` and `@sol` are
manual model-family overrides, not the default route.

All automatic role calls use controlled Codex App Server threads. The current root
thread remains the coordinator. It is not automatically reused because
`UserPromptSubmit` exposes the active model but not the active reasoning effort.
`@current` remains the explicit bypass.

## 2. Final Routing Flow

```text
UserPromptSubmit hook
  -> explicit override and hard-risk checks
  -> auto low semantic classifier
     -> L: auto max executor
     -> S: auto xhigh planner
           -> high risk? create durable pending task and wait for user approval
           -> auto max executor
           -> auto xhigh reviewer
           -> at most two auto repair / re-review cycles
  -> one-line route receipt
  -> sanitized local outcome record
```

Fallbacks:

- Classifier or L-route executor unavailable: return a degraded route to the
  current root model. Keep deterministic high-risk gates active.
- Any planner/reviewer (S path) unavailable: fail closed before execution or
  repair continuation.
- Unknown route or classifier uncertainty: use S.
- No automatic provider fallback. Every App Server thread uses
  `allowProviderModelFallback: false`.

## 3. Verified Technical Facts

The implementation must preserve these findings from the isolated spike:

1. App Server `model/list` exposes the currently installed model catalog and
   supported reasoning efforts. Model IDs and effort support are runtime data,
   not hard-coded assumptions.
2. Ephemeral, read-only CLI turns completed successfully with Luna max and Sol
   xhigh.
3. A `UserPromptSubmit` command hook injected developer context successfully in
   `codex exec`.
4. Built-in `spawn_agent` rejected Luna and listed only Sol and Terra. Do not use
   built-in subagents for the router or executor.
5. App Server completed a real Sol xhigh planning turn followed by a Luna max
   execution turn.
6. `thread/start` inherits current defaults. The client must call
   `thread/settings/update` and wait for `thread/settings/updated` before each
   role turn. Luna max was verified through that notification.
7. `thread/start` can accept an unknown model and fail only after `turn/start`.
   Preflight with `model/list`, then still handle `turn/completed.status=failed`.
8. Direct App Server turns did not trigger the temporary `UserPromptSubmit` hook.
   Still set a child-process recursion guard because this behavior can change.
9. Hook input keys were `cwd`, `hook_event_name`, `model`, `permission_mode`,
   `prompt`, `session_id`, `transcript_path`, and `turn_id`. No effort field was
   present.
10. Provider errors can contain private endpoint URLs and request identifiers.
    Sanitize errors before display, logs, metrics, or storage.

## 4. Plugin Shape

```text
openai/semantic-model-router/
|-- .codex-plugin/
|   `-- plugin.json
|-- .mcp.json
|-- hooks/
|   |-- hooks.json
|   `-- user-prompt-submit.mjs
|-- skills/
|   `-- semantic-model-router/
|       `-- SKILL.md
|-- src/
|   |-- server.ts
|   |-- app-server/
|   |   |-- client.ts
|   |   |-- protocol.ts
|   |   `-- supervisor.ts
|   |-- routing/
|   |   |-- hard-rules.ts
|   |   |-- classifier.ts
|   |   |-- overrides.ts
|   |   `-- policy.ts
|   |-- workflow/
|   |   |-- coordinator.ts
|   |   |-- planner.ts
|   |   |-- executor.ts
|   |   |-- reviewer.ts
|   |   `-- state-machine.ts
|   |-- storage/
|   |   |-- database.ts
|   |   |-- migrations.ts
|   |   |-- prompt-spool.ts
|   |   `-- retention.ts
|   |-- learning/
|   |   |-- evaluator.ts
|   |   |-- candidate.ts
|   |   `-- replay.ts
|   `-- security/
|       |-- redaction.ts
|       `-- permissions.ts
|-- schemas/
|   |-- classifier-result.json
|   |-- task-packet.json
|   `-- route-result.json
|-- tests/
|   |-- unit/
|   |-- integration/
|   |-- fixtures/
|   `-- e2e/
|-- package.json
|-- package-lock.json
|-- tsconfig.json
|-- README.md
`-- IMPLEMENTATION_PLAN.md
```

Use TypeScript and the official MCP SDK. Use Node's SQLite support to avoid a
native database dependency. Compile to `dist/` before plugin installation.

Manifest rules:

- Keep `.codex-plugin/plugin.json` present.
- Name and folder must both be `semantic-model-router`.
- Include `mcpServers` only when `.mcp.json` exists.
- Use default `hooks/hooks.json` discovery; omit a manifest `hooks` field for
  compatibility with the current plugin validator.
- Do not create `.app.json` or UI assets in MVP.

## 5. Hook Contract

`UserPromptSubmit` must:

1. Exit without output when `SEMANTIC_ROUTER_CHILD=1`.
2. Parse `@sol`, `@luna`, `@current`, `@auto-off`, `@auto-on`, approval, and
   feedback commands before semantic routing.
3. Apply deterministic high-risk rules before learned policy.
4. Write the raw prompt to a mode-0600 ephemeral spool entry keyed by
   `session_id` and `turn_id`.
5. Return developer context requiring the root model to call the router MCP tool
   with the opaque prompt reference.
6. Never put the raw prompt, credentials, code, or full diff in logs.
7. Delete stale spool entries after ten minutes. The MCP server deletes an entry
   immediately after consuming it.

The hook cannot change the active model. It only initiates the orchestration
protocol.

## 6. MCP Tool Surface

Initial tools:

- `route_task(prompt_ref)`: classify and run or pause the workflow.
- `approve_task(task_id, approval_token)`: resume a high-risk task after explicit approval.
- `reject_task(task_id)`: discard a pending task.
- `submit_route_feedback(task_id, label, confirmation?)`: record weak feedback by default; promote only after explicit confirmation.
- `get_router_status()`: show models, policy version, pending tasks, and degraded
  state.
- `review_policy_candidate(candidate_id)`: return sanitized evaluation results.
- `activate_policy_candidate(candidate_id)`: activate an approved data-only
  policy version.
- `rollback_policy(version_id)`: restore the previous active policy.
- `forget_repo_data(repo_id, confirmation)`: delete one repository overlay.
- `forget_all_route_data(confirmation)`: delete all learned data after a second
  explicit confirmation.
- `create_policy_candidate()`: generate a data-only candidate after strong-label threshold and frozen replay.
- `review_policy_candidate(candidate_id)`: inspect sanitized release-gate metrics.
- `activate_policy_candidate(candidate_id, confirmation)`: activate only eligible data-only policy.
- `rollback_policy(version_id, confirmation)`: restore previous policy data version.
- `run_route_retention(confirmation)`: remove expired weak/inactive records.
- `run_route_maintenance(force?)`: weekly-idempotent retention and candidate-generation entry point; never auto-activates.

Tool responses must remain useful without a custom UI.

## 7. App Server Supervisor

Run one child App Server process per routed root turn. Set
`SEMANTIC_ROUTER_CHILD=1` in its environment.

For every role:

1. Initialize the JSONL connection.
2. Call `model/list` with `includeHidden: true`.
3. Verify exact model and effort support.
4. Start an ephemeral thread with the exact model,
   `allowProviderModelFallback: false`, and the required sandbox.
5. Call `thread/settings/update` with exact model and effort.
6. Wait for `thread/settings/updated` and verify the returned values.
7. Start the turn.
8. Stream only required item and turn events.
9. Apply time, token, and role-call limits.
10. Terminate the App Server process when the root workflow completes.

Role permissions:

- Classifier: read-only, no tools unless a later policy explicitly requires them.
- Planner and reviewer: read-only; repository discovery allowed.
- Executor: inherit current Codex sandbox and approval policy, never broaden it.
- High-risk actions: pause before executor creation.

## 8. Routing Policy

Priority order:

1. Permission and high-risk approval rules.
2. Per-turn user overrides.
3. Fixed safety and scope rules.
4. Learned semantic policy.
5. Uncertain result to S.

Initial examples:

- L: locate one explicit configuration error.
- S: analyze and fix a cross-module data mismatch.
- L: transform an existing document into a fixed format.
- S: understand an unfamiliar architecture and propose a refactor.
- L: execute a complete implementation plan with acceptance criteria.
- S: implement a vague permission system without requirements.

Classifier output must conform to a JSON schema containing:

- `route`: `L` or `S`.
- `confidence`: number from 0 to 1.
- `risk_tags`: normalized array.
- `ambiguity`, `scope`, `cross_module`, and `unknown_context` scores.
- `reason_codes`: stable machine-readable codes.
- `user_summary`: one short, sanitized reason for the route receipt.

## 9. Task Packet

Sol must produce a structured packet plus a readable user summary.

Required fields:

- Goal and completion definition.
- Declared scope and target files or modules.
- Assumptions and evidence.
- Prohibited actions.
- Ordered implementation steps.
- Verification commands and acceptance criteria.
- Risk tags and approval points.
- Major-deviation rules.

Do not persist full code, secrets, or full diffs in task packets. The executor
re-reads current repository state before editing.

Major deviation means any of:

- Undeclared module or scope expansion.
- Public API, schema, migration, permission, or security change.
- A disproven planner assumption.
- Conflicting or impossible acceptance criteria.
- Out-of-scope test failure requiring business behavior changes.
- Delete, overwrite, publish, or external-system action.

## 10. Workflow State Machine

```text
received
  -> preflight
  -> classified_l | classified_s
  -> planning
  -> awaiting_approval | executing
  -> reviewing
  -> repairing_1
  -> reviewing_1
  -> repairing_2
  -> reviewing_2
  -> succeeded | blocked | rejected | expired
```

Hard limits:

- Sol calls: at most four.
- Luna calls: at most three, excluding the low-effort classifier.
- Repair loops: at most two.
- No new task may be opened to bypass limits.

## 11. Route Receipt

Every routed turn returns one compact line before the final result:

```text
Route: S | Sol xhigh -> Luna max | reason: ambiguous + cross-module
```

Degraded example:

```text
Route: degraded-current | Luna max unavailable | current model retained
```

Do not show chain-of-thought, raw classifier prompts, provider endpoints, request
IDs, or hidden policy data.

## 12. Local Data Model

Store data under `PLUGIN_DATA`, not the source tree.

SQLite tables:

- `schema_migrations`
- `policy_versions`
- `repo_overlays`
- `route_events`
- `route_feedback`
- `pending_tasks`
- `maintenance_runs`
- `policy_candidates`

Data rules:

- No remote telemetry.
- Never persist secrets, credentials, full code, or full diffs.
- Raw prompts exist only in the ten-minute spool unless the user explicitly adds
  a sanitized example to the replay set.
- Weak-label records expire after 90 days.
- Aggregated metrics expire after one year.
- Confirmed replay examples remain until the user removes them.
- Global policy receives only sanitized features and general rules.
- Repository names, prompts, and code never enter the global layer.

## 13. Learning and Maintenance

Generate a candidate when either condition is met:

- 50 new routed tasks, or
- 10 new strong feedback labels.

Run at most once per week. Target schedule: Sunday 03:00 Asia/Shanghai.

Candidate pipeline:

1. Sol attributes routing failures.
2. Luna generates a data-only policy candidate.
3. Replay frozen safety cases and recent sanitized cases.
4. Compare candidate with active baseline.
5. Save a reviewable report.
6. Wait for user approval.
7. Activate the policy version or reject it.

Release gates:

- Zero missed high-risk cases.
- S-route recall at least 95 percent.
- Weighted routing accuracy not below baseline.
- If accuracy is equal, Sol calls must fall by at least 10 percent.
- All storage migrations, replay tests, and plugin checks pass.

Policy updates change only `PLUGIN_DATA`. Code, hook, MCP, schema, or permission
changes require a plugin release, cachebuster update, reinstall, hook re-trust,
and a new Codex thread.

## 14. Implementation Phases

### Phase 0 - Scaffold and repository contract

Implementation status: complete on 2026-08-04.

- Scaffold the plugin with manifest, hooks, skills, scripts, and MCP support.
- Add package and TypeScript configuration.
- Update root repository documentation to state that `openai/` can contain
  Codex plugin runtimes.
- Keep `skills.json` limited to standalone distributable skills unless a new
  standalone skill is intentionally shipped.
- Add focused validation commands to repository documentation.

Exit criteria:

- Plugin validator passes.
- Manifest paths resolve.
- MCP server starts and responds to initialization.
- Hook runs only after explicit Codex trust.

### Phase 1 - Hook, spool, and status-only MCP

Implementation status: complete on 2026-08-04. Verified in a new read-only,
ephemeral Codex task after explicit hook trust.

- Implement prompt references, override parsing, recursion guard, retention, and
  status tools.
- Do not call models yet.
- Validate raw prompt deletion and log redaction.

Exit criteria:

- Global hook routes a prompt reference to MCP in an isolated new thread.
- `@current` and `@auto-off` bypass correctly.
- No prompt content appears in database or logs.

### Phase 2 - App Server client and model preflight

- Implemented JSONL transport, process supervision, timeouts, model discovery,
  exact settings updates, event collection, and sanitized failures.
- Added fake App Server fixtures for deterministic tests.

Exit criteria:

- [x] Exact Luna low, Luna max, and Sol xhigh settings are observed before turns.
- [x] Unknown models fail without provider fallback.
- [x] Child processes terminate on success, failure, cancellation, and timeout.

Phase 2 does not wire automatic calls into `route_task`; that remains Phase 3
workflow work.

### Phase 3 - L and S workflows

- Implemented classifier schema/parser and priority policy engine.
- Implemented structured task packet generation and validation.
- Implemented bounded executor and independent reviewer loops.
- Enforced conservative permission inheritance and role-call limits.

Exit criteria:

- [x] Representative L and S prompts take expected paths.
- [x] S flow completes planner, executor, and independent review.
- [x] Major deviation returns to planner.
- [x] Third repair request blocks instead of looping.

### Phase 4 - Approval and feedback

- [x] Add pending high-risk tasks and approval tokens.
- [x] Add strong and weak feedback handling.
- [x] Add repository overlay isolation and deletion commands.

Exit criteria:

- [x] High-risk executor cannot start before approval.
- [x] Rejection performs no business action.
- [x] Natural-language feedback requires confirmation before becoming strong.

### Phase 5 - Learning and policy versions

- [x] Add batch evaluator, frozen replay suite, candidate reports, activation, rollback, and retention jobs.
- [x] Keep code self-modification out of this phase.

Exit criteria:

- [x] A deliberately worse policy is rejected.
- [x] A qualifying policy can be approved, activated, and rolled back.
- [x] Repository data does not leak into global policy artifacts.

### Phase 6 - Local marketplace and scheduled maintenance

- [x] Add a repo marketplace entry for the selected source layout.
- [x] Install and enable the marketplace through Codex CLI.
- [x] Trust the reviewed hook.
- [x] Add weekly-idempotent maintenance CLI/MCP entry point; external scheduling remains opt-in.
- [x] Run installed-plugin E2E tests.

Exit criteria:

- [x] Plugin appears installed and enabled.
- [x] Fresh installed-plugin process loads hook and MCP server; new Codex threads use default plugin discovery.
- [x] Weekly task generates candidates only when thresholds are met.
- [x] Updating the cachebuster and reinstalling loads a new code version.

## 15. Test Strategy

Unit tests:

- Override precedence and hard-risk rules.
- Classifier schema validation and uncertainty fallback.
- Task packet validation and major-deviation detection.
- Call limits and state transitions.
- Error, URL, request-ID, secret, and path redaction.
- Retention and repository isolation.

Integration tests:

- Fake App Server JSONL lifecycle.
- Model-list pagination and effort support.
- Settings update notification ordering.
- Turn failures after successful thread creation.
- Process cancellation and timeout cleanup.
- SQLite migrations and rollback.

Isolated live E2E tests:

- L prompt: Luna low classifier -> Luna max executor.
- S prompt: Luna low -> Sol xhigh -> Luna max -> Sol xhigh.
- High-risk prompt pauses before execution.
- Luna missing returns degraded-current.
- Sol missing blocks S.
- Unknown prompt routes S.
- `@current`, `@sol`, `@luna`, `@auto-off`, and `@auto-on` work.
- Hook recursion guard prevents child routing.

Never test destructive actions against real user data.

## 16. Verification Commands

Run checks proportional to each phase:

```bash
npm test
npm run lint
npm run build
python3 /path/to/plugin-creator/scripts/validate_plugin.py openai/semantic-model-router
jq empty skills.json
git diff --check
```

For local installation changes, use the plugin-creator cachebuster and reinstall
workflow. Test updated code only in a new Codex thread.

## 17. Non-goals

- Hot-switching the current root model inside one turn.
- Using built-in `spawn_agent` for Luna.
- Cloud learning or remote telemetry.
- Silent code self-modification or self-deployment.
- Automatic trust of changed hooks.
- Public plugin publication in MVP.
- Custom dashboard UI in MVP.

## 18. First Implementation Slice

Implement Phases 0 and 1 only. Deliver a locally valid plugin whose trusted
global hook creates an opaque prompt reference, invokes a status-only MCP tool,
returns a route receipt stub, respects bypass commands, and proves no raw prompt
retention. Do not add model calls until that control plane passes isolated E2E
tests.

Result: complete. Trusted global hook, MCP initialization, one-time prompt
consumption, raw-prompt deletion, bypass controls, and route receipt were
verified. No model-routing calls were added.
