---
name: chatgpt-codex-history-repair
description: Diagnose and safely repair missing or invisible local Codex history in ChatGPT.app on macOS. Use when ChatGPT.app Codex tasks or projects disappear after config changes, the history list is empty, project/workspace filtering looks wrong, or session JSONL files exist while the Desktop SQLite/index is out of sync. Do not use for npm/CLI Codex, ChatGPT cloud chat history, or provider migration.
---

# ChatGPT Codex History Repair

Repair local history visibility only. Preserve session-body JSONL; repair metadata, indexes, project hints, or the active SQLite selection only when evidence supports it.

## Safety

- Default to read-only inspection and dry-run.
- Fully quit ChatGPT.app before any write. Confirm no ChatGPT process still owns the database.
- Back up every file before changing it, using a timestamped directory.
- Never delete `~/.codex/sessions/`.
- Never overwrite or replace `state_5.sqlite` just because another copy exists.
- Do not run provider sync, model-provider migration, or CCSwitchMulti routing repair.
- Treat ChatGPT cloud history as a separate system.

## Workflow

### 1. Confirm scope and active app

- Confirm the user means Codex inside ChatGPT.app, not the standalone CLI.
- Treat `/Applications/ChatGPT.app/Contents/Resources/codex` as the bundled runtime when runtime details matter; do not modify the app bundle.
- Find the running ChatGPT process and inspect its open files to identify the SQLite file it actually uses:

```sh
pgrep -fl 'ChatGPT|chatgpt'
lsof -p "<ChatGPT PID>" | rg 'state_5\.sqlite|\.codex|sessions'
```

- Compare only plausible local candidates, normally:

```text
~/.codex/state_5.sqlite
~/.codex/sqlite/state_5.sqlite
~/.codex/sessions/
~/.codex/config.toml
```

Respect `CODEX_HOME` when set. Do not assume the first SQLite path is active.

### 2. Run read-only consistency checks

Record paths, modification times, and counts before proposing a fix:

```sh
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
find "$CODEX_HOME/sessions" -type f -name '*.jsonl' 2>/dev/null | wc -l
sqlite3 -readonly "$CODEX_HOME/state_5.sqlite" 'PRAGMA integrity_check;'
sqlite3 -readonly "$CODEX_HOME/state_5.sqlite" \
  "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
```

If the active database is elsewhere, run the same checks against that path. Discover the schema before querying thread counts; do not assume table names. Compare:

- session JSONL presence versus database rows;
- duplicate or stale session-index entries;
- project/workspace hints and current project path;
- user-event markers used by the Desktop history list;
- database integrity and last-write times.

Report which layer is missing or inconsistent. Do not call a session “deleted” only because it is absent from the visible list.

### 3. Prepare a dry-run repair plan

Prefer the smallest metadata-only repair:

- select the SQLite file ChatGPT.app actually opened;
- rebuild or repair session index entries from existing JSONL;
- correct project/workspace hints only when the session path proves the target;
- restore missing user-event visibility markers when schema and evidence match;
- leave session bodies and unrelated config/provider values unchanged.

Use CCSwitchMulti's `repair_codex_history_visibility` and `list_codex_history_sessions` concepts as a reference for dry-run reporting, provider buckets, session indexes, project hints, and active-DB selection. Do not invoke its provider-switch or `sync_codex_history_to_multirouter` actions for this task.

Show, before any write:

1. active database path and why it is active;
2. files to back up;
3. exact rows/metadata to change;
4. expected visible-history result;
5. rollback command or restore path.

Require explicit user confirmation before applying the plan.

### 4. Apply and verify only after confirmation

1. Quit ChatGPT.app completely.
2. Create timestamped backups of the selected SQLite, config, and any index files.
3. Apply only the approved metadata changes.
4. Re-run `PRAGMA integrity_check` and schema-specific counts.
5. Reopen ChatGPT.app, clear project/workspace filters, and verify known sessions in Codex.
6. If history is still missing, stop and report evidence; do not escalate to deletion or provider migration.

## Output Contract

Return:

- active ChatGPT.app database path;
- JSONL/SQLite/index consistency result;
- dry-run changes and backup paths;
- whether a write was performed;
- post-restart verification result and remaining uncertainty.
