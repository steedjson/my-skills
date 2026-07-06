---
name: route-effort
version: 1.4.0
description: 根据任务描述自动路由到合适的 agent effort 级别（low/medium/high/xhigh/max）。可作为可移植路由规范嵌入任何 agent 系统——Claude Code Workflow、Anthropic SDK、LangChain 或自定义框架均适用。当你需要为 agent 调度决定 effort 参数、或在 system prompt 中内嵌任务复杂度路由规则时，应优先参考本 skill。
---

# Route Effort

## 目的

根据任务的**风险**和**推理深度**需求，为 agent 调度选择合适的 `effort` 级别，避免简单任务浪费算力，也避免关键任务推理不足。

本 skill 提供三层使用方式：
1. **规范层**：可复制到任何 agent system prompt 的路由规则片段
2. **调用层**：Anthropic SDK / 任意框架的路由函数实现示例
3. **执行层**：Claude Code Workflow 一键路由 + 执行（`effort-routed-task.js`）

---

## 路由规则

| effort | 适用条件 | 典型任务 |
|--------|----------|----------|
| `low` | 机械性操作，确定性高，无需推理 | 格式化、重命名、简单文本替换、摘要生成、grep 搜索 |
| `medium` | 日常任务，需少量推理（默认） | 单文件 bug 修复、代码解释、简单功能实现 |
| `high` | 多文件或有歧义，需权衡方案 | 多文件功能开发、架构分析、有范围的重构、接口设计 |
| `xhigh` | 跨模块、影响面大，需深度理解上下文 | 跨模块变更、复杂 bug 根因分析、变更影响评估、性能优化 |
| `max` | 极难问题，需穷举推理路径才能保证正确 | 安全审计、并发竞态分析、微妙算法 bug、对抗性验证 |

## 决策树

```
任务是否机械性/无需推理？
  └── 是 → low

是否单文件 + 边界清晰？
  └── 是 → medium

是否涉及多文件 + 有歧义/方案选择？
  └── 是 → high

是否跨模块 + 影响面大 + 需要深度上下文？
  └── 是 → xhigh

是否安全/并发/算法正确性 + 错了代价极高？
  └── 是 → max

以上都不确定？
  └── 倾向上一级（保守策略）
```

## 决策依据

**核心原则**：`答案出错的概率 × 出错的代价 → effort`

- 省算力优先 `low`
- 关键决策用 `high` 以上
- `max` 不是"更好"，是"更贵"——只在真正需要时使用

---

## 执行流程（Skill 直接调用模式）

当通过 `Skill` 工具调用本 skill 时，按以下步骤执行，无需 `.js` 文件：

**Step 1：读取输入**
- 从用户消息或 `args` 中提取任务描述
- 检查是否有显式 `effort` override（如 `effort=xhigh`）

**Step 2：路由评估**
- 若有 override → 直接使用，跳到 Step 3
- 若无 override → 按路由规则表和决策树评估，输出：

```
[路由] effort=<level> — <1句理由>
```

**Step 3：执行**
- 以推荐的 effort 级别完成任务
- 在 Claude Code 环境中，高 effort 级别意味着更深入的分析、更多边界条件检查、更完整的输出
- 任务完成后输出：

```
[完成] effort=<level> 已使用
```

**输入格式示例**：
```
任务：给认证模块增加 OAuth2 支持，影响 3 个服务文件
```
或带 override：
```
任务：简单重命名变量
effort=high
```

---

## 可嵌入路由规范（framework-agnostic）

以下片段可**直接复制**到任何 agent system prompt，无需依赖 Claude Code：

```
## Effort Routing Rules
When dispatching sub-agents or allocating reasoning budget, select effort level
based on: P(wrong) × cost(wrong) → effort

| effort | When to use | Examples |
|--------|-------------|---------|
| low    | Mechanical, deterministic, no reasoning needed | rename, format, grep |
| medium | Routine task, some reasoning (default) | single-file bugfix, explain code |
| high   | Multi-file, ambiguous, tradeoffs required | new feature, refactor, API design |
| xhigh  | Cross-module, large blast radius, deep context | auth changes, cache layer rewrite |
| max    | Correctness-critical, exhaustive reasoning needed | security audit, concurrency bugs |

Conservative strategy: when task description is ambiguous, route up one level.
Override: pass effort=<level> explicitly to skip routing.
```

该片段：
- 语言无关（英文，适配多语言模型）
- 框架无关（适用于 LangChain、AutoGen、自定义 orchestrator）
- 模型无关（不依赖 Claude 特有语义）

---

## 在各类框架中使用

### 直接文本咨询（零代码）

在任何对话中直接问：

```
按照 route-effort 规则，以下任务应使用哪个 effort 级别？
只返回 effort=<level>。

任务：[你的任务描述]
```

### Anthropic Python SDK

```python
import re
import anthropic

ROUTING_SYSTEM = """You are an effort router. Given a task description, output exactly one line:
effort=<level>  where level is one of: low / medium / high / xhigh / max

Rules:
- low:    mechanical, deterministic (rename, format, grep)
- medium: routine dev task, some reasoning (single-file bug fix, explain code)
- high:   multi-file, tradeoffs required (new feature, refactor, API design)
- xhigh:  cross-module, large blast radius (auth changes, cache layer)
- max:    correctness-critical, exhaustive reasoning (security audit, concurrency)

Conservative: when uncertain, route up one level. Output ONLY the effort=<level> line."""

def route_effort(task: str, client: anthropic.Anthropic | None = None) -> str:
    client = client or anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # 路由本身用轻量模型
        max_tokens=20,
        system=ROUTING_SYSTEM,
        messages=[{"role": "user", "content": task}],
    )
    text = response.content[0].text
    match = re.search(r"effort=(low|medium|high|xhigh|max)", text)
    return match.group(1) if match else "medium"


# 使用示例
if __name__ == "__main__":
    tasks = [
        "把 README.md 里的版本号从 1.0 改成 1.1",
        "重构认证模块，影响 API 层、Service 层和 DB 层",
        "审计支付系统的并发安全性，防止双重扣款",
    ]
    for task in tasks:
        print(f"{route_effort(task):8s}  {task}")
```

### Anthropic TypeScript SDK

```typescript
import Anthropic from "@anthropic-ai/sdk";

const ROUTING_SYSTEM = `You are an effort router. Output exactly: effort=<level>
Levels: low(mechanical) / medium(routine) / high(multi-file) / xhigh(cross-module) / max(correctness-critical)
Conservative: when uncertain, route up one level. Output ONLY the effort=<level> line.`;

async function routeEffort(
  task: string,
  client = new Anthropic()
): Promise<string> {
  const response = await client.messages.create({
    model: "claude-haiku-4-5-20251001",
    max_tokens: 20,
    system: ROUTING_SYSTEM,
    messages: [{ role: "user", content: task }],
  });
  const text = (response.content[0] as { text: string }).text;
  const match = text.match(/effort=(low|medium|high|xhigh|max)/);
  return match ? match[1] : "medium";
}
```

### Claude Code Workflow（高级用法，可选）

> 需要额外安装 `effort-routed-task.js`（见下文）。仅在需要通过 Workflow API 实际传递 `effort` 参数给 `agent()` 时使用。

```javascript
// 路由 + 执行一体
Workflow({
  scriptPath: '~/.claude/workflows/effort-routed-task.js',
  args: { task: '跨模块变更：修改认证中间件，评估影响范围' }
})

// 手动 override
Workflow({
  scriptPath: '~/.claude/workflows/effort-routed-task.js',
  args: { task: '任务描述', effort: 'xhigh' }
})
```

> **说明**：`effort` 参数只在 Workflow 脚本的 `agent()` 中生效，直接调用 `Agent` 工具无效。

### 直接文本咨询（无代码场景）

在任何对话中直接问：

```
按照 route-effort 规则，以下任务应使用哪个 effort 级别？
只返回 effort=<level>。

任务：[你的任务描述]
```

---

## 描述关键词指南

明确说明**变更性质**和**影响范围**可提高路由准确率，尤其对 `xhigh` 和 `max` 级别。

| 目标 effort | 描述中应包含 | 易被低估的写法 |
|------------|------------|----------------|
| `high` | 多文件、架构、重构、接口设计 | "看一下这几个文件" |
| `xhigh` | 跨模块变更、修改X影响Y模块、调用链风险 | "帮我看看这个功能" |
| `max` | 安全审计、并发竞态、财务数据正确性、对抗性验证 | "检查一下安全性" |

**示例对比**：

```
⚠️  较模糊："帮我看看这段逻辑有没有问题"           → 可能 medium
✅ 较准确："审计支付结算逻辑的并发安全性，防止双重扣款" → max
```

**说明**：对有明确领域语义的任务（如"修改认证中间件"），路由 agent 通常能自行判断其跨模块性。补充关键词在任务语义模糊时最有价值。

---

## 升级方式

```bash
./route-effort/install.sh
```

当前版本：查看 `~/.claude/skills/route-effort/SKILL.md` frontmatter 中的 `version` 字段。
最新版本：[GitHub 仓库](https://github.com/steedjson/my-skills/blob/main/route-effort/SKILL.md)

## 已知限制

- `effort` 参数的实际行为由 Anthropic API 决定，可能随版本变更（仅影响 Claude Code Workflow 模式）
- 路由准确率经过基准测试验证，对有明确领域语义的描述表现良好；对完全无语义的模糊描述建议补充上下文
- SDK 示例中路由本身使用 `claude-haiku-4-5-20251001` 以控制成本，可替换为其他模型
