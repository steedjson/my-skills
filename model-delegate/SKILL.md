---
name: model-delegate
description: 为 Codex 建立低上下文成本的任务分工。用于把已确认、边界清楚的实现交给新的 Codex App 顶层任务，默认单向交接并结束旧主任务；只读工作默认留在当前任务，高风险工作可选压缩后协调验收。
---

# 模型委派

使用 Codex App 原生顶层任务。最大成本风险是旧主任务在每次唤醒时重复处理长历史，因此默认不让旧主任务等待、轮询或验收。

## 模式选择

每次只选择一种模式：

| 模式 | 适用范围 | 默认行为 |
|---|---|---|
| `INLINE` | 计划、方案整理、普通审计、信息收集、小修正 | 当前任务直接完成，不创建任务 |
| `HANDOFF` | 已确认、边界清楚的低风险或中风险实现 | 创建一个全新执行任务，旧主任务立即结束 |
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

## 与 grill-me 联动

`grill-me` 只负责质疑并收敛方案。用户随后显式调用 `$model-delegate` 或明确说“按已确认方案委派执行”时：

1. 把最终方案作为既定输入，不重复架构讨论。
2. 仍有未决范围、权限或验收条件时，留在 `INLINE` 补齐。
3. 只发送最终决策、边界、必要事实和验收条件，不发送完整聊天记录。

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

- 用户明确指定规范模型名和 reasoning effort：按当前 `create_thread` 接受的组合传入。
- 用户未指定：省略 `model` 和 `thinking`，使用用户配置的运行时默认值。
- 用户要求选择，或指定组合被拒绝：列出当前 `create_thread` 明确接受的全部规范模型和 effort。
- `max` 或 `ultra` 只在用户显式指定时使用；不得因任务复杂而自动提高。
- 不使用 provider 路由后缀、显示名或历史记录猜测模型。

## 交接包

创建任务前生成一个不超过 30 行的 `DELEGATION_CAPSULE`。创建后不再重写或扩展。

```text
DELEGATION_CAPSULE
MODE: HANDOFF | COMPACT_COORDINATOR
ROLE: Standalone bounded execution task; report directly to user
DELEGATION_KEY: 唯一标识
PROJECT_ROOT: 共享主项目检出目录
BASE_COMMIT: 委派前提交
SCOPE: 唯一目标
INPUTS: 已确认的最小事实
ACCEPTANCE: 可执行验收条件
FILE_BOUNDARIES: 允许读取和修改的文件
PROJECT_RULES: 规则读取顺序
PROJECT_TOOLING: 仅列本任务需要的工具及 REQUIRED 状态
CHECKS: 必须运行的检查
POST_COMMIT_ACTIONS: 明确存在的收尾动作
COST_BUDGET:
  MAX_DELEGATED_TASKS: 1
  MAX_BROAD_DISCOVERY_PASSES: 1
  MAX_REPORT_LINES: 20
  STOP_RULE: 超出范围或预算时立即返回 BLOCKED 或 BUDGET_EXHAUSTED
CONSTRAINTS: local、无 worktree、无范围扩展、无破坏性操作
```

`FILE_BOUNDARIES` 是硬边界。业务逻辑、架构、权限、数据范围或公共接口未在 capsule 明确授权时，执行任务必须停止。

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
- 只修改 `FILE_BOUNDARIES` 内文件。
- 运行约定检查；完成前 `git add` 预期文件并提交，返回 `COMMIT_ID`。
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

报告不超过 20 行：

```text
STATUS: COMPLETE | BLOCKED | BUDGET_EXHAUSTED
DELEGATION_KEY: 原样回显
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
- 预计超出预算：返回 `BUDGET_EXHAUSTED`，不自动提高 effort、续派或创建替代任务。
- 静态技能校验不证明真实任务生命周期；未经用户明确批准，不运行高成本委派 E2E。
