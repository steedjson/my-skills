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
CAPSULE_PATH = SKILL_DIR / "references" / "delegation-capsule.md"
STAGED_REVIEW_PATH = SKILL_DIR / "references" / "staged-review.md"
LOG_ANALYSIS_PATH = SKILL_DIR / "references" / "log-analysis.md"

LEGACY_SKILL_BYTES = 25_741
LEGACY_ESTIMATED_TOKENS = 8_140
LEGACY_CAPSULE_LINES = 30
LEGACY_REPORT_LINES = 20

MAX_SKILL_BYTES = 12_000
MAX_SKILL_ESTIMATED_TOKENS = 4_000
MAX_COORDINATOR_BYTES = 5_000
MAX_MODE_REFERENCE_BYTES = 6_000
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


def block_fields(block: str | None) -> list[str]:
    if not block:
        return []
    fields = []
    for line in block.splitlines()[1:]:
        if ":" in line:
            fields.append(line.split(":", 1)[0])
    return fields


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


def validate_contract(
    skill: str,
    coordinator: str,
    capsule_reference: str,
    staged_review: str,
    log_analysis: str,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    skill_bytes = len(skill.encode("utf-8"))
    coordinator_bytes = len(coordinator.encode("utf-8"))
    capsule_reference_bytes = len(capsule_reference.encode("utf-8"))
    staged_review_bytes = len(staged_review.encode("utf-8"))
    log_analysis_bytes = len(log_analysis.encode("utf-8"))

    capsule = fenced_block(capsule_reference, "DELEGATION_CAPSULE")
    report = fenced_block(skill, "STATUS: COMPLETE")
    capsule_lines = len(capsule.splitlines()) if capsule else 0
    report_lines = len(report.splitlines()) if report else 0
    capsule_fields = block_fields(capsule)
    report_fields = block_fields(report)

    metrics = {
        "skill_bytes": skill_bytes,
        "skill_estimated_tokens": estimate_tokens(skill),
        "coordinator_bytes": coordinator_bytes,
        "coordinator_estimated_tokens": estimate_tokens(coordinator),
        "capsule_reference_bytes": capsule_reference_bytes,
        "capsule_reference_estimated_tokens": estimate_tokens(capsule_reference),
        "staged_review_bytes": staged_review_bytes,
        "staged_review_estimated_tokens": estimate_tokens(staged_review),
        "log_analysis_bytes": log_analysis_bytes,
        "log_analysis_estimated_tokens": estimate_tokens(log_analysis),
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
    for name, size in (
        ("delegation-capsule.md", capsule_reference_bytes),
        ("staged-review.md", staged_review_bytes),
        ("log-analysis.md", log_analysis_bytes),
    ):
        if size > MAX_MODE_REFERENCE_BYTES:
            errors.append(f"{name} too large: {size} > {MAX_MODE_REFERENCE_BYTES} bytes")
    if not capsule:
        errors.append("DELEGATION_CAPSULE block missing")
    elif capsule_lines > MAX_CAPSULE_LINES:
        errors.append(f"capsule too long: {capsule_lines} > {MAX_CAPSULE_LINES} lines")
    if not report:
        errors.append("execution report block missing")
    elif report_lines > MAX_REPORT_LINES:
        errors.append(f"report template too long: {report_lines} > {MAX_REPORT_LINES} lines")

    expected_capsule_fields = [
        "MODE",
        "DELEGATION_KEY",
        "ROLE",
        "PROJECT_ROOT",
        "MODEL",
        "SCOPE",
        "INPUTS",
        "ACCEPTANCE",
        "READ_BOUNDARIES",
        "WRITE_BOUNDARIES",
        "RULES_AND_TOOLING",
        "CHECKS_AND_POST_ACTIONS",
        "REVIEW_POLICY",
        "COST_CONTROL",
        "LIMITS",
        "HARD_LIMITS_UNAVAILABLE",
        "STOP_RULE",
        "OUTPUT_PROFILE",
        "CONSTRAINTS",
    ]
    if capsule and capsule_fields != expected_capsule_fields:
        errors.append("DELEGATION_CAPSULE fields changed, duplicated, missing, or reordered")

    expected_report_fields = [
        "DELEGATION_KEY",
        "TASK_KIND",
        "RESULT",
        "COMMIT_ID",
        "FILES",
        "CHECKS",
        "TOOLS_USED",
        "TOOLING_GAPS",
        "RISKS",
    ]
    if report and report_fields != expected_report_fields:
        errors.append("execution report fields changed, duplicated, missing, or reordered")

    required_skill = (
        "## 委派准入",
        "## COST_FIRST 上下文策略",
        "## STAGED_REVIEW",
        "## LOG_ANALYSIS profile",
        "每次委派都要求用户明确确认规范模型名和 reasoning effort",
        "HARD_BUDGET_UNAVAILABLE",
        "报告不超过 12 行",
        "不得调用 `wait_threads`、`read_thread`、`list_threads` 或 `send_message_to_thread`",
        "执行任务不得再创建任务",
        "核心协议不得依赖特定代理、供应商、价格表、本地计费数据库或 usage API",
        "`COMPACT_COORDINATOR` 只在用户明确要求旧主任务压缩后继续验收时使用",
        "真实委派 E2E 仅在用户明确确认后运行",
        "LIVE_E2E: NOT_RUN_BY_USER_CHOICE",
        "RUNTIME_USAGE: UNAVAILABLE",
        "COST_SAVINGS: NOT_VERIFIED",
    )
    for value in required_skill:
        if value not in skill:
            errors.append(f"required skill contract missing: {value}")

    required_capsule = (
        "TASK_KIND: READ_ONLY | WRITE",
        "PROFILE: STANDARD | LOG_ANALYSIS",
        "REVIEW_POLICY: NONE | FRESH_USER_TRIGGERED | COMPACT_PARENT",
        "WRITE_BOUNDARIES: WRITE 允许修改的文件；READ_ONLY 必须为 NONE",
        "COST_CONTROL: SOFT; USER_ACCEPTED=YES",
        "HARD_LIMITS_UNAVAILABLE",
        "OUTPUT_PROFILE: TERSE_SAFE",
    )
    for value in required_capsule:
        if value not in capsule_reference:
            errors.append(f"required capsule contract missing: {value}")

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

    required_staged_review = (
        "旧主任务不得恢复",
        "执行任务不得创建审查任务",
        "用户明确触发审查后，才创建全新审查任务",
        "REVIEW_CAPSULE",
        "重新读取原始日志",
        "不得自动续派",
    )
    for value in required_staged_review:
        if value not in staged_review:
            errors.append(f"required staged review contract missing: {value}")

    required_log_analysis = (
        "TASK_KIND: READ_ONLY",
        "TIME_RANGE:",
        "INPUT_LOCATION:",
        "QUERY:",
        "MAX_SCAN_PASSES: 1",
        "RAW_LOG_OUTPUT: FORBIDDEN",
        "不得依赖特定日志代理、供应商或计费数据库",
        "最多一次原始数据扫描",
        "报告不超过 10 行",
    )
    for value in required_log_analysis:
        if value not in log_analysis:
            errors.append(f"required log analysis contract missing: {value}")

    forbidden_skill = (
        "使用用户配置的运行时默认值",
        "FILE_BOUNDARIES",
        "报告不超过 20 行",
        "数据库迁移、数据修复、认证授权、租户隔离、生产配置、并发、公共接口、不可逆操作，或用户明确要求独立验收",
    )
    for value in forbidden_skill:
        if value in skill:
            errors.append(f"forbidden legacy contract present: {value}")

    all_contract_text = "\n".join(
        (skill, coordinator, capsule_reference, staged_review, log_analysis)
    )
    forbidden_runtime_coupling = (
        ".cc-switch",
        "proxy_request_logs",
        "CC_SWITCH_DB",
        "total_cost_usd",
        "input_cost_usd",
    )
    for value in forbidden_runtime_coupling:
        if value in all_contract_text:
            errors.append(f"provider-specific runtime coupling present: {value}")

    if re.search(r"(?<!SOFT_)BUDGET_EXHAUSTED", skill):
        errors.append("unqualified BUDGET_EXHAUSTED present; soft limit must stay explicit")
    if metrics["parent_review_passes"] != 1:
        errors.append("parent review passes must equal 1")
    if metrics["parent_tool_calls"] != 4:
        errors.append("parent tool calls must equal 4")
    if metrics["correction_messages"] != 1:
        errors.append("correction messages must equal 1")

    return errors, metrics


def mutation_self_test(
    skill: str,
    coordinator: str,
    capsule_reference: str,
    staged_review: str,
    log_analysis: str,
) -> list[str]:
    failures: list[str] = []
    mutations = {
        "missing task kind": (
            skill.replace("TASK_KIND: READ_ONLY | WRITE", ""),
            coordinator,
            capsule_reference.replace("TASK_KIND: READ_ONLY | WRITE", ""),
            staged_review,
            log_analysis,
        ),
        "runtime default model": (
            skill + "\n用户未指定时使用用户配置的运行时默认值。\n",
            coordinator,
            capsule_reference,
            staged_review,
            log_analysis,
        ),
        "verbose report": (
            skill.replace("报告不超过 12 行", "报告不超过 20 行", 1),
            coordinator,
            capsule_reference,
            staged_review,
            log_analysis,
        ),
        "unbounded parent review": (
            skill,
            coordinator.replace("`MAX_PARENT_REVIEW_PASSES: 1`", "", 1),
            capsule_reference,
            staged_review,
            log_analysis,
        ),
        "missing delegation gate": (
            skill.replace("## 委派准入", "", 1),
            coordinator,
            capsule_reference,
            staged_review,
            log_analysis,
        ),
        "automatic fresh reviewer": (
            skill,
            coordinator,
            capsule_reference,
            staged_review.replace("执行任务不得创建审查任务", "执行任务创建审查任务", 1),
            log_analysis,
        ),
        "raw log output allowed": (
            skill,
            coordinator,
            capsule_reference,
            staged_review,
            log_analysis.replace("RAW_LOG_OUTPUT: FORBIDDEN", "RAW_LOG_OUTPUT: ALLOWED", 1),
        ),
        "provider runtime dependency": (
            skill + "\n读取 ~/.cc-switch/cc-switch.db 计算费用。\n",
            coordinator,
            capsule_reference,
            staged_review,
            log_analysis,
        ),
        "automatic live e2e": (
            skill.replace(
                "真实委派 E2E 仅在用户明确确认后运行",
                "每次修改后自动运行真实委派 E2E",
                1,
            ),
            coordinator,
            capsule_reference,
            staged_review,
            log_analysis,
        ),
        "duplicate capsule field": (
            skill,
            coordinator,
            capsule_reference.replace("INPUTS:", "SCOPE:", 1),
            staged_review,
            log_analysis,
        ),
        "coordinator restored as default": (
            skill.replace(
                "`COMPACT_COORDINATOR` 只在用户明确要求旧主任务压缩后继续验收时使用",
                "`COMPACT_COORDINATOR` 默认用于高风险任务",
                1,
            ),
            coordinator,
            capsule_reference,
            staged_review,
            log_analysis,
        ),
    }
    for name, texts in mutations.items():
        errors, _metrics = validate_contract(*texts)
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
    print(
        "  conditional_reference_tokens="
        f"capsule:{metrics['capsule_reference_estimated_tokens']} "
        f"staged:{metrics['staged_review_estimated_tokens']} "
        f"log:{metrics['log_analysis_estimated_tokens']} "
        f"coordinator:{metrics['coordinator_estimated_tokens']}"
    )
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
    capsule_reference = CAPSULE_PATH.read_text(encoding="utf-8")
    staged_review = STAGED_REVIEW_PATH.read_text(encoding="utf-8")
    log_analysis = LOG_ANALYSIS_PATH.read_text(encoding="utf-8")
    errors, metrics = validate_contract(
        skill,
        coordinator,
        capsule_reference,
        staged_review,
        log_analysis,
    )
    errors.extend(
        mutation_self_test(
            skill,
            coordinator,
            capsule_reference,
            staged_review,
            log_analysis,
        )
    )
    print_metrics(metrics)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: model-delegate cost and safety contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
