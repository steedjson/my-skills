---
name: model-delegate
description: 为 Codex 建立低上下文成本的任务分工。用于判断工作应留在当前任务、由用户选定的只读辅助模型被动回传、单向交接、分阶段独立审查或显式压缩协调；支持受限日志分析、软预算和用户确认后的可选真实 E2E。
---

# 模型委派

使用 Codex 原生子智能体和 Codex App 顶层任务。最大成本风险是主任务反复处理长历史，因此只允许明确受限的一次性返回，禁止轮询式协调。

核心协议不得依赖特定代理、供应商、价格表、本地计费数据库或 usage API。运行环境没有费用或 token 数据时，委派流程仍应正常工作。

## 委派准入

先判断是否值得创建新顶层任务。

以下情况使用 `INLINE`：

- 预计不超过 6 次底层工具调用、3 个文件，且无大日志或大型产物。
- 计划、普通审计、信息收集、小修正，或范围仍未收敛。
- 创建任务成本高于工作本身，或共享检出目录状态不安全。

用户明确要求且满足以下任一条件时才考虑委派：

- 预计需要 7 次以上底层工具调用、跨多个模块或多轮执行。
- 需要处理长日志、大型输出、依赖树或其他大产物。
- 当前任务已有长历史，且结果可由新任务独立完成并直接报告用户。
- 主任务仍需最终判断，但只需要一个只读证据摘要。

这些数量是软判断，不是硬费用保证。高风险工作即使规模较小，也可进入 `STAGED_REVIEW`。

## 模式选择

每次只选择一种模式：

| 模式 | 适用范围 | 默认行为 |
|---|---|---|
| `INLINE` | 未通过委派准入或范围未收敛 | 当前任务直接完成，不创建任务 |
| `PASSIVE_RETURN` | 主任务仍需最终判断，且只需只读证据或大型输出摘要 | 创建一个无历史继承的子智能体；完成后被动返回一次；主任务继续 |
| `HANDOFF` | 已确认、边界清楚的低风险或中风险工作 | 创建新任务；旧主任务立即结束 |
| `STAGED_REVIEW` | 数据迁移、数据修复、认证授权、租户隔离、生产配置、并发、公共接口、不可逆操作或其他高风险工作 | 执行任务完成后输出短审查包；用户明确触发全新审查任务；旧主任务永不恢复 |
| `COMPACT_COORDINATOR` | 用户明确要求旧主任务在 `/compact` 后继续验收 | 创建执行任务；旧主任务压缩后最多恢复一次 |

默认优先级：`INLINE` > `PASSIVE_RETURN` > `HANDOFF` > `STAGED_REVIEW`。`COMPACT_COORDINATOR` 只在用户明确要求旧主任务压缩后继续验收时使用。

主任务上下文较短或中等、仍需结果时使用 `PASSIVE_RETURN`。主任务已很长时，普通工作使用 `HANDOFF`，高风险工作使用 `STAGED_REVIEW`。

不要使用 `/fork` 解决上下文成本；它会复制当前聊天历史。优先创建全新任务。`create_thread` 不可用时，输出紧凑交接包，让用户通过 `/task` 开始新任务。

## 硬约束

- 只有用户显式调用本技能或明确确认委派后，才创建任务。
- 默认最多创建一个执行任务；不得自动拆成多个任务或并发。
- 顶层任务始终使用保存项目的 `local` 环境和共享检出目录，不使用 worktree。
- `PASSIVE_RETURN` 只读子智能体不得调用 worktree 管理工具或依赖子工作区写入。
- 只有 `PASSIVE_RETURN` 可创建一个原生只读子智能体；其他模式不使用子智能体协议。
- 不使用独立 `codex exec`、脚本编排、共享状态文件或高频轮询。
- 执行任务不得再创建任务，不得扩大范围。
- `PASSIVE_RETURN` 子智能体不得写文件、继承父聊天或创建后代。
- `STAGED_REVIEW` 的审查任务必须由用户明确触发；执行任务不得创建审查任务。
- 不读取特定代理的数据库、日志或价格表作为核心流程前置条件。
- `create_thread` 没有硬 token budget 参数；不要声称已设置 token 上限。
- 当前 `create_thread` 未暴露工具调用数、运行时长、累计上下文、费用上限或任务中断参数。没有这些运行时能力时，任何提示词预算都只是软限制。
- 用户未明确接受软预算风险时，不创建任何委派；使用 `INLINE`。
- 用户在原请求中已给出模型、effort 和软预算接受声明时，视为完成确认，不额外增加确认回合。

## 与 grill-me 联动

`grill-me` 只负责收敛方案。用户随后明确要求委派时，把最终方案作为既定输入；仍有未决范围、权限或验收条件时留在 `INLINE`。只发送最终决策、边界、必要事实和验收条件。

## COST_FIRST 上下文策略

省钱优先时使用“最短且足够”的任务说明。过短导致重新发现、追问或返工时，成本反而增加。

- capsule 不超过 20 行；`INPUTS` 最多 5 项事实，`ACCEPTANCE` 最多 5 项检查。
- 只传最终决定和无法从项目读取的事实；项目内容使用路径、符号、`BASE_COMMIT`、命令和测试名作为指针。
- 不传完整聊天、搜索结果、日志、diff、历史失败或重复工具说明。
- 大输出先用过滤、聚合或索引工具提取关键段；不要让父模型读取后再人工总结。
- 父任务不得要求执行任务重述可从提交或文件直接验证的信息。

## 委派前检查

一次性完成以下检查：

1. 读取项目 `AGENTS.md`、相关目录规则及明确要求的技能。
2. 记录 `PROJECT_ROOT`、分支、`BASE_COMMIT`、边界、检查和必需工具；不要假设新任务继承实时连接。
3. 检查 `git status`；不干净时不 stash、覆盖或删除。干净后运行 `git pull --ff-only`，失败时停止。
4. 顶层任务模式使用 `list_projects` 确认保存项目及 `projectId`。

只做一次定向发现。不要在主任务重复扫描仓库、重新读取已确认文件或执行实现级调查。

## 模型选择

- 每次委派都要求用户明确确认规范模型名和 reasoning effort。未确认时停止。
- 列出所选运行时工具明确接受的全部规范模型和 effort；不得依赖默认模型。
- `PASSIVE_RETURN` 显式传入子智能体 `model` 和 `reasoning_effort`；顶层模式显式传入 `model` 和 `thinking`。
- `max` 或 `ultra` 只在用户明确选择时使用；不得推荐为默认值，不得因任务复杂而自动提高。
- 不从路由后缀、显示名或历史记录猜测模型。

## 交接包

`HANDOFF`、`STAGED_REVIEW` 或 `COMPACT_COORDINATOR` 通过准入并完成确认后，才读取 [references/delegation-capsule.md](references/delegation-capsule.md)。`INLINE` 和 `PASSIVE_RETURN` 不读取该文件。

创建任务前生成不超过 20 行的 `DELEGATION_CAPSULE`。创建后不重写、不扩展；读写边界、预算语义和报告压缩规则以该 reference 为准。

## LOG_ANALYSIS profile

日志、测试输出、依赖树或其他大型文本证据使用 `PROFILE: LOG_ANALYSIS`，模式选择 `PASSIVE_RETURN`、`HANDOFF` 或 `STAGED_REVIEW`。选择后才读取 [references/log-analysis.md](references/log-analysis.md)。

核心限制：

- 固定 `TASK_KIND: READ_ONLY`，要求明确时间范围、输入位置和分析问题。
- 最多一次原始数据扫描；优先使用当前环境可用的索引、过滤或聚合工具。
- 不要求特定工具存在；没有安全过滤方法时返回 `TOOLING_GAP`。
- 不在任务包或报告中传递完整原始日志。

## PASSIVE_RETURN

主任务仍需最终判断、当前上下文尚可继续且子任务严格只读时使用。选择后才读取 [references/passive-return.md](references/passive-return.md)。

核心限制：

- 使用一个原生子智能体，`fork_context=false`，显式传入用户确认的模型和 effort。
- 主任务最多调用一次 `wait_agent`；不调用 `send_input`，不做纠偏或第二次等待。
- 子智能体返回不超过 10 行的 `RETURN_CAPSULE`；主任务不读取原始日志或重复执行同一调查。
- 子智能体工具不可用、超时或协议不合格时返回 `TOOLING_GAP` 或 `BLOCKED`，不自动改用其他模式。

## HANDOFF

这是默认顶层委派模式。生命周期、执行边界和报告格式见 [references/delegation-capsule.md](references/delegation-capsule.md)。创建后旧主任务立即结束，不等待、不读取、不发送消息跟踪执行。

## INLINE

不调用任务协调工具。当前任务直接完成工作并按项目规则验证。

以下情况强制使用 `INLINE`：

- 只读计划、方案整理、普通审计或信息收集，且用户未明确要求委派。
- 创建任务的固定成本高于工作本身。
- 范围仍未收敛。
- 工作区状态不满足共享检出目录安全条件。

`INLINE` 可由当前任务直接完成，或由当前任务按自身规则选择原生子智能体；本技能不编排该子智能体流程。

## STAGED_REVIEW

高风险工作默认使用本模式。选择后才读取 [references/staged-review.md](references/staged-review.md)。

核心限制：

- 旧主任务创建执行任务后立即结束，不等待、不恢复、不验收。
- 执行任务完成后输出不超过 12 行的 `REVIEW_CAPSULE`。
- 用户明确要求审查后，才创建全新审查任务。
- 执行任务不得创建审查任务；审查任务不得重新读取完整历史或原始日志。

## COMPACT_COORDINATOR

仅用户明确要求旧主任务在 `/compact` 后继续独立验收时使用。选择后才读取 [references/compact-coordinator.md](references/compact-coordinator.md)。

核心限制：

- 创建执行任务后，旧主任务不得立即等待。
- 先输出 `COMPACTION_CHECKPOINT` 并要求用户执行 `/compact`。
- 用户压缩并明确要求继续验收后，旧主任务最多调用一次 `wait_threads`、一次定向审查、一次纠偏。
- 无法确认已压缩时，不恢复协调；改用新的独立审查任务。

## 失败策略

- `create_thread` 不可用：输出 capsule，让用户用 `/task` 创建新任务；不得改用 `/fork`。
- 原生子智能体工具不可用：`PASSIVE_RETURN` 返回 `TOOLING_GAP`；未经用户决定不自动改用顶层任务。
- 必需工具缺失：返回 `TOOLING_GAP`；影响安全或验收时停止。
- 发现范围扩展：返回 `BLOCKED`，不自动增加任务。
- 用户未确认模型、effort 或软预算风险：使用 `INLINE`，不创建任务。
- 达到软预算：返回 `SOFT_BUDGET_EXHAUSTED`，不自动提高 effort、续派或创建替代任务。
- 用户要求硬费用上限，但运行面没有硬限制或中断能力：返回 `HARD_BUDGET_UNAVAILABLE`，不创建任务。
- 静态技能校验不证明真实任务生命周期；真实委派 E2E 仅在用户明确确认后运行。

## 验证策略

每次修改本技能后运行：

```bash
python3 model-delegate/scripts/validate_contract.py
python3 scripts/validate_repo.py
```

这些静态门禁不调用模型、不创建任务、不依赖外部代理或计费环境，默认执行。

真实委派 E2E 是辅助验证。用户在当前请求中未明确批准时，修改完成后只询问一次；不得自动创建测试任务。用户不运行时报告：

```text
STATIC_VALIDATION: PASS
LIVE_E2E: NOT_RUN_BY_USER_CHOICE
```

运行时 usage 属于可选外部证据。缺失时报告 `RUNTIME_USAGE: UNAVAILABLE` 和 `COST_SAVINGS: NOT_VERIFIED`，不得阻塞核心流程，也不得从模型名或历史价格推算真实费用。

静态 token 估算仅覆盖技能、capsule 和报告文本：CJK 类字符按 1 token，其他内容按每 4 UTF-8 bytes 估算 1 token；不得当作真实账单。
