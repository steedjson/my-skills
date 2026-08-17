# Staged Review

仅 `STAGED_REVIEW` 模式读取本文件。

## 目标

执行和审查都使用全新短上下文。旧主任务不得恢复，执行任务不得创建审查任务。

## 执行阶段

旧主任务：

1. 创建一个执行任务，设置 `REVIEW_POLICY: FRESH_USER_TRIGGERED`。
2. 创建成功后只返回任务链接、目标和未验证项。
3. 立即结束，不调用等待、读取或消息工具跟踪执行。

执行任务：

1. 按 `DELEGATION_CAPSULE` 完成实现和验证。
2. 不扩大范围，不创建任务，不请求旧主任务验收。
3. 写任务返回 `COMMIT_ID`；只读任务返回证据位置。
4. 附加不超过 12 行的 `REVIEW_CAPSULE`。

```text
REVIEW_CAPSULE
DELEGATION_KEY: 原样回显
PROJECT_ROOT: 共享检出目录
BASE_COMMIT: 委派前提交
TASK_KIND: READ_ONLY | WRITE
COMMIT_ID: WRITE 任务提交；READ_ONLY 为 NONE
READ_BOUNDARIES: 读取边界
WRITE_BOUNDARIES: 写边界；READ_ONLY 为 NONE
ACCEPTANCE: 最多 5 项
CHECKS: 已运行的关键检查
RISK: 需要独立审查的原因
UNVERIFIED: 未验证项
```

## 审查触发

用户明确触发审查后，才创建全新审查任务。原请求已明确授权“执行完成后再创建独立审查任务”时，该授权仍不允许执行任务自行创建；用户必须在执行结果出现后再次发出审查指令。

运行面不能创建新任务时，向用户输出 `REVIEW_CAPSULE`，让用户通过 `/task` 开始审查。不要使用 `/fork`。

## 审查任务

审查任务只接收 `REVIEW_CAPSULE`，并按需读取：

- `BASE_COMMIT..COMMIT_ID` 的提交差异。
- capsule 指定的文件和检查结果。
- 高风险路径所需的最小补充证据。

审查任务不得：

- 读取旧主任务或执行任务的完整聊天历史。
- 要求执行任务重述完整日志、diff 或 capsule。
- 重新读取原始日志；只使用执行任务提供的过滤证据和明确指针。
- 修改文件，除非用户另行授权一个新的写任务。
- 自动创建修复任务。

## 结果

审查报告不超过 12 行：

```text
STATUS: APPROVED | CHANGES_REQUIRED | BLOCKED
DELEGATION_KEY: 原样回显
COMMIT_ID: WRITE 任务提交；READ_ONLY 省略
FINDINGS: 按严重度列出
CHECKS: 补充检查
BOUNDARIES: 是否越界
RISKS: 剩余风险
NEXT_ACTION: 用户需要决定的唯一动作
```

需要修正时，用户决定由原执行任务修正还是创建新写任务。不得自动续派。
