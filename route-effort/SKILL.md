---
name: route-effort
version: 1.1.0
description: 根据任务描述自动选择最合适的 agent effort 级别（low/medium/high/xhigh/max）。在派遣子 agent 前调用，返回推荐的 effort 字符串。
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
    `用 route-effort 规则评估以下任务的 effort 级别，只返回 effort=<level>（不要其他内容）：\n"${taskDesc}"`,
    { effort: 'low' }  // 路由本身用 low，节省 token
  );
  const match = result.match(/effort=(low|medium|high|xhigh|max)/);
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

路由 agent 对描述措辞敏感。**纯"分析"类描述容易被低估**——应明确说明变更性质和影响范围。

| 目标 effort | 描述中应包含 | 容易被低估的写法 |
|------------|------------|----------------|
| `high` | 多文件、架构、重构、接口设计 | "看一下这几个文件" |
| `xhigh` | **跨模块变更**、**修改X影响Y模块**、**变更影响范围**、**调用链风险** | "分析影响范围" |
| `max` | 安全审计、并发竞态、财务数据正确性、对抗性验证 | "检查一下安全性" |

**示例对比**：

```
❌ 低估："分析缓存策略修改的影响"           → medium
✅ 准确："跨模块变更：修改缓存策略，变更影响 A、B 等多个模块，评估调用链风险" → xhigh
```

**规律**：描述中同时出现"跨模块 + 变更/修改 + 影响N个模块"三个要素，才能可靠触发 `xhigh`。

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
- 路由准确率未经基准测试，对模糊任务描述有系统性误判风险
- 不适用于非自然语言任务（如直接传入代码文件路径）
