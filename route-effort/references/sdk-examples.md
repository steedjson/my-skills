# SDK 实现示例

## Python（Anthropic SDK）

```python
import re
import anthropic

ROUTING_SYSTEM = """You are an effort router. Output exactly one line: effort=<level>
Levels: low / medium / high / xhigh / max

- low:    mechanical, deterministic (rename, format, grep)
- medium: routine dev task (single-file bugfix, explain code)
- high:   multi-file, tradeoffs (new feature, refactor, API design)
- xhigh:  cross-module, large blast radius (auth changes, cache layer)
- max:    correctness-critical (security audit, concurrency bugs)

Conservative: when uncertain, route up one level.
Output ONLY the effort=<level> line, nothing else."""

def route_effort(task: str, client: anthropic.Anthropic | None = None) -> str:
    client = client or anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # 路由用轻量模型，控制成本
        max_tokens=20,
        system=ROUTING_SYSTEM,
        messages=[{"role": "user", "content": task}],
    )
    text = response.content[0].text
    match = re.search(r"effort=(low|medium|high|xhigh|max)", text)
    return match.group(1) if match else "medium"
```

## TypeScript（Anthropic SDK）

```typescript
import Anthropic from "@anthropic-ai/sdk";

const ROUTING_SYSTEM = `You are an effort router. Output exactly: effort=<level>
Levels: low / medium / high / xhigh / max
Conservative: when uncertain, route up. Output ONLY the effort=<level> line.`;

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

## Claude Code Workflow

```javascript
// 自动路由 + 执行
Workflow({
  scriptPath: "~/.claude/workflows/effort-routed-task.js",
  args: { task: "跨模块变更：修改认证中间件，评估影响范围" },
});

// 手动 override（跳过路由）
Workflow({
  scriptPath: "~/.claude/workflows/effort-routed-task.js",
  args: { task: "任务描述", effort: "xhigh" },
});
```

> 需先执行 `./install.sh --with-workflow` 安装 `effort-routed-task.js`。
