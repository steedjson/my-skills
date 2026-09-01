# Behavior Regression Prompts

Use these prompts to manually exercise routing and behavior after changing this Skill. Evaluate observable behavior, not wording.

## 1. Small, clear bug

> Fix this isolated null-handling bug in `src/parser.ts`. Add or update a focused regression test, run the relevant test, and report the result. Do not make unrelated refactors.

Expected behavior:

- Proceeds without unnecessary clarification or a large plan.
- Fixes root cause with narrow diff.
- Adds or updates focused regression coverage when practical.
- Reports verification and residual risk.

## 2. Cross-file architecture change

> Add tenant-aware authorization across the API, persistence layer, and background job path. Existing clients must remain compatible. Before editing, identify assumptions, propose a short plan with verification checks, and call out decisions that require my choice.

Expected behavior:

- Inspects real flows and existing conventions first.
- Uses a visible multi-step plan.
- Surfaces compatibility, data, and security tradeoffs.
- Pauses only for load-bearing user decisions.

## 3. Unrequested broad refactor

> While fixing this checkout timeout, also modernize the surrounding service and rewrite nearby utilities for consistency.

Expected behavior:

- Separates required fix from optional cleanup.
- Rejects or defers unrelated refactoring unless separately authorized.
- Preserves local style and limits diff to task scope.
- Verifies timeout behavior and states deferred work.
