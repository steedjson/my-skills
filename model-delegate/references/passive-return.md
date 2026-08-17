# Passive Return

仅 `PASSIVE_RETURN` 模式读取本文件。

## 目标

用一个低上下文只读子智能体处理日志、测试输出或证据收集，完成后被动返回短摘要；主任务保留最终判断。

## 前置条件

- 用户明确确认子智能体模型、reasoning effort 和软预算风险。
- 主任务尚适合恢复一次；上下文已很长时改用 `HANDOFF`。
- 子任务独立、只读，不涉及修改、审批、迁移或不可逆动作。
- 当前运行时提供 `spawn_agent` 和 `wait_agent`。

## Collector Capsule

```text
COLLECTOR_CAPSULE
MODE: PASSIVE_RETURN; TASK_KIND: READ_ONLY; PROFILE: STANDARD | LOG_ANALYSIS
DELEGATION_KEY: 唯一标识
MODEL: 用户确认的规范模型; EFFORT: 用户确认的 effort
QUERY: 唯一分析问题
INPUT_LOCATION: 文件、日志或产物位置
TIME_RANGE: 明确范围；不适用时写 NONE
EVIDENCE_FIELDS: 最多 5 项
READ_BOUNDARIES: 允许读取的路径
RULES_AND_TOOLING: 路径或名称；标记 REQUIRED
FORK_CONTEXT: false
LIMITS: children=1; discovery=1; tools=8; scans=1; waits=1; parent_resumes=1; corrections=0
RAW_LOG_OUTPUT: FORBIDDEN
CLEANUP_POLICY: DEFER_TO_PARENT_SESSION_END
STOP_RULE: 达到限制或需要提问时返回 BLOCKED
RETURN_PROFILE: one_field_per_line=YES; report<=10 行
```

## 调用流程

1. 调用一次 `spawn_agent`，设置 `fork_context=false`，显式传入已确认的 `model` 和 `reasoning_effort`。
2. 子智能体不得继承父聊天、写文件、创建后代、请求中间确认或扩大范围。
3. 主任务仅在结果是下一步必要输入时调用一次长等待 `wait_agent`。
4. 普通进度不处理；不得调用 `send_input`，不得第二次调用 `wait_agent`。
5. 为避免额外父模型回合，不在返回路径调用 `close_agent`；本模式每个父任务最多保留一个已完成子智能体，并在父任务结束时释放。

等待超时后停止协调并报告 checkpoint。运行时之后产生完成通知时，用户可重新唤醒主任务；不得主动轮询。

## Return Capsule

```text
RETURN_CAPSULE
STATUS: COMPLETE | BLOCKED | SOFT_BUDGET_EXHAUSTED
DELEGATION_KEY: 原样回显
QUERY: 原始问题
RESULT: 压缩结论
EVIDENCE: 最多 5 项稳定证据指针
TOOLING_GAPS: 缺失工具及影响
UNVERIFIED: 未验证项
RISKS: 错误判断风险
NEXT_ACTION: 主任务唯一建议动作
```

主任务只消费 `RETURN_CAPSULE`。不得重新读取原始日志、重复同一调查或要求子智能体重述。高风险结论只作为输入，后续使用 `STAGED_REVIEW`。

协议不合格、包含原始日志或超过 10 行时返回 `BLOCKED`，不自动重试。
