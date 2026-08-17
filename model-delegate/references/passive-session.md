# Passive Session

仅 `PASSIVE_SESSION` 模式读取本文件。

## 目标

复用一个无父历史的只读子智能体处理最多两轮依赖式问题。第一轮足够时立即结束，不为“可能有用”自动启动第二轮。

## 前置条件

- 用户一次性确认模型、reasoning effort、最多两轮和软预算风险。
- 第二轮问题必须依赖第一轮结果，并保持相同输入位置、读取边界和业务目标。
- 可预先确定的问题应合并到一次 `PASSIVE_RETURN`；预计需要第三轮时直接使用 `HANDOFF`。
- 主任务上下文已很长、高风险或涉及写入时不得使用。

## Session Capsule

```text
SESSION_CAPSULE
MODE: PASSIVE_SESSION; TASK_KIND: READ_ONLY; PROFILE: STANDARD | LOG_ANALYSIS
DELEGATION_KEY: 唯一标识
MODEL: 用户确认的规范模型; EFFORT: 用户确认的 effort
ROUND_1_QUERY: 第一轮问题
INPUT_LOCATION: 文件、日志或产物位置
TIME_RANGE: 明确范围；不适用时写 NONE
EVIDENCE_FIELDS: 最多 5 项
READ_BOUNDARIES: 允许读取的路径
RULES_AND_TOOLING: 路径或名称；标记 REQUIRED
FORK_CONTEXT: false
LIMITS: children=1; rounds=2; send_inputs=1; waits=2; parent_resumes=2; corrections=0
ROUND_INPUT: DELTA_ONLY
RAW_LOG_OUTPUT: FORBIDDEN
CLEANUP_POLICY: DEFER_TO_PARENT_SESSION_END
STOP_RULE: 达到限制、需要扩大范围或需要第三轮时返回 BLOCKED
RETURN_PROFILE: one_field_per_line=YES; report<=10 行
```

## 调用流程

1. 调用一次 `spawn_agent`，设置 `fork_context=false`，显式传入模型和 effort。
2. 第一轮完成通知已包含最终 capsule 时直接使用；否则最多调用一次 `wait_agent`。
3. 第一轮足够时直接完成；不得自动启动第二轮。
4. 确需第二轮时，调用一次 `send_input`，只发送 `ROUND_DELTA`；完成通知没有最终 capsule 时再调用一次 `wait_agent`。
5. 第二轮后必须结束。不得第三次等待、第二次 `send_input`、创建新子智能体或自动切换模式。
6. 不在返回路径调用 `close_agent`，避免额外父模型回合；父任务结束时释放。

```text
ROUND_DELTA
DELEGATION_KEY: 原样回显
ROUND: 2/2
DEPENDENCY: 第一轮中触发本轮的证据
QUERY_DELTA: 唯一新增问题
EVIDENCE_DELTA: 最多 3 项新增字段
```

## Session Return

```text
SESSION_RETURN_CAPSULE
STATUS: COMPLETE | BLOCKED | SOFT_BUDGET_EXHAUSTED
DELEGATION_KEY: 原样回显
ROUND: 1/2 | 2/2
QUERY: 本轮问题
RESULT: 本轮压缩结论
EVIDENCE: 最多 5 项稳定证据指针
TOOLING_GAPS: 缺失工具及影响
UNVERIFIED: 未验证项和风险
NEXT_ACTION: 主任务唯一建议动作
```

主任务每轮只消费 capsule，不重新读取原始日志。第二轮不是纠错通道；第一轮协议不合格时返回 `BLOCKED`，不得用第二轮修复格式。
