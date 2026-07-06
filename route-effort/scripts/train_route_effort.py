#!/usr/bin/env python3
"""Route-effort SkillOpt 训练脚本。

功能：
1. 把 ~/.gstack/route-effort-usage.jsonl 转为训练数据
2. 调用 SkillOpt 训练
3. 用 best_skill.md 更新 SKILL.md
"""
import json
import subprocess
import shutil
import datetime
from pathlib import Path

# 路径配置
SKILL_DIR = Path.home() / ".claude" / "skills" / "vlong" / "route-effort"
SKILL_OPT_DIR = SKILL_DIR / "skill-opt"
LOG_FILE = SKILL_OPT_DIR / "route-effort-usage.jsonl"
SKILL_PATH = SKILL_DIR / "SKILL.md"
DATA_DIR = SKILL_OPT_DIR / "train-data"
OUT_DIR = SKILL_OPT_DIR / "skillopt-out"
SKILLOPT_ENV = SKILL_OPT_DIR

# 最小数据量要求
MIN_ENTRIES = 50

def load_usage_log() -> list[dict]:
    """加载使用日志。"""
    if not LOG_FILE.exists():
        print(f"❌ 使用日志不存在: {LOG_FILE}")
        return []

    entries = []
    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries

def convert_to_training_data(entries: list[dict]) -> list[dict]:
    """把使用日志转为训练数据格式。

    注意：使用日志只有"触发了/没触发"，没有 ground truth。
    这里假设：如果 output_snippet 非空，说明触发了。
    """
    items = []
    for i, entry in enumerate(entries):
        query = entry.get("args", "")
        if not query or not isinstance(query, str):
            continue

        items.append({
            "id": f"usage-{i}",
            "query": query,
            "should_trigger": entry.get("triggered", False)
        })

    return items

def split_data(items: list[dict]) -> dict[str, list[dict]]:
    """80/10/10 拆分为 train/val/test。"""
    n = len(items)
    return {
        "train": items[:int(n * 0.8)],
        "val": items[int(n * 0.8):int(n * 0.9)],
        "test": items[int(n * 0.9):]
    }

def prepare_training_data():
    """准备训练数据文件。"""
    entries = load_usage_log()

    if len(entries) < MIN_ENTRIES:
        print(f"⚠️  数据量不足：{len(entries)}/{MIN_ENTRIES}")
        print(f"   需要更多真实使用数据才能训练。")
        print(f"   继续使用 Claude Code 几周后再运行此脚本。")
        return False

    print(f"✅ 加载 {len(entries)} 条使用记录")

    items = convert_to_training_data(entries)
    print(f"✅ 转换为 {len(items)} 条训练样本")

    splits = split_data(items)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for split_name, split_items in splits.items():
        if not split_items:
            print(f"⚠️  {split_name} split 为空，跳过")
            continue
        output_file = DATA_DIR / f"{split_name}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(split_items, f, ensure_ascii=False, indent=2)
        print(f"   {split_name}: {len(split_items)} 条 → {output_file}")

    return True

def check_skillopt_env():
    """检查 SkillOpt 环境是否就绪。"""
    if not SKILLOPT_ENV.exists():
        print(f"❌ SkillOpt 环境未准备")
        print(f"   运行: python3 {Path(__file__).parent}/prepare_skillopt_env.py")
        return False

    required_files = ["dataloader.py", "rollout.py", "initial.md"]
    for fname in required_files:
        if not (SKILLOPT_ENV / fname).exists():
            print(f"❌ 缺少文件: {SKILLOPT_ENV / fname}")
            return False

    return True

def run_skillopt():
    """调用 SkillOpt 训练。"""
    print(f"\n🚀 启动 SkillOpt 训练...")
    print(f"   输出目录: {OUT_DIR}")

    cmd = [
        "skillopt", "train",
        "--env", "route-effort",
        "--split_dir", str(DATA_DIR),
        "--out_root", str(OUT_DIR),
        "--num_epochs", "3",
        "--cfg-options",
        "model.optimizer_backend=claude_chat",
        "model.target_backend=claude_chat",
        "model.optimizer_model=claude-sonnet-4-20250514",
        "model.target_model=claude-sonnet-4-20250514",
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ SkillOpt 训练失败")
        print(e.stderr)
        return False

def apply_best_skill():
    """用 best_skill.md 替换当前 SKILL.md。"""
    best_skill = OUT_DIR / "best_skill.md"
    if not best_skill.exists():
        print(f"❌ 未找到 best_skill.md: {best_skill}")
        return

    # 备份当前版本
    backup_name = f"SKILL.md.bak.{datetime.date.today()}"
    backup_path = SKILL_PATH.parent / backup_name
    shutil.copy(SKILL_PATH, backup_path)
    print(f"📦 备份当前版本: {backup_path}")

    # 应用新版本
    shutil.copy(best_skill, SKILL_PATH)
    print(f"✅ SKILL.md 已更新")

    # 显示改进指标
    metrics_file = OUT_DIR / "metrics.json"
    if metrics_file.exists():
        with open(metrics_file) as f:
            metrics = json.load(f)
        print(f"\n📊 训练结果:")
        print(f"   验证准确率: {metrics.get('val_acc', 'N/A')}")
        print(f"   测试准确率: {metrics.get('test_acc', 'N/A')}")

def main():
    print("=" * 60)
    print("Route-Effort SkillOpt 训练")
    print("=" * 60)

    # 1. 检查环境
    if not check_skillopt_env():
        return

    # 2. 准备数据
    if not prepare_training_data():
        return

    # 3. 训练
    if not run_skillopt():
        return

    # 4. 应用结果
    apply_best_skill()

    print("\n✅ 训练完成！")
    print(f"\n下次训练：积累更多使用数据后再运行此脚本")

if __name__ == "__main__":
    main()
