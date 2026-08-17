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
PASSIVE_RETURN_PATH = SKILL_DIR / "references" / "passive-return.md"
PASSIVE_SESSION_PATH = SKILL_DIR / "references" / "passive-session.md"
CONTEXT_GATE_PATH = SKILL_DIR / "references" / "context-gate.md"

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
MAX_COLLECTOR_CAPSULE_LINES = 16
MAX_RETURN_CAPSULE_LINES = 10
MAX_SESSION_CAPSULE_LINES = 18
MAX_ROUND_DELTA_LINES = 6
MAX_SESSION_RETURN_LINES = 10
MAX_CONTEXT_POLICY_LINES = 11
MAX_CONTEXT_GATE_LINES = 15


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
    passive_return: str,
    passive_session: str,
    context_gate: str,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    skill_bytes = len(skill.encode("utf-8"))
    coordinator_bytes = len(coordinator.encode("utf-8"))
    capsule_reference_bytes = len(capsule_reference.encode("utf-8"))
    staged_review_bytes = len(staged_review.encode("utf-8"))
    log_analysis_bytes = len(log_analysis.encode("utf-8"))
    passive_return_bytes = len(passive_return.encode("utf-8"))
    passive_session_bytes = len(passive_session.encode("utf-8"))
    context_gate_bytes = len(context_gate.encode("utf-8"))

    capsule = fenced_block(capsule_reference, "DELEGATION_CAPSULE")
    report = fenced_block(capsule_reference, "STATUS: COMPLETE")
    collector_capsule = fenced_block(passive_return, "COLLECTOR_CAPSULE")
    return_capsule = fenced_block(passive_return, "RETURN_CAPSULE")
    session_capsule = fenced_block(passive_session, "SESSION_CAPSULE")
    round_delta = fenced_block(passive_session, "ROUND_DELTA")
    session_return = fenced_block(passive_session, "SESSION_RETURN_CAPSULE")
    context_gate_block = fenced_block(context_gate, "CONTEXT_GATE")
    context_policy_block = fenced_block(context_gate, "CONTEXT_POLICY")
    capsule_lines = len(capsule.splitlines()) if capsule else 0
    report_lines = len(report.splitlines()) if report else 0
    collector_capsule_lines = len(collector_capsule.splitlines()) if collector_capsule else 0
    return_capsule_lines = len(return_capsule.splitlines()) if return_capsule else 0
    session_capsule_lines = len(session_capsule.splitlines()) if session_capsule else 0
    round_delta_lines = len(round_delta.splitlines()) if round_delta else 0
    session_return_lines = len(session_return.splitlines()) if session_return else 0
    context_gate_lines = len(context_gate_block.splitlines()) if context_gate_block else 0
    context_policy_lines = len(context_policy_block.splitlines()) if context_policy_block else 0
    capsule_fields = block_fields(capsule)
    report_fields = block_fields(report)
    collector_capsule_fields = block_fields(collector_capsule)
    return_capsule_fields = block_fields(return_capsule)
    session_capsule_fields = block_fields(session_capsule)
    round_delta_fields = block_fields(round_delta)
    session_return_fields = block_fields(session_return)
    context_gate_fields = block_fields(context_gate_block)
    context_policy_fields = block_fields(context_policy_block)

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
        "passive_return_bytes": passive_return_bytes,
        "passive_return_estimated_tokens": estimate_tokens(passive_return),
        "passive_session_bytes": passive_session_bytes,
        "passive_session_estimated_tokens": estimate_tokens(passive_session),
        "context_gate_bytes": context_gate_bytes,
        "context_gate_estimated_tokens": estimate_tokens(context_gate),
        "capsule_lines": capsule_lines,
        "capsule_estimated_tokens": estimate_tokens(capsule or ""),
        "report_lines": report_lines,
        "report_estimated_tokens": estimate_tokens(report or ""),
        "collector_capsule_lines": collector_capsule_lines,
        "return_capsule_lines": return_capsule_lines,
        "session_capsule_lines": session_capsule_lines,
        "round_delta_lines": round_delta_lines,
        "session_return_lines": session_return_lines,
        "context_gate_lines": context_gate_lines,
        "context_policy_lines": context_policy_lines,
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
        ("passive-return.md", passive_return_bytes),
        ("passive-session.md", passive_session_bytes),
        ("context-gate.md", context_gate_bytes),
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
    if not collector_capsule:
        errors.append("COLLECTOR_CAPSULE block missing")
    elif collector_capsule_lines > MAX_COLLECTOR_CAPSULE_LINES:
        errors.append(
            f"collector capsule too long: {collector_capsule_lines} > "
            f"{MAX_COLLECTOR_CAPSULE_LINES} lines"
        )
    if not return_capsule:
        errors.append("RETURN_CAPSULE block missing")
    elif return_capsule_lines > MAX_RETURN_CAPSULE_LINES:
        errors.append(
            f"return capsule too long: {return_capsule_lines} > "
            f"{MAX_RETURN_CAPSULE_LINES} lines"
        )
    if not session_capsule:
        errors.append("SESSION_CAPSULE block missing")
    elif session_capsule_lines > MAX_SESSION_CAPSULE_LINES:
        errors.append(
            f"session capsule too long: {session_capsule_lines} > "
            f"{MAX_SESSION_CAPSULE_LINES} lines"
        )
    if not round_delta:
        errors.append("ROUND_DELTA block missing")
    elif round_delta_lines > MAX_ROUND_DELTA_LINES:
        errors.append(f"round delta too long: {round_delta_lines} > {MAX_ROUND_DELTA_LINES} lines")
    if not session_return:
        errors.append("SESSION_RETURN_CAPSULE block missing")
    elif session_return_lines > MAX_SESSION_RETURN_LINES:
        errors.append(
            f"session return too long: {session_return_lines} > "
            f"{MAX_SESSION_RETURN_LINES} lines"
        )
    if not context_gate_block:
        errors.append("CONTEXT_GATE block missing")
    elif context_gate_lines > MAX_CONTEXT_GATE_LINES:
        errors.append(
            f"context gate too long: {context_gate_lines} > {MAX_CONTEXT_GATE_LINES} lines"
        )
    if not context_policy_block:
        errors.append("CONTEXT_POLICY block missing")
    elif context_policy_lines > MAX_CONTEXT_POLICY_LINES:
        errors.append(
            f"context policy too long: {context_policy_lines} > "
            f"{MAX_CONTEXT_POLICY_LINES} lines"
        )

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

    expected_collector_fields = [
        "MODE",
        "DELEGATION_KEY",
        "MODEL",
        "QUERY",
        "INPUT_LOCATION",
        "TIME_RANGE",
        "EVIDENCE_FIELDS",
        "READ_BOUNDARIES",
        "RULES_AND_TOOLING",
        "FORK_CONTEXT",
        "LIMITS",
        "RAW_LOG_OUTPUT",
        "CLEANUP_POLICY",
        "STOP_RULE",
        "RETURN_PROFILE",
    ]
    if collector_capsule and collector_capsule_fields != expected_collector_fields:
        errors.append("COLLECTOR_CAPSULE fields changed, duplicated, missing, or reordered")

    expected_return_fields = [
        "STATUS",
        "DELEGATION_KEY",
        "QUERY",
        "RESULT",
        "EVIDENCE",
        "TOOLING_GAPS",
        "UNVERIFIED",
        "RISKS",
        "NEXT_ACTION",
    ]
    if return_capsule and return_capsule_fields != expected_return_fields:
        errors.append("RETURN_CAPSULE fields changed, duplicated, missing, or reordered")

    expected_session_fields = [
        "MODE",
        "DELEGATION_KEY",
        "MODEL",
        "ROUND_1_QUERY",
        "INPUT_LOCATION",
        "TIME_RANGE",
        "EVIDENCE_FIELDS",
        "READ_BOUNDARIES",
        "RULES_AND_TOOLING",
        "FORK_CONTEXT",
        "LIMITS",
        "ROUND_INPUT",
        "RAW_LOG_OUTPUT",
        "CLEANUP_POLICY",
        "STOP_RULE",
        "RETURN_PROFILE",
    ]
    if session_capsule and session_capsule_fields != expected_session_fields:
        errors.append("SESSION_CAPSULE fields changed, duplicated, missing, or reordered")

    expected_round_delta_fields = [
        "DELEGATION_KEY",
        "ROUND",
        "DEPENDENCY",
        "QUERY_DELTA",
        "EVIDENCE_DELTA",
    ]
    if round_delta and round_delta_fields != expected_round_delta_fields:
        errors.append("ROUND_DELTA fields changed, duplicated, missing, or reordered")

    expected_session_return_fields = [
        "STATUS",
        "DELEGATION_KEY",
        "ROUND",
        "QUERY",
        "RESULT",
        "EVIDENCE",
        "TOOLING_GAPS",
        "UNVERIFIED",
        "NEXT_ACTION",
    ]
    if session_return and session_return_fields != expected_session_return_fields:
        errors.append("SESSION_RETURN_CAPSULE fields changed, duplicated, missing, or reordered")

    expected_context_gate_fields = [
        "ACTIVE_MODEL",
        "MODEL_CONTEXT_WINDOW",
        "EFFECTIVE_CONTEXT_WINDOW",
        "AUTO_COMPACT_LIMIT",
        "COST_CLIFF_TOKENS",
        "CONTEXT_BASE",
        "LIMIT_SOURCE",
        "LIMIT_VALID",
        "CURRENT_CONTEXT",
        "CONTEXT_RATIO",
        "SAMPLE_AGE_TURNS",
        "RESERVE",
        "AUTO_COMPACT_POLICY",
        "DECISION",
    ]
    if context_gate_block and context_gate_fields != expected_context_gate_fields:
        errors.append("CONTEXT_GATE fields changed, duplicated, missing, or reordered")

    expected_context_policy_fields = [
        "PERCENT_BASE",
        "PASSIVE_SESSION_MAX_PERCENT",
        "PASSIVE_RETURN_MAX_PERCENT",
        "HANDOFF_PERCENT",
        "COMPACTION_CHECKPOINT_PERCENT",
        "HYSTERESIS_PERCENT",
        "MIN_RESERVE_TOKENS",
        "CONTEXT_SAMPLE_MAX_AGE",
        "AUTO_COMPACT_POLICY",
        "ENFORCEMENT",
    ]
    if context_policy_block and context_policy_fields != expected_context_policy_fields:
        errors.append("CONTEXT_POLICY fields changed, duplicated, missing, or reordered")

    required_skill = (
        "## 委派准入",
        "## COST_FIRST 上下文策略",
        "## CONTEXT_GATE",
        "## PASSIVE modes",
        "## STAGED_REVIEW",
        "## LOG_ANALYSIS profile",
        "每次委派都要求用户明确确认规范模型名和 reasoning effort",
        "HARD_BUDGET_UNAVAILABLE",
        "执行任务不得再创建任务",
        "只有 `PASSIVE_RETURN` 和 `PASSIVE_SESSION` 可创建一个原生只读子智能体",
        "顶层任务始终使用保存项目的 `local` 环境和共享检出目录，不使用 worktree",
        "被动模式子智能体不得调用 worktree 管理工具或依赖子工作区写入",
        "`fork_context=false`",
        "`PASSIVE_SESSION`：最多两次 `wait_agent`、一次 `send_input`",
        "完成通知已包含最终 capsule 时直接使用",
        "磁盘配置不证明已生效",
        "自动压缩只防溢出，不保费用",
        "当前工具面不能主动执行 `/compact`",
        "不自动改用其他模式",
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
        "one_field_per_line=YES",
        "READ_ONLY_OMIT_COMMIT_ID=YES",
        "报告不超过 12 行",
        "不调用 `wait_threads`、`read_thread`、`list_threads` 或 `send_message_to_thread`",
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

    required_passive_return = (
        "TASK_KIND: READ_ONLY",
        "FORK_CONTEXT: false",
        "children=1",
        "scans=1",
        "waits=1",
        "parent_resumes=1",
        "corrections=0",
        "RAW_LOG_OUTPUT: FORBIDDEN",
        "CLEANUP_POLICY: DEFER_TO_PARENT_SESSION_END",
        "fork_context=false",
        "不得调用 `send_input`",
        "不得第二次调用 `wait_agent`",
        "完成通知已包含最终 `RETURN_CAPSULE` 时直接使用",
        "不在返回路径调用 `close_agent`",
        "RETURN_CAPSULE",
        "协议不合格、包含原始日志或超过 10 行时返回 `BLOCKED`",
        "不得重新读取原始日志、重复同一调查或要求子智能体重述",
        "高风险结论只作为输入，后续使用 `STAGED_REVIEW`",
    )
    for value in required_passive_return:
        if value not in passive_return:
            errors.append(f"required passive return contract missing: {value}")

    required_passive_session = (
        "TASK_KIND: READ_ONLY",
        "FORK_CONTEXT: false",
        "children=1",
        "rounds=2",
        "send_inputs=1",
        "waits=2",
        "parent_resumes=2",
        "corrections=0",
        "ROUND_INPUT: DELTA_ONLY",
        "RAW_LOG_OUTPUT: FORBIDDEN",
        "CLEANUP_POLICY: DEFER_TO_PARENT_SESSION_END",
        "第一轮足够时立即结束",
        "第二轮问题必须依赖第一轮结果",
        "不得自动启动第二轮",
        "调用一次 `send_input`",
        "第一轮完成通知已包含最终 capsule 时直接使用",
        "不得第三次等待、第二次 `send_input`",
        "预计需要第三轮时直接使用 `HANDOFF`",
        "第一轮协议不合格时返回 `BLOCKED`",
    )
    for value in required_passive_session:
        if value not in passive_session:
            errors.append(f"required passive session contract missing: {value}")

    required_context_gate = (
        "PERCENT_BASE: EFFECTIVE_LIMIT",
        "PASSIVE_SESSION_MAX_PERCENT: 40",
        "PASSIVE_RETURN_MAX_PERCENT: 55",
        "HANDOFF_PERCENT: 70",
        "COMPACTION_CHECKPOINT_PERCENT: 85",
        "HYSTERESIS_PERCENT: 5",
        "MIN_RESERVE_TOKENS: 32000",
        "CONTEXT_SAMPLE_MAX_AGE: 1",
        "ENFORCEMENT: SOFT",
        "0 < PASSIVE_SESSION_MAX_PERCENT",
        "PASSIVE_SESSION_MAX_PERCENT < PASSIVE_RETURN_MAX_PERCENT",
        "PASSIVE_RETURN_MAX_PERCENT < HANDOFF_PERCENT",
        "HANDOFF_PERCENT < COMPACTION_CHECKPOINT_PERCENT",
        "COMPACTION_CHECKPOINT_PERCENT < 100",
        "CONTEXT_POLICY_INVALID",
        "ACTIVE_SESSION > MODEL_CATALOG > DISK_CONFIG",
        "LIMIT_SOURCE: DISK_ONLY",
        "当前任务不使用该值；新任务重新验证",
        "0 < AUTO_COMPACT_LIMIT < EFFECTIVE_CONTEXT_WINDOW",
        "AUTO_COMPACT_LIMIT: MODEL_DERIVED",
        "LIMIT_VALID: NO",
        "不得依赖自动压缩",
        "CURRENT_CONTEXT: UNKNOWN",
        "`PASSIVE_SESSION` 返回 `CONTEXT_GAP`",
        "AUTO_COMPACT_POLICY: RUNTIME_SAFETY_ONLY",
        "CONTEXT_BASE: min(EFFECTIVE_CONTEXT_WINDOW, 有效 AUTO_COMPACT_LIMIT, 已知 COST_CLIFF_TOKENS)",
        "COST_CLIFF_TOKENS: 运行时明确值或 UNKNOWN",
        "CURRENT_CONTEXT: 当前上下文 token 或 UNKNOWN",
        "last_token_usage.input_tokens",
        "缓存输入仍占上下文，不得扣除",
        "RESERVE = max(MIN_RESERVE_TOKENS, CONTEXT_BASE 的 10%)",
        "SAMPLE_AGE_TURNS: 0 | 1 | STALE | UNKNOWN",
        "超过 `CONTEXT_SAMPLE_MAX_AGE` 标记 `STALE`",
        "compaction 后必须重新读取 active session",
        "`CONTEXT_RATIO < 40%`",
        "`40% <= CONTEXT_RATIO < 55%`",
        "`55% <= CONTEXT_RATIO < 70%`",
        "`70% <= CONTEXT_RATIO < 85%`",
        "`CONTEXT_RATIO >= 85%`",
        "应用 5% hysteresis",
        "不能主动执行 `/compact`",
        "不修改 `config.toml`、模型目录或运行时设置",
    )
    for value in required_context_gate:
        if value not in context_gate:
            errors.append(f"required context gate contract missing: {value}")

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
        (
            skill,
            coordinator,
            capsule_reference,
            staged_review,
            log_analysis,
            passive_return,
            passive_session,
            context_gate,
        )
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
    passive_return: str,
    passive_session: str,
    context_gate: str,
) -> list[str]:
    failures: list[str] = []
    names = (
        "skill",
        "coordinator",
        "capsule_reference",
        "staged_review",
        "log_analysis",
        "passive_return",
        "passive_session",
        "context_gate",
    )
    base = dict(
        zip(
            names,
            (
                skill,
                coordinator,
                capsule_reference,
                staged_review,
                log_analysis,
                passive_return,
                passive_session,
                context_gate,
            ),
            strict=True,
        )
    )

    def variant(**changes: str) -> tuple[str, ...]:
        values = base | changes
        return tuple(values[name] for name in names)

    mutations = {
        "missing task kind": variant(
            capsule_reference=capsule_reference.replace("TASK_KIND: READ_ONLY | WRITE", "")
        ),
        "runtime default model": variant(
            skill=skill + "\n用户未指定时使用用户配置的运行时默认值。\n"
        ),
        "verbose report": variant(
            capsule_reference=capsule_reference.replace(
                "报告不超过 12 行", "报告不超过 20 行", 1
            )
        ),
        "unbounded parent review": variant(
            coordinator=coordinator.replace("`MAX_PARENT_REVIEW_PASSES: 1`", "", 1)
        ),
        "missing delegation gate": variant(
            skill=skill.replace("## 委派准入", "", 1)
        ),
        "automatic fresh reviewer": variant(
            staged_review=staged_review.replace(
                "执行任务不得创建审查任务", "执行任务创建审查任务", 1
            )
        ),
        "raw log output allowed": variant(
            log_analysis=log_analysis.replace(
                "RAW_LOG_OUTPUT: FORBIDDEN", "RAW_LOG_OUTPUT: ALLOWED", 1
            )
        ),
        "provider runtime dependency": variant(
            skill=skill + "\n读取 ~/.cc-switch/cc-switch.db 计算费用。\n"
        ),
        "automatic live e2e": variant(
            skill=skill.replace(
                "真实委派 E2E 仅在用户明确确认后运行",
                "每次修改后自动运行真实委派 E2E",
                1,
            )
        ),
        "duplicate capsule field": variant(
            capsule_reference=capsule_reference.replace("INPUTS:", "SCOPE:", 1)
        ),
        "coordinator restored as default": variant(
            skill=skill.replace(
                "`COMPACT_COORDINATOR` 只在用户明确要求旧主任务压缩后继续验收时使用",
                "`COMPACT_COORDINATOR` 默认用于高风险任务",
                1,
            )
        ),
        "read-only commit id restored": variant(
            capsule_reference=capsule_reference.replace(
                "READ_ONLY_OMIT_COMMIT_ID=YES",
                "READ_ONLY_OMIT_COMMIT_ID=NO",
                1,
            )
        ),
        "passive return write enabled": variant(
            passive_return=passive_return.replace(
                "TASK_KIND: READ_ONLY", "TASK_KIND: WRITE", 1
            )
        ),
        "passive context inherited": variant(
            passive_return=passive_return.replace(
                "FORK_CONTEXT: false", "FORK_CONTEXT: true", 1
            )
        ),
        "multiple passive children": variant(
            passive_return=passive_return.replace("children=1", "children=2", 1)
        ),
        "multiple passive waits": variant(
            passive_return=passive_return.replace("waits=1", "waits=2", 1)
        ),
        "passive correction enabled": variant(
            passive_return=passive_return.replace("corrections=0", "corrections=1", 1)
        ),
        "passive raw logs allowed": variant(
            passive_return=passive_return.replace(
                "RAW_LOG_OUTPUT: FORBIDDEN", "RAW_LOG_OUTPUT: ALLOWED", 1
            )
        ),
        "passive automatic fallback": variant(
            skill=skill.replace("不自动改用其他模式", "自动改用 HANDOFF", 1)
        ),
        "parent rereads raw logs": variant(
            passive_return=passive_return.replace(
                "不得重新读取原始日志", "重新读取原始日志", 1
            )
        ),
        "session write enabled": variant(
            passive_session=passive_session.replace(
                "TASK_KIND: READ_ONLY", "TASK_KIND: WRITE", 1
            )
        ),
        "session context inherited": variant(
            passive_session=passive_session.replace(
                "FORK_CONTEXT: false", "FORK_CONTEXT: true", 1
            )
        ),
        "session third round": variant(
            passive_session=passive_session.replace("rounds=2", "rounds=3", 1)
        ),
        "session second child": variant(
            passive_session=passive_session.replace("children=1", "children=2", 1)
        ),
        "session extra input": variant(
            passive_session=passive_session.replace("send_inputs=1", "send_inputs=2", 1)
        ),
        "session extra wait": variant(
            passive_session=passive_session.replace("waits=2", "waits=3", 1)
        ),
        "session correction enabled": variant(
            passive_session=passive_session.replace("corrections=0", "corrections=1", 1)
        ),
        "session full context round": variant(
            passive_session=passive_session.replace(
                "ROUND_INPUT: DELTA_ONLY", "ROUND_INPUT: FULL_CONTEXT", 1
            )
        ),
        "session raw logs allowed": variant(
            passive_session=passive_session.replace(
                "RAW_LOG_OUTPUT: FORBIDDEN", "RAW_LOG_OUTPUT: ALLOWED", 1
            )
        ),
        "session automatic round two": variant(
            passive_session=passive_session.replace(
                "第一轮足够时立即结束", "第一轮后自动启动第二轮", 1
            )
        ),
        "session allows round three": variant(
            passive_session=passive_session.replace(
                "预计需要第三轮时直接使用 `HANDOFF`", "允许进入第三轮", 1
            )
        ),
        "completion notification ignored": variant(
            skill=skill.replace(
                "完成通知已包含最终 capsule 时直接使用",
                "完成通知后仍调用 wait_agent",
                1,
            )
        ),
        "disk config treated active": variant(
            context_gate=context_gate.replace(
                "当前任务不使用该值；新任务重新验证",
                "当前任务直接使用磁盘值",
                1,
            )
        ),
        "invalid compact limit accepted": variant(
            context_gate=context_gate.replace(
                "不得依赖自动压缩",
                "继续依赖自动压缩",
                1,
            )
        ),
        "auto compact treated as cost control": variant(
            skill=skill.replace(
                "自动压缩只防溢出，不保费用",
                "自动压缩同时保证费用上限",
                1,
            )
        ),
        "unknown context allows session": variant(
            context_gate=context_gate.replace(
                "`PASSIVE_SESSION` 返回 `CONTEXT_GAP`",
                "`PASSIVE_SESSION` 继续执行",
                1,
            )
        ),
        "automatic compact execution": variant(
            skill=skill.replace(
                "当前工具面不能主动执行 `/compact`",
                "当前任务自动执行 `/compact`",
                1,
            )
        ),
        "invalid percentage ordering": variant(
            context_gate=context_gate.replace(
                "PASSIVE_RETURN_MAX_PERCENT: 55",
                "PASSIVE_RETURN_MAX_PERCENT: 35",
                1,
            )
        ),
        "cumulative token usage": variant(
            context_gate=context_gate.replace(
                "last_token_usage.input_tokens",
                "total_token_usage.total_tokens",
                1,
            )
        ),
        "cached input deducted": variant(
            context_gate=context_gate.replace(
                "缓存输入仍占上下文，不得扣除",
                "缓存输入从上下文扣除",
                1,
            )
        ),
        "stale sample accepted": variant(
            context_gate=context_gate.replace(
                "超过 `CONTEXT_SAMPLE_MAX_AGE` 标记 `STALE`",
                "过期样本继续使用",
                1,
            )
        ),
        "context base uses maximum": variant(
            context_gate=context_gate.replace(
                "CONTEXT_BASE: min(EFFECTIVE_CONTEXT_WINDOW, 有效 AUTO_COMPACT_LIMIT, 已知 COST_CLIFF_TOKENS)",
                "CONTEXT_BASE: max(EFFECTIVE_CONTEXT_WINDOW, AUTO_COMPACT_LIMIT)",
                1,
            )
        ),
        "hysteresis removed": variant(
            context_gate=context_gate.replace(
                "HYSTERESIS_PERCENT: 5",
                "HYSTERESIS_PERCENT: 0",
                1,
            )
        ),
        "cost cliff guessed": variant(
            context_gate=context_gate.replace(
                "COST_CLIFF_TOKENS: 运行时明确值或 UNKNOWN",
                "COST_CLIFF_TOKENS: 根据模型名称猜测",
                1,
            )
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
        f"passive:{metrics['passive_return_estimated_tokens']} "
        f"session:{metrics['passive_session_estimated_tokens']} "
        f"context:{metrics['context_gate_estimated_tokens']} "
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
        "  passive_capsules="
        f"collector:{metrics['collector_capsule_lines']}/{MAX_COLLECTOR_CAPSULE_LINES} "
        f"return:{metrics['return_capsule_lines']}/{MAX_RETURN_CAPSULE_LINES}"
    )
    print(
        "  session_capsules="
        f"session:{metrics['session_capsule_lines']}/{MAX_SESSION_CAPSULE_LINES} "
        f"delta:{metrics['round_delta_lines']}/{MAX_ROUND_DELTA_LINES} "
        f"return:{metrics['session_return_lines']}/{MAX_SESSION_RETURN_LINES}"
    )
    print(
        "  context_policy="
        f"{metrics['context_policy_lines']}/{MAX_CONTEXT_POLICY_LINES} "
        f"gate:{metrics['context_gate_lines']}/{MAX_CONTEXT_GATE_LINES}"
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
    passive_return = PASSIVE_RETURN_PATH.read_text(encoding="utf-8")
    passive_session = PASSIVE_SESSION_PATH.read_text(encoding="utf-8")
    context_gate = CONTEXT_GATE_PATH.read_text(encoding="utf-8")
    errors, metrics = validate_contract(
        skill,
        coordinator,
        capsule_reference,
        staged_review,
        log_analysis,
        passive_return,
        passive_session,
        context_gate,
    )
    errors.extend(
        mutation_self_test(
            skill,
            coordinator,
            capsule_reference,
            staged_review,
            log_analysis,
            passive_return,
            passive_session,
            context_gate,
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
