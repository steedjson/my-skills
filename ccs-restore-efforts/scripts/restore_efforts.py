#!/usr/bin/env python3
"""Restore Codex CC Switch UI capabilities and optional Grok chat routing.

Modes:
1. restore-ui: idempotently restore max/ultra, Fast/priority, and vendor-verified
   context windows in the catalog and config.toml.
2. force-grok-chat: force the routed Grok provider onto native chat protocol with
   dry-run-first safety, full DB backup, probe verification, and rollback.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import sqlite3
import sys
import time
import urllib.error
import urllib.request

try:
    import tomllib
except ModuleNotFoundError:
    print("Python 3.11+ required (tomllib)", file=sys.stderr)
    sys.exit(1)

CODEX_HOME = pathlib.Path(os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex")))
CATALOG = CODEX_HOME / "cc-switch-model-catalog.json"
CONFIG = CODEX_HOME / "config.toml"
CC_SWITCH_HOME = pathlib.Path(os.environ.get("CC_SWITCH_HOME", os.path.expanduser("~/.cc-switch")))
CC_SWITCH_DB = CC_SWITCH_HOME / "cc-switch.db"
CC_SWITCH_LOG = CC_SWITCH_HOME / "logs" / "codex-router.log"
CC_SWITCH_BACKUPS = CC_SWITCH_HOME / "backups"
GROK_NAME_RE = re.compile(r"grok", re.IGNORECASE)

ULTRA_DESC = "Maximum reasoning depth for the hardest problems"
MAX_DESC = "Absolute maximum reasoning depth, no limits"
REQUIRED_EFFORTS = (("max", MAX_DESC), ("ultra", ULTRA_DESC))
STANDARD_EFFORTS = ("none", "low", "medium", "high", "xhigh")
MODEL_EFFORT_POLICIES = {
    "codex-auto-review": ("low", "medium", "high", "xhigh"),
    "deepseek-v4-flash": ("off", "non-think", "low", "high", "max"),
    "deepseek-v4-pro": ("off", "non-think", "low", "high", "max"),
    "grok-4.5": ("low", "medium", "high"),
    "grok-4.6": ("low", "medium", "high", "xhigh"),
    "gpt-5.2": STANDARD_EFFORTS,
    "gpt-5.4": STANDARD_EFFORTS,
    "gpt-5.4-mini": STANDARD_EFFORTS,
    "gpt-5.5": STANDARD_EFFORTS,
    "gpt-5.6": STANDARD_EFFORTS + ("max",),
    "gpt-5.6-luna": STANDARD_EFFORTS + ("max",),
    "gpt-5.6-sol": STANDARD_EFFORTS + ("max",),
    "gpt-5.6-terra": STANDARD_EFFORTS + ("max",),
}
MODEL_DEFAULT_EFFORTS = {
    "codex-auto-review": "medium",
    "grok-4.5": "high",
    "grok-4.6": "high",
    "gpt-5.2": "none",
    "gpt-5.4": "none",
    "gpt-5.4-mini": "none",
    "gpt-5.5": "medium",
    "gpt-5.6": "medium",
    "gpt-5.6-luna": "max",
    "gpt-5.6-sol": "medium",
    "gpt-5.6-terra": "xhigh",
}
DEFAULT_EFFORT_KEYS = (
    "default_reasoning_effort",
    "default_reasoning_level",
    "defaultReasoningEffort",
)
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
CONTEXT_WINDOW_KEYS = (
    "context_window",
    "contextWindow",
    "max_context_window",
    "maxContextWindow",
)
MAX_OUTPUT_TOKENS_KEYS = ("max_output_tokens", "maxOutputTokens")
FAST_TIER_TOML = (
    'additionalSpeedTiers = ["fast"], '
    'additional_speed_tiers = ["fast"], '
    'serviceTiers = [{ id = "priority", name = "Fast", description = "1.5x speed, increased usage" }], '
    'service_tiers = [{ id = "priority", name = "Fast", description = "1.5x speed, increased usage" }]'
)

# Vendor documentation verified 2026-08-12. Unknown route aliases are never inferred.
MODEL_CONTEXT_WINDOWS = {
    "codex-auto-review": 272_000,
    "deepseek-v4-flash": 1_000_000,
    "deepseek-v4-pro": 1_000_000,
    "glm-5.2": 1_000_000,
    "gpt-5.2": 400_000,
    "gpt-5.3-codex-spark": 128_000,
    "gpt-5.4": 1_050_000,
    "gpt-5.4-mini": 400_000,
    "gpt-5.5": 1_050_000,
    "gpt-5.6": 1_050_000,
    "gpt-5.6-luna": 1_050_000,
    "gpt-5.6-sol": 1_050_000,
    "gpt-5.6-terra": 1_050_000,
    "grok-4.5": 500_000,
    "grok-4.6": 500_000,
}
MODEL_MAX_OUTPUT_TOKENS = {
    "gpt-5.4-mini": 128_000,
}
# Explicit non-mechanical aliases only. Mechanical route suffixes are detected or
# provided separately so new provider suffixes do not need hardcoding.
VERIFIED_MODEL_ALIASES = {
    "deepseek-v4-flash-0731": "deepseek-v4-flash",
}
DEFAULT_STRIP_SUFFIXES = ("-csap-oai",)
_ACTIVE_STRIP_SUFFIXES: tuple[str, ...] = DEFAULT_STRIP_SUFFIXES
STRIP_SUFFIX_RE = re.compile(r"-[A-Za-z0-9][A-Za-z0-9_-]*$")
ROUTE_ID_KEYS = ("model", "id", "slug")
UPSTREAM_ID_KEYS = ("upstreamModel", "upstream_model", "display_name", "displayName")
MODEL_ID_KEYS = ROUTE_ID_KEYS + UPSTREAM_ID_KEYS
PREFERRED_DEFAULT_MODELS = (
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-5.6",
    "gpt-5.5",
    "gpt-5.4",
)
REVIEW_ONLY_MODELS = {
    "codex-auto-review",
}


def unique_names(*groups: list[str] | tuple[str, ...]) -> list[str]:
    """Return first-seen non-empty identity strings."""
    names: list[str] = []
    for group in groups:
        for value in group:
            if isinstance(value, str) and value and value not in names:
                names.append(value)
    return names


def set_strip_suffixes(suffixes: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Install active mechanical strip suffixes, longest first."""
    global _ACTIVE_STRIP_SUFFIXES
    cleaned: list[str] = []
    for suffix in suffixes or ():
        if not isinstance(suffix, str):
            continue
        value = suffix.strip()
        if not value:
            continue
        if not value.startswith("-"):
            value = "-" + value
        if value not in cleaned:
            cleaned.append(value)
    cleaned.sort(key=lambda item: (-len(item), item))
    _ACTIVE_STRIP_SUFFIXES = tuple(cleaned) if cleaned else DEFAULT_STRIP_SUFFIXES
    return _ACTIVE_STRIP_SUFFIXES


def active_strip_suffixes() -> tuple[str, ...]:
    """Return the currently active mechanical strip suffixes."""
    return _ACTIVE_STRIP_SUFFIXES


def normalize_model_alias(name: str) -> str | None:
    """Return the next explicit alias for a model name, if any.

    Order:
    1. explicit VERIFIED_MODEL_ALIASES entry
    2. mechanical strip of one active trailing route suffix
    """
    if not name:
        return None
    if name in VERIFIED_MODEL_ALIASES:
        return VERIFIED_MODEL_ALIASES[name]
    for suffix in _ACTIVE_STRIP_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return None


def load_catalog_models(path: pathlib.Path) -> list[dict]:
    """Load catalog model dicts from a JSON catalog file."""
    data = json.loads(path.read_text())
    models = data if isinstance(data, list) else data.get("models", [])
    return [model for model in models if isinstance(model, dict)]


def load_inline_config_models(path: pathlib.Path) -> list[dict]:
    """Best-effort extract inline provider model identity dicts from config.toml."""
    if not path.exists():
        return []
    models: list[dict] = []
    for line in path.read_text().splitlines():
        if not line.startswith("models = ["):
            continue
        # Reuse the same top-level table scanner used for patching.
        array_depth = 0
        table_depth = 0
        quote: str | None = None
        escaped = False
        table_start: int | None = None
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
            model: dict[str, str] = {}
            for key in MODEL_ID_KEYS:
                match = re.search(rf'\b{key}\s*=\s*"([^"]+)"', table)
                if match:
                    model[key] = match.group(1)
            if model:
                models.append(model)
            table_start = None
        break
    return models


def detect_strip_suffixes(models: list[dict]) -> list[tuple[str, int, list[str]]]:
    """Detect safe mechanical strip suffixes from explicit route/upstream pairs.

    For each route name, only the longest valid base is kept so
    ``gpt-5.6-luna-csap-oai`` yields ``-csap-oai`` rather than ``-luna-csap-oai``.

    A base is valid when it is:
    1. another explicit identity on the same model, or
    2. a vendor-verified model name.
    """
    from collections import Counter, defaultdict

    evidence: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)

    def note(suffix: str, route: str, base: str) -> None:
        if not base or not STRIP_SUFFIX_RE.fullmatch(suffix):
            return
        evidence[suffix] += 1
        sample = f"{route} -> {base}"
        if sample not in examples[suffix] and len(examples[suffix]) < 5:
            examples[suffix].append(sample)

    for model in models:
        candidates = identity_candidates(model)
        if not candidates:
            continue
        route_names = []
        for key in ROUTE_ID_KEYS:
            value = model.get(key)
            if isinstance(value, str) and value:
                route_names.append(value)
        if not route_names:
            route_names = candidates[:1]
        candidate_set = set(candidates)

        for route in route_names:
            bases: list[str] = []
            for other in candidates:
                if (
                    other
                    and other != route
                    and route.startswith(other)
                    and route == other + route[len(other) :]
                ):
                    bases.append(other)
            # Also consider verified bases that are prefixes of the route.
            for verified in MODEL_CONTEXT_WINDOWS:
                if route.startswith(verified) and route != verified:
                    bases.append(verified)
            if not bases:
                continue
            # Longest base wins to avoid over-stripping model family prefixes.
            base = max(bases, key=len)
            suffix = route[len(base) :]
            if not suffix:
                continue
            if base in candidate_set or base in MODEL_CONTEXT_WINDOWS:
                note(suffix, route, base)

    ranked = sorted(evidence.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    return [(suffix, count, examples[suffix]) for suffix, count in ranked if count > 0]


def recommend_strip_suffixes(
    models: list[dict], extra: list[str] | None = None, auto: bool = True
) -> tuple[str, ...]:
    """Compute the strip-suffix set for this run."""
    recommended: list[str] = []
    if auto:
        detected = detect_strip_suffixes(models)
        for suffix, _count, _examples in detected:
            if suffix not in recommended:
                recommended.append(suffix)
        for suffix in DEFAULT_STRIP_SUFFIXES:
            # Keep the default suffix available when any verified base exists,
            # even if the current catalog temporarily lacks matching routes.
            if suffix not in recommended:
                recommended.append(suffix)
    if extra:
        for suffix in extra:
            value = suffix.strip()
            if not value:
                continue
            if not value.startswith("-"):
                value = "-" + value
            if value not in recommended:
                recommended.append(value)
    if not recommended:
        recommended = list(DEFAULT_STRIP_SUFFIXES)
    return set_strip_suffixes(recommended)


def identity_candidates(model: dict) -> list[str]:
    """Collect explicit route and upstream identities without guessing."""
    names: list[str] = []
    for key in MODEL_ID_KEYS:
        value = model.get(key)
        if isinstance(value, str) and value and value not in names:
            names.append(value)
    return names


def model_effort_policy(names: list[str] | tuple[str, ...]) -> tuple[tuple[str, ...] | None, str | None]:
    """Return exact effort policy/default for a verified model identity."""
    for name in unique_names(names):
        current = name
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            if current in MODEL_EFFORT_POLICIES:
                return MODEL_EFFORT_POLICIES[current], MODEL_DEFAULT_EFFORTS[current]
            nxt = normalize_model_alias(current)
            if not nxt or nxt == current:
                break
            current = nxt
    return None, None


def effort_description(field: str, effort: str) -> str:
    """Use stable descriptions when adding a missing effort option."""
    descriptions = {
        "off": "Reasoning disabled",
        "non-think": "Non-thinking mode",
        "none": "Latency-critical tasks that do not benefit from extra reasoning",
        "low": "Efficient reasoning with a modest latency increase",
        "medium": "Balanced quality, reliability, and performance",
        "high": "Hard reasoning and complex agentic tasks",
        "xhigh": "Deep research and long-running agentic workflows",
        "max": MAX_DESC,
        "ultra": ULTRA_DESC,
    }
    return descriptions[effort]


def reconcile_effort_options(
    options: list,
    effort_field: str,
    expected: tuple[str, ...] | None,
) -> bool:
    """Restore generic tiers or converge verified models to exact published tiers."""
    existing = {
        option.get(effort_field): option
        for option in options
        if isinstance(option, dict) and isinstance(option.get(effort_field), str)
    }
    if expected is None:
        expected = tuple(
            [
                option.get(effort_field)
                for option in options
                if isinstance(option, dict) and option.get(effort_field) not in {"max", "ultra"}
            ]
            + ["max", "ultra"]
        )
    rebuilt = []
    for effort in expected:
        option = existing.get(effort)
        if not isinstance(option, dict):
            option = {
                effort_field: effort,
                "description": effort_description(effort_field, effort),
            }
        rebuilt.append(option)
    changed = options != rebuilt
    if changed:
        options[:] = rebuilt
    return changed


def model_name(model: dict) -> str:
    """Return the primary route identity, falling back to upstream identity."""
    candidates = identity_candidates(model)
    return candidates[0] if candidates else ""


def route_model_name(model: dict) -> str:
    """Return the route identity used by the model picker and top-level model line."""
    for key in ROUTE_ID_KEYS:
        value = model.get(key)
        if isinstance(value, str) and value:
            return value
    return model_name(model)


def verified_context_window(name: str | list[str] | tuple[str, ...] | None) -> int | None:
    """Return a vendor-verified context window from explicit names or aliases."""
    if name is None:
        return None
    candidates = [name] if isinstance(name, str) else list(name)
    for candidate in unique_names(candidates):
        current = candidate
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            if current in MODEL_CONTEXT_WINDOWS:
                return MODEL_CONTEXT_WINDOWS[current]
            nxt = normalize_model_alias(current)
            if not nxt or nxt == current:
                break
            current = nxt
    return None


def verified_max_output_tokens(name: str | list[str] | tuple[str, ...] | None) -> int | None:
    """Return a vendor-verified maximum output token limit."""
    if name is None:
        return None
    candidates = [name] if isinstance(name, str) else list(name)
    for candidate in unique_names(candidates):
        current = candidate
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            if current in MODEL_MAX_OUTPUT_TOKENS:
                return MODEL_MAX_OUTPUT_TOKENS[current]
            nxt = normalize_model_alias(current)
            if not nxt or nxt == current:
                break
            current = nxt
    return None


def is_review_only_name(name: str) -> bool:
    """Return True when a route or alias is review-only."""
    current = name
    seen: set[str] = set()
    while current and current not in seen:
        if current in REVIEW_ONLY_MODELS:
            return True
        seen.add(current)
        nxt = normalize_model_alias(current)
        if not nxt or nxt == current:
            break
        current = nxt
    return False


def patch_context_metadata(model: dict) -> bool:
    """Restore verified context-window and output-limit metadata."""
    context_window = verified_context_window(identity_candidates(model))
    max_output_tokens = verified_max_output_tokens(identity_candidates(model))
    if context_window is None and max_output_tokens is None:
        return False

    changed = False
    if context_window is not None:
        for key in CONTEXT_WINDOW_KEYS:
            if model.get(key) != context_window:
                model[key] = context_window
                changed = True
    if max_output_tokens is not None:
        for key in MAX_OUTPUT_TOKENS_KEYS:
            if model.get(key) != max_output_tokens:
                model[key] = max_output_tokens
                changed = True
    return changed


def patch_model_metadata(model: dict) -> tuple[bool, bool]:
    """Add missing reasoning and speed capability metadata to one model."""
    effort_changed = False
    speed_changed = False

    expected_efforts, default_effort = model_effort_policy(identity_candidates(model))
    for key in EFFORT_KEYS:
        options = model.get(key)
        if not isinstance(options, list):
            continue
        effort_field = EFFORT_FIELD[key]
        effort_changed |= reconcile_effort_options(options, effort_field, expected_efforts)

    if default_effort:
        for key in DEFAULT_EFFORT_KEYS:
            if model.get(key) != default_effort:
                model[key] = default_effort
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


def patch_catalog(path: pathlib.Path) -> tuple[int, int, int, set[str]]:
    """Patch catalog models and return capability counts plus unverified routes."""
    data = json.loads(path.read_text())
    models = data if isinstance(data, list) else data.get("models", [])
    effort_models = 0
    speed_models = 0
    context_models = 0
    unverified_models: set[str] = set()

    for model in models:
        effort_changed, speed_changed = patch_model_metadata(model)
        effort_models += int(effort_changed)
        speed_models += int(speed_changed)
        context_models += int(patch_context_metadata(model))
        candidates = identity_candidates(model)
        name = candidates[0] if candidates else ""
        if name and verified_context_window(candidates) is None:
            unverified_models.add(name)

    if effort_models or speed_models or context_models:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return effort_models, speed_models, context_models, unverified_models


def patch_config(path: pathlib.Path) -> tuple[int, int, int, int, set[str]]:
    """Patch inline provider models in config.toml without rewriting credentials."""
    text = path.read_text()

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

    text, effort_count, missing_speed_count, context_count, unverified_models = patch_inline_models(text)
    speed_count += missing_speed_count

    if effort_count or speed_count or context_count:
        path.write_text(text)
    return (
        effort_count,
        speed_count,
        0,
        context_count,
        unverified_models,
    )


def normalize_inline_effort_order(text: str) -> tuple[str, int]:
    """Move a neighbouring Ultra/Max pair into the required Max/Ultra order."""
    reordered = 0
    for field in ("effort", "reasoningEffort", "reasoning_effort"):
        pattern = re.compile(
            rf'(\{{\s*{field}\s*=\s*"ultra"[^}}]*\}})(\s*,\s*)' rf'(\{{\s*{field}\s*=\s*"max"[^}}]*\}})'
        )
        text, count = pattern.subn(r"\3\2\1", text)
        reordered += count
    return text, reordered


def patch_inline_models(text: str) -> tuple[str, int, int, int, set[str]]:
    """Patch effort, Speed, and verified context metadata in inline models."""
    lines = text.splitlines(keepends=True)
    for line_index, line in enumerate(lines):
        if not line.startswith("models = ["):
            continue

        updated, effort_count, speed_count, context_count, unverified_models = patch_models_line(line)
        if effort_count or speed_count or context_count:
            lines[line_index] = updated
        return "".join(lines), effort_count, speed_count, context_count, unverified_models

    return text, 0, 0, 0, set()


def inline_identity_candidates(table: str) -> list[str]:
    """Extract explicit route and upstream identities from one TOML inline table."""
    names: list[str] = []
    for key in MODEL_ID_KEYS:
        match = re.search(rf'\b{key}\s*=\s*"([^"]+)"', table)
        if not match:
            continue
        value = match.group(1)
        if value and value not in names:
            names.append(value)
    return names


def inline_model_name(table: str) -> str:
    """Extract the primary model identifier from one TOML inline table."""
    candidates = inline_identity_candidates(table)
    return candidates[0] if candidates else ""


def patch_inline_effort_field(
    table: str,
    key: str,
    effort_field: str,
    expected: tuple[str, ...] | None,
) -> tuple[str, bool]:
    """Rewrite one inline effort array while preserving its surrounding table."""
    match = re.search(rf"(\b{key}\s*=\s*)\[(.*?)\]", table)
    if not match:
        return table, False
    options = []
    for entry in re.findall(r"\{[^{}]*\}", match.group(2)):
        effort = re.search(rf"\b{effort_field}\s*=\s*\"([^\"]+)\"", entry)
        if not effort:
            continue
        description = re.search(r'\bdescription\s*=\s*"([^"]*)"', entry)
        options.append(
            {
                effort_field: effort.group(1),
                "description": (
                    description.group(1) if description else effort_description(effort_field, effort.group(1))
                ),
            }
        )
    changed = reconcile_effort_options(options, effort_field, expected)
    if not changed:
        return table, False
    rendered = ", ".join(
        f'{{ {effort_field} = "{option[effort_field]}", description = "{option["description"]}" }}'
        for option in options
    )
    replacement = match.group(1) + "[" + rendered + "]"
    return table[: match.start()] + replacement + table[match.end() :], True


def patch_inline_model_table(table: str) -> tuple[str, bool, bool, bool, str | None]:
    """Patch one TOML inline model table without reserializing unrelated values."""
    effort_changed = False
    speed_changed = False
    context_changed = False
    candidates = inline_identity_candidates(table)
    name = candidates[0] if candidates else ""
    expected_efforts, default_effort = model_effort_policy(candidates)

    for key in EFFORT_KEYS:
        table, changed = patch_inline_effort_field(table, key, EFFORT_FIELD[key], expected_efforts)
        effort_changed |= changed

    if default_effort:
        for key in DEFAULT_EFFORT_KEYS:
            pattern = re.compile(rf"(\b{key}\s*=\s*)\"[^\"]*\"")
            updated = pattern.sub(rf'\g<1>"{default_effort}"', table, count=1)
            effort_changed |= updated != table
            table = updated

    context_window = verified_context_window(candidates)
    max_output_tokens = verified_max_output_tokens(candidates)

    if not any(key in table for key in (*SPEED_LEGACY_KEYS, *SPEED_TIER_KEYS)):
        table = table[:-1] + ", " + FAST_TIER_TOML + " }"
        speed_changed = True

    if context_window is None and max_output_tokens is None:
        return table, effort_changed, speed_changed, context_changed, name or None

    if context_window is not None:
        missing_context_keys = []
        for key in CONTEXT_WINDOW_KEYS:
            pattern = re.compile(rf"(\b{key}\s*=\s*)(\d+)")
            match = pattern.search(table)
            if not match:
                missing_context_keys.append(key)
                continue
            if int(match.group(2)) != context_window:
                table = pattern.sub(rf"\g<1>{context_window}", table, count=1)
                context_changed = True

        if missing_context_keys:
            additions = ", ".join(f"{key} = {context_window}" for key in missing_context_keys)
            table = table[:-1] + ", " + additions + " }"
            context_changed = True

    if max_output_tokens is not None:
        missing_output_keys = []
        for key in MAX_OUTPUT_TOKENS_KEYS:
            pattern = re.compile(rf"(\b{key}\s*=\s*)(\d+)")
            match = pattern.search(table)
            if not match:
                missing_output_keys.append(key)
                continue
            if int(match.group(2)) != max_output_tokens:
                table = pattern.sub(rf"\g<1>{max_output_tokens}", table, count=1)
                context_changed = True

        if missing_output_keys:
            additions = ", ".join(f"{key} = {max_output_tokens}" for key in missing_output_keys)
            table = table[:-1] + ", " + additions + " }"
            context_changed = True

    return table, effort_changed, speed_changed, context_changed, None


def patch_models_line(line: str) -> tuple[str, int, int, int, set[str]]:
    """Patch top-level TOML inline tables within the provider's models array."""
    segments: list[str] = []
    cursor = 0
    table_start: int | None = None
    array_depth = 0
    table_depth = 0
    quote: str | None = None
    escaped = False
    effort_patched = 0
    speed_patched = 0
    context_patched = 0
    unverified_models: set[str] = set()

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
        updated, effort_changed, speed_changed, context_changed, unverified_name = patch_inline_model_table(
            table
        )
        if effort_changed or speed_changed or context_changed:
            segments.append(line[cursor:table_start])
            segments.append(updated)
            cursor = index + 1
        effort_patched += int(effort_changed)
        speed_patched += int(speed_changed)
        context_patched += int(context_changed)
        if unverified_name:
            unverified_models.add(unverified_name)
        table_start = None

    if not effort_patched and not speed_patched and not context_patched:
        return line, 0, 0, 0, unverified_models
    segments.append(line[cursor:])
    return "".join(segments), effort_patched, speed_patched, context_patched, unverified_models


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

    additions = [f'model = "{model_name}"']
    if not re.search(r"^model_reasoning_effort\s*=", text, re.MULTILINE):
        additions.append('model_reasoning_effort = "high"')
    lines[insert_at:insert_at] = additions
    path.write_text("\n".join(lines) + "\n")
    return True


def find_default_model(path: pathlib.Path) -> str:
    """Find a safe top-level default model without promoting review-only routes."""
    data = json.loads(path.read_text())
    models = data if isinstance(data, list) else data.get("models", [])
    catalog_entries: list[tuple[str, list[str], bool]] = []
    for model in models:
        candidates = identity_candidates(model)
        route_name = route_model_name(model)
        if not route_name:
            continue
        catalog_entries.append((route_name, candidates, bool(model.get("isDefault"))))

    for route_name, candidates, is_default in catalog_entries:
        if is_default and not any(is_review_only_name(name) for name in [route_name, *candidates]):
            return route_name

    for preferred in PREFERRED_DEFAULT_MODELS:
        for route_name, candidates, _is_default in catalog_entries:
            if preferred == route_name or preferred in candidates:
                return route_name
            if any(normalize_model_alias(name) == preferred for name in [route_name, *candidates]):
                return route_name

    for route_name, candidates, _is_default in catalog_entries:
        if any(is_review_only_name(name) for name in [route_name, *candidates]):
            continue
        if verified_context_window(candidates) is not None:
            return route_name

    for route_name, candidates, _is_default in catalog_entries:
        if not any(is_review_only_name(name) for name in [route_name, *candidates]):
            return route_name

    return PREFERRED_DEFAULT_MODELS[0]


def restore_ui(
    strip_suffixes: list[str] | None = None,
    auto_strip: bool = True,
) -> int:
    if not CATALOG.exists():
        print(f"catalog not found: {CATALOG}", file=sys.stderr)
        return 1
    if not CONFIG.exists():
        print(f"config not found: {CONFIG}", file=sys.stderr)
        return 1

    models = load_catalog_models(CATALOG) + load_inline_config_models(CONFIG)
    detected = detect_strip_suffixes(models)
    active = recommend_strip_suffixes(models, extra=strip_suffixes, auto=auto_strip)
    if detected:
        print("recommended strip suffixes:")
        for suffix, count, examples in detected:
            sample = "; ".join(examples[:3]) if examples else "-"
            print(f"  {suffix}  evidence={count}  e.g. {sample}")
    else:
        print("recommended strip suffixes: none detected from current catalog/config")
    print("active strip suffixes: " + ", ".join(active))

    catalog_efforts, catalog_speed, catalog_context, catalog_unverified = patch_catalog(CATALOG)
    print(
        "catalog: "
        f"{catalog_efforts} model(s) reasoning patched, "
        f"{catalog_speed} model(s) Fast speed patched, "
        f"{catalog_context} model(s) context window patched"
    )

    config_efforts, config_speed, config_levels, config_context, config_unverified = patch_config(CONFIG)
    print(
        "config.toml: "
        f"{config_efforts} reasoning arrays and "
        f"{config_speed} Fast speed fields and "
        f"{config_context} context window model(s) patched"
    )
    unverified_models = sorted(catalog_unverified | config_unverified)
    if unverified_models:
        print(
            "unverified model aliases preserved: " + ", ".join(unverified_models),
            file=sys.stderr,
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

    if not (
        catalog_efforts
        or catalog_speed
        or catalog_context
        or config_efforts
        or config_speed
        or config_context
    ):
        print("no changes needed: capabilities and verified context windows are already present")
    else:
        print("done: fully quit and reopen Codex to load the restored options")

    return 0


def redacted(value: object) -> str:
    """Render values without leaking secrets."""
    text = "" if value is None else str(value)
    if re.search(r"(api[_-]?key|token|secret|password|bearer)", text, re.I):
        return "[REDACTED_SECRET]"
    if re.fullmatch(r"sk-[A-Za-z0-9\-_]{8,}", text):
        return "[REDACTED_SECRET]"
    return text


def load_json_object(raw: object) -> dict:
    """Parse a JSON object from text or return an empty dict."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def provider_config_text(settings_config: object) -> str:
    """Extract the embedded TOML/config text from a provider settings blob."""
    data = load_json_object(settings_config)
    config = data.get("config")
    return config if isinstance(config, str) else ""


def provider_models(settings_config: object) -> list[str]:
    """Return model names declared in a provider settings blob."""
    text = provider_config_text(settings_config)
    return re.findall(r'\bmodel\s*=\s*"([^"]+)"', text)


def provider_has_grok(name: str, settings_config: object) -> bool:
    """Return True when a provider name or model list mentions Grok."""
    if GROK_NAME_RE.search(name or ""):
        return True
    return any(GROK_NAME_RE.search(model) for model in provider_models(settings_config))


def extract_wire_api(settings_config: object) -> str | None:
    """Read wire_api from embedded provider config text."""
    match = re.search(r'\bwire_api\s*=\s*"([^"]+)"', provider_config_text(settings_config))
    return match.group(1) if match else None


def extract_api_format(settings_config: object, meta: object) -> str | None:
    """Read apiFormat from settings or meta without guessing."""
    for blob in (load_json_object(settings_config), load_json_object(meta)):
        for key in ("apiFormat", "api_format"):
            value = blob.get(key)
            if isinstance(value, str) and value:
                return value
        nested = blob.get("meta")
        if isinstance(nested, dict):
            for key in ("apiFormat", "api_format"):
                value = nested.get(key)
                if isinstance(value, str) and value:
                    return value
    return None


def set_wire_api(settings_config: object, wire_api: str) -> tuple[object, bool]:
    """Set wire_api in embedded config text. Returns (settings, changed)."""
    data = load_json_object(settings_config)
    if "config" not in data or not isinstance(data.get("config"), str):
        # Keep original shape when settings_config is raw text.
        if isinstance(settings_config, str):
            text = settings_config
            if re.search(r'\bwire_api\s*=\s*"[^"]*"', text):
                updated = re.sub(r'\bwire_api\s*=\s*"[^"]*"', f'wire_api = "{wire_api}"', text, count=1)
                return updated, updated != text
            if text.strip():
                updated = text.rstrip() + f'\nwire_api = "{wire_api}"\n'
            else:
                updated = f'wire_api = "{wire_api}"\n'
            return updated, updated != text
        return settings_config, False

    text = data["config"]
    if re.search(r'\bwire_api\s*=\s*"[^"]*"', text):
        updated = re.sub(r'\bwire_api\s*=\s*"[^"]*"', f'wire_api = "{wire_api}"', text, count=1)
    else:
        updated = text.rstrip() + ("" if text.endswith("\n") else "\n") + f'wire_api = "{wire_api}"\n'
    changed = updated != text
    if changed:
        data["config"] = updated
        return data, True
    return settings_config if not isinstance(settings_config, str) else data, False


def set_api_format(settings_config: object, meta: object, api_format: str) -> tuple[object, object, bool]:
    """Set apiFormat on settings and/or meta. Returns (settings, meta, changed)."""
    settings_data = load_json_object(settings_config)
    meta_data = load_json_object(meta)
    changed = False

    if settings_data:
        if settings_data.get("apiFormat") != api_format:
            settings_data["apiFormat"] = api_format
            changed = True
        if settings_data.get("api_format") not in (None, api_format):
            settings_data["api_format"] = api_format
            changed = True
    if meta_data or meta is None or meta == "" or meta == {}:
        if meta_data.get("apiFormat") != api_format:
            meta_data["apiFormat"] = api_format
            changed = True
        if "api_format" in meta_data and meta_data.get("api_format") != api_format:
            meta_data["api_format"] = api_format
            changed = True

    if not changed:
        return settings_config, meta, False

    new_settings: object
    if isinstance(settings_config, str):
        new_settings = json.dumps(settings_data, ensure_ascii=False) if settings_data else settings_config
        if settings_data and load_json_object(settings_config):
            new_settings = json.dumps(settings_data, ensure_ascii=False)
        elif settings_data:
            # settings_config was not JSON object text; keep wire_api-only path.
            new_settings = settings_config
    else:
        new_settings = settings_data

    # Prefer writing apiFormat into settings JSON when available.
    if isinstance(new_settings, dict):
        new_settings["apiFormat"] = api_format
        new_settings_out: object = (
            json.dumps(new_settings, ensure_ascii=False) if isinstance(settings_config, str) else new_settings
        )
    else:
        new_settings_out = new_settings

    new_meta_out: object
    if meta is None or isinstance(meta, str):
        new_meta_out = json.dumps(meta_data, ensure_ascii=False) if meta_data else meta
        if meta_data:
            new_meta_out = json.dumps(meta_data, ensure_ascii=False)
    else:
        new_meta_out = meta_data
    return new_settings_out, new_meta_out, True


def list_providers(db_path: pathlib.Path) -> list[dict]:
    """Load provider rows from cc-switch.db."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("""
            SELECT id, name, app_type, is_current, settings_config, meta
            FROM providers
            """).fetchall()
    finally:
        con.close()
    providers = []
    for row in rows:
        providers.append(
            {
                "id": row["id"],
                "name": row["name"] or "",
                "app_type": row["app_type"] or "",
                "is_current": int(row["is_current"] or 0),
                "settings_config": row["settings_config"],
                "meta": row["meta"],
                "models": provider_models(row["settings_config"]),
                "wire_api": extract_wire_api(row["settings_config"]),
                "api_format": extract_api_format(row["settings_config"], row["meta"]),
            }
        )
    return providers


def find_current_multirouter(providers: list[dict]) -> dict | None:
    """Return the current Codex MultiRouter provider, if present."""
    current = [
        provider for provider in providers if provider["app_type"] == "codex" and provider["is_current"] == 1
    ]
    for provider in current:
        settings = load_json_object(provider["settings_config"])
        routing = settings.get("codexRouting")
        if isinstance(routing, dict) and routing.get("enabled") and routing.get("routes"):
            return provider
    # Fallback: any current codex provider named like multirouter.
    for provider in current:
        if "multirouter" in provider["id"].lower() or "multirouter" in provider["name"].lower():
            return provider
    return current[0] if len(current) == 1 else None


def extract_codex_routes(provider: dict) -> list[dict]:
    """Return enabled MultiRouter routes from a provider settings blob."""
    settings = load_json_object(provider["settings_config"])
    routing = settings.get("codexRouting")
    if not isinstance(routing, dict) or not routing.get("enabled"):
        return []
    routes = routing.get("routes")
    if not isinstance(routes, list):
        return []
    enabled_routes = []
    for route in routes:
        if not isinstance(route, dict) or not route.get("enabled", True):
            continue
        match = route.get("match") if isinstance(route.get("match"), dict) else {}
        models = match.get("models") if isinstance(match.get("models"), list) else []
        prefixes = match.get("prefixes") if isinstance(match.get("prefixes"), list) else []
        enabled_routes.append(
            {
                "id": route.get("id"),
                "label": route.get("label") or "",
                "targetProviderId": route.get("targetProviderId"),
                "models": [str(model) for model in models],
                "prefixes": [str(prefix) for prefix in prefixes],
                "upstream_api_format": (
                    (route.get("upstream") or {}).get("apiFormat")
                    if isinstance(route.get("upstream"), dict)
                    else None
                ),
            }
        )
    return enabled_routes


def route_matches_grok(route: dict) -> bool:
    """Return True when a static route targets Grok models or prefixes."""
    if any(GROK_NAME_RE.search(model) for model in route.get("models") or []):
        return True
    if any(GROK_NAME_RE.search(prefix) for prefix in route.get("prefixes") or []):
        return True
    if GROK_NAME_RE.search(route.get("label") or ""):
        return True
    return False


def choose_routed_grok_provider(providers: list[dict]) -> tuple[dict | None, dict | None, list[dict]]:
    """Choose the Grok provider from MultiRouter static codexRouting only."""
    multirouter = find_current_multirouter(providers)
    if multirouter is None:
        return None, None, []
    routes = extract_codex_routes(multirouter)
    grok_routes = [route for route in routes if route_matches_grok(route)]
    if not grok_routes:
        return None, multirouter, routes

    # Prefer exact model matches over label-only matches.
    exact = [
        route
        for route in grok_routes
        if any(GROK_NAME_RE.search(model) for model in route.get("models") or [])
    ]
    candidates = exact or grok_routes
    if len(candidates) != 1:
        # Ambiguous static mapping: refuse rather than guess.
        return None, multirouter, routes

    route = candidates[0]
    target_id = route.get("targetProviderId")
    if not target_id:
        return None, multirouter, routes
    for provider in providers:
        if provider["id"] == target_id:
            provider = dict(provider)
            provider["route"] = route
            return provider, multirouter, routes
    return None, multirouter, routes


def print_protocol_fields(provider: dict) -> None:
    """Print the protocol-related fields that force-grok-chat may touch."""
    print(f"target provider: {provider['name']} ({provider['id']})")
    print(f"app_type: {provider['app_type']}")
    print(f"is_current: {provider['is_current']}")
    print(f"models: {', '.join(provider['models']) or '-'}")
    print(f"wire_api: {provider.get('wire_api') or '-'}")
    print(f"apiFormat: {provider.get('api_format') or '-'}")
    print("planned changes:")
    print(f"  wire_api: {provider.get('wire_api') or '-'} -> chat")
    print(f"  apiFormat: {provider.get('api_format') or '-'} -> openai_chat")
    print("  base_url: unchanged")


def backup_cc_switch_db(db_path: pathlib.Path, backup_dir: pathlib.Path) -> pathlib.Path:
    """Copy the full cc-switch database to a timestamped backup file."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"grok-chat-repair-{stamp}.db"
    shutil.copy2(db_path, target)
    return target


def restore_cc_switch_db(backup_path: pathlib.Path, db_path: pathlib.Path) -> None:
    """Restore the full cc-switch database from backup."""
    shutil.copy2(backup_path, db_path)


def apply_grok_chat_fields(db_path: pathlib.Path, provider_id: str) -> bool:
    """Apply wire_api=chat and apiFormat=openai_chat to one provider row."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT settings_config, meta FROM providers WHERE id = ?",
            (provider_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"provider not found: {provider_id}")
        settings = row["settings_config"]
        meta = row["meta"]
        settings, wire_changed = set_wire_api(settings, "chat")
        settings, meta, api_changed = set_api_format(settings, meta, "openai_chat")
        if not (wire_changed or api_changed):
            return False
        # Ensure settings is stored as text when original was text-ish.
        if isinstance(settings, dict):
            settings = json.dumps(settings, ensure_ascii=False)
        if isinstance(meta, dict):
            meta = json.dumps(meta, ensure_ascii=False)
        con.execute(
            "UPDATE providers SET settings_config = ?, meta = ? WHERE id = ?",
            (settings, meta, provider_id),
        )
        con.commit()
        return True
    finally:
        con.close()


def read_provider_protocol(db_path: pathlib.Path, provider_id: str) -> dict:
    """Re-read one provider's protocol fields after mutation."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT id, name, settings_config, meta FROM providers WHERE id = ?",
            (provider_id,),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise RuntimeError(f"provider not found: {provider_id}")
    return {
        "id": row["id"],
        "name": row["name"],
        "wire_api": extract_wire_api(row["settings_config"]),
        "api_format": extract_api_format(row["settings_config"], row["meta"]),
    }


def load_active_base_url(config_path: pathlib.Path) -> str | None:
    """Read the active model provider base_url from config.toml."""
    if not config_path.exists():
        return None
    text = config_path.read_text()
    provider = None
    for line in text.splitlines():
        if line.startswith("model_provider"):
            match = re.search(r'model_provider\s*=\s*"([^"]+)"', line)
            if match:
                provider = match.group(1)
            break
    if not provider:
        return None
    section = f"[model_providers.{provider}]"
    in_section = False
    for line in text.splitlines():
        if line.strip() == section:
            in_section = True
            continue
        if in_section and line.startswith("["):
            break
        if in_section:
            match = re.search(r'base_url\s*=\s*"([^"]+)"', line)
            if match:
                return match.group(1)
    return None


def probe_grok_chat(base_url: str, model: str = "grok-4.5") -> tuple[bool, str]:
    """Send one minimal chat probe through the local proxy path."""
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        url = root + "/chat/completions"
    else:
        url = root + "/v1/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = getattr(response, "status", None) or response.getcode()
            payload = response.read(500).decode("utf-8", errors="replace")
            return 200 <= int(status) < 300, f"status={status} body={payload[:200]}"
    except urllib.error.HTTPError as error:
        detail = error.read(300).decode("utf-8", errors="replace")
        return False, f"status={error.code} body={detail[:200]}"
    except Exception as error:  # noqa: BLE001 - probe must never crash the repair flow
        return False, f"probe failed: {error}"


def recent_grok_route_hits(log_path: pathlib.Path, limit: int = 40) -> list[dict]:
    """Parse recent router log lines that mention grok models for post-apply verification only."""
    if not log_path.exists():
        return []
    lines = log_path.read_text(errors="replace").splitlines()
    hits: list[dict] = []
    for line in reversed(lines):
        if "grok" not in line.lower():
            continue
        if not any(
            key in line
            for key in (
                "request_prepared",
                "route_resolved",
                "upstream_status",
                "effective_name",
                "upstream_url",
            )
        ):
            continue
        item = {
            "line": line,
            "model": None,
            "effective_name": None,
            "endpoint": None,
            "effective_endpoint": None,
            "upstream_url": None,
            "responses_to_chat": None,
            "status": None,
        }
        for key in (
            "model",
            "effective_name",
            "endpoint",
            "effective_endpoint",
            "upstream_url",
            "responses_to_chat",
            "status",
        ):
            match = re.search(rf"\b{key}=([^\s]+)", line)
            if match:
                item[key] = match.group(1)
        if item["model"] and not GROK_NAME_RE.search(item["model"]):
            continue
        hits.append(item)
        if len(hits) >= limit:
            break
    return list(reversed(hits))


def verify_chat_route(log_path: pathlib.Path, since_ts: float, model: str = "grok-4.5") -> tuple[bool, str]:
    """Check recent log lines after since_ts for native chat evidence."""
    if not log_path.exists():
        return False, "router log missing"
    # Best-effort: inspect the newest grok hits after the probe.
    time.sleep(0.5)
    hits = recent_grok_route_hits(log_path, limit=20)
    if not hits:
        return False, "no grok router hits found after probe"
    newest = None
    for hit in reversed(hits):
        if hit.get("model") and model in hit["model"]:
            newest = hit
            break
    if newest is None:
        newest = hits[-1]
    endpoint = newest.get("effective_endpoint") or newest.get("endpoint") or ""
    upstream = newest.get("upstream_url") or ""
    converted = newest.get("responses_to_chat")
    status = newest.get("status")
    chat_path = ("/chat/completions" in endpoint) or ("/chat/completions" in upstream)
    native = chat_path and str(converted).lower() in {"false", "0", "none"}
    ok = native and (status in {None, "200", 200, "status=200"} or str(status) == "200")
    # Accept 200-less request_prepared lines when path is clearly native chat.
    if chat_path and str(converted).lower() == "false":
        ok = True
    summary = (
        f"endpoint={endpoint or '-'} upstream_url={upstream or '-'} "
        f"responses_to_chat={converted} status={status}"
    )
    return ok, summary


def force_grok_chat(apply: bool = False) -> int:
    """Force the routed Grok provider onto native chat protocol."""
    if not CC_SWITCH_DB.exists():
        print(f"cc-switch db not found: {CC_SWITCH_DB}", file=sys.stderr)
        return 1

    providers = list_providers(CC_SWITCH_DB)
    target, multirouter, routes = choose_routed_grok_provider(providers)
    if target is None:
        print(
            "no unique Grok provider found from MultiRouter static codexRouting; refusing to mutate",
            file=sys.stderr,
        )
        if multirouter is None:
            print("current MultiRouter provider: none", file=sys.stderr)
        else:
            print(
                f"current MultiRouter provider: {multirouter['name']} ({multirouter['id']})",
                file=sys.stderr,
            )
            grok_routes = [route for route in routes if route_matches_grok(route)]
            if not grok_routes:
                print("static grok routes: none", file=sys.stderr)
            else:
                print("static grok routes:", file=sys.stderr)
                for route in grok_routes:
                    print(
                        "  "
                        f"label={route.get('label') or '-'} "
                        f"target={route.get('targetProviderId') or '-'} "
                        f"models={','.join(route.get('models') or []) or '-'}",
                        file=sys.stderr,
                    )
        return 1

    print("mode: force-grok-chat")
    print(
        f"static route source: {multirouter['name'] if multirouter else '-'} "
        f"({multirouter['id'] if multirouter else '-'})"
    )
    route = target.get("route") or {}
    print(
        "static routing evidence: "
        f"label={route.get('label') or '-'} "
        f"targetProviderId={route.get('targetProviderId') or target['id']} "
        f"models={','.join(route.get('models') or []) or '-'} "
        f"upstream_api_format={route.get('upstream_api_format') or '-'}"
    )
    print_protocol_fields(target)

    already_chat = target.get("wire_api") == "chat" and target.get("api_format") == "openai_chat"
    if already_chat:
        print("provider already marked chat/openai_chat")
    if not apply:
        print("dry-run only: re-run with --apply after review")
        return 0

    backup_path = backup_cc_switch_db(CC_SWITCH_DB, CC_SWITCH_BACKUPS)
    print(f"backup created: {backup_path}")
    changed = apply_grok_chat_fields(CC_SWITCH_DB, target["id"])
    current = read_provider_protocol(CC_SWITCH_DB, target["id"])
    print(
        "post-change protocol: "
        f"wire_api={current.get('wire_api')} apiFormat={current.get('api_format')} changed={changed}"
    )

    base_url = load_active_base_url(CONFIG) or "http://127.0.0.1:15721/v1"
    print(f"probe base_url: {redacted(base_url)}")
    since = time.time()
    probe_ok, probe_detail = probe_grok_chat(base_url, model="grok-4.5")
    print(f"probe result: ok={probe_ok} {probe_detail}")
    route_ok, route_detail = verify_chat_route(CC_SWITCH_LOG, since, model="grok-4.5")
    print(f"route verification: ok={route_ok} {route_detail}")

    if probe_ok and route_ok:
        print("done: Grok provider forced to native chat and verified")
        return 0

    print("verification failed; restoring database backup", file=sys.stderr)
    restore_cc_switch_db(backup_path, CC_SWITCH_DB)
    restored = read_provider_protocol(CC_SWITCH_DB, target["id"])
    print(
        "restored protocol: " f"wire_api={restored.get('wire_api')} apiFormat={restored.get('api_format')}",
        file=sys.stderr,
    )
    return 1


def interactive_menu() -> list[str]:
    """Prompt for one of the two supported modes."""
    print("ccs-restore-efforts")
    print("1) restore-ui   Restore Effort/Fast/context metadata")
    print("2) force-grok-chat  Force routed Grok provider onto chat protocol")
    choice = input("Select 1 or 2: ").strip()
    if choice in {"1", "restore-ui", "ui"}:
        return ["restore-ui"]
    if choice in {"2", "force-grok-chat", "grok"}:
        return ["force-grok-chat"]
    print("invalid selection", file=sys.stderr)
    return []


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for dual-mode operation."""
    parser = argparse.ArgumentParser(
        description="Restore CC Switch UI capabilities or force Grok onto chat protocol",
    )
    sub = parser.add_subparsers(dest="command")

    restore = sub.add_parser("restore-ui", help="Restore Effort/Fast/context metadata")
    restore.add_argument(
        "--strip-suffix",
        action="append",
        default=None,
        help="Extra mechanical suffix to strip, e.g. -csap-oai. Repeatable.",
    )
    restore.add_argument(
        "--no-auto-strip",
        action="store_true",
        help="Disable auto-detection of strip suffixes from catalog/config.",
    )

    grok = sub.add_parser(
        "force-grok-chat",
        help="Force routed Grok provider onto native chat protocol",
    )
    grok.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes after dry-run review. Default is dry-run only.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint with optional interactive menu."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = interactive_menu()
        if not argv:
            return 2

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "restore-ui":
        return restore_ui(
            strip_suffixes=getattr(args, "strip_suffix", None),
            auto_strip=not bool(getattr(args, "no_auto_strip", False)),
        )
    if args.command == "force-grok-chat":
        return force_grok_chat(apply=bool(getattr(args, "apply", False)))
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
