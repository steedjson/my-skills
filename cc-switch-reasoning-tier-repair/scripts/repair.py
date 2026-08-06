#!/usr/bin/env python3
"""Repair reasoning-effort tiers in Codex/cc-switch runtime configuration.

Reads the live config.toml, finds the multi-router provider and the referenced
model catalog, then aligns both with the expected tier map shipped in
references/expected-tier-map.json. Backs up every file before modification.

Usage:
  python3 repair.py --check
  python3 repair.py --dry-run
  python3 repair.py [--config ~/.codex/config.toml] [--backup-dir ~/.codex]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Any


PROVIDER_KEY = "codex_model_router_v2"
MODELS_ASSIGNMENT = re.compile(r"\bmodels\s*=\s*\[")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return str(value)
    raise TypeError(f"unsupported TOML scalar: {type(value)!r}")


def toml_inline(value: Any) -> str:
    if isinstance(value, list):
        return "[ " + ", ".join(toml_inline(v) for v in value) + " ]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{k} = {toml_inline(v)}" for k, v in value.items()) + " }"
    return toml_scalar(value)


def serialize_models(models: list[dict[str, Any]]) -> str:
    lines = ["models = ["]
    for i, model in enumerate(models):
        comma = "," if i < len(models) - 1 else ""
        lines.append(f"  {toml_inline(model)}{comma}")
    lines.append("]")
    return "\n".join(lines)


def model_id(model: dict[str, Any]) -> str | None:
    value = model.get("model") or model.get("id") or model.get("slug")
    return value if isinstance(value, str) and value else None


def tier_values(entries: Any, key: str) -> list[str]:
    if not isinstance(entries, list):
        return []
    return [entry.get(key) for entry in entries if isinstance(entry, dict)]


def apply_tiers(
    model: dict[str, Any],
    expected: list[str],
    descriptions: dict[str, str],
) -> bool:
    changed = False
    for field, key in (
        ("supported_reasoning_levels", "effort"),
        ("supported_reasoning_efforts", "reasoning_effort"),
        ("supportedReasoningEfforts", "reasoningEffort"),
    ):
        entries = model.get(field)
        if not isinstance(entries, list):
            continue
        # This legacy compatibility field is intentionally empty in some
        # configs; do not invent a second representation when it has no data.
        if field == "supported_reasoning_efforts" and not entries:
            continue
        allowed = {tier: descriptions.get(tier, f"Reasoning effort {tier}") for tier in expected}
        rebuilt = [
            next(
                (e for e in entries if isinstance(e, dict) and e.get(key) == tier),
                {"description": allowed[tier], key: tier},
            )
            for tier in expected
        ]
        if tier_values(entries, key) != tier_values(rebuilt, key):
            model[field] = rebuilt
            changed = True
    return changed


def matching_bracket(text: str, start: int) -> int:
    """Return the matching closing bracket, ignoring brackets inside strings."""
    if start >= len(text) or text[start] != "[":
        raise ValueError("array start must point to '['")

    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quote is not None:
            if quote == '"' and escaped:
                escaped = False
            elif quote == '"' and char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unterminated models array")


def find_provider_models(config_text: str, provider_key: str) -> tuple[str, str, str] | None:
    marker = f"[model_providers.{provider_key}]"
    provider_start = config_text.find(marker)
    if provider_start < 0:
        return None
    provider_body_start = provider_start + len(marker)
    next_table = re.search(r"\n\[[^\n]+\]", config_text[provider_body_start:])
    provider_end = (
        provider_body_start + next_table.start() if next_table is not None else len(config_text)
    )
    match = MODELS_ASSIGNMENT.search(config_text, provider_body_start, provider_end)
    if not match:
        return None
    array_start = match.end() - 1
    try:
        array_end = matching_bracket(config_text, array_start)
    except ValueError:
        return None
    return (
        config_text[: match.start()],
        config_text[array_start : array_end + 1],
        config_text[array_end + 1 :],
    )


def extract_inline_models(expr: str) -> list[dict[str, Any]]:
    return tomllib.loads("models = " + expr)["models"]


def backup(path: Path, backup_dir: Path) -> Path | None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"{path.name}.before-reasoning-tier-repair-{stamp}"
    shutil.copy2(path, target)
    return target


def repair_config(
    config_text: str,
    expected_map: dict[str, list[str]],
    descriptions: dict[str, str],
) -> tuple[str, list[str], list[str]]:
    provider_parts = find_provider_models(config_text, PROVIDER_KEY)
    if provider_parts is None:
        raise RuntimeError(f"provider [{PROVIDER_KEY}] models assignment not found")
    prefix, models_expr, suffix = provider_parts
    models = extract_inline_models(models_expr)
    changes: list[str] = []
    unresolved: list[str] = []

    for model in models:
        current_id = model_id(model)
        expected = expected_map.get(current_id) if current_id else None
        if expected is None:
            if current_id:
                unresolved.append(current_id)
            continue
        before = tier_values(model.get("supported_reasoning_levels"), "effort")
        if apply_tiers(model, expected, descriptions):
            changes.append(f"{current_id}: {before} -> {expected}")

    new_models_text = serialize_models(models)
    return prefix + new_models_text + suffix, changes, unresolved


def repair_catalog(
    catalog: dict[str, Any],
    expected_map: dict[str, list[str]],
    descriptions: dict[str, str],
) -> tuple[list[str], list[str]]:
    models = catalog.get("models") if isinstance(catalog, dict) else catalog
    if not isinstance(models, list):
        raise RuntimeError("model catalog does not contain a models array")
    changes: list[str] = []
    unresolved: list[str] = []
    for model in models:
        current_id = model_id(model)
        expected = expected_map.get(current_id) if current_id else None
        if expected is None:
            if current_id:
                unresolved.append(current_id)
            continue
        before = tier_values(model.get("supported_reasoning_levels"), "effort")
        if apply_tiers(model, expected, descriptions):
            changes.append(f"{current_id}: {before} -> {expected}")
    return changes, unresolved


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    codex_home = default_codex_home()
    parser.add_argument("--config", default=str(codex_home / "config.toml"))
    parser.add_argument("--backup-dir", default=str(codex_home))
    parser.add_argument(
        "--tier-map",
        default=str(Path(__file__).resolve().parent.parent / "references" / "expected-tier-map.json"),
        help="JSON map of known model ids to expected reasoning tiers",
    )
    parser.add_argument("--check", action="store_true", help="report drift and exit without writing")
    parser.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    args = parser.parse_args()

    tier_map_path = Path(args.tier_map).expanduser()
    tier_map = load_json(tier_map_path)
    expected_map: dict[str, list[str]] = tier_map["models"]
    descriptions: dict[str, str] = tier_map["descriptions"]

    config_path = Path(args.config).expanduser()
    if not config_path.exists():
        print(f"config not found: {config_path}")
        return 2
    config_text = config_path.read_text(encoding="utf-8")

    try:
        config_data = tomllib.loads(config_text)
    except tomllib.TOMLDecodeError as exc:
        print(f"config.toml is not valid TOML: {exc}")
        return 2

    provider = config_data.get("model_providers", {}).get(PROVIDER_KEY)
    if provider is None:
        print(f"provider [{PROVIDER_KEY}] not present in config")
        return 2

    catalog_name = config_data.get("model_catalog_json")
    catalog_path: Path | None = None
    if catalog_name:
        candidate = Path(catalog_name)
        if not candidate.is_absolute():
            candidate = config_path.parent / candidate
        if candidate.exists():
            catalog_path = candidate
        else:
            print(f"warning: model_catalog_json not found: {candidate}")

    config_changes, catalog_changes = [], []
    unresolved_models: set[str] = set()
    new_config_text: str | None = None
    try:
        new_config_text, config_changes, unresolved = repair_config(
            config_text, expected_map, descriptions
        )
        unresolved_models.update(unresolved)
    except RuntimeError as exc:
        print(f"config repair failed: {exc}")
        return 2
    if catalog_path:
        try:
            catalog = load_json(catalog_path)
            catalog_changes, unresolved = repair_catalog(catalog, expected_map, descriptions)
            unresolved_models.update(unresolved)
        except (OSError, json.JSONDecodeError, RuntimeError) as exc:
            print(f"catalog read/repair failed: {exc}")
            return 2

    if unresolved_models:
        print("Unresolved models preserved (no tiers inferred):")
        for unresolved_model in sorted(unresolved_models):
            print(f"  {unresolved_model}")

    if not config_changes and not catalog_changes and catalog_path:
        print("OK: all tiers already match the expected map")
        return 0
    if not config_changes and not catalog_changes:
        print(f"OK: config.toml tiers match; catalog {catalog_path or '(none)'} not checked")
        return 0

    print("Changes needed:")
    for change in config_changes:
        print(f"  config.toml: {change}")
    for change in catalog_changes:
        print(f"  catalog: {change}")

    if args.check or args.dry_run:
        action = "check" if args.check else "dry-run"
        print(f"[{action}] no files modified")
        return 0 if args.check else 1

    backup_dir = Path(args.backup_dir).expanduser()
    config_backup = backup(config_path, backup_dir)
    print(f"backup: {config_backup}")

    catalog_data: Any | None = None
    if catalog_path:
        catalog_data = load_json(catalog_path)
        repair_catalog(catalog_data, expected_map, descriptions)
        catalog_backup = backup(catalog_path, backup_dir)
        print(f"backup: {catalog_backup}")
    config_path.write_text(new_config_text, encoding="utf-8")
    print(f"updated: {config_path}")

    if catalog_path and catalog_data is not None:
        catalog_path.write_text(
            json.dumps(catalog_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"updated: {catalog_path}")

    # Validate the written files can be parsed again.
    tomllib.loads(config_path.read_text(encoding="utf-8"))
    if catalog_path:
        json.loads(catalog_path.read_text(encoding="utf-8"))
    print("validation: config.toml and catalog parse OK")
    print("restart Codex (or start a new session) for the change to take effect")
    return 0


if __name__ == "__main__":
    sys.exit(main())
