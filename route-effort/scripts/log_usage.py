#!/usr/bin/env python3
"""Route-effort skill 使用日志收集器。

由 Claude Code PostToolUse hook 调用，记录每次 skill 触发事件。
"""
import json
import sys
import datetime
import re
from pathlib import Path
from fcntl import flock, LOCK_EX, LOCK_UN

SKILL_DIR = Path.home() / ".claude" / "skills" / "vlong" / "route-effort"
SKILL_OPT_DIR = SKILL_DIR / "skill-opt"
LOG_FILE = SKILL_OPT_DIR / "route-effort-usage.jsonl"
MAX_LOG_SIZE_MB = 10  # 日志文件大小上限（MB）


def redact_secrets(text: str) -> str:
    """移除明显的 secrets（API keys, tokens, passwords）。"""
    if not isinstance(text, str):
        text = str(text)
    # 移除常见 secret 模式
    text = re.sub(r'(api[_-]?key|token|password|secret|bearer)["\s:=]+[\w\-]{16,}',
                  r'\1=***', text, flags=re.IGNORECASE)
    # 移除 sk-*, ghp-*, gho-* 等前缀 token
    text = re.sub(r'\b(sk|ghp|gho|glpat|xox[apbors])-[\w]{20,}\b', r'\1-***', text)
    return text


def main():
    # 只有安装了 --with-skill-opt 时才记录
    # 默认纯 skill 安装不创建 skill-opt/，因此静默跳过
    if not SKILL_OPT_DIR.exists():
        return

    # 解析 hook 传入的参数
    tool_input = sys.argv[1] if len(sys.argv) > 1 else "{}"
    tool_output = sys.argv[2] if len(sys.argv) > 2 else ""

    try:
        input_data = json.loads(tool_input)
    except json.JSONDecodeError:
        input_data = {"raw": tool_input}

    # 构造日志条目（过滤 secrets）
    entry = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "skill": input_data.get("skill", "route-effort"),
        "args": redact_secrets(str(input_data.get("args", ""))[:200]),
        "output_snippet": redact_secrets(tool_output[:300]),
        "triggered": len(tool_output) > 0,
    }

    # 大小检查：超过限制则截断（保留最新一半）
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_SIZE_MB * 1024 * 1024:
        try:
            lines = LOG_FILE.read_text(encoding='utf-8').strip().split('\n')
            keep_lines = lines[len(lines)//2:]
            LOG_FILE.write_text('\n'.join(keep_lines) + '\n', encoding='utf-8')
        except Exception:
            pass  # 截断失败不影响后续写入

    # 带文件锁的追加写入
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            flock(f.fileno(), LOCK_EX)
            try:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            finally:
                flock(f.fileno(), LOCK_UN)
    except (IOError, OSError):
        # 权限/锁失败静默跳过，不破坏 hook
        pass

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 静默失败，不打断主流程
        error_log = SKILL_OPT_DIR / "log-errors.txt"
        with open(error_log, "a") as f:
            f.write(f"{datetime.datetime.utcnow().isoformat()}: {e}\n")
