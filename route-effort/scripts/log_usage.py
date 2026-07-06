#!/usr/bin/env python3
"""Route-effort skill 使用日志收集器。

由 Claude Code PostToolUse hook 调用，记录每次 skill 触发事件。
"""
import json
import sys
import datetime
from pathlib import Path

LOG_FILE = Path.home() / ".gstack" / "route-effort-usage.jsonl"

def main():
    # 确保日志目录存在
    LOG_FILE.parent.mkdir(exist_ok=True)

    # 解析 hook 传入的参数
    tool_input = sys.argv[1] if len(sys.argv) > 1 else "{}"
    tool_output = sys.argv[2] if len(sys.argv) > 2 else ""

    try:
        input_data = json.loads(tool_input)
    except json.JSONDecodeError:
        input_data = {"raw": tool_input}

    # 构造日志条目
    entry = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "skill": input_data.get("skill", "route-effort"),
        "args": input_data.get("args", ""),
        "output_snippet": tool_output[:300],  # 只保留前300字符
        "triggered": len(tool_output) > 0,
    }

    # 追加写入 JSONL
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 静默失败，不打断主流程
        error_log = Path.home() / ".gstack" / "route-effort-log-errors.txt"
        with open(error_log, "a") as f:
            f.write(f"{datetime.datetime.utcnow().isoformat()}: {e}\n")
