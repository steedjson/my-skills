# Compact Coordinator

仅 `COMPACT_COORDINATOR` 模式读取本文件。

## 目标

高风险任务保留独立验收，同时避免旧主任务在执行期间反复处理完整历史。旧主任务只允许两个活跃阶段：

1. 委派前生成 capsule 并创建执行任务。
2. 用户执行 `/compact` 后进行一次最终验收。

本模式只控制旧主任务上下文成本，不是执行任务的外部费用熔断。运行面没有硬预算或中断能力时，创建任务前仍需用户明确接受 capsule 中的软限制。

## 创建后暂停

创建执行任务后，不调用等待或读取工具。立即输出：

```text
COMPACTION_CHECKPOINT
DELEGATION_KEY: 唯一标识
THREAD_ID: 正式 threadId；尚未生成时记录 CLIENT_THREAD_ID
HOST_ID: 创建响应中的 host
PROJECT_ROOT: 共享检出目录
BASE_COMMIT: 委派前提交
TASK_KIND: READ_ONLY | WRITE
READ_BOUNDARIES: 读取边界
WRITE_BOUNDARIES: 写边界；只读任务为 NONE
ACCEPTANCE: 验收条件摘要
CURSOR: 尚无时写 NONE
NEXT_ACTION: 用户执行 /compact，之后明确要求继续验收
```

checkpoint 不超过 15 行。不要重复 capsule、日志或方案讨论。

当前运行面未提供可编程 `/compact` 工具时：

- 不模拟压缩。
- 不声称已压缩。
- 不在同一回合自动等待。
- 让用户在 Codex 中执行 `/compact`，再发送“继续验收”。

## 压缩后恢复

用户明确要求继续验收后：

1. 只从 checkpoint 恢复 `DELEGATION_KEY`、任务 ID、项目、提交基线、文件边界和验收条件。
2. 正式 `threadId` 未验证时，用一次 `list_threads` 定向确认 `clientThreadId` 映射；不得按标题、时间、模型或最近活动猜测。
3. 用一次较长、有界的 `wait_threads` 等待；携带已保存 `afterCursor`。
4. 最终消息已在等待结果中时直接使用，不再 `read_thread`。
5. 只有结果缺失、身份不一致或工具错误时，才允许一次 `read_thread` 或 `list_threads` 诊断。
6. 超时无新状态时立即暂停，不自动再次等待或催促。

## 父任务成本上限

父任务只允许一次验收：

- `MAX_PARENT_REVIEW_PASSES: 1`
- `MAX_PARENT_TOOL_CALLS: 4`
- `MAX_CORRECTION_MESSAGES: 1`

直接使用 `wait_threads` 返回的最终报告和提交指针。不要请求执行任务重复发送日志、diff、capsule 或已经报告的检查。

将 Git 状态、提交存在性、文件边界和必要检查合并为一次批量读取。大日志先过滤关键错误；除非唯一失败需要诊断，不把完整日志送入父模型。执行证据完整时不重跑全部检查，只补高风险关键证据。

## 验收

用一次批量只读检查确认：

- 工作区没有执行任务遗留的未提交修改。
- 读取未越过 `READ_BOUNDARIES`。
- 写入未越过 `WRITE_BOUNDARIES`。
- 必需检查已运行。
- `TOOLING_GAP` 不影响安全和验收。

`TASK_KIND: READ_ONLY` 时确认没有文件修改、`git add` 或新提交。`TASK_KIND: WRITE` 时确认 `COMMIT_ID` 存在并位于当前共享分支。

高风险任务检查完整提交差异和相关集成行为，但不要重跑执行任务全部命令；只补关键证据。

主任务允许一次纠偏：

- 只向原正式 `threadId` 发送一次定向修正。
- 不传新模型或 effort，保持原任务设置。
- 不扩大范围。
- 第二次仍不通过时停止，由用户决定。

## 独立审查替代

压缩状态无法确认、旧主任务仍明显过长，或用户不愿继续使用旧任务时，不恢复协调。输出不超过 15 行的 `REVIEW_CAPSULE`：

```text
REVIEW_CAPSULE
PROJECT_ROOT: 共享检出目录
BASE_COMMIT: 委派前提交
TASK_KIND: READ_ONLY | WRITE
COMMIT_ID: WRITE 任务提交；READ_ONLY 为 NONE
READ_BOUNDARIES: 读取边界
WRITE_BOUNDARIES: 写边界；只读任务为 NONE
ACCEPTANCE: 验收条件
CHECKS: 必需检查
RISK: 高风险原因
```

让用户通过 `/task` 创建全新审查任务，或在用户已明确授权创建新任务时使用 `create_thread`。不要使用 `/fork`，不要把旧聊天历史复制给审查任务。

## 完成报告

成功时只报告：

- 验收结论。
- 写任务的 `COMMIT_ID`；只读任务省略。
- 关键检查。
- 剩余风险和未验证项。

阻塞时报告 checkpoint 标识、实际证据和需要用户决定的唯一问题。不要输出完整任务历史。
