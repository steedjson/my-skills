#!/usr/bin/env python3
"""Restore reasoning efforts and the Fast speed tier in Codex CC Switch metadata.

Idempotent: adds missing max/ultra reasoning tiers in their required order and the Fast/priority speed
tier without removing any existing model capability metadata.
"""

import json
import os
import pathlib
import re
import sys

try:
    import tomllib
except ModuleNotFoundError:
    print("Python 3.11+ required (tomllib)", file=sys.stderr)
    sys.exit(1)

CODEX_HOME = pathlib.Path(os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex")))
CATALOG = CODEX_HOME / "cc-switch-model-catalog.json"
CONFIG = CODEX_HOME / "config.toml"

ULTRA_DESC = "Maximum reasoning depth for the hardest problems"
MAX_DESC = "Absolute maximum reasoning depth, no limits"
REQUIRED_EFFORTS = (("max", MAX_DESC), ("ultra", ULTRA_DESC))
FAST_TIER = {
    "id": "priority",
    "name": "Fast",
    "description": "1.5x speed, increased usage",
}

EFFORT_KEYS = (
    "supported_reasoning_levels",
    "supported_reasoning_efforts",
    "supportedReasoningEfforts",
)
EFFORT_FIELD = {
    "supported_reasoning_levels": "effort",
    "supported_reasoning_efforts": "reasoning_effort",
    "supportedReasoningEfforts": "reasoningEffort",
}
SPEED_TIER_KEYS = ("serviceTiers", "service_tiers")
SPEED_LEGACY_KEYS = ("additionalSpeedTiers", "additional_speed_tiers")
FAST_TIER_TOML = (
    'additionalSpeedTiers = ["fast"], '
    'additional_speed_tiers = ["fast"], '
    'serviceTiers = [{ id = "priority", name = "Fast", description = "1.5x speed, increased usage" }], '
    'service_tiers = [{ id = "priority", name = "Fast", description = "1.5x speed, increased usage" }]'
)


def patch_model_metadata(model: dict) -> tuple[bool, bool]:
    """Add missing reasoning and speed capability metadata to one model."""
    effort_changed = False
    speed_changed = False

    for key in EFFORT_KEYS:
        options = model.get(key)
        if not isinstance(options, list):
            continue
        effort_field = EFFORT_FIELD[key]
        existing = {option.get(effort_field) for option in options if isinstance(option, dict)}
        for effort, description in REQUIRED_EFFORTS:
            if effort not in existing:
                options.append({effort_field: effort, "description": description})
                effort_changed = True

        # Max must always appear immediately before the final Ultra option.
        max_options = [
            option
            for option in options
            if isinstance(option, dict) and option.get(effort_field) == "max"
        ]
        ultra_options = [
            option
            for option in options
            if isinstance(option, dict) and option.get(effort_field) == "ultra"
        ]
        ordered_options = [
            option
            for option in options
            if not (
                isinstance(option, dict)
                and option.get(effort_field) in {"max", "ultra"}
            )
        ] + max_options + ultra_options
        if options != ordered_options:
            options[:] = ordered_options
            effort_changed = True

    for key in SPEED_LEGACY_KEYS:
        tiers = model.get(key)
        if not isinstance(tiers, list):
            continue
        if "fast" not in tiers:
            tiers.append("fast")
            speed_changed = True

    for key in SPEED_TIER_KEYS:
        tiers = model.get(key)
        if not isinstance(tiers, list):
            continue
        if not any(isinstance(tier, dict) and tier.get("id") == FAST_TIER["id"] for tier in tiers):
            tiers.append(dict(FAST_TIER))
            speed_changed = True

    return effort_changed, speed_changed


def patch_catalog(path: pathlib.Path) -> tuple[int, int]:
    """Patch all models in the JSON catalog. Returns reasoning/speed model counts."""
    data = json.loads(path.read_text())
    models = data if isinstance(data, list) else data.get("models", [])
    effort_models = 0
    speed_models = 0

    for model in models:
        effort_changed, speed_changed = patch_model_metadata(model)
        effort_models += int(effort_changed)
        speed_models += int(speed_changed)

    if effort_models or speed_models:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return effort_models, speed_models


def patch_config(path: pathlib.Path) -> tuple[int, int, int]:
    """Patch inline provider models in config.toml without rewriting credentials."""
    text = path.read_text()

    old_level = '{ effort = "xhigh", description = "Extra high reasoning depth for complex problems" }]'
    new_level = (
        '{ effort = "xhigh", description = "Extra high reasoning depth for complex problems" }, '
        '{ effort = "max", description = "' + MAX_DESC + '" }, '
        '{ effort = "ultra", description = "' + ULTRA_DESC + '" }]'
    )
    level_count = text.count(old_level)
    text = text.replace(old_level, new_level)

    old_effort = '{ reasoningEffort = "xhigh", description = "Extra high reasoning depth for complex problems" }]'
    new_effort = (
        '{ reasoningEffort = "xhigh", description = "Extra high reasoning depth for complex problems" }, '
        '{ reasoningEffort = "max", description = "' + MAX_DESC + '" }, '
        '{ reasoningEffort = "ultra", description = "' + ULTRA_DESC + '" }]'
    )
    effort_count = text.count(old_effort)
    text = text.replace(old_effort, new_effort)

    old_snake_effort = '{ reasoning_effort = "xhigh", description = "Extra high reasoning depth for complex problems" }]'
    new_snake_effort = (
        '{ reasoning_effort = "xhigh", description = "Extra high reasoning depth for complex problems" }, '
        '{ reasoning_effort = "max", description = "' + MAX_DESC + '" }, '
        '{ reasoning_effort = "ultra", description = "' + ULTRA_DESC + '" }]'
    )
    snake_effort_count = text.count(old_snake_effort)
    text = text.replace(old_snake_effort, new_snake_effort)
    text, reordered_count = normalize_inline_effort_order(text)

    replacements = (
        ('additionalSpeedTiers = []', 'additionalSpeedTiers = ["fast"]'),
        ('additional_speed_tiers = []', 'additional_speed_tiers = ["fast"]'),
        (
            'serviceTiers = []',
            'serviceTiers = [{ id = "priority", name = "Fast", description = "1.5x speed, increased usage" }]',
        ),
        (
            'service_tiers = []',
            'service_tiers = [{ id = "priority", name = "Fast", description = "1.5x speed, increased usage" }]',
        ),
    )
    speed_count = 0
    for old, new in replacements:
        count = text.count(old)
        speed_count += count
        text = text.replace(old, new)

    text, missing_speed_count = add_missing_speed_fields(text)
    speed_count += missing_speed_count

    if level_count or effort_count or snake_effort_count or reordered_count or speed_count:
        path.write_text(text)
    return (
        level_count + effort_count + snake_effort_count + reordered_count,
        speed_count,
        level_count,
    )


def normalize_inline_effort_order(text: str) -> tuple[str, int]:
    """Move a neighbouring Ultra/Max pair into the required Max/Ultra order."""
    reordered = 0
    for field in ("effort", "reasoningEffort", "reasoning_effort"):
        pattern = re.compile(
            rf'(\{{\s*{field}\s*=\s*"ultra"[^}}]*\}})(\s*,\s*)'
            rf'(\{{\s*{field}\s*=\s*"max"[^}}]*\}})'
        )
        text, count = pattern.subn(r"\3\2\1", text)
        reordered += count
    return text, reordered


def add_missing_speed_fields(text: str) -> tuple[str, int]:
    """Add Speed metadata when route models omit the capability fields entirely."""
    lines = text.splitlines(keepends=True)
    for line_index, line in enumerate(lines):
        if not line.startswith("models = ["):
            continue

        updated, count = patch_models_line(line)
        if count:
            lines[line_index] = updated
        return "".join(lines), count

    return text, 0


def patch_models_line(line: str) -> tuple[str, int]:
    """Patch top-level TOML inline tables within the provider's models array."""
    segments: list[str] = []
    cursor = 0
    table_start: int | None = None
    array_depth = 0
    table_depth = 0
    quote: str | None = None
    escaped = False
    patched = 0

    for index, character in enumerate(line):
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue

        if character in ('"', "'"):
            quote = character
            continue
        if character == "[":
            array_depth += 1
            continue
        if character == "]":
            array_depth -= 1
            continue
        if character == "{":
            if array_depth == 1 and table_depth == 0:
                table_start = index
            table_depth += 1
            continue
        if character != "}":
            continue

        table_depth -= 1
        if array_depth != 1 or table_depth != 0 or table_start is None:
            continue

        table = line[table_start : index + 1]
        if not any(key in table for key in (*SPEED_LEGACY_KEYS, *SPEED_TIER_KEYS)):
            segments.append(line[cursor:index])
            segments.append(", " + FAST_TIER_TOML + " }")
            cursor = index + 1
            patched += 1
        table_start = None

    if not patched:
        return line, 0
    segments.append(line[cursor:])
    return "".join(segments), patched


def check_model_line(path: pathlib.Path) -> str | None:
    """Return the top-level model value, if present."""
    for line in path.read_text().splitlines():
        if line.startswith("model = "):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def restore_model_line(path: pathlib.Path, model_name: str) -> bool:
    """Insert model and model_reasoning_effort when the top-level key is absent."""
    text = path.read_text()
    if re.search(r"^model\s*=", text, re.MULTILINE):
        return False

    lines = text.splitlines()
    insert_at = 0
    for index, line in enumerate(lines):
        if line.startswith("notify = "):
            insert_at = index + 1
            break

    lines[insert_at:insert_at] = [
        f'model = "{model_name}"',
        'model_reasoning_effort = "high"',
    ]
    path.write_text("\n".join(lines) + "\n")
    return True


def find_default_model(path: pathlib.Path) -> str:
    """Find the catalog default model, falling back to the first one."""
    data = json.loads(path.read_text())
    models = data if isinstance(data, list) else data.get("models", [])
    for model in models:
        if model.get("isDefault"):
            return model.get("model") or model.get("id", "")
    for model in models:
        return model.get("model") or model.get("id", "")
    return "gpt-5.6-sol"


def main() -> int:
    if not CATALOG.exists():
        print(f"catalog not found: {CATALOG}", file=sys.stderr)
        return 1
    if not CONFIG.exists():
        print(f"config not found: {CONFIG}", file=sys.stderr)
        return 1

    catalog_efforts, catalog_speed = patch_catalog(CATALOG)
    print(
        "catalog: "
        f"{catalog_efforts} model(s) reasoning patched, "
        f"{catalog_speed} model(s) Fast speed patched"
    )

    config_efforts, config_speed, config_levels = patch_config(CONFIG)
    print(
        "config.toml: "
        f"{config_efforts} reasoning arrays and "
        f"{config_speed} Fast speed fields patched"
    )

    model_name = check_model_line(CONFIG)
    if model_name:
        print(f"model line present: {model_name}")
    else:
        default = find_default_model(CATALOG)
        if restore_model_line(CONFIG, default):
            print(f"model line restored: {default}")

    try:
        tomllib.loads(CONFIG.read_text())
        print("config.toml: valid TOML")
    except Exception as error:
        print(f"config.toml: TOML validation FAILED: {error}", file=sys.stderr)
        return 1

    if not (catalog_efforts or catalog_speed or config_efforts or config_speed):
        print("no changes needed: reasoning tiers and Fast speed are already present")
    else:
        print("done: fully quit and reopen Codex to load the restored options")

    return 0


if __name__ == "__main__":
    sys.exit(main())
