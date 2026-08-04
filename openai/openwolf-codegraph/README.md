# OpenWolf + CodeGraph

Codex plugin bridging global lifecycle hooks to repository-local OpenWolf hooks while injecting CodeGraph-first navigation guidance.

## Activation

Plugin runs globally but acts only when active repository contains `.wolf/` or `.codegraph/`:

- `.wolf/`: forwards session start, pre-write, post-write, and stop events to repository hooks.
- `.codegraph/`: injects guidance to use `codegraph_explore` before broad code searches.
- Neither marker: exits without output or project changes.

Project-specific OpenWolf logic remains inside each repository. Plugin only adapts Codex event payloads and handles deleted-file bookkeeping.

## Validate

```bash
node --check hooks/openwolf.mjs
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

After installation or update, trust plugin hooks and open a new Codex task so lifecycle hooks load.
