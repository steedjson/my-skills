---
name: agent-model-policy-sync
description: 将项目级子智能体模型与 reasoning effort 策略写入对应 Agent 指令文件。用于用户要求统一、生成、同步或修订 Codex 子智能体模型策略，或要求把模型委派约定落到 AGENTS.md/CLAUDE.md 等项目 Agent 配置中。
---

# Agent Model Policy Sync

把“子智能体该用什么模型、什么推理程度”变成项目可执行的 Agent 指令，而不是只停留在聊天约定。

## 默认范围

- Codex：`AGENTS.md`
- Claude Code：`CLAUDE.md`
- 其他宿主：只在用户明确指定对应文件时更新
- 默认只更新当前项目根目录中的目标文件；不扫描或修改用户目录、父目录和其他项目

## 工作流

1. 解析当前项目根目录。优先使用当前工作目录最近的 `.git` 根；用户指定路径时使用指定路径。
2. 先读取目标 Agent 文件和现有 `model-delegate`/模型路由规则。
3. 生成最小策略：
   - 快速浏览、搜索：便宜模型 + `low`
   - 普通编码、测试：平衡模型 + `medium`
   - 架构、复杂调试：强模型 + `high`
   - `xhigh`/`max` 只用于质量优先且明确批准的任务
4. 保留文件其余内容，只替换由本技能拥有的标记区块：

   ```md
   <!-- AGENT_MODEL_POLICY:START -->
   ...
   <!-- AGENT_MODEL_POLICY:END -->
   ```

5. 若策略不明确，使用默认策略并在结果中标注；不要虚构模型可用性。模型和 effort 必须符合目标宿主当前支持范围。
6. 默认执行同步；先展示将修改的文件和策略。用户要求只查看时使用 dry-run。
7. 同步后运行脚本自检，并报告是否创建文件、更新文件或未改动。

## 默认策略模板

```md
## 子智能体模型策略

父智能体创建子智能体时，显式指定 `model` 和 `reasoning_effort`。

| 任务 | 模型 | reasoning effort |
|---|---|---|
| 文件搜索、代码浏览、简单检查 | `gpt-5.6-luna` | `low` |
| 普通实现、测试、重构 | `gpt-5.6-terra` | `medium` |
| 架构设计、复杂调试、跨模块修改 | `gpt-5.6-sol` | `high` |
| 质量优先的极难任务 | `gpt-5.6-sol` | `xhigh` 或 `max`，需明确确认 |

不要让 `AGENTS.md` 中的约定替代创建子智能体时的运行时参数；实际调用必须传入对应模型和推理程度。
```

## 工具

需要确定性地更新文件时，运行：

```bash
python3 agent-model-policy-sync/scripts/sync_policy.py --root <project> --apply
```

预览、不写文件：

```bash
python3 agent-model-policy-sync/scripts/sync_policy.py --root <project>
```

指定宿主文件：

```bash
python3 agent-model-policy-sync/scripts/sync_policy.py \
  --root <project> --agent-file CLAUDE.md --apply
```

脚本只改标记区块；没有区块时追加；不会覆盖未标记内容。默认目标为 `AGENTS.md`。

## 不适用

- 需要修改 Codex 全局运行时模型设置，而非项目 Agent 指令时
- 需要实时查询模型目录、价格或可用性时；先查询官方文档或当前宿主能力
- 用户只要建议、不想写入项目文件时

## 输出

```md
目标：<绝对路径>
动作：created | updated | unchanged | dry-run
策略：<模型 / effort 摘要>
验证：<命令和结果>
```
