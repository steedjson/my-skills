---
name: coding-discipline
description: Apply evidence-driven coding discipline for non-trivial or risky implementation work, especially when the user asks for minimal changes, explicit tradeoffs, root-cause fixes, or stronger verification. Do not use as a substitute for framework-specific workflows or dedicated code-quality audits.
---

# Coding Discipline

Use this skill to improve decisions during coding work. It is a working method, not a replacement for repository instructions or the user's requested scope.

## Before changing code

- State material assumptions briefly. If ambiguity affects API, data, architecture, security, or irreversible behavior, ask before choosing.
- Inspect the real execution path and existing conventions before proposing abstractions.
- For non-trivial work, define a short plan with a verification check for each step. Use the host's plan/todo mechanism when available; do not create tracking files unless requested.
- Preserve unrelated uncommitted changes. Inspect overlapping diffs before editing.

## Prefer the smallest sound solution

Choose the first option that satisfies the requirement after understanding the problem:

1. Omit work that is not needed (YAGNI).
2. Reuse existing helpers, patterns, platform features, standard library, and installed dependencies.
3. Add the smallest maintainable implementation only when existing options do not fit.

Do not add speculative configurability, one-off abstractions, new dependencies, or broad refactors. Keep security checks, trust-boundary validation, data-loss protection, accessibility basics, and explicit requirements even when simplifying.

## Make precise edits

- Match local style. Change only code required for task.
- Do not opportunistically reformat, rename, or improve adjacent code.
- Remove imports, variables, or functions made unused by your own change.
- Do not delete pre-existing dead code unless requested.
- Prefer root-cause fixes over symptom patches. For a bug, reproduce it with a focused test when practical.
- If a deliberate shortcut has a known scaling or correctness ceiling that affects current scale, reliability, or maintenance, document it with a concise `debt:` note and upgrade condition. Do not record purely theoretical limits.

## Verify before declaring done

Translate request into observable acceptance criteria. Before completion:

- Run focused tests first, then broader checks proportional to risk.
- Inspect failures, logs, generated output, and the final diff; do not infer success from code inspection alone.
- Confirm error paths, boundary inputs, compatibility, and security-sensitive behavior when relevant.
- Report what was verified and what could not be verified.

Never claim completion when required checks are failing or have not been run; state the blocker clearly.

## Workflow choices

- Handle small, clearly scoped fixes autonomously.
- For work spanning multiple files, multiple steps, or architecture decisions, keep a visible plan and pause only at decisions that require user choice.
- Use parallel agents only when available and useful: one bounded task per agent, disjoint write scopes, and review returned changes before integrating. Never delegate merely to appear thorough.
- Record a project-specific lesson only when the user explicitly requests persistence or the repository already defines a lessons/conventions location. Keep it actionable and narrow; do not create a memory system or tracking file by default.

## Communication

Keep updates concise and technical. Explain important tradeoffs, changed files, verification results, and blockers. Do not bury uncertainty or silently choose among materially different interpretations.

## Minimum delivery format

For completed implementation work, report:

- What changed
- Why this approach was chosen
- What was verified
- Checks not run
- Remaining risks or follow-up
