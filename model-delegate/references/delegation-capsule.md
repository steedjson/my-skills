# Delegation Capsule

仅实际创建执行任务时读取本文件。

创建任务前生成一个不超过 20 行的 `DELEGATION_CAPSULE`。创建后不再重写或扩展。

```text
DELEGATION_CAPSULE
MODE: HANDOFF | STAGED_REVIEW | COMPACT_COORDINATOR; PROFILE: STANDARD | LOG_ANALYSIS; TASK_KIND: READ_ONLY | WRITE
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
REVIEW_POLICY: NONE | FRESH_USER_TRIGGERED | COMPACT_PARENT
COST_CONTROL: SOFT; USER_ACCEPTED=YES
LIMITS: tasks=1; discovery=1; tools=12; batch=4; minutes=20; retries=1
HARD_LIMITS_UNAVAILABLE: token、累计上下文、费用、外部中断
STOP_RULE: 达到软限制即返回 SOFT_BUDGET_EXHAUSTED
OUTPUT_PROFILE: TERSE_SAFE; one_field_per_line=YES; READ_ONLY_OMIT_COMMIT_ID=YES; report<=12 行; error<=3 行
CONSTRAINTS: local、无 worktree、无范围扩展、无破坏性操作
```

`READ_BOUNDARIES` 和 `WRITE_BOUNDARIES` 是硬边界。业务逻辑、架构、权限、数据范围或公共接口未在 capsule 明确授权时，执行任务必须停止。

只有运行面实际提供并启用 token、费用、工具调用、时长上限或外部中断能力时，才可把 `ENFORCEMENT` 写为 `HARD`，并记录具体工具参数和验证证据。不得把模型自报停止当作硬熔断。

`LIMITS.tools` 按底层工具调用计数；批量或并行包装中的每个子调用分别计数。单次批量最多包含 `LIMITS.batch` 个子调用。

`TERSE_SAFE` 只压缩过程说明和报告：

- 无前言、进度播报和重复总结。
- 模板字段逐行输出，不拼接；`READ_ONLY` 报告省略 `COMMIT_ID`。
- 不附完整日志、diff、capsule 或逐文件叙述。
- 失败只保留决定性错误，最多 3 行。
- 每个事实只写一次；保留所有否定词、数字、路径、ID 和安全约束。
- 代码、文档、提交信息和用户要求的正式产物使用正常语言。

## HANDOFF 生命周期

1. 调用 `create_thread`，传入完整 capsule，使用保存项目的 `local` 环境。
2. 执行任务直接面向用户完成工作，不向旧主任务回传。
3. 创建成功后，旧主任务只回复任务链接、模式、目标和未验证项，然后立即结束。
4. 不调用 `wait_threads`、`read_thread`、`list_threads` 或 `send_message_to_thread` 跟踪执行。
5. 返回 `threadId` 时发出 `::created-thread{threadId="..."}`；仅返回 `clientThreadId` 时使用对应指令。

执行任务先验证项目、基线、规则和工作区。`READ_ONLY` 不修改、暂存或提交；`WRITE` 只修改授权边界，运行检查后提交。达到软限制时返回 `SOFT_BUDGET_EXHAUSTED`，不唤醒旧主任务。

## 执行报告

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
