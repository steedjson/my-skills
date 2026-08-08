#!/usr/bin/env python3
"""Offline stdlib-only consistency validator for the my-skills repo."""
import json
import re
import sys
from pathlib import Path

HOME_PATH_RE = re.compile(r"/(?:Users|home)/[^/\s]+")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_skills(repo):
    errors = []
    data = load_json(repo / "skills.json")
    for skill in data.get("skills", []):
        name = skill.get("name")
        if not name:
            errors.append("skill entry missing 'name'")
            continue
        sdir = repo / name
        if not sdir.is_dir():
            errors.append(f"skill dir missing: {name}/")
            continue
        if not (sdir / "SKILL.md").is_file():
            errors.append(f"skill missing SKILL.md: {name}/")
        for rel in skill.get("files", []):
            if not (sdir / rel).is_file():
                errors.append(f"skill file missing: {name}/{rel}")
    return errors


def check_marketplace(repo):
    mp = repo / ".agents" / "plugins" / "marketplace.json"
    if not mp.is_file():
        return []
    data = load_json(mp)
    errors = []
    for plug in data.get("plugins", []):
        name = plug.get("name")
        if not name:
            errors.append("marketplace plugin entry missing 'name'")
            continue
        path = (plug.get("source") or {}).get("path", "")
        if not path:
            errors.append(f"marketplace plugin {name} missing source.path")
            continue
        pdir = Path(path) if Path(path).is_absolute() else repo / path
        manifest = pdir / ".codex-plugin" / "plugin.json"
        if not manifest.is_file():
            errors.append(f"plugin manifest missing: {name} -> {manifest}")
            continue
        try:
            load_json(manifest)
        except json.JSONDecodeError as e:
            errors.append(f"plugin manifest invalid JSON ({name}): {e}")
    return errors


def _tracked_docs(repo):
    docs = ["CLAUDE.md", "README.md", "AGENTS.md"]
    plugs = repo / "plugins"
    if plugs.is_dir():
        for pdir in sorted(plugs.iterdir()):
            readme = pdir / "README.md"
            if readme.is_file():
                docs.append(str(readme.relative_to(repo)))
    return docs


def check_paths(repo):
    errors = []
    for rel in _tracked_docs(repo):
        path = repo / rel
        if not path.is_file():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if HOME_PATH_RE.search(line):
                errors.append(f"hardcoded home path {rel}:{line_no}: {line.strip()[:80]}")
    return errors


def main():
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    errors = check_skills(repo) + check_marketplace(repo) + check_paths(repo)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        print(f"\n{len(errors)} problem(s) found.", file=sys.stderr)
        return 1
    print("OK: skills.json, marketplace.json, plugin manifests, and tracked docs validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
