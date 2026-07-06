---
name: route-effort
version: 1.2.1
description: 根据任务描述自动选择最合适的 agent effort 级别（low/medium/high/xhigh/max）。在构建多 agent Workflow 时，于派遣子 agent 前调用，返回推荐的 effort 字符串。适用于任何需要通过 Workflow 派遣 agent 的场景——当你不确定该用哪个 effort，或想让系统自动决定时，应优先使用本 skill。
---

# Route Effort

## 目的

根据任务的**风险**和**推理深度**需求，自动选择最合适的 `effort` 级别，避免对简单任务过度消耗 token，也避免对关键任务用不足的推理能力。

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
```

## 决策依据

**核心原则**：`答案出错的概率 × 出错的代价 → effort`

- 省 token 优先 `low`
- 关键决策用 `high` 以上
- `max` 只给真正难的问题

## 使用方式

> **重要约束**：`effort` 参数只在 **Workflow 脚本内的 `agent()` 函数**中生效。
> 直接调用 `Agent` 工具**不支持** `effort` 参数，路由结果必须通过 Workflow 应用。

### ✅ 正确方式：通过 Workflow 使用

路由结果必须在 Workflow 脚本中通过 `agent()` 函数应用：

```javascript
// workflow 脚本中
const effort = await routeEffort(taskDesc);
await agent(taskDesc, { effort });  // ← effort 在这里生效
```

调用方式：
```
Workflow({scriptPath: '/path/to/effort-routed-task.js', args: {task: "任务描述"}})
```

### ❌ 错误方式：直接使用 Agent 工具

```
Agent({ prompt: "...", effort: "xhigh" })  // ← effort 参数不存在，会被忽略
```

### 在 Workflow 脚本中使用

```javascript
// 调用 route-effort skill agent 获取推荐 effort
async function routeEffort(taskDesc) {
  const result = await agent(
    `用 route-effort 规则评估以下任务的 effort 级别，只返回 effort=<level>（不要其他内容）：\n---\n${taskDesc}\n---`,
    { effort: 'medium' }  // 用 medium 而非 low：low 会系统性低估复杂任务
  );
  const match = (result || '').match(/effort=(low|medium|high|xhigh|max)/);
  return match ? match[1] : 'medium';
}

// 使用示例
const effort = await routeEffort('跨模块变更：修改认证中间件，变更影响 3 个服务模块');
await agent('跨模块变更：修改认证中间件，变更影响 3 个服务模块', { effort });
```

## 注意事项

- 路由决策本身用 `medium` effort（`low` 无法正确评估复杂任务，会系统性低估）
- 当任务描述模糊时，倾向于向上一级（保守策略）
- `max` 不是"更好"，是"更贵"——只在真正需要时使用

## 描述关键词指南

明确说明**变更性质**和**影响范围**可以提高路由准确率，尤其对 `xhigh` 和 `max` 级别。

| 目标 effort | 描述中应包含 | 易被低估的写法 |
|------------|------------|----------------|
| `high` | 多文件、架构、重构、接口设计 | "看一下这几个文件" |
| `xhigh` | 跨模块变更、修改X影响Y模块、调用链风险 | "帮我看看这个功能" |
| `max` | 安全审计、并发竞态、财务数据正确性、对抗性验证 | "检查一下安全性" |

**示例对比**：

```
⚠️  较模糊："帮我看看这段逻辑有没有问题"         → 可能 medium
✅ 较准确："审计支付结算逻辑的并发安全性，防止双重扣款" → max
```

**说明**：对于有明确领域语义的任务（如"修改认证中间件"），路由 agent 通常能自行判断其跨模块性。补充关键词在任务语义模糊时最有价值，不必为所有任务强制套用三要素写法。

## 手动 Override（绕过路由）

当自动路由结果不准确时，在 `args` 中直接传入 `effort` 字段即可跳过路由：

```javascript
Workflow({
  scriptPath: '~/.claude/workflows/effort-routed-task.js',
  args: { task: '你的任务描述', effort: 'xhigh' }
})
```

`effort` 字段存在时，`effort-routed-task.js` 直接使用该值，不调用路由 agent，零额外开销。

## 升级方式

本地重新运行安装脚本即可覆盖升级：

```bash
./route-effort/install.sh
```

当前版本：查看 `~/.claude/skills/route-effort/SKILL.md` frontmatter 中的 `version` 字段。
最新版本：查看 [GitHub 仓库](https://github.com/steedjson/my-skills/blob/main/route-effort/SKILL.md)。

## 已知限制

- `effort` 参数的实际行为由 Anthropic API 决定，可能随版本变更
- 路由准确率经过基准测试验证，对有明确领域语义的描述表现良好；对完全无语义的模糊描述（如"帮我看看这个"）建议补充上下文
- 不适用于非自然语言任务（如直接传入代码文件路径）
