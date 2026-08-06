---
name: delegate-execution-agent
description: 为 Codex 任务建立轻量主 Agent 与执行 Agent 分工。用户要求模型分工、自动委派、执行型 Agent、Luna、DeepSeek，或希望从当前可用模型中选择执行模型时使用。
---

# 执行 Agent 分工

保持当前主模型不变。主 Agent 负责理解目标、拆解任务、关键判断、风险控制、结果整合和最终验收。

同模型委派优先使用宿主当前实际暴露的原生工具。跨模型委派若原生子 Agent 路径无法兼容当前 provider，则启动独立、临时的 `codex exec` 进程。不要创建或依赖未验证的 custom agent TOML、全局默认子代理模型或未确认的并发配置。

## 选择模型与执行 Agent

每次需要委派前读取当前工具实际提供的 Agent 类型、模型和 reasoning effort。不得使用记忆中的旧列表，也不得根据显示名称猜测模型 ID 或 effort。

默认候选是当前实际可用的 GPT-5.6 Luna Max。模型目录、Agent 目录、原生委派工具和 provider 暴露的模型 ID 可能不同，必须以当前运行时实际接受的完整模型 ID 和启动结果为准。

首次委派前执行一次任务级模型确认：

1. 若用户已明确指定模型和 effort，直接使用该组合。
2. 否则向用户展示 Luna Max 作为默认选项，并列出最多 5 个当前运行时实际接受的替代组合。每项包含完整模型 ID、effort 和已知限制。
3. 用户明确选择替代模型后，仅对当前顶层任务覆盖默认模型；不修改全局配置。
4. 用户未确认时不启动子 Agent；继续由主 Agent 处理或等待确认。
5. 原生路径兼容时，将选定的完整模型 ID 和 `reasoning_effort` 显式传入 `spawn_agent`。`task_name` 只是实例标识，`agent_type` 只是宿主支持的执行角色，不代表 custom agent 配置名。
6. 原生跨模型路径出现加密 child payload、模型继承或 provider 命名空间兼容错误时，不再使用默认 Agent 重试；改用下方独立 `codex exec` 路径。
7. 完整 provider 模型 ID 必须来自当前运行时。不得把 provider-facing ID 擅自缩写为上游模型名，也不得永久假定示例 ID 始终有效。
8. 模型或 effort 被拒绝、继承主模型或无法由运行时确认时立即停止。禁止静默替换、自动降级或声称未运行的模型已运行。

## 跨模型兼容路径

跨模型 Luna 委派在原生 `spawn_agent` 不兼容时，使用同步、独立、临时的 Codex 进程：

```bash
codex exec --json --ephemeral --sandbox read-only \
  --disable plugins \
  --disable apps \
  --disable memories \
  --disable multi_agent \
  --disable multi_agent_v2 \
  -c 'approval_policy="never"' \
  -c 'model_reasoning_effort="max"' \
  -m '<当前运行时实际接受的完整 Luna 模型 ID>' \
  '<完整任务包>'
```

- 不使用 `--ignore-rules`；子进程必须继续遵守项目 `AGENTS.md` 和本地规则。
- 启动前用 `codex features list` 确认命令中的 feature 名称。禁用子进程不需要的 plugins、apps、memories 和 multi-agent，减少上下文并禁止二次委派；当前版本不支持时删除对应禁用项，不猜测替代字段。
- 只读任务使用 `--sandbox read-only`。
- 写文件任务使用当前运行时支持的 workspace sandbox，并限制为独立 worktree 或不重叠文件范围；无法隔离时串行执行。
- 高风险、不可逆、需要额外权限或无法限制写入范围的任务留给主 Agent，并按现有规则询问用户。
- 同步等待进程退出，不建立轮询、守护进程、回调服务或主动唤醒协议。
- 非零退出、JSON 输出无法解析、模型被拒绝、effort 被拒绝或修改越界时，结果判定失败并停止；不得自动换模型。
- 启动参数只能证明请求了指定模型。只有运行时事件或 provider 证据明确返回实际模型与 effort 时，才报告“已确认”；否则报告“请求值已明确，实际值无法独立确认”。

## 委派边界

只委派范围明确、可独立完成、可独立验证的任务。任务包必须包含：

- 目标和完成条件；
- 允许修改的文件或责任范围；
- 必须遵守的约束；
- 验证方式；
- 返回主 Agent 的结果格式。

主 Agent 保留架构决策、跨任务协调、权限与安全判断、冲突处理和最终验收。高风险或不可逆操作仍需用户确认。

## 轻量执行与反馈

1. 判断任务是否适合独立委派；普通、紧密耦合或需要架构判断的工作留在主 Agent。
2. 只读任务可并行。写文件任务使用独立 worktree；无法隔离时串行执行。
3. 启动原生子 Agent 后，主 Agent 不做高频轮询。优先使用宿主提供的一次阻塞式等待（例如 `wait_agent`），等待消息或最终状态。独立 `codex exec` 路径直接同步等待进程退出。
4. 子 Agent 仅在以下事件主动反馈：阻塞、需要决策、范围或验收标准冲突、验证失败、可以交付。禁止心跳和重复进度消息。
5. 主 Agent 收到反馈后检查子 Agent 状态、文件差异和验证证据；必要时发送一次修正任务。
6. 子 Agent 的主动消息不保证在主 Agent 未等待时立即触发新的主模型回合；消息会进入待处理队列。一次阻塞式等待比持续轮询更省上下文。
7. 等待本身通常不会启动新的主模型推理回合；工具返回和反馈消息会占用上下文，主 Agent 处理它们时才产生后续推理消耗。
8. 所有子 Agent 完成后，主 Agent 统一整合、复核并输出最终结论。

报告实际使用的 Agent、模型、effort、状态和验证结果。无法确认时标记为未知，不做推测。
