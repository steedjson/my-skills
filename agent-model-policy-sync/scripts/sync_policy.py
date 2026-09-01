#!/usr/bin/env python3
"""Idempotently add or replace a project Agent model-policy block."""
from __future__ import annotations

import argparse
from pathlib import Path

START = "<!-- AGENT_MODEL_POLICY:START -->"
END = "<!-- AGENT_MODEL_POLICY:END -->"
BLOCK = f"""{START}
## 子智能体模型策略

父智能体创建子智能体时，显式指定 `model` 和 `reasoning_effort`。

| 任务 | 模型 | reasoning effort |
|---|---|---|
| 文件搜索、代码浏览、简单检查 | `gpt-5.6-luna` | `low` |
| 普通实现、测试、重构 | `gpt-5.6-terra` | `medium` |
| 架构设计、复杂调试、跨模块修改 | `gpt-5.6-sol` | `high` |
| 质量优先的极难任务 | `gpt-5.6-sol` | `xhigh` 或 `max`，需明确确认 |

不要让 Agent 指令中的约定替代创建子智能体时的运行时参数；实际调用必须传入对应模型和推理程度。
{END}"""


def replace_block(text: str) -> tuple[str, str]:
    start = text.find(START)
    end = text.find(END)
    if start == -1 and end == -1:
        prefix = "" if not text or text.endswith("\n") else "\n"
        return text + prefix + "\n" + BLOCK + "\n", "created"
    if start == -1 or end < start:
        raise ValueError("malformed AGENT_MODEL_POLICY markers")
    end += len(END)
    updated = text[:start] + BLOCK + text[end:]
    return updated, "updated" if updated != text else "unchanged"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--agent-file", default="AGENTS.md", help="relative Agent instruction file")
    parser.add_argument("--apply", action="store_true", help="write changes; default is dry-run")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"project root is not a directory: {root}")
    target = (root / args.agent_file).resolve()
    if root not in target.parents and target != root:
        parser.error("agent file must stay inside project root")
    if target.exists() and target.is_symlink():
        parser.error(f"refusing symlink target: {target}")

    original = target.read_text(encoding="utf-8") if target.exists() else ""
    updated, action = replace_block(original)
    if args.apply and updated != original:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(updated, encoding="utf-8")

    mode = "apply" if args.apply else "dry-run"
    print(f"target: {target}")
    print(f"action: {action if args.apply else mode + ':' + action}")
    print("policy: luna/low, terra/medium, sol/high, sol/xhigh-or-max-confirmed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
