---
name: model-delegate
description: 为 Codex 建立低上下文成本的任务分工。用于把已确认、边界清楚的工作交给新的 Codex App 顶层任务，默认单向交接并结束旧主任务；明确区分只读和写任务，并在运行面缺少硬费用熔断时先取得软预算风险确认。
---

# 模型委派

使用 Codex App 原生顶层任务。最大成本风险是旧主任务在每次唤醒时重复处理长历史，因此默认不让旧主任务等待、轮询或验收。

## 模式选择

每次只选择一种模式：

| 模式 | 适用范围 | 默认行为 |
|---|---|---|
| `INLINE` | 计划、方案整理、普通审计、信息收集、小修正 | 当前任务直接完成，不创建任务 |
| `HANDOFF` | 已确认、边界清楚的低风险或中风险工作 | 用户确认模型、effort 和软预算风险后创建新任务；旧主任务立即结束 |
| `COMPACT_COORDINATOR` | 数据库迁移、数据修复、认证授权、租户隔离、生产配置、并发、公共接口、不可逆操作，或用户明确要求独立验收 | 创建执行任务；旧主任务先暂停，用户执行 `/compact` 后最多恢复一次验收 |

默认优先级：`INLINE` > `HANDOFF` > `COMPACT_COORDINATOR`。不要因工具可用而委派。用户显式要求只读委派时使用 `HANDOFF`，仍保持单任务。

若当前任务已有长讨论、大量工具输出或多轮方案变更，禁止选择会持续唤醒旧任务的流程。使用 `HANDOFF`；高风险任务必须协调时，使用 `COMPACT_COORDINATOR`。

不要使用 `/fork` 解决上下文成本；它会复制当前聊天历史。优先创建全新任务。`create_thread` 不可用时，输出紧凑交接包，让用户通过 `/task` 开始新任务。

## 硬约束

- 只有用户显式调用本技能或明确确认委派后，才创建任务。
- 默认最多创建一个执行任务；不得自动拆成多个任务或并发。
- 始终使用保存项目的 `local` 环境和当前共享检出目录。
- 不创建、切换、合并、rebase、cherry-pick 或清理 worktree。
- 不使用子智能体协议、独立 `codex exec`、脚本编排、共享状态文件或高频轮询。
- 执行任务不得再创建任务，不得扩大范围。
- `create_thread` 没有硬 token budget 参数；不要声称已设置 token 上限。
- 当前 `create_thread` 未暴露工具调用数、运行时长、累计上下文、费用上限或任务中断参数。没有这些运行时能力时，任何提示词预算都只是软限制。
- 用户未明确接受软预算风险时，不创建 `HANDOFF` 或 `COMPACT_COORDINATOR` 任务；使用 `INLINE`。

## 与 grill-me 联动

`grill-me` 只负责质疑并收敛方案。用户随后显式调用 `$model-delegate` 或明确说“按已确认方案委派执行”时：

1. 把最终方案作为既定输入，不重复架构讨论。
2. 仍有未决范围、权限或验收条件时，留在 `INLINE` 补齐。
3. 只发送最终决策、边界、必要事实和验收条件，不发送完整聊天记录。

## COST_FIRST 上下文策略

省钱优先时使用“最短且足够”的任务说明。过短导致重新发现、追问或返工时，成本反而增加。

- capsule 不超过 20 行；`INPUTS` 最多 5 项事实，`ACCEPTANCE` 最多 5 项检查。
- 只传最终决定和无法从项目读取的事实。项目规则、代码和配置只传路径或符号，不粘贴正文。
- 不传完整聊天记录、搜索结果、日志、diff、历史失败或重复工具说明。
- 使用 `BASE_COMMIT`、文件路径、命令和测试名作为证据指针，让执行任务按需读取。
- 大输出先用过滤、聚合或索引工具提取关键段；不要让父模型读取后再人工总结。
- 父任务不得要求执行任务重述可从提交或文件直接验证的信息。

## 委派前检查

一次性完成以下检查：

1. 读取项目 `AGENTS.md`、相关目录规则及明确要求的技能。
2. 记录 `PROJECT_ROOT`、当前分支、`BASE_COMMIT`、文件边界、检查命令和相关工具。
3. 按项目要求使用 CodeGraph、OpenWolf 或其他工具；不要假设新任务继承主任务已加载的上下文或实时连接。
4. 检查 `git status`。工作区不干净时不得自动 stash、覆盖或删除用户修改；先让用户决定。
5. 工作区干净后运行 `git pull --ff-only`。无法 fast-forward 时停止，不自动 merge 或 rebase。
6. 使用 `list_projects` 确认保存项目及 `projectId`。

只做一次定向发现。不要在主任务重复扫描仓库、重新读取已确认文件或执行实现级调查。

## 模型选择

- 每次委派都要求用户明确确认规范模型名和 reasoning effort。未确认时停止，不调用 `create_thread`。
- 列出当前 `create_thread` 明确接受的全部规范模型和 effort；不得依赖用户配置的默认模型。
- 创建任务时必须显式传入已确认的 `model` 和 `thinking`，使后续默认配置变化不会改变本次任务。
- `max` 或 `ultra` 只在用户明确选择时使用；不得推荐为默认值，不得因任务复杂而自动提高。
- 不使用 provider 路由后缀、显示名或历史记录猜测模型。

## 交接包

创建任务前生成一个不超过 20 行的 `DELEGATION_CAPSULE`。创建后不再重写或扩展。

```text
DELEGATION_CAPSULE
MODE: HANDOFF | COMPACT_COORDINATOR; TASK_KIND: READ_ONLY | WRITE
DELEGATION_KEY: 唯一标识
ROLE: Standalone bounded execution task; report directly to user
PROJECT_ROOT: 共享检出目录; BASE_COMMIT: 委派前提交
MODEL: 用户确认的规范模型; THINKING: 用户确认的 effort
SCOPE: 唯一目标
INPUTS: 最多 5 项无法从项目读取的事实
ACCEPTANCE: 最多 5 项可执行检查
READ_BOUNDARIES: 允许读取的文件或目录
WRITE_BOUNDARIES: WRITE 允许修改的文件；READ_ONLY 必须为 NONE
RULES_AND_TOOLING: 路径或名称；标记 REQUIRED
CHECKS_AND_POST_ACTIONS: 命令或入口
COST_CONTROL: SOFT; USER_ACCEPTED=YES
LIMITS: tasks=1; discovery=1; tools=12; batch=4; minutes=20; retries=1
HARD_LIMITS_UNAVAILABLE: token、累计上下文、费用、外部中断
STOP_RULE: 达到软限制即返回 SOFT_BUDGET_EXHAUSTED
OUTPUT_PROFILE: TERSE_SAFE; report<=12 行; error<=3 行
CONSTRAINTS: local、无 worktree、无范围扩展、无破坏性操作
```

`READ_BOUNDARIES` 和 `WRITE_BOUNDARIES` 是硬边界。业务逻辑、架构、权限、数据范围或公共接口未在 capsule 明确授权时，执行任务必须停止。

只有运行面实际提供并启用 token、费用、工具调用、时长上限或外部中断能力时，才可把 `ENFORCEMENT` 写为 `HARD`，并记录具体工具参数和验证证据。不得把模型自报停止当作硬熔断。

`LIMITS.tools` 按底层工具调用计数；批量或并行包装中的每个子调用分别计数，不得把几十个子调用算作一次。单次批量最多包含 `LIMITS.batch` 个子调用。

`TERSE_SAFE` 只压缩过程说明和报告：

- 无前言、进度播报和重复总结。
- 不附完整日志、diff、capsule 或逐文件叙述。
- 失败只保留决定性错误，最多 3 行。
- 每个事实只写一次；保留所有否定词、数字、路径、ID 和安全约束。
- 代码、文档、提交信息和用户要求的正式产物使用正常语言。

## HANDOFF

这是默认委派模式。

1. 调用 `create_thread`，传入完整 capsule，使用保存项目的 `local` 环境。
2. 执行任务直接面向用户完成实现、验证和最终报告，不向旧主任务回传。
3. 创建成功后，旧主任务只回复任务链接、模式、目标和未验证项。
4. 立即结束旧主任务。不得调用 `wait_threads`、`read_thread`、`list_threads` 或 `send_message_to_thread` 跟踪执行。
5. 返回 `threadId` 时发出 `::created-thread{threadId="..."}`；仅返回 `clientThreadId` 时发出对应 `clientThreadId` 指令。

执行任务必须：

- 先验证 `PROJECT_ROOT`、`BASE_COMMIT`、项目规则和工作区状态。
- 使用索引、定向读取或批量工具获取最小上下文；最多一次广域发现。
- `TASK_KIND: READ_ONLY` 时不得修改文件、运行写操作、`git add` 或提交；报告省略 `COMMIT_ID`。
- `TASK_KIND: WRITE` 时只修改 `WRITE_BOUNDARIES` 内文件；运行约定检查，完成前 `git add` 预期文件并提交，返回 `COMMIT_ID`。
- 每次工具调用前更新软预算计数；达到任一软限制时停止并返回 `SOFT_BUDGET_EXHAUSTED`。
- 低风险和中风险任务自行完成差异审查及验收。
- 遇到阻塞或预算不足时在执行任务中直接向用户报告，不唤醒旧主任务。

## INLINE

不调用任务协调工具。当前任务直接完成工作并按项目规则验证。

以下情况强制使用 `INLINE`：

- 只读计划、方案整理、普通审计或信息收集，且用户未明确要求委派。
- 创建任务的固定成本高于工作本身。
- 范围仍未收敛。
- 工作区状态不满足共享检出目录安全条件。

## COMPACT_COORDINATOR

仅高风险工作或用户明确要求旧主任务独立验收时使用。选择后才读取 [references/compact-coordinator.md](references/compact-coordinator.md)。

核心限制：

- 创建执行任务后，旧主任务不得立即等待。
- 先输出 `COMPACTION_CHECKPOINT` 并要求用户执行 `/compact`。
- 用户压缩并明确要求继续验收后，旧主任务最多调用一次 `wait_threads`、一次定向审查、一次纠偏。
- 无法确认已压缩时，不恢复协调；改用新的独立审查任务。

## 执行任务报告

报告不超过 12 行：

```text
STATUS: COMPLETE | BLOCKED | SOFT_BUDGET_EXHAUSTED
DELEGATION_KEY: 原样回显
TASK_KIND: READ_ONLY | WRITE
RESULT: 完成内容
COMMIT_ID: 写任务提交；只读任务省略
FILES: 修改或检查的文件
CHECKS: 命令和简短结果
TOOLS_USED: 实际使用的关键工具
TOOLING_GAPS: 缺失工具及影响
RISKS: 未验证项
```

不要附完整日志、完整 diff、重复 capsule 或逐文件叙述。

## 失败策略

- `create_thread` 不可用：输出 capsule，让用户用 `/task` 创建新任务；不得改用 `/fork`。
- 必需工具缺失：返回 `TOOLING_GAP`；影响安全或验收时停止。
- 发现范围扩展：返回 `BLOCKED`，不自动增加任务。
- 用户未确认模型、effort 或软预算风险：使用 `INLINE`，不创建任务。
- 达到软预算：返回 `SOFT_BUDGET_EXHAUSTED`，不自动提高 effort、续派或创建替代任务。
- 用户要求硬费用上限，但运行面没有硬限制或中断能力：返回 `HARD_BUDGET_UNAVAILABLE`，不创建任务。
- 静态技能校验不证明真实任务生命周期；未经用户明确批准，不运行高成本委派 E2E。

## 回归测试

每次修改本技能后运行：

```bash
python3 model-delegate/scripts/validate_contract.py
python3 scripts/validate_repo.py
```

第一条命令使用固定历史基线检查上下文体积、估算 token、capsule 和报告行数、读写协议、模型锁定、预算语义及父任务验收上限。token 使用透明的混合文本估算：CJK 类字符按 1 token，其余内容按每 4 UTF-8 bytes 估算 1 token。

该指标只覆盖技能、capsule 和报告文本，不包含系统提示、工具 schema、聊天历史、缓存、推理或实际执行；不得当作真实账单。准确费用 E2E 只能在运行面提供可比较 usage 数据后执行。
