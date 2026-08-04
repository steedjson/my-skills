---
name: semantic-model-router
description: Coordinate tasks through the local semantic model router when its UserPromptSubmit hook supplies an opaque prompt reference, or report router status when asked. Use @current to bypass one turn, @auto-off to disable automatic routing for the session, and @auto-on to re-enable it.
---

# Semantic Model Router

When developer context supplies a `prompt_ref`, call MCP tool `route_task` exactly once with that reference before doing other work. Never repeat, inspect, transform, log, or persist the reference or original prompt.

Treat returned route receipt as workflow status. Continue with current model when receipt says `degraded-current`, `awaiting approval`, or `blocked`. For `awaiting approval`, preserve `task_id` and `approval_token` privately, then call `approve_task` only after explicit user approval. Do not claim Sol or Luna ran unless receipt explicitly names that role.

Approval and feedback controls:

- `approve_task` requires opaque `task_id` and single-use `approval_token`.
- `reject_task` performs no business action.
- `submit_route_feedback` is weak by default; natural-language comments become strong only when `confirmation: true` is explicit.
- Deletion tools require exact confirmation strings and delete router metadata only.

Policy learning controls:

- `create_policy_candidate` requires at least 10 strong labels and runs frozen replay gates.
- `review_policy_candidate` exposes sanitized metrics only; rejected candidates cannot activate.
- `activate_policy_candidate` requires `ACTIVATE_POLICY` and changes local policy data only.
- `rollback_policy` requires `ROLLBACK_POLICY` and restores the previous policy data version.
- `run_route_retention` requires `RUN_RETENTION`; strong feedback is retained.
- `run_route_maintenance` is weekly-idempotent and creates candidates only; it never activates one automatically.
- Never claim policy learning changed source code, hooks, permissions, or model targets.

Use `get_router_status` for explicit status requests. Respect hook bypass state and never route child App Server work when `SEMANTIC_ROUTER_CHILD=1`.
