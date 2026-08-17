#!/usr/bin/env python3
"""Validate model-delegate cost and safety contracts without model calls."""

from __future__ import annotations

import math
import re
import sys
import unicodedata
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_PATH = SKILL_DIR / "SKILL.md"
COORDINATOR_PATH = SKILL_DIR / "references" / "compact-coordinator.md"

LEGACY_SKILL_BYTES = 25_741
LEGACY_ESTIMATED_TOKENS = 8_140
LEGACY_CAPSULE_LINES = 30
LEGACY_REPORT_LINES = 20

MAX_SKILL_BYTES = 12_000
MAX_SKILL_ESTIMATED_TOKENS = 4_000
MAX_COORDINATOR_BYTES = 5_000
MAX_CAPSULE_LINES = 20
MAX_REPORT_LINES = 12


def fenced_block(text: str, marker: str) -> str | None:
    for block in re.findall(r"```text\n(.*?)\n```", text, re.DOTALL):
        if marker in block:
            return block
    return None


def integer_setting(text: str, name: str) -> int | None:
    match = re.search(rf"`{re.escape(name)}:\s*(\d+)`", text)
    return int(match.group(1)) if match else None


def estimate_tokens(text: str) -> int:
    """Return a deterministic mixed Chinese/ASCII token estimate."""
    cjk_like = 0
    other_bytes = 0
    for character in text:
        if ord(character) > 127 and unicodedata.east_asian_width(character) in {"W", "F", "A"}:
            cjk_like += 1
        else:
            other_bytes += len(character.encode("utf-8"))
    return cjk_like + math.ceil(other_bytes / 4)


def validate_contract(skill: str, coordinator: str) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    skill_bytes = len(skill.encode("utf-8"))
    coordinator_bytes = len(coordinator.encode("utf-8"))

    capsule = fenced_block(skill, "DELEGATION_CAPSULE")
    report = fenced_block(skill, "STATUS: COMPLETE")
    capsule_lines = len(capsule.splitlines()) if capsule else 0
    report_lines = len(report.splitlines()) if report else 0

    metrics = {
        "skill_bytes": skill_bytes,
        "skill_estimated_tokens": estimate_tokens(skill),
        "coordinator_bytes": coordinator_bytes,
        "coordinator_estimated_tokens": estimate_tokens(coordinator),
        "capsule_lines": capsule_lines,
        "capsule_estimated_tokens": estimate_tokens(capsule or ""),
        "report_lines": report_lines,
        "report_estimated_tokens": estimate_tokens(report or ""),
        "parent_review_passes": integer_setting(coordinator, "MAX_PARENT_REVIEW_PASSES") or 0,
        "parent_tool_calls": integer_setting(coordinator, "MAX_PARENT_TOOL_CALLS") or 0,
        "correction_messages": integer_setting(coordinator, "MAX_CORRECTION_MESSAGES") or 0,
    }

    if skill_bytes > MAX_SKILL_BYTES:
        errors.append(f"SKILL.md too large: {skill_bytes} > {MAX_SKILL_BYTES} bytes")
    if metrics["skill_estimated_tokens"] > MAX_SKILL_ESTIMATED_TOKENS:
        errors.append(
            "SKILL.md estimated tokens too high: "
            f"{metrics['skill_estimated_tokens']} > {MAX_SKILL_ESTIMATED_TOKENS}"
        )
    if metrics["skill_estimated_tokens"] >= LEGACY_ESTIMATED_TOKENS:
        errors.append("SKILL.md no longer improves on legacy estimated token baseline")
    if coordinator_bytes > MAX_COORDINATOR_BYTES:
        errors.append(
            f"compact-coordinator.md too large: {coordinator_bytes} > {MAX_COORDINATOR_BYTES} bytes"
        )
    if not capsule:
        errors.append("DELEGATION_CAPSULE block missing")
    elif capsule_lines > MAX_CAPSULE_LINES:
        errors.append(f"capsule too long: {capsule_lines} > {MAX_CAPSULE_LINES} lines")
    if not report:
        errors.append("execution report block missing")
    elif report_lines > MAX_REPORT_LINES:
        errors.append(f"report template too long: {report_lines} > {MAX_REPORT_LINES} lines")

    required_skill = (
        "## COST_FIRST 上下文策略",
        "TASK_KIND: READ_ONLY | WRITE",
        "WRITE_BOUNDARIES: WRITE 允许修改的文件；READ_ONLY 必须为 NONE",
        "每次委派都要求用户明确确认规范模型名和 reasoning effort",
        "COST_CONTROL: SOFT; USER_ACCEPTED=YES",
        "HARD_LIMITS_UNAVAILABLE",
        "HARD_BUDGET_UNAVAILABLE",
        "OUTPUT_PROFILE: TERSE_SAFE",
        "报告不超过 12 行",
        "不得调用 `wait_threads`、`read_thread`、`list_threads` 或 `send_message_to_thread`",
    )
    for value in required_skill:
        if value not in skill:
            errors.append(f"required skill contract missing: {value}")

    required_coordinator = (
        "`MAX_PARENT_REVIEW_PASSES: 1`",
        "`MAX_PARENT_TOOL_CALLS: 4`",
        "`MAX_CORRECTION_MESSAGES: 1`",
        "不把完整日志送入父模型",
        "不要重跑执行任务全部命令",
    )
    for value in required_coordinator:
        if value not in coordinator:
            errors.append(f"required coordinator contract missing: {value}")

    forbidden_skill = (
        "使用用户配置的运行时默认值",
        "FILE_BOUNDARIES",
        "报告不超过 20 行",
    )
    for value in forbidden_skill:
        if value in skill:
            errors.append(f"forbidden legacy contract present: {value}")

    if re.search(r"(?<!SOFT_)BUDGET_EXHAUSTED", skill):
        errors.append("unqualified BUDGET_EXHAUSTED present; soft limit must stay explicit")
    if metrics["parent_review_passes"] != 1:
        errors.append("parent review passes must equal 1")
    if metrics["parent_tool_calls"] != 4:
        errors.append("parent tool calls must equal 4")
    if metrics["correction_messages"] != 1:
        errors.append("correction messages must equal 1")

    return errors, metrics


def mutation_self_test(skill: str, coordinator: str) -> list[str]:
    failures: list[str] = []
    mutations = {
        "missing task kind": (skill.replace("TASK_KIND: READ_ONLY | WRITE", ""), coordinator),
        "runtime default model": (
            skill + "\n用户未指定时使用用户配置的运行时默认值。\n",
            coordinator,
        ),
        "verbose report": (skill.replace("报告不超过 12 行", "报告不超过 20 行", 1), coordinator),
        "unbounded parent review": (
            skill,
            coordinator.replace("`MAX_PARENT_REVIEW_PASSES: 1`", "", 1),
        ),
    }
    for name, (mutated_skill, mutated_coordinator) in mutations.items():
        errors, _metrics = validate_contract(mutated_skill, mutated_coordinator)
        if not errors:
            failures.append(f"mutation escaped validator: {name}")
    return failures


def print_metrics(metrics: dict[str, int]) -> None:
    byte_reduction = 100 * (LEGACY_SKILL_BYTES - metrics["skill_bytes"]) / LEGACY_SKILL_BYTES
    estimated_tokens_saved = LEGACY_ESTIMATED_TOKENS - metrics["skill_estimated_tokens"]
    estimated_token_reduction = 100 * estimated_tokens_saved / LEGACY_ESTIMATED_TOKENS
    print("model-delegate optimization metrics:")
    print(
        f"  skill_bytes={metrics['skill_bytes']} "
        f"(legacy={LEGACY_SKILL_BYTES}, reduction={byte_reduction:.1f}%)"
    )
    print(
        f"  estimated_skill_tokens={metrics['skill_estimated_tokens']} "
        f"(legacy={LEGACY_ESTIMATED_TOKENS}, saved={estimated_tokens_saved}, "
        f"reduction={estimated_token_reduction:.1f}%)"
    )
    print(
        f"  estimated_coordinator_tokens={metrics['coordinator_estimated_tokens']} "
        "(conditional COMPACT_COORDINATOR load)"
    )
    print(f"  coordinator_bytes={metrics['coordinator_bytes']} (max={MAX_COORDINATOR_BYTES})")
    print(
        f"  capsule_lines={metrics['capsule_lines']} "
        f"(legacy={LEGACY_CAPSULE_LINES}, max={MAX_CAPSULE_LINES}, "
        f"estimated_tokens={metrics['capsule_estimated_tokens']})"
    )
    print(
        f"  report_lines={metrics['report_lines']} "
        f"(legacy={LEGACY_REPORT_LINES}, max={MAX_REPORT_LINES}, "
        f"estimated_tokens={metrics['report_estimated_tokens']})"
    )
    print(
        "  parent_limits="
        f"review:{metrics['parent_review_passes']} "
        f"tools:{metrics['parent_tool_calls']} "
        f"corrections:{metrics['correction_messages']}"
    )
    print("  estimator=CJK-like chars + ceil(other UTF-8 bytes / 4)")
    print("  scope=skill/capsule/report text only; excludes system, tools, history, cache, reasoning")


def main() -> int:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    coordinator = COORDINATOR_PATH.read_text(encoding="utf-8")
    errors, metrics = validate_contract(skill, coordinator)
    errors.extend(mutation_self_test(skill, coordinator))
    print_metrics(metrics)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: model-delegate cost and safety contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
