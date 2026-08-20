---
name: ln-install-skill
description: "Link agent skills with symlinks between a source skill directory and any host's skills directory — install, list, verify, uninstall. Hosts: DSH (~/.dsh/skills), Claude Code (~/.claude/skills), pi (~/.pi/agent/skills), cross-tool (~/.agents/skills), project-local skill directories. Use when the user wants to link/install a skill from a local directory into any agent host, list available source skills, check whether a linked skill is valid, or remove a linked skill. Only touches symlinks — never source files — so it is low-risk and reversible."
---

# ln-install-skill

Install, list, verify, or uninstall skills of **any Agent-Skills-compatible host** (DSH, Claude Code, pi, Codex, …) by creating **symlinks** ("ln") from a source skills directory into the host's skills directory. Hosts discover a skill from its `SKILL.md`; symlinking the source skill directory into the target is enough — no copy, no build.

This skill **only ever touches symlinks**. It never deletes, moves, or edits the source skill directories or their `SKILL.md` files.

## Defaults (override per request)

- **Source directory** `SRC` = `~/.cc-switch/skills` — the user's local collection of skill bundles.
  - If the user names a different directory (e.g. `~/.claude/skills`, `./skills`), use that instead.
- **Target directory** `DST` = the destination host's skills directory. Resolve in order:
  1. Path explicitly given by the user — use it.
  2. "project" / "in this repo" → `<repo>/.claude/skills` or `<repo>/.agents/skills`.
  3. Probe, take the first existing: `~/.dsh/skills` → `~/.claude/skills` → `~/.agents/skills`.
  4. None exists → ask, or `mkdir -p` the one they name. Known hosts: DSH `~/.dsh/skills`, Claude Code `~/.claude/skills`, pi `~/.pi/agent/skills`, cross-tool `~/.agents/skills`; Codex and other hosts — use the path from that host's docs.
- **Link name** = the source skill's directory basename (e.g. `SRC/grilling` → `DST/grilling`).
  - If the source `SKILL.md` frontmatter `name` differs from the directory basename, **report the difference** but still link by directory basename. (hosts identify a skill by its frontmatter `name`; the link name only needs to be unique in `DST`.)

## When to use this skill

The user wants to, or clearly should, do any of:

- "install / link / mount skill X (from ~/.cc-switch/skills) into DSH / Claude Code / pi / this repo"
- "list what skills are available to install"
- "check if skill X is properly installed / recognized"
- "uninstall / remove skill X" (only the link, never the source)

Trigger phrases: "ln install skill", "软链装 skill", "把 skill 链接到 dsh / claude code", "把这个 skill 装到项目里", "装到所有宿主", "列一下可装的 skill", "卸载 skill 的链接".

## Actions

In every action: **report the state before you change it**, then **echo the result with `ls -l` after**. Resolve `~` with the user's actual home directory (`$HOME`) — never pass a literal `~` to a tool that won't expand it.

### 1. List available skills (`list`)

```bash
ls -1d "$SRC"/*/ 2>/dev/null
```

For each source skill directory `S`, report:

- whether `S/SKILL.md` exists (skip directories without one — not installable),
- the frontmatter `name` and `description` (first line) if present,
- whether a link already exists at `DST/<basename>` and, if so, whether it points at `S` (✓ installed) or elsewhere (⚠ linked elsewhere → `<target>`).

Present this as a table. Never modify anything.

### 2. Install (`install <skill>`)

`<skill>` is the source skill's directory basename (e.g. `grill-me`). Resolve `SRC/<skill>`.

1. **Verify source**: `SRC/<skill>` must be a directory containing `SKILL.md`. If not, stop and report — do not create a link to something the host can't read.
2. **Report existing target state**: if `DST/<skill>` already exists (file, dir, or symlink), print `ls -ld "DST/<skill>"` and `readlink "DST/<skill>"` so the user can see what's being replaced.
3. **Report name mismatch** (if any): if `SRC/<skill>/SKILL.md` frontmatter `name` ≠ `<skill>`, say so explicitly. Link name stays `<skill>`; the host registers the skill under the frontmatter `name`.
4. **Create the link**:

   ```bash
   mkdir -p "$DST"
   ln -sfn "$SRC/$SKILL" "$DST/$SKILL"
   ```

   `-s` = symbolic, `-f` = replace existing, `-n` = treat an existing symlink-to-dir as a file (don't recurse into it) — this prevents `ln` from creating the new link *inside* an existing linked directory.

5. **Verify** (run the **Verify** action below) and report the result. If verification fails (e.g. missing frontmatter), the link is still created but warn the user the skill may not be picked up by the host until the source `SKILL.md` is fixed.

### 3. Verify (`verify <skill>`)

For an installed skill at `DST/<skill>`:

1. `test -L "DST/<skill>"` — must be a symlink. If not, report "not a symlink" and stop.
2. `readlink "DST/<skill>"` → `target`. `test -d "$target"` — the link must resolve to an existing directory.
3. `test -f "$target/SKILL.md"` — the host reads this file. Missing → "skill will not be recognized by the host".
4. Parse the `SKILL.md` YAML frontmatter (the `---`-delimited block at the top). Report the `name` and `description`. If `name` or `description` is missing, warn (hosts need both).
5. **Collision check**: scan other entries in `DST` for a `SKILL.md` frontmatter `name` equal to this skill's. Collision → warn: the host may resolve the two nondeterministically. Compare with `realpath` — `DST` entries are symlinks and `normpath` keeps link-path text, which false-flags the skill's own link as a collision (see buglog `bug-002`).
6. Report whether the link was created from `SRC` (the configured source) or elsewhere.

### 4. Uninstall (`uninstall <skill>`)

Only ever `rm` the **link** at `DST/<skill>`. **Never** delete the source directory `SRC/<skill>` or any file inside it.

1. Verify `DST/<skill>` is a symlink (`test -L`). If it's a real directory, **stop and ask** — don't `rm -rf` a real directory.
2. Report what the link points at (`readlink`) before removing.
3. `rm "DST/<skill>"` (no `-r`, no `-f`).
4. Echo `ls -ld "DST/<skill>"` (should now be "No such file or directory").

### 5. Install to all hosts (`install-all <skill>`)

User says "装到所有宿主" / "everywhere". For each **existing** directory in the probe list (`~/.dsh/skills`, `~/.claude/skills`, `~/.agents/skills`, plus any the user names), run **Install** steps 1–5 with that `DST`. Hosts with no existing directory are skipped (and reported). A failed verify on one host does not stop the other hosts.

## Rules

- **Only symlinks.** Source directories and their `SKILL.md` are read-only from this skill's perspective.
- **Host-agnostic.** DSH, Claude Code, pi, cross-tool, a project directory — the same symlink rules apply regardless of `DST`.
- **Report before changing.** Always show `ls -ld` / `readlink` of the existing target before `ln` / `rm`, and `ls -l` after.
- **Resolve `~` to `$HOME`.** Never pass a literal `~` to tools that don't expand it.
- **One skill per install/uninstall** unless the user says "install all" / "install X and Y".
- `disable-model-invocation` is **not** set: the model may invoke this skill on its own when the user's request clearly matches (e.g. "把 grill-me 装上"). The user may also invoke it directly via `/ln-install-skill`.
