# Route-Effort SkillOpt 自训练部署清单

## ✅ 已完成

| 组件 | 状态 | 位置 |
|------|------|------|
| 使用日志脚本 | ✅ 已创建 | `route-effort/scripts/log_usage.py` |
| SkillOpt 环境准备 | ✅ 已创建 | `route-effort/scripts/prepare_skillopt_env.py` |
| 训练脚本 | ✅ 已创建 | `route-effort/scripts/train_route_effort.py` |
| 文档 | ✅ 已创建 | `route-effort/scripts/README.md` |
| Git 提交 | ✅ 已推送 | https://github.com/steedjson/my-skills |

---

## 🔧 待手动配置（5分钟）

### 1. 配置 Claude Code Hook

**文件**：`~/.claude/settings.json`

在 `hooks` 部分添加（如果已有其他 hook，追加到数组中）：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": {"tool": "Skill"},
        "hooks": [
          {
            "type": "command",
            "command": "python3 /Users/changsailong/BDSYNC/self/AI/tools/my-skills/route-effort/scripts/log_usage.py '$CLAUDE_TOOL_INPUT' '$CLAUDE_TOOL_OUTPUT'"
          }
        ]
      }
    ]
  }
}
```

**验证**：使用任意项目触发 route-effort skill 后，运行：
```bash
cat ~/.skill-opt/route-effort/route-effort-usage.jsonl
```
应该看到一条 JSON 记录。

---

### 2. 安装 SkillOpt（首次训练前）

```bash
pip install skillopt
```

**验证**：
```bash
skillopt --version
```

---

### 3. 配置 Anthropic API Key

**临时**（单次使用）：
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python3 route-effort/scripts/train_route_effort.py
```

**永久**（推荐）：在 `~/.zshrc` 或 `~/.bashrc` 添加：
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## 📊 使用流程

### 阶段1：数据收集（3-4周）

1. ✅ Hook 已配置
2. 正常使用 Claude Code，让 route-effort 自然触发
3. 定期检查数据量：
   ```bash
   wc -l ~/.skill-opt/route-effort/route-effort-usage.jsonl
   ```
4. 目标：≥50 条记录

### 阶段2：首次训练

**当数据量 ≥50 时**：

```bash
# 1. 准备 SkillOpt 环境
python3 route-effort/scripts/prepare_skillopt_env.py

# 2. 运行训练
python3 route-effort/scripts/train_route_effort.py

# 3. 检查结果
cat ~/.claude/skills/route-effort/SKILL.md  # 自动更新
```

**预期**：
- 训练时间：5-10 分钟
- 输出：`best_skill.md`
- 自动备份旧版本到 `SKILL.md.bak.2026-07-06`

### 阶段3：持续改进（可选）

**方案 A：手动触发**（推荐首次验证效果后再自动化）
```bash
# 每隔几周手动运行一次
python3 route-effort/scripts/train_route_effort.py
```

**方案 B：定时自动**（验证效果好后启用）
```bash
# 编辑 crontab
crontab -e

# 添加：每周一凌晨2点自动训练
0 2 * * 1 python3 /Users/changsailong/BDSYNC/self/AI/tools/my-skills/route-effort/scripts/train_route_effort.py >> ~/.skill-opt/route-effort/train.log 2>&1
```

---

## 📁 文件布局

```
~/.claude/skills/route-effort/
├── SKILL.md                    ← 会被自动更新
├── SKILL.md.bak.YYYY-MM-DD     ← 自动备份
└── scripts/
    ├── log_usage.py            ← Hook 调用
    ├── prepare_skillopt_env.py ← 首次训练前运行
    ├── train_route_effort.py   ← 训练脚本
    └── README.md

~/.skill-opt/route-effort/
├── route-effort-usage.jsonl    ← 使用日志（持续追加）
├── train-data/                 ← 训练数据（自动生成）
│   ├── train.json
│   ├── val.json
│   └── test.json
└── skillopt-out/               ← SkillOpt 输出
    ├── best_skill.md
    ├── metrics.json
    └── ...

~/.skill-opt/route-effort/  ← SkillOpt 环境（首次训练时生成）
├── dataloader.py
├── rollout.py
└── initial.md
```

---

## ⚠️ 注意事项

1. **数据隐私**：使用日志包含你的查询内容，敏感项目慎用
2. **API 成本**：每次训练约消耗 100-200 次 Claude API 调用
3. **Ground Truth 问题**：使用日志没有"正确答案"，只有"触发了/没触发"，这可能导致训练偏向当前行为
4. **首次训练建议手动**：验证效果好后再启用自动化

---

## 🎯 下一步

**立即执行**：
```bash
# 1. 编辑 Claude Code settings
open ~/.claude/settings.json

# 2. 添加上面的 Hook 配置

# 3. 验证 Hook 工作
# （使用任意项目触发 route-effort，然后检查日志）
cat ~/.skill-opt/route-effort/route-effort-usage.jsonl
```

**3-4周后**：
```bash
# 当数据量 ≥50 时
python3 route-effort/scripts/prepare_skillopt_env.py
python3 route-effort/scripts/train_route_effort.py
```

**完成 ✓**
