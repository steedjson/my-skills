---
name: vlong:route-effort
version: 2.2.0
description: >
  评估任务复杂度并路由到合适的 effort 级别（low/medium/high/xhigh/max）和模型（haiku/sonnet/fable）。
  帮用户判断一个任务"该花多少力气、用什么模型"——从简单机械操作到高风险跨模块变更都能处理。

  以下场景应主动调用本 skill，即使用户没有说"effort"或"route-effort"这两个词：
  - 用户问任务难度、复杂度、工作量："这个任务有多复杂"、"要花多少精力"、"难不难"
  - 用户在判断该认真处理还是快速搞定："这个要仔细看吗"、"简单任务还是要深度分析"
  - 用户要给子 agent 或 Workflow 分配推理预算："这个任务给 xhigh 还是 high"
  - 用户提到"route effort"、"effort 路由"、"任务难度评估"、"模型路由"、"用哪个模型"
  - 构建 multi-agent 系统需要按复杂度分配算力和模型
  - 询问如何把 effort 路由规则嵌入 SDK 或 system prompt

  只要用户在评估"这个任务值得投入多少推理资源"或"该用哪个模型"，就应调用。
---

# Route Effort

## 执行指令

调用本 skill 时，按顺序执行以下步骤：

**1. 读取输入**
从用户消息或 `args` 中提取：
- `task`：任务描述（必须）
- `effort`：手动 override（可选，存在时跳过 effort 路由）
- `model`：手动 override（可选，存在时跳过模型映射）

**2. 路由判断**（无 override 时执行）
对照下方路由规则表，沿决策树逐步判断，确定 effort 级别。
不确定时保守策略：**向上一级**。

**3. 输出路由结果**
```
[路由] effort=<level> model=<model> — <一句理由，说明命中哪条规则>
```

**4. 执行任务**
以该 effort 级别完成任务：
- `low`：直接完成，不过度分析
- `medium`：正常处理，适量推理
- `high`：多方案权衡，覆盖边界条件
- `xhigh`：深入上下文，评估全链路影响
- `max`：穷举推理路径，确保正确性，输出要完整详尽

**5. 完成确认**
```
[完成] effort=<level> model=<model> 已使用
```

**完整示例（high 级别）：**
```
[路由] effort=high model=sonnet — 涉及3个文件的功能开发，需要权衡接口设计方案

[执行内容]
... （任务执行结果）

[完成] effort=high model=sonnet 已使用
```

**Override 示例（跳过路由）：**
```
检测到 effort=max model=fable override，跳过路由判断。

[执行内容]
... （以 max/fable 深度执行）

[完成] effort=max model=fable 已使用
```

---

## 路由规则

核心原则：`P(出错) × 出错代价 → effort`

| effort | 适用条件 | 典型任务 |
|--------|----------|----------|
| `low` | 机械性操作，确定性高，无需推理 | 格式化、重命名、文本替换、grep |
| `medium` | 日常任务，需少量推理（**默认**） | 单文件 bug 修复、代码解释、简单实现 |
| `high` | 多文件或有歧义，需权衡方案 | 多文件功能开发、架构分析、接口设计 |
| `xhigh` | 跨模块、影响面大，需深度上下文 | 跨模块变更、根因分析、变更影响评估 |
| `max` | 极难，错了代价极高 | 安全审计、并发竞态、微妙算法 bug |

## 决策树

```
机械性 / 无需推理？             → low
单文件 + 边界清晰？             → medium
多文件 + 有歧义 / 方案选择？    → high
跨模块 + 影响面大？             → xhigh
安全 / 并发 / 正确性至关重要？  → max
以上不确定？                    → 上一级（保守）
```

## 模型路由规则

effort 确定后，按以下映射自动选择模型：

| effort | 默认模型 | 理由 |
|--------|----------|------|
| `low` | `claude-haiku-4-5-20251001` | 机械任务，速度/成本优先 |
| `medium` | `claude-sonnet-5` | 日常任务，能力与成本平衡 |
| `high` | `claude-sonnet-5` | 多文件开发，sonnet 足够胜任 |
| `xhigh` | `claude-fable-5` | 跨模块深度分析，需要最强推理 |
| `max` | `claude-fable-5` | 安全审计/并发/正确性极限，最强模型 |

模型别名对应：完整 ID 直接传入 `agent()` 的 `model` 参数。

## 手动 Override

用户明确指定 effort 或 model 时，跳过对应路由：
```
任务：[描述]
effort=xhigh
model=fable
```
在 Claude Code Workflow 中：`args: { task: "...", effort: "xhigh", model: "fable" }`

两者可独立 override：只指定 `model` 时 effort 仍自动路由，反之亦然。

---

## 嵌入任意 Agent 系统

将以下片段复制到任何 agent 的 system prompt，无需依赖 Claude Code：

```
## Effort Routing
Select effort level based on: P(wrong) × cost(wrong)

| effort | Use when | Examples |
|--------|----------|---------|
| low    | Mechanical, deterministic | rename, format, grep |
| medium | Routine, some reasoning (default) | single-file bugfix, explain code |
| high   | Multi-file, tradeoffs | new feature, refactor, API design |
| xhigh  | Cross-module, large blast radius | auth changes, cache layer |
| max    | Correctness-critical | security audit, concurrency bugs |

Conservative: when uncertain, route up one level.
```

SDK 实现示例（Python / TypeScript）→ 见 `references/sdk-examples.md`

---

## 提示词质量指南

任务描述越具体，路由越准确。对 `xhigh` / `max` 尤其重要：

| 目标 | 写法 |
|------|------|
| `xhigh` | "跨模块变更：修改 X，影响 A、B、C 模块" |
| `max` | "审计支付并发逻辑，防止双重扣款" |
| 避免 | "帮我看看这个"（无语义，触发保守策略） |

---

## 注意事项

- `effort` 和 `model` 参数仅在 Workflow 脚本的 `agent()` 内生效；直接调用 `Agent` 工具无效
- 路由本身应使用 `medium` effort（`low` 会系统性低估复杂任务）
- Workflow 执行模式需额外安装 `vlong-route-effort-task.js`（`./install.sh --with-workflow`）
- 模型别名由 Claude Code Workflow 解析，与 Anthropic API 的完整模型 ID 不同
