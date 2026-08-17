# Log Analysis

仅 `PROFILE: LOG_ANALYSIS` 时读取本文件。

## 目标

在工具侧过滤和聚合大型文本，只把决定性证据交给模型。不得依赖特定日志代理、供应商或计费数据库。

## 必填输入

任务包必须包含：

```text
TASK_KIND: READ_ONLY
TIME_RANGE: 明确起止时间或单次事件边界
INPUT_LOCATION: 日志、测试输出或产物位置
QUERY: 唯一分析问题
EVIDENCE_FIELDS: 需要提取的字段
MAX_SCAN_PASSES: 1
RAW_LOG_OUTPUT: FORBIDDEN
```

缺少时间范围、输入位置或分析问题时返回 `BLOCKED`，不进行广域扫描。

## 工具策略

- 优先使用当前环境已有的索引、查询、过滤、聚合或结构化解析工具。
- 没有专用工具时，使用有界命令按时间、错误码、请求 ID、测试名或其他明确键过滤。
- 无法在不读取完整原始数据的情况下安全分析时返回 `TOOLING_GAP`。
- 最多一次原始数据扫描；后续分析只使用第一次扫描生成的索引或聚合结果。
- 不修改日志、配置、数据库、代码或其他文件。
- 不把完整日志、完整测试输出或大段连续原文传给父任务、审查任务或最终报告。

## 输出

报告不超过 10 行：

```text
STATUS: COMPLETE | BLOCKED | SOFT_BUDGET_EXHAUSTED
TIME_RANGE: 实际分析范围
INPUT: 输入位置
QUERY: 分析问题
MATCHES: 命中数量或 NONE
EVIDENCE: 最多 5 项决定性证据
ROOT_CAUSE: 已证实根因或 UNVERIFIED
TOOLING_GAPS: 缺失工具及影响
RISKS: 未验证项
NEXT_ACTION: 唯一建议动作
```

每项证据包含时间、稳定标识和简短结论。必要原文只保留最短片段，禁止原始日志转储。
