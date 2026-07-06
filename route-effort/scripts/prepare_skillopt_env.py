#!/usr/bin/env python3
"""SkillOpt 环境准备脚本。

在 ~/SkillOpt/envs/route-effort/ 下创建：
- dataloader.py
- rollout.py
- initial.md
"""
import os
from pathlib import Path
import shutil

SKILLOPT_ENV = Path.home() / "SkillOpt" / "envs" / "route-effort"
SKILL_PATH = Path(__file__).parent.parent / "SKILL.md"

def create_initial_md():
    """复制当前 SKILL.md 作为 initial.md"""
    shutil.copy(SKILL_PATH, SKILLOPT_ENV / "initial.md")
    print(f"✅ initial.md created from {SKILL_PATH}")

def create_dataloader():
    """生成 dataloader.py"""
    code = '''"""Route-effort skill dataloader."""
from __future__ import annotations
import json
from pathlib import Path
from skillopt.datasets.base import SplitDataLoader

class RouteEffortDataLoader(SplitDataLoader):
    """加载触发测试数据。

    每个 item 格式：
    {
        "id": "unique-id",
        "query": "用户查询",
        "should_trigger": bool
    }
    """

    def load_raw_items(self, data_path: str) -> list[dict]:
        """从 JSON 文件加载数据。"""
        with open(data_path, encoding="utf-8") as f:
            items = json.load(f)

        # 确保每个 item 有 id
        for i, item in enumerate(items):
            if "id" not in item:
                item["id"] = f"item-{i}"

        return items
'''
    (SKILLOPT_ENV / "dataloader.py").write_text(code, encoding="utf-8")
    print("✅ dataloader.py created")

def create_rollout():
    """生成 rollout.py"""
    code = '''"""Route-effort skill rollout — 触发测试执行。"""
from __future__ import annotations
import anthropic
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_one(
    item: dict,
    out_root: str,
    skill_content: str,
    max_turns: int = 1,
    diagnostic_mode: bool = False,
    diagnostic_instruction: str = "",
    diagnostic_trace_context: str = "",
    exec_timeout: int = 120,
    max_completion_tokens: int = 16384,
) -> dict:
    """执行单个触发测试。

    Returns:
        dict with:
            - id: item id
            - hard: 1 if correct, 0 if wrong
            - agent_ok: True if executed successfully
            - response: model output
            - fail_reason: error message if failed
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # 提取 description（SkillOpt 会传入完整 SKILL.md）
    description = ""
    for line in skill_content.split("\\n"):
        if line.startswith("description:"):
            description = line.split(":", 1)[1].strip()
            break

    if not description:
        return {
            "id": item["id"],
            "hard": 0,
            "agent_ok": False,
            "fail_reason": "No description found in skill_content",
            "response": ""
        }

    prompt = f"""你有一个 skill，description 如下：

{description}

判断以下用户查询是否应该触发这个 skill。
只回答 TRIGGER 或 NO_TRIGGER，不要解释。

用户查询：{item["query"]}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )
        output = response.content[0].text.strip().upper()

        predicted_trigger = "TRIGGER" in output and "NO_TRIGGER" not in output
        expected_trigger = item["should_trigger"]
        correct = predicted_trigger == expected_trigger

        return {
            "id": item["id"],
            "hard": 1 if correct else 0,
            "agent_ok": True,
            "response": output,
            "fail_reason": ""
        }
    except Exception as e:
        return {
            "id": item["id"],
            "hard": 0,
            "agent_ok": False,
            "fail_reason": str(e),
            "response": ""
        }

def run_batch(
    items: list[dict],
    out_root: str,
    skill_content: str,
    max_turns: int = 1,
    exec_timeout: int = 120,
    workers: int = 8,
    max_completion_tokens: int = 16384,
    diagnostic_mode: bool = False,
    diagnostic_instruction: str = "",
    diagnostic_trace_context_by_id: dict[str, str] | None = None,
    task_timeout: int = 600,
) -> list[dict]:
    """并行执行批量测试。"""
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                process_one,
                item,
                out_root,
                skill_content,
                max_turns,
                diagnostic_mode,
                diagnostic_instruction,
                diagnostic_trace_context_by_id.get(item["id"], "") if diagnostic_trace_context_by_id else "",
                exec_timeout,
                max_completion_tokens,
            ): item
            for item in items
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"  [{result['id']}] hard={result['hard']} ({result['response'][:50]})")

    return results
'''
    (SKILLOPT_ENV / "rollout.py").write_text(code, encoding="utf-8")
    print("✅ rollout.py created")

def main():
    # 创建目录
    SKILLOPT_ENV.mkdir(parents=True, exist_ok=True)
    print(f"📁 Environment directory: {SKILLOPT_ENV}")

    # 生成三个文件
    create_initial_md()
    create_dataloader()
    create_rollout()

    print(f"""
✅ SkillOpt 环境准备完成！

下一步：
1. 确保有 ANTHROPIC_API_KEY 环境变量
2. 运行训练：python3 {Path(__file__).parent}/train_route_effort.py
""")

if __name__ == "__main__":
    main()
