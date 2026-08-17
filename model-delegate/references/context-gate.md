# Context Gate

被动模式或主任务历史明显较长时读取本文件。

## 目标

区分当前 session、模型目录和磁盘配置，防止使用未生效或超过模型窗口的自动压缩阈值。自动压缩只作运行时安全线，`COST_FIRST` 可更早选择 `HANDOFF`。

## Gate

```text
CONTEXT_GATE
ACTIVE_MODEL: 当前 session 实际模型
MODEL_CONTEXT_WINDOW: 当前模型声明窗口或 UNKNOWN
EFFECTIVE_CONTEXT_WINDOW: 当前运行时有效窗口或 UNKNOWN
AUTO_COMPACT_LIMIT: 当前 session 已加载值、MODEL_DERIVED 或 UNKNOWN
LIMIT_SOURCE: ACTIVE_SESSION | MODEL_CATALOG | DISK_ONLY | UNKNOWN
LIMIT_VALID: YES | NO | UNKNOWN
CURRENT_CONTEXT: 当前上下文 token 或 UNKNOWN
RESERVE: max(32000, AUTO_COMPACT_LIMIT 的 10%) 或 UNKNOWN
AUTO_COMPACT_POLICY: RUNTIME_SAFETY_ONLY
DECISION: PASSIVE_ALLOWED | COMPACTION_CHECKPOINT | HANDOFF
```

## 证据优先级

`ACTIVE_SESSION > MODEL_CATALOG > DISK_CONFIG`。

- 当前任务模型、窗口和已加载阈值优先于磁盘 `config.toml`。
- 配置修改晚于任务创建、或磁盘模型与当前模型不同，标记 `LIMIT_SOURCE: DISK_ONLY`，不得声称已生效。
- 不读取供应商数据库、价格表或私有日志作为核心前置条件。

## 阈值校验

- `0 < AUTO_COMPACT_LIMIT < EFFECTIVE_CONTEXT_WINDOW` 才是有效绝对阈值。
- 阈值缺失时使用模型目录计算的有效窗口，标记 `AUTO_COMPACT_LIMIT: MODEL_DERIVED`。
- 阈值大于或等于有效窗口时标记 `LIMIT_VALID: NO`，不得依赖自动压缩。
- 当前上下文达到 `AUTO_COMPACT_LIMIT - RESERVE` 时输出 `COMPACTION_CHECKPOINT`；不能主动执行 `/compact`。

## 模式决策

- `LIMIT_VALID: NO`：禁止被动模式，使用 `HANDOFF` 或等待用户修正配置。
- `LIMIT_SOURCE: DISK_ONLY`：当前任务不使用该值；新任务重新验证。
- `CURRENT_CONTEXT: UNKNOWN`：历史明显短时可用 `PASSIVE_RETURN`；`PASSIVE_SESSION` 返回 `CONTEXT_GAP`。
- 接近自动压缩阈值：不启动新被动轮次，输出 checkpoint；主任务已很长时使用 `HANDOFF`。
- 未接近阈值也不代表费用低；重复恢复成本高时，`COST_FIRST` 可提前选择 `HANDOFF`。

本门禁只读取和判断，不修改 `config.toml`、模型目录或运行时设置。
