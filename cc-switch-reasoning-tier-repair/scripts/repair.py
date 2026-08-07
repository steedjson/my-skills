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
import plistlib
import re
import shutil
import sqlite3
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Any


MODELS_ASSIGNMENT = re.compile(r"\bmodels\s*=\s*\[")
TOP_LEVEL_EFFORT = re.compile(
    r'(?m)^model_reasoning_effort\s*=\s*"([^"]+)"\s*$'
)
MODEL_ASSIGNMENT = re.compile(r'(?m)^model\s*=\s*"([^"]+)"\s*$')
EFFORT_ASSIGNMENT = re.compile(r'model_reasoning_effort\s*=\s*"([^"]+)"')
RUNTIME_REASONING_EFFORTS = re.compile(
    r'reasoningEfforts\s*=\s*\(\)\s*=>\s*\[\s*'
    r'(?P<values>"[^"]+"(?:\s*,\s*"[^"]+")*)\s*\]'
)
DEFAULT_CCSWITCH_APP = Path("/Applications/CCSwitchMulti.app")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ccswitch_runtime_diagnostics(
    app_path: Path = DEFAULT_CCSWITCH_APP,
) -> dict[str, Any]:
    """Inspect bundled picker support without launching or modifying CCSwitchMulti."""
    app_path = app_path.expanduser()
    binary_path = app_path / "Contents" / "MacOS" / "cc-switch"
    info_path = app_path / "Contents" / "Info.plist"
    diagnostics: dict[str, Any] = {
        "app_path": str(app_path),
        "binary_path": str(binary_path),
        "version": None,
        "picker_efforts": None,
        "supports_max": None,
        "evidence": None,
    }
    if info_path.exists():
        try:
            with info_path.open("rb") as handle:
                info = plistlib.load(handle)
            version = info.get("CFBundleShortVersionString") or info.get("CFBundleVersion")
            if isinstance(version, str):
                diagnostics["version"] = version
        except (OSError, plistlib.InvalidFileException, ValueError):
            pass
    if not binary_path.is_file():
        return diagnostics
    try:
        binary_text = binary_path.read_bytes().decode("utf-8", errors="ignore")
    except OSError:
        return diagnostics
    match = RUNTIME_REASONING_EFFORTS.search(binary_text)
    if match is None:
        return diagnostics
    values = re.findall(r'"([^"]+)"', match.group("values"))
    diagnostics["picker_efforts"] = values
    diagnostics["supports_max"] = "max" in values
    diagnostics["evidence"] = "embedded reasoningEfforts picker"
    return diagnostics


def runtime_effort_warning(
    diagnostics: dict[str, Any],
    requested_effort: str | None,
) -> str | None:
    """Explain when the installed runtime cannot preserve the requested effort."""
    if requested_effort != "max":
        return None
    picker_efforts = diagnostics.get("picker_efforts")
    if not isinstance(picker_efforts, list) or diagnostics.get("supports_max") is not False:
        return None
    version = diagnostics.get("version")
    version_label = f" {version}" if isinstance(version, str) else ""
    efforts = ", ".join(str(value) for value in picker_efforts)
    return (
        f"CCSwitchMulti{version_label} runtime picker only embeds [{efforts}]; "
        "it has no max handler. Config/catalog may stay at max, but this build can "
        "normalize the selected effort to xhigh before outbound conversion. "
        "This is a runtime compatibility blocker, not a catalog drift; do not map max to xhigh."
    )


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


def model_identifiers(model: dict[str, Any]) -> list[str]:
    identifiers: list[str] = []
    for field in ("model", "id", "slug", "upstreamModel", "upstream_model"):
        value = model.get(field)
        if isinstance(value, str) and value and value not in identifiers:
            identifiers.append(value)
    return identifiers


def model_id(model: dict[str, Any]) -> str | None:
    identifiers = model_identifiers(model)
    return identifiers[0] if identifiers else None


def resolve_model_key(
    value: str | None,
    expected_map: dict[str, list[str]],
    aliases: dict[str, str] | None = None,
) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if value in expected_map:
        return value
    aliases = aliases or {}
    canonical = aliases.get(value)
    return canonical if canonical in expected_map else None


def known_model_key(
    model: dict[str, Any],
    expected_map: dict[str, list[str]],
    aliases: dict[str, str] | None = None,
) -> str | None:
    for identifier in model_identifiers(model):
        resolved = resolve_model_key(identifier, expected_map, aliases)
        if resolved is not None:
            return resolved
    return None


def extract_configured_model(text: str) -> str | None:
    match = MODEL_ASSIGNMENT.search(text)
    return match.group(1) if match else None


def tier_values(entries: Any, key: str) -> list[str]:
    if not isinstance(entries, list):
        return []
    return [entry.get(key) for entry in entries if isinstance(entry, dict)]


def apply_tiers(
    model: dict[str, Any],
    expected: list[str],
    descriptions: dict[str, str],
    default_effort: str | None = None,
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
    if default_effort is not None:
        for field in (
            "default_reasoning_effort",
            "default_reasoning_level",
            "defaultReasoningEffort",
            "defaultReasoningLevel",
        ):
            if field not in model or model[field] == default_effort:
                continue
            model[field] = default_effort
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


def provider_keys_with_known_models(
    config_data: dict[str, Any],
    expected_map: dict[str, list[str]],
    aliases: dict[str, str] | None = None,
) -> list[str]:
    matches: list[str] = []
    providers = config_data.get("model_providers", {})
    if not isinstance(providers, dict):
        return matches
    for provider_key, provider in providers.items():
        if not isinstance(provider, dict):
            continue
        models = provider.get("models")
        if not isinstance(models, list):
            continue
        if any(
            isinstance(model, dict) and known_model_key(model, expected_map, aliases) is not None
            for model in models
        ):
            matches.append(provider_key)
    return matches


def set_top_level_effort(config_text: str, effort: str | None) -> tuple[str, str | None]:
    if effort is None:
        return config_text, None
    match = TOP_LEVEL_EFFORT.search(config_text)
    if match:
        before = match.group(1)
        if before == effort:
            return config_text, None
        replacement = f'model_reasoning_effort = "{effort}"'
        return (
            config_text[: match.start()] + replacement + config_text[match.end() :],
            f"model_reasoning_effort: {before} -> {effort}",
        )
    return (
        f'model_reasoning_effort = "{effort}"\n' + config_text,
        f"model_reasoning_effort: (missing) -> {effort}",
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
    effort: str | None = None,
    aliases: dict[str, str] | None = None,
) -> tuple[str, list[str], list[str]]:
    config_data = tomllib.loads(config_text)
    provider_keys = provider_keys_with_known_models(config_data, expected_map, aliases)
    if not provider_keys:
        raise RuntimeError("no provider with known inline models found")

    changes: list[str] = []
    unresolved: list[str] = []
    repaired_text = config_text

    for provider_key in provider_keys:
        provider_parts = find_provider_models(repaired_text, provider_key)
        if provider_parts is None:
            raise RuntimeError(f"provider [{provider_key}] models assignment not found")
        prefix, models_expr, suffix = provider_parts
        models = extract_inline_models(models_expr)

        for model in models:
            current_id = model_id(model)
            canonical_id = known_model_key(model, expected_map, aliases)
            expected = expected_map.get(canonical_id) if canonical_id else None
            if expected is None:
                if current_id:
                    unresolved.append(current_id)
                continue
            before = tier_values(model.get("supported_reasoning_levels"), "effort")
            before_defaults = {
                field: model.get(field)
                for field in (
                    "default_reasoning_effort",
                    "default_reasoning_level",
                    "defaultReasoningEffort",
                    "defaultReasoningLevel",
                )
                if field in model
            }
            if apply_tiers(model, expected, descriptions, effort):
                after = tier_values(model.get("supported_reasoning_levels"), "effort")
                detail: list[str] = []
                if before != after:
                    detail.append(f"tiers {before} -> {after}")
                default_changes = [
                    f"{field} {before_defaults[field]} -> {model[field]}"
                    for field in before_defaults
                    if before_defaults[field] != model.get(field)
                ]
                if default_changes:
                    detail.append("defaults " + ", ".join(default_changes))
                changes.append(
                    f"{provider_key}/{current_id}: " + "; ".join(detail)
                )

        repaired_text = prefix + serialize_models(models) + suffix

    repaired_text, effort_change = set_top_level_effort(repaired_text, effort)
    if effort_change:
        changes.insert(0, effort_change)
    return repaired_text, changes, unresolved


def repair_catalog(
    catalog: dict[str, Any],
    expected_map: dict[str, list[str]],
    descriptions: dict[str, str],
    effort: str | None = None,
    aliases: dict[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    models = catalog.get("models") if isinstance(catalog, dict) else catalog
    if not isinstance(models, list):
        raise RuntimeError("model catalog does not contain a models array")
    changes: list[str] = []
    unresolved: list[str] = []
    for model in models:
        current_id = model_id(model)
        canonical_id = known_model_key(model, expected_map, aliases)
        expected = expected_map.get(canonical_id) if canonical_id else None
        if expected is None:
            if current_id:
                unresolved.append(current_id)
            continue
        before = tier_values(model.get("supported_reasoning_levels"), "effort")
        before_defaults = {
            field: model.get(field)
            for field in (
                "default_reasoning_effort",
                "default_reasoning_level",
                "defaultReasoningEffort",
                "defaultReasoningLevel",
            )
            if field in model
        }
        if apply_tiers(model, expected, descriptions, effort):
            after = tier_values(model.get("supported_reasoning_levels"), "effort")
            detail: list[str] = []
            if before != after:
                detail.append(f"tiers {before} -> {after}")
            default_changes = [
                f"{field} {before_defaults[field]} -> {model[field]}"
                for field in before_defaults
                if before_defaults[field] != model.get(field)
            ]
            if default_changes:
                detail.append("defaults " + ", ".join(default_changes))
            changes.append(f"{current_id}: " + "; ".join(detail))
    return changes, unresolved


def extract_configured_effort(text: str) -> str | None:
    match = EFFORT_ASSIGNMENT.search(text)
    return match.group(1) if match else None


def replace_configured_effort(text: str, effort: str) -> tuple[str, int]:
    updated, count = EFFORT_ASSIGNMENT.subn(
        f'model_reasoning_effort = "{effort}"', text
    )
    return updated, count


def json_config_effort(text: str) -> str | None:
    """Read model_reasoning_effort from a JSON object's config string."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    config = data.get("config") if isinstance(data, dict) else None
    if not isinstance(config, str):
        return None
    return extract_configured_effort(config)


def replace_json_config_effort(
    text: str,
    effort: str,
) -> tuple[str, int]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text, 0
    config = data.get("config") if isinstance(data, dict) else None
    if not isinstance(config, str):
        return text, 0
    updated, count = replace_configured_effort(config, effort)
    if count == 0:
        return text, 0
    data["config"] = updated
    return json.dumps(data, ensure_ascii=False), count


def database_drift(
    db_path: Path,
    effort: str,
) -> list[str]:
    """Return cc-switch database rows whose configured effort differs."""
    if not db_path.exists():
        return []
    changes: list[str] = []
    conn = sqlite3.connect(f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True)
    try:
        for provider_id, name, settings_config in conn.execute(
            "SELECT id, name, settings_config FROM providers WHERE app_type='codex'"
        ):
            current = json_config_effort(settings_config)
            if current is not None and current != effort:
                changes.append(
                    f"provider {name} ({provider_id}): model_reasoning_effort {current} -> {effort}"
                )
        for key, value in conn.execute(
            "SELECT key, value FROM settings WHERE value LIKE '%model_reasoning_effort%'"
        ):
            current = extract_configured_effort(value)
            if current is not None and current != effort:
                changes.append(
                    f"settings {key}: model_reasoning_effort {current} -> {effort}"
                )
        for app_type, original_config in conn.execute(
            "SELECT app_type, original_config FROM proxy_live_backup "
            "WHERE original_config LIKE '%model_reasoning_effort%'"
        ):
            current = json_config_effort(original_config)
            if current is not None and current != effort:
                changes.append(
                    f"live backup {app_type}: model_reasoning_effort {current} -> {effort}"
                )
    finally:
        conn.close()
    return changes


def backup_database(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"{db_path.name}.before-reasoning-tier-repair-{stamp}"
    source = sqlite3.connect(db_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def repair_database(
    db_path: Path,
    effort: str,
    backup_dir: Path,
) -> tuple[list[str], Path | None]:
    changes = database_drift(db_path, effort)
    if not changes:
        return [], None

    backup_path = backup_database(db_path, backup_dir)
    conn = sqlite3.connect(db_path)
    try:
        for provider_id, settings_config in conn.execute(
            "SELECT id, settings_config FROM providers WHERE app_type='codex'"
        ):
            current = json_config_effort(settings_config)
            if current is not None and current != effort:
                updated, _ = replace_json_config_effort(settings_config, effort)
                conn.execute(
                    "UPDATE providers SET settings_config=? "
                    "WHERE id=? AND app_type='codex'",
                    (updated, provider_id),
                )
        for key, value in conn.execute(
            "SELECT key, value FROM settings WHERE value LIKE '%model_reasoning_effort%'"
        ):
            current = extract_configured_effort(value)
            if current is not None and current != effort:
                updated, _ = replace_configured_effort(value, effort)
                conn.execute("UPDATE settings SET value=? WHERE key=?", (updated, key))
        for app_type, original_config in conn.execute(
            "SELECT app_type, original_config FROM proxy_live_backup "
            "WHERE original_config LIKE '%model_reasoning_effort%'"
        ):
            current = json_config_effort(original_config)
            if current is not None and current != effort:
                updated, _ = replace_json_config_effort(original_config, effort)
                conn.execute(
                    "UPDATE proxy_live_backup SET original_config=? WHERE app_type=?",
                    (updated, app_type),
                )
        conn.commit()
    finally:
        conn.close()
    return changes, backup_path


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
    parser.add_argument(
        "--effort",
        help="also set top-level model_reasoning_effort, for example max",
    )
    parser.add_argument(
        "--db",
        default=str(Path.home() / ".cc-switch" / "cc-switch.db"),
        help="cc-switch database to check and repair",
    )
    parser.add_argument(
        "--ccswitch-app",
        default=str(DEFAULT_CCSWITCH_APP),
        help="CCSwitchMulti.app bundle used for read-only runtime compatibility checks",
    )
    parser.add_argument(
        "--skip-runtime-check",
        action="store_true",
        help="skip the read-only CCSwitchMulti binary compatibility check",
    )
    parser.add_argument("--check", action="store_true", help="report drift and exit without writing")
    parser.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    args = parser.parse_args()

    tier_map_path = Path(args.tier_map).expanduser()
    tier_map = load_json(tier_map_path)
    expected_map: dict[str, list[str]] = tier_map["models"]
    descriptions: dict[str, str] = tier_map["descriptions"]
    aliases: dict[str, str] = tier_map.get("aliases", {})
    if args.effort is not None and args.effort not in descriptions:
        print(f"unknown reasoning effort: {args.effort}")
        return 2

    runtime_warning: str | None = None
    if not args.skip_runtime_check:
        runtime_warning = runtime_effort_warning(
            ccswitch_runtime_diagnostics(Path(args.ccswitch_app).expanduser()),
            args.effort,
        )
        if runtime_warning:
            print(f"runtime blocker: {runtime_warning}")

    db_path = Path(args.db).expanduser()
    db_changes: list[str] = []
    if args.effort is None:
        print("note: --effort is required to check/repair cc-switch database")
    elif db_path.exists():
        db_changes = database_drift(db_path, args.effort)
    else:
        print(f"warning: cc-switch database not found: {db_path}")

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

    catalog_name = config_data.get("model_catalog_json")
    catalog_paths: list[Path] = []
    if catalog_name:
        candidate = Path(catalog_name)
        if not candidate.is_absolute():
            candidate = config_path.parent / candidate
        if candidate.exists():
            catalog_paths.append(candidate)
        else:
            print(f"warning: model_catalog_json not found: {candidate}")
    models_cache_path = config_path.parent / "models_cache.json"
    if models_cache_path.exists() and models_cache_path not in catalog_paths:
        catalog_paths.append(models_cache_path)

    config_changes: list[str] = []
    catalog_changes: dict[Path, list[str]] = {}
    catalog_data: dict[Path, Any] = {}
    unresolved_models: set[str] = set()
    new_config_text: str | None = None
    try:
        new_config_text, config_changes, unresolved = repair_config(
            config_text,
            expected_map,
            descriptions,
            args.effort,
            aliases,
        )
        unresolved_models.update(unresolved)
    except RuntimeError as exc:
        print(f"config repair failed: {exc}")
        return 2
    for catalog_path in catalog_paths:
        try:
            catalog = load_json(catalog_path)
            changes, unresolved = repair_catalog(
                catalog,
                expected_map,
                descriptions,
                args.effort,
                aliases,
            )
            catalog_changes[catalog_path] = changes
            catalog_data[catalog_path] = catalog
            unresolved_models.update(unresolved)
        except (OSError, json.JSONDecodeError, RuntimeError) as exc:
            print(f"catalog read/repair failed ({catalog_path}): {exc}")
            return 2

    if unresolved_models:
        print("Unresolved models preserved (no tiers inferred):")
        for unresolved_model in sorted(unresolved_models):
            print(f"  {unresolved_model}")

    has_catalog_changes = any(catalog_changes.values())
    if not config_changes and not has_catalog_changes and not db_changes and catalog_paths:
        if runtime_warning:
            print("CONFIG OK: stored effort and tiers match, but runtime cannot preserve max")
            return 1
        print("OK: active effort and all checked tiers match the expected map")
        return 0
    if not config_changes and not has_catalog_changes and not db_changes:
        if runtime_warning:
            print("CONFIG OK: stored effort and tiers match, but runtime cannot preserve max")
            return 1
        print("OK: config.toml effort and tiers match; no catalog checked")
        return 0

    print("Changes needed:")
    for change in config_changes:
        print(f"  config.toml: {change}")
    for catalog_path, changes in catalog_changes.items():
        for change in changes:
            print(f"  {catalog_path.name}: {change}")
    for change in db_changes:
        print(f"  cc-switch.db: {change}")

    if args.check or args.dry_run:
        action = "check" if args.check else "dry-run"
        print(f"[{action}] no files modified")
        return 1 if args.dry_run or runtime_warning else 0

    backup_dir = Path(args.backup_dir).expanduser()
    config_backup = backup(config_path, backup_dir)
    print(f"backup: {config_backup}")
    db_backup: Path | None = None
    if db_changes:
        db_backup = repair_database(
            db_path,
            args.effort,
            backup_dir,
        )[1]
        print(f"backup: {db_backup}")

    for catalog_path, changes in catalog_changes.items():
        if not changes:
            continue
        catalog_backup = backup(catalog_path, backup_dir)
        print(f"backup: {catalog_backup}")
    config_path.write_text(new_config_text, encoding="utf-8")
    print(f"updated: {config_path}")

    for catalog_path, changes in catalog_changes.items():
        if not changes:
            continue
        catalog_path.write_text(
            json.dumps(catalog_data[catalog_path], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"updated: {catalog_path}")

    # Validate the written files can be parsed again.
    tomllib.loads(config_path.read_text(encoding="utf-8"))
    for catalog_path in catalog_paths:
        json.loads(catalog_path.read_text(encoding="utf-8"))
    if db_changes and database_drift(db_path, args.effort):
        print("validation failed: cc-switch database still has drift")
        return 1
    print("validation: config.toml, checked catalogs, and cc-switch database parse OK")
    if runtime_warning:
        print("validation: stored max is intact; runtime blocker remains")
        return 1
    print("restart Codex (or start a new session) for the change to take effect")
    return 0


if __name__ == "__main__":
    sys.exit(main())
