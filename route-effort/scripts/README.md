# Route-Effort SkillOpt 自动训练设置指南

本目录包含让 route-effort skill 从真实使用中自我改进的组件。

## 第一阶段：部署使用日志（当前）

### 1. 配置 Claude Code Hook

编辑 `~/.claude/settings.json`，在 `hooks` 部分添加：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": {"tool": "Skill"},
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/route-effort/scripts/log_usage.py '$CLAUDE_TOOL_INPUT' '$CLAUDE_TOOL_OUTPUT'"
          }
        ]
      }
    ]
  }
}
```

**注意**：如果 route-effort 安装在其他位置，修改路径为：
```
/Users/changsailong/BDSYNC/self/AI/tools/my-skills/route-effort/scripts/log_usage.py
```

### 2. 验证日志工作

使用任意 Claude Code 项目触发 route-effort skill 后，检查日志：

```bash
cat ~/.skill-opt/route-effort/route-effort-usage.jsonl
```

应看到 JSON 行格式的记录。

### 3. 收集数据

**目标**：收集至少 50 条真实使用记录后再启动训练。

**查看当前数据量**：
```bash
wc -l ~/.skill-opt/route-effort/route-effort-usage.jsonl
```

---

## 第二阶段：SkillOpt 训练（数据量 ≥50 后执行）

### 1. 安装 SkillOpt

```bash
pip install skillopt
```

### 2. 创建 SkillOpt 环境

运行准备脚本：
```bash
python3 route-effort/scripts/prepare_skillopt_env.py
```

这会创建：
- `~/SkillOpt/envs/route-effort/` 目录
- `dataloader.py`、`rollout.py`、`initial.md`

### 3. 手动训练（首次）

```bash
python3 route-effort/scripts/train_route_effort.py
```

检查输出：
```bash
cat ~/.skill-opt/route-effort/skillopt-out/best_skill.md
```

如果效果好，脚本会自动备份旧 SKILL.md 并应用新版本。

### 4. 定时自动训练（可选）

**方案 A：系统 cron**
```bash
crontab -e
# 添加：每周一凌晨2点自动训练
0 2 * * 1 python3 /Users/changsailong/BDSYNC/self/AI/tools/my-skills/route-effort/scripts/train_route_effort.py >> ~/.skill-opt/route-effort/train.log 2>&1
```

**方案 B：Claude Code `/loop` skill**
```
/loop 1w python3 route-effort/scripts/train_route_effort.py
```

---

## 文件说明

| 文件 | 作用 |
|------|------|
| `log_usage.py` | Hook 脚本，记录每次 skill 触发 |
| `train_route_effort.py` | 训练脚本，调用 SkillOpt |
| `prepare_skillopt_env.py` | 生成 SkillOpt 所需的三个文件 |
| `~/.skill-opt/route-effort/route-effort-usage.jsonl` | 使用日志 |
| `~/.skill-opt/route-effort/skillopt-out/` | SkillOpt 输出目录 |

---

## 当前状态

✅ **阶段1完成**：使用日志已部署
⏳ **阶段2待执行**：等待数据积累到 50+ 条

**下一步**：配置 Hook，然后正常使用 Claude Code 几周，让数据自然积累。
